import json
from collections.abc import Callable
from email.message import Message
from pathlib import Path
from urllib.request import Request

import pytest

from omnipack import cli
from omnipack.build import BuildInputs
from omnipack.cli import main
from omnipack.http import HttpClient, HttpResponse
from omnipack.merge import CompositionReport, CompositionResult
from omnipack.model import App, Provenance, SourceType, Variant
from omnipack.overlay import ComposedApp
from omnipack.sources import IngestionReport, IngestionResult, SourceError

EMPTY_POLICY = '{"schemaVersion":1,"candidates":[],"pins":[]}'


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
    for name, value in (
        ("composition.json", {"schemaVersion": 1, "candidates": [], "pins": []}),
        ("sources.json", {}),
        ("extras.json", []),
        ("deny.json", []),
        ("overlay.json", []),
    ):
        (tmp_path / "config" / name).write_text(json.dumps(value), encoding="utf-8")
    app = ComposedApp(
        "package:app.test",
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
            Variant.DUAL: [ComposedApp(app.family, dict(app.data))],
        },
        CompositionReport(),
    )
    monkeypatch.setattr(
        cli,
        "_ingest_for_build",
        lambda root, inputs, report=None: IngestionResult(
            [], report or IngestionReport()
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
    (tmp_path / "config").mkdir()
    (tmp_path / "config/composition.json").write_text(EMPTY_POLICY)
    for name, value in (
        ("sources.json", "{}"),
        ("extras.json", "[]"),
        ("deny.json", "[]"),
        ("overlay.json", "[]"),
    ):
        (tmp_path / "config" / name).write_text(value)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cli,
        "_ingest_for_build",
        lambda root, inputs, report=None: (_ for _ in ()).throw(
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
        ("sources.json", {}),
        ("extras.json", []),
        ("deny.json", []),
        ("overlay.json", []),
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

    def resolved(
        _root: Path, _inputs: BuildInputs, report: IngestionReport | None = None
    ) -> IngestionResult:
        return IngestionResult([], report or IngestionReport())

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
        "extras.json": [],
        "composition.json": {"schemaVersion": 1, "candidates": [], "pins": []},
        "deny.json": [],
        "overlay.json": [],
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
) -> Callable[[HttpClient, Request, float], HttpResponse]:
    def transport(
        _client: HttpClient, request: Request, _timeout: float
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
        _client: HttpClient, request: Request, _timeout: float
    ) -> HttpResponse:
        requested.append(request.full_url)
        body = responses[request.full_url].encode()
        return HttpResponse(request.full_url, 200, Message(), body)

    if invalid_gate:
        from omnipack import build as build_module

        real_render = build_module.render

        def invalid_render(apps: list[ComposedApp]) -> str:
            rendered = json.loads(real_render(apps))
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
    candidate = App(
        "current.id",
        "https://example.test/current",
        "Current",
        SourceType.HTML,
        (),
        Provenance("extras", "fixture"),
        eligibility=frozenset(Variant),
    )
    for name, value in (
        ("composition.json", policy_document),
        ("sources.json", {}),
        ("extras.json", []),
        ("deny.json", []),
        ("overlay.json", []),
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
        lambda root, inputs, report: IngestionResult([candidate], report),
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
        ("sources.json", {}),
        ("extras.json", []),
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
        lambda root, inputs, report: IngestionResult(apps, report),
    )
    monkeypatch.chdir(tmp_path)

    assert main(["build"]) == 1
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["stage"] == "composition"
    assert "missing.app" in report["error"]
    assert report["selections"] == [
        {
            "family": "package:collision.app",
            "variant": variant.value,
            "original_id": "collision.app",
            "effective_id": "collision.app",
            "url": "https://example.test/app",
            "source": "extras",
            "origin": "extras",
            "reason": "source" if variant is Variant.SINGLE else "ordinary-fallback",
            "considered": [
                {
                    "source": "rjny",
                    "origin": "rjny",
                    "original_id": "collision.app",
                    "url": "https://example.test/app",
                }
            ],
        }
        for variant in Variant
    ]
    assert "displacements" not in report
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
        ("sources.json", {}),
        ("extras.json", []),
        ("deny.json", []),
        ("overlay.json", []),
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
        lambda root, inputs, report: IngestionResult([], report),
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
    (config / "composition.json").write_text(EMPTY_POLICY)
    (config / "sources.json").write_text("{}")
    (config / "extras.json").write_text("[]")
    candidates = [
        App(
            "same.package",
            "https://example.test/project",
            "Candidate",
            SourceType.HTML,
            (),
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
        lambda root, inputs, report: IngestionResult(
            list(reversed(candidates)) if reverse else candidates, report
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


@pytest.mark.parametrize(
    "edited",
    [
        "README.md",
        "config/overlay.json",
        "config/deny.json",
        "config/composition.json",
        "config/sources.json",
        "config/extras.json",
    ],
)
def test_inputs_edited_after_the_build_starts_do_not_reach_its_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, edited: str
) -> None:
    responses = write_fixture_pipeline(tmp_path)
    readme_before = (tmp_path / "README.md").read_bytes()
    edits = {
        "README.md": b"Edited guide\n" + readme_before,
        "config/overlay.json": json.dumps(
            [
                {
                    "id": "app.fixture",
                    "url": "https://example.test/app",
                    "patch": {"name": "Edited"},
                }
            ]
        ).encode(),
        "config/deny.json": json.dumps(
            [{"id": "app.fixture", "reason": "edited"}]
        ).encode(),
        "config/composition.json": b"not json",
        "config/sources.json": b"not json",
        "config/extras.json": json.dumps(
            [
                {
                    "id": "edited.extra",
                    "url": "https://example.test/edited",
                    "name": "Edited Extra",
                }
            ]
        ).encode(),
    }
    real_ingest = cli._ingest_for_build

    def ingest_then_edit(
        root: Path, inputs: BuildInputs, report: IngestionReport | None = None
    ) -> IngestionResult:
        (root / edited).write_bytes(edits[edited])
        return real_ingest(root, inputs, report)

    monkeypatch.setattr(cli, "_ingest_for_build", ingest_then_edit)
    monkeypatch.setattr(HttpClient, "_urllib_transport", fixture_transport(responses))
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 0
    for name in ("single-screen.json", "dual-screen.json"):
        apps = json.loads((tmp_path / "dist" / name).read_text())["apps"]
        assert [app["name"] for app in apps if app["id"] == "app.fixture"] == [
            "Fixture"
        ]
        assert "edited.extra" not in {app["id"] for app in apps}
    readme = (tmp_path / "README.md").read_bytes()
    assert b"Edited guide" not in readme and b"Fixture" in readme
    if edited != "README.md":
        assert (tmp_path / edited).read_bytes() == edits[edited]


@pytest.mark.parametrize(
    "http_config", [None, b"not json"], ids=["absent", "unreadable"]
)
def test_build_fetches_catalogs_without_credentials_or_http_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, http_config: bytes | None
) -> None:
    responses = write_fixture_pipeline(tmp_path)
    if http_config is not None:
        (tmp_path / "config/http.json").write_bytes(http_config)
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    requests: list[Request] = []

    def transport(
        _client: HttpClient, request: Request, _timeout: float
    ) -> HttpResponse:
        requests.append(request)
        body = responses[request.full_url].encode()
        return HttpResponse(request.full_url, 200, Message(), body)

    monkeypatch.setattr(HttpClient, "_urllib_transport", transport)
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 0
    assert {request.full_url for request in requests} == set(responses)
    assert all(request.get_header("Authorization") is None for request in requests)


@pytest.mark.parametrize(
    ("missing", "source"),
    [
        ("config/sources.json", "sources"),
        ("config/deny.json", "denylist"),
        ("config/overlay.json", "overlay"),
        ("config/composition.json", "composition policy"),
    ],
)
def test_missing_local_input_fails_at_ingestion_before_any_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str, source: str
) -> None:
    write_fixture_pipeline(tmp_path)
    (tmp_path / missing).unlink()

    def fetch(*_args: object) -> HttpResponse:
        pytest.fail("the build fetched a catalog after a missing input")

    monkeypatch.setattr(HttpClient, "_urllib_transport", fetch)
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 1
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["stage"] == "ingestion"
    assert report["error"].startswith(f"{source}: ")
    assert not (tmp_path / "dist").exists()
