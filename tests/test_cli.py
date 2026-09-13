import json
from collections.abc import Callable
from email.message import Message
from pathlib import Path
from urllib.request import Request

import pytest

from omnipack import cli
from omnipack.cli import main
from omnipack.composition_policy import parse_composition_policy
from omnipack.http import HttpClient, HttpResponse
from omnipack.merge import CompositionReport, CompositionResult
from omnipack.model import App, Provenance, SourceType, Variant
from omnipack.overlay import ComposedApp
from omnipack.sources import IngestionReport, IngestionResult, SourceError

EMPTY_POLICY = parse_composition_policy(
    {"schemaVersion": 1, "candidates": [], "pins": []}
)


def test_no_command_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main([])
    assert "required" in capsys.readouterr().err


@pytest.mark.parametrize(("status", "expected"), [("success", 0), ("failed", 1)])
def test_generate_source_codm_exit_status(
    monkeypatch: pytest.MonkeyPatch, status: str, expected: int
) -> None:
    calls: list[Path] = []

    def generate(root: Path) -> dict[str, object]:
        calls.append(root)
        return {"status": status}

    monkeypatch.setattr(cli, "generate_codm", generate)
    assert main(["generate-source", "codm"]) == expected
    assert calls == [Path.cwd()]


def test_generate_source_codm_rejects_force(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["generate-source", "codm", "--force"])
    assert excinfo.value.code == 2
    assert "--force" in capsys.readouterr().err


def test_verify_missing_inputs_fails_and_report_displays_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["verify"]) == 1
    assert main(["report"]) == 0


def test_build_writes_both_variants_and_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "README.md").write_bytes(
        b"<!-- omnipack:catalog:start -->\n<!-- omnipack:catalog:end -->\n"
    )
    (tmp_path / "config").mkdir()
    (tmp_path / "config/settings.json").write_text("{}", encoding="utf-8")
    for name, value in (
        ("composition.json", {"schemaVersion": 1, "candidates": [], "pins": []}),
        ("deny.json", []),
        ("overlay.json", []),
    ):
        (tmp_path / "config" / name).write_text(json.dumps(value), encoding="utf-8")
    app = ComposedApp(
        Variant.SINGLE,
        Provenance("extras", "https://example.test/app"),
        {
            "id": "app.test",
            "url": "https://example.test/app",
            "name": "App",
            "overrideSource": "HTML",
            "categories": [],
        },
    )
    composed = CompositionResult(
        {
            Variant.SINGLE: [app],
            Variant.DUAL: [ComposedApp(Variant.DUAL, app.provenance, dict(app.data))],
        },
        CompositionReport(),
    )
    monkeypatch.setattr(
        cli,
        "_ingest_for_build",
        lambda root, report=None: IngestionResult(
            [],
            report or IngestionReport(),
            EMPTY_POLICY,
            (root / "config/composition.json").read_bytes(),
        ),
    )
    monkeypatch.setattr(cli, "compose", lambda *args, **kwargs: composed)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["build"]) == 0
    assert (
        json.loads((tmp_path / "dist/single-screen.json").read_text())["apps"][0]["id"]
        == "app.test"
    )
    assert (
        json.loads((tmp_path / "dist/dual-screen.json").read_text())["apps"][0]["id"]
        == "app.test"
    )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["status"] == "success"
    assert report["changes"]["single"]["added"] == ["app.test"]
    assert not (tmp_path / "dist/report.json").exists()


def test_build_failure_returns_nonzero_and_writes_diagnostic_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    before = b'{"apps":[{"id":"existing.app"}]}\n'
    for name in ("single-screen.json", "dual-screen.json"):
        (dist / name).write_bytes(before)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cli,
        "_ingest_for_build",
        lambda root, report=None: (_ for _ in ()).throw(
            SourceError("rjny", "HTTP 503")
        ),
    )
    assert cli.main(["build"]) == 1
    assert "rjny" in capsys.readouterr().err
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["status"] == "failed"
    assert report["stage"] == "ingestion"
    assert report["offlineVerification"] == {"status": "not-run", "findings": []}
    assert "HTTP 503" in report["error"]
    assert report["changes"] is None
    for name in ("single-screen.json", "dual-screen.json"):
        assert (dist / name).read_bytes() == before


def test_build_failure_does_not_mutate_committed_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "README.md").write_bytes(
        b"<!-- omnipack:catalog:start -->\n<!-- omnipack:catalog:end -->\n"
    )
    config = tmp_path / "config"
    config.mkdir()
    for name, value in (
        ("composition.json", {"schemaVersion": 1, "candidates": [], "pins": []}),
        ("deny.json", []),
        ("overlay.json", []),
        ("settings.json", {}),
    ):
        (config / name).write_text(json.dumps(value), encoding="utf-8")
    dist = tmp_path / "dist"
    dist.mkdir()
    before = {"settings": {}, "apps": [{"id": "old.id"}]}
    for name in ("single-screen.json", "dual-screen.json"):
        (dist / name).write_text(json.dumps(before), encoding="utf-8")

    composed = CompositionResult(
        {variant: [] for variant in Variant}, CompositionReport()
    )

    (config / "catalogs").mkdir()
    catalog = b'{"apps":[{"id":"app.old","url":"https://github.com/old/project"}]}\n'
    (config / "catalogs/codm.json").write_bytes(catalog)

    def resolved(_root: Path, report: IngestionReport | None = None) -> IngestionResult:
        return IngestionResult(
            [],
            report or IngestionReport(),
            EMPTY_POLICY,
            (_root / "config/composition.json").read_bytes(),
        )

    monkeypatch.setattr(cli, "_ingest_for_build", resolved)
    monkeypatch.setattr(cli, "compose", lambda *args, **kwargs: composed)
    monkeypatch.setattr(
        "omnipack.build.render",
        lambda *_args: (_ for _ in ()).throw(ValueError("render failed")),
    )
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 1
    assert (config / "catalogs/codm.json").read_bytes() == catalog
    for name in ("single-screen.json", "dual-screen.json"):
        assert json.loads((dist / name).read_text()) == before


def write_fixture_pipeline(root: Path) -> dict[str, str]:
    """Write a fixture configuration and return the upstream responses it needs."""
    (root / "README.md").write_bytes(
        b"<!-- omnipack:catalog:start -->\n<!-- omnipack:catalog:end -->\n"
    )
    config = root / "config"
    config.mkdir()
    source_config = {
        "rjny": {"repo": "fixture/rjny", "branch": "main", "path": "apps.json"},
        "bboi": {
            "codeberg_repo": "fixture/bboi",
            "single_asset_pattern": "single-*.json",
            "dual_asset_pattern": "dual-*.json",
        },
        "codm": {"catalog": "config/catalogs/codm.json"},
    }
    files: dict[str, object] = {
        "sources.json": source_config,
        "http.json": {"credentials": {}},
        "extras.json": [],
        "composition.json": {"schemaVersion": 1, "candidates": [], "pins": []},
        "deny.json": [],
        "overlay.json": [],
        "settings.json": {},
    }
    for name, value in files.items():
        (config / name).write_text(json.dumps(value), encoding="utf-8")
    (config / "catalogs").mkdir()
    (config / "catalogs/codm.json").write_text(
        json.dumps(
            {
                "apps": [
                    {
                        "id": "app.generated",
                        "url": "https://github.com/fixture/generated",
                        "name": "Generated",
                        "overrideSource": "GitHub",
                    },
                    {
                        "id": "app.retained",
                        "url": "https://github.com/fixture/retained",
                        "name": "Retained",
                        "overrideSource": "GitHub",
                    },
                ]
            }
        )
    )
    record = {
        "id": "app.fixture",
        "url": "https://example.test/app",
        "name": "Fixture",
        "overrideSource": "HTML",
    }
    return {
        "https://raw.githubusercontent.com/fixture/rjny/main/apps.json": json.dumps(
            {"apps": [record]}
        ),
        "https://codeberg.org/api/v1/repos/fixture/bboi/releases/latest": json.dumps(
            {
                "assets": [
                    {
                        "name": "single-1.json",
                        "browser_download_url": "https://fixture.test/single",
                    },
                    {
                        "name": "dual-1.json",
                        "browser_download_url": "https://fixture.test/dual",
                    },
                ]
            }
        ),
        "https://fixture.test/single": '{"apps":[]}',
        "https://fixture.test/dual": '{"apps":[]}',
    }


def fixture_transport(
    responses: dict[str, str],
) -> Callable[[HttpClient, Request, float, int | None], HttpResponse]:
    def transport(
        _client: HttpClient, request: Request, _timeout: float, _max_bytes: int | None
    ) -> HttpResponse:
        body = responses[request.full_url].encode()
        return HttpResponse(request.full_url, 200, Message(), body)

    return transport


def test_build_verify_and_report_sequence_records_no_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    responses = write_fixture_pipeline(tmp_path)
    monkeypatch.setattr(HttpClient, "_urllib_transport", fixture_transport(responses))
    monkeypatch.chdir(tmp_path)

    assert main(["build"]) == 0
    build_report = json.loads((tmp_path / ".build/report.json").read_text())
    assert build_report["offlineVerification"] == {"status": "success", "findings": []}
    assert main(["verify"]) == 0
    verification = json.loads((tmp_path / ".build/verify.json").read_text())
    assert (verification["status"], verification["errors"]) == ("success", [])
    capsys.readouterr()
    assert main(["report"]) == 0
    output = capsys.readouterr().out
    for variant in Variant:
        assert f"Selection: {variant.value} package:app.fixture -> " in output
    assert "Evidence: current" in output


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("invalid_gate", [False, True])
def test_build_runs_the_real_pipeline_with_transport_only_fixtures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: bool, invalid_gate: bool
) -> None:
    responses = write_fixture_pipeline(tmp_path)
    if existing:
        (tmp_path / "dist").mkdir()
        (tmp_path / "dist/dual-screen.json").write_text(
            json.dumps({"apps": [{"id": "app.generated"}]})
        )
    requested: list[str] = []

    def transport(
        _client: HttpClient, request: Request, _timeout: float, _max_bytes: int | None
    ) -> HttpResponse:
        requested.append(request.full_url)
        body = responses[request.full_url].encode()
        return HttpResponse(request.full_url, 200, Message(), body)

    if invalid_gate:
        from omnipack import build as build_module

        real_render = build_module.render

        def invalid_render(apps: list[ComposedApp], settings: dict) -> str:
            rendered = json.loads(real_render(apps, settings))
            rendered["apps"][0]["preferredApkIndex"] = "first"
            return json.dumps(rendered)

        monkeypatch.setattr(build_module, "render", invalid_render)
    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache/sentinel").write_bytes(b"unrelated cache")
    before_outputs = {
        path.name: path.read_bytes() for path in (tmp_path / "dist").glob("*.json")
    }
    monkeypatch.setattr(HttpClient, "_urllib_transport", transport)
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == (1 if invalid_gate else 0)
    assert (tmp_path / ".cache/sentinel").read_bytes() == b"unrelated cache"
    assert set(requested) == set(responses)
    assert not any(
        "github.com/repos" in url or url.endswith(".apk") for url in requested
    )
    if invalid_gate:
        assert {
            path.name: path.read_bytes() for path in (tmp_path / "dist").glob("*.json")
        } == before_outputs
    else:
        for name in ("single-screen.json", "dual-screen.json"):
            assert (
                json.loads((tmp_path / "dist" / name).read_text())["apps"][0]["id"]
                == "app.fixture"
            )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["status"] == ("failed" if invalid_gate else "success")
    assert report["offlineVerification"]["status"] == (
        "failed" if invalid_gate else "success"
    )
    if invalid_gate:
        assert report["stage"] == "offline verification"
    assert not ({"generated", "unresolved", "retainedFailures"} & report.keys())
    assert {(item["kind"], item["id"]) for item in report["sourceAdmissions"]} == {
        ("apk", "app.generated"),
        ("apk", "app.retained"),
    }
    assert report["changes"]["dual"] == {
        "added": ["app.fixture", "app.retained"]
        if existing
        else ["app.fixture", "app.generated", "app.retained"],
        "removed": [],
    }
    assert not (tmp_path / "dist/report.json").exists()


@pytest.mark.parametrize("stage", ["rendering", "report writing", "publication"])
@pytest.mark.parametrize("existing", [False, True])
def test_failed_build_reports_exact_stage_and_preserves_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str, existing: bool
) -> None:
    (tmp_path / "README.md").write_bytes(
        b"<!-- omnipack:catalog:start -->\n<!-- omnipack:catalog:end -->\n"
    )
    config = tmp_path / "config"
    config.mkdir()
    policy_document = {"schemaVersion": 1, "candidates": [], "pins": []}
    consumed_policy = parse_composition_policy(policy_document)
    candidate = App(
        "current.id",
        "https://example.test/current",
        "Current",
        SourceType.HTML,
        (),
        Variant.SINGLE,
        Provenance("extras", "fixture"),
        eligibility=frozenset(Variant),
    )
    for name, value in (
        ("composition.json", policy_document),
        ("deny.json", []),
        ("overlay.json", []),
        ("settings.json", {}),
    ):
        (config / name).write_text(json.dumps(value))
    before = json.dumps(
        {
            "apps": [
                {"id": "before.id", "url": "https://example.test/old"},
                {"id": "unknown.id", "url": "https://example.test/unknown"},
            ]
        }
    ).encode()
    paths = [
        tmp_path / "dist" / name for name in ("single-screen.json", "dual-screen.json")
    ]
    if existing:
        paths[0].parent.mkdir()
        for path in paths:
            path.write_bytes(before)
    monkeypatch.setattr(
        cli,
        "_ingest_for_build",
        lambda root, report: IngestionResult(
            [candidate],
            report,
            consumed_policy,
            (root / "config/composition.json").read_bytes(),
        ),
    )
    if stage == "rendering":
        from omnipack import build as build_module

        real_render = build_module.render
        renders = 0

        def render(*args):
            nonlocal renders
            renders += 1
            if renders == 2:
                raise ValueError("injected rendering failure")
            return real_render(*args)

        monkeypatch.setattr(build_module, "render", render)
    else:
        real_replace = Path.replace
        failed = False

        def replace(source: Path, target: Path) -> Path:
            nonlocal failed
            target_path = Path(target)
            selected = (
                target_path.name == "report.json"
                if stage == "report writing"
                else target_path.name == "dual-screen.json"
            )
            if selected and not failed:
                failed = True
                raise OSError(f"injected {stage} failure")
            return real_replace(source, target)

        monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 1
    for path in paths:
        if existing:
            assert path.read_bytes() == before
        else:
            assert not path.exists()
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["stage"] == stage
    assert report["error"] == f"injected {stage} failure"
    assert report["offlineVerification"] == {
        "status": "not-run" if stage == "rendering" else "success",
        "findings": [],
    }
    assert report["changes"] == {
        variant.value: {
            "added": ["current.id"],
            "removed": ["before.id", "unknown.id"] if existing else [],
        }
        for variant in Variant
    }


def test_composition_failure_preserves_collected_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "README.md").write_bytes(
        b"<!-- omnipack:catalog:start -->\n<!-- omnipack:catalog:end -->\n"
    )
    config = tmp_path / "config"
    config.mkdir()
    for name, value in (
        ("composition.json", {"schemaVersion": 1, "candidates": [], "pins": []}),
        (
            "deny.json",
            [
                {"id": "removed.app", "reason": "excluded"},
                {"id": "stale.app", "reason": "obsolete"},
            ],
        ),
        (
            "overlay.json",
            [
                {
                    "id": "missing.app",
                    "url": "https://example.com/missing",
                    "patch": {"name": "Missing"},
                }
            ],
        ),
    ):
        (config / name).write_text(json.dumps(value), encoding="utf-8")
    apps = [
        App(
            package_id,
            "https://example.test/app",
            source,
            SourceType.HTML,
            (),
            Variant.SINGLE,
            Provenance(source, "https://example.test/catalog"),
            eligibility=frozenset(Variant),
        )
        for package_id, source in (
            ("collision.app", "rjny"),
            ("collision.app", "extras"),
            ("removed.app", "extras"),
        )
    ]
    monkeypatch.setattr(
        cli,
        "_ingest_for_build",
        lambda root, report: IngestionResult(
            apps, report, EMPTY_POLICY, (root / "config/composition.json").read_bytes()
        ),
    )
    monkeypatch.chdir(tmp_path)

    assert main(["build"]) == 1
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["stage"] == "composition"
    assert "missing.app" in report["error"]
    assert report["displacements"] == [
        {
            "id": "collision.app",
            "variant": variant.value,
            "winner_source": "extras",
            "loser_source": "rjny",
            "differing_fields": ["name"],
        }
        for variant in Variant
    ]
    assert report["denylistRemovals"] == [
        {
            "id": "removed.app",
            "variant": variant.value,
            "reason": "excluded",
            "family": "package:removed.app",
        }
        for variant in Variant
    ]
    assert report["staleExclusions"] == [{"id": "stale.app", "reason": "obsolete"}]
    assert report["changes"] is None
    assert not (tmp_path / "dist").exists()


def test_offline_gate_preserves_pair_and_standalone_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "README.md").write_bytes(
        b"<!-- omnipack:catalog:start -->\n<!-- omnipack:catalog:end -->\n"
    )
    config = tmp_path / "config"
    config.mkdir()
    for name, value in (
        ("composition.json", {"schemaVersion": 1, "candidates": [], "pins": []}),
        ("deny.json", []),
        ("overlay.json", []),
        ("settings.json", {}),
    ):
        (config / name).write_text(json.dumps(value))
    dist = tmp_path / "dist"
    dist.mkdir()
    before = b'{"settings":{"categories":"{}"},"apps":[]}\n'
    for name in ("single-screen.json", "dual-screen.json"):
        (dist / name).write_bytes(before)
    verify_path = tmp_path / ".build/verify.json"
    verify_path.parent.mkdir()
    verify_path.write_bytes(b'{"keep":true}\n')
    composed = CompositionResult(
        {variant: [] for variant in Variant}, CompositionReport()
    )
    monkeypatch.setattr(
        cli,
        "_ingest_for_build",
        lambda root, report: IngestionResult(
            [], report, EMPTY_POLICY, (root / "config/composition.json").read_bytes()
        ),
    )
    monkeypatch.setattr(cli, "compose", lambda *_args, **_kwargs: composed)
    calls = 0

    def render(*_args: object) -> str:
        nonlocal calls
        calls += 1
        return (
            '{"settings":{"categories":"{}"},"apps":[]}\n' if calls == 1 else "not json"
        )

    monkeypatch.setattr("omnipack.build.render", render)
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 1
    assert all(
        (dist / name).read_bytes() == before
        for name in ("single-screen.json", "dual-screen.json")
    )
    assert verify_path.read_bytes() == b'{"keep":true}\n'
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["stage"] == "offline verification"
    assert report["offlineVerification"]["status"] == "failed"
    assert report["changes"] == {
        variant.value: {"added": [], "removed": []} for variant in Variant
    }


def test_build_rejects_semantically_equal_policy_bytes_replaced_after_ingestion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "README.md").write_bytes(
        b"<!-- omnipack:catalog:start -->\n<!-- omnipack:catalog:end -->\n"
    )
    config = tmp_path / "config"
    config.mkdir()
    original = b'{"schemaVersion":1,"candidates":[],"pins":[]}'
    (config / "composition.json").write_bytes(original)
    for name, value in (
        ("deny.json", []),
        ("overlay.json", []),
        ("settings.json", {}),
    ):
        (config / name).write_text(json.dumps(value))

    def ingested(root: Path, report: IngestionReport) -> IngestionResult:
        (root / "config/composition.json").write_bytes(original + b"\n")
        return IngestionResult([], report, EMPTY_POLICY, original)

    monkeypatch.setattr(cli, "_ingest_for_build", ingested)
    monkeypatch.setattr(
        cli,
        "compose",
        lambda *_args, **_kwargs: CompositionResult(
            {variant: [] for variant in Variant}, CompositionReport()
        ),
    )
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 1
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["stage"] == "offline verification"
    assert report["offlineVerification"]["findings"][0]["code"] == "input_changed"
    assert not (tmp_path / "dist").exists()


@pytest.mark.parametrize("reverse", [False, True])
def test_winning_tie_reports_original_selectors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    reverse: bool,
) -> None:
    (tmp_path / "README.md").write_bytes(
        b"<!-- omnipack:catalog:start -->\n<!-- omnipack:catalog:end -->\n"
    )
    config = tmp_path / "config"
    config.mkdir()
    for name in ("deny.json", "overlay.json"):
        (config / name).write_text("[]")
    candidates = [
        App(
            "same.package",
            "https://example.test/project",
            "Candidate",
            SourceType.HTML,
            (),
            Variant.SINGLE,
            Provenance("bboi", "fixture"),
            eligibility=frozenset(Variant),
            origin=origin,
            original_id=original,
        )
        for origin, original in (
            ("bboi-standard-asset", "original.standard"),
            ("bboi-dual-asset", "original.dual"),
        )
    ]
    monkeypatch.setattr(
        cli,
        "_ingest_for_build",
        lambda root, report: IngestionResult(
            list(reversed(candidates)) if reverse else candidates,
            report,
            EMPTY_POLICY,
            b'{"schemaVersion":1,"candidates":[],"pins":[]}',
        ),
    )
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 1
    report = json.loads((tmp_path / ".build/report.json").read_text())
    expected = (
        "family 'package:same.package' target 'single' has ambiguous winning candidates: "
        "source='bboi', origin='bboi-dual-asset', original_id='original.dual', "
        "url='example.test/project'; "
        "source='bboi', origin='bboi-standard-asset', original_id='original.standard', "
        "url='example.test/project'"
    )
    assert report["stage"] == "composition"
    assert report["changes"] is None
    assert report["error"] == expected
    assert expected in capsys.readouterr().err
    assert main(["report"]) == 0
    assert expected in capsys.readouterr().out
