import json
from collections.abc import Callable
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.request import Request

import pytest

from omnipack import cli
from omnipack.build import BuildInputs
from omnipack.cli import main
from omnipack.http import HttpClient, HttpResponse
from omnipack.model import App, Provenance, SourceType, Variant
from omnipack.overlay import ComposedApp
from omnipack.sources import IngestionReport
from tests.test_build import write_config
from tests.test_composition_policy import candidate as policy_candidate
from tests.test_composition_policy import policy, rule

EMPTY_POLICY = '{"schemaVersion":1,"candidates":[],"pins":[]}'


def test_no_command_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main([])
    assert "required" in capsys.readouterr().err


def test_verify_missing_inputs_fails_and_report_displays_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["verify"]) == 1
    assert main(["report"]) == 0


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
    assert build_report["status"] == "success"
    assert build_report["offlineVerification"] == {"status": "success", "findings": []}
    for variant in Variant:
        expected_ids = (
            ["app.fixture"]
            if variant is Variant.SINGLE
            else ["app.fixture", "app.generated", "app.retained"]
        )
        rendered = json.loads(
            (tmp_path / "dist" / f"{variant.value}-screen.json").read_text()
        )
        assert [app["id"] for app in rendered["apps"]] == expected_ids
        assert build_report["changes"][variant.value] == {
            "added": expected_ids,
            "removed": [],
        }
    assert not (tmp_path / "dist/report.json").exists()
    assert main(["verify"]) == 0
    verification = json.loads((tmp_path / ".build/verify.json").read_text())
    assert (verification["status"], verification["errors"]) == ("success", [])
    capsys.readouterr()
    assert main(["report"]) == 0
    output = capsys.readouterr().out
    for variant in Variant:
        assert f"Selection: {variant.value} package:app.fixture -> " in output
    assert "Evidence: current" in output


@pytest.mark.parametrize(
    ("existing", "invalid_variant"),
    [
        ("none", None),
        ("dual", None),
        ("both", None),
        ("none", "single"),
        ("both", "dual"),
    ],
    ids=["first-build", "partial-outputs", "rebuild", "invalid-single", "invalid-dual"],
)
def test_build_runs_the_real_pipeline_with_transport_only_fixtures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing: str,
    invalid_variant: str | None,
) -> None:
    responses = write_fixture_pipeline(tmp_path)
    invalid_gate = invalid_variant is not None
    if existing != "none":
        (tmp_path / "dist").mkdir()
        if existing == "both":
            (tmp_path / "dist/single-screen.json").write_text('{"apps": []}\n')
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
            variant = (
                "dual"
                if any(app["id"] == "app.generated" for app in rendered["apps"])
                else "single"
            )
            if variant == invalid_variant:
                if variant == "dual":
                    return "not json"
                rendered["apps"][0]["preferredApkIndex"] = "first"
            return json.dumps(rendered)

        monkeypatch.setattr(build_module, "render", invalid_render)
    evidence = tmp_path / ".build/verify.json"
    evidence.parent.mkdir()
    evidence.write_bytes(b'{"keep":true}\n')
    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache/sentinel").write_bytes(b"unrelated cache")
    before_outputs = {
        path.name: path.read_bytes() for path in (tmp_path / "dist").glob("*.json")
    }
    monkeypatch.setattr(HttpClient, "_urllib_transport", transport)
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == (1 if invalid_gate else 0)
    assert (tmp_path / ".cache/sentinel").read_bytes() == b"unrelated cache"
    assert evidence.read_bytes() == b'{"keep":true}\n'
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
    assert report["changes"]["single"] == {"added": ["app.fixture"], "removed": []}
    assert report["changes"]["dual"] == {
        "added": ["app.fixture", "app.retained"]
        if existing != "none"
        else ["app.fixture", "app.generated", "app.retained"],
        "removed": [],
    }
    assert not (tmp_path / "dist/report.json").exists()


def test_guarded_extras_field_fails_build_and_preserves_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    responses = write_fixture_pipeline(tmp_path)
    extras_path = tmp_path / "config/extras.json"
    extras_path.write_text(
        json.dumps(
            [
                {
                    "id": "app.extra",
                    "url": "https://example.test/extra",
                    "name": "Guarded extra",
                    "packageId": None,
                }
            ]
        )
    )
    dist = tmp_path / "dist"
    dist.mkdir()
    before = {
        "single-screen.json": b'{"apps":[{"id":"before-single"}]}\n',
        "dual-screen.json": b'{"apps":[{"id":"before-dual"}]}\n',
    }
    for name, body in before.items():
        (dist / name).write_bytes(body)

    def transport(
        _client: HttpClient, request: Request, _timeout: float
    ) -> HttpResponse:
        body = responses[request.full_url].encode()
        return HttpResponse(request.full_url, 200, Message(), body)

    monkeypatch.setattr(HttpClient, "_urllib_transport", transport)
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 1
    assert {name: (dist / name).read_bytes() for name in before} == before
    error = capsys.readouterr().err
    assert "extras" in error
    assert "Guarded extra" in error
    assert "packageId" in error
    assert "cannot come from a source record" in error
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["stage"] == "ingestion"
    assert report["error"].startswith("extras: ")


@pytest.mark.parametrize(
    ("stage", "existing"),
    [
        ("rendering", True),
        ("report writing", True),
        ("publication", False),
        ("publication", True),
    ],
    ids=["rendering", "report-writing", "first-publication", "replacement"],
)
def test_failed_build_reports_exact_stage_and_preserves_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str, existing: bool
) -> None:
    write_config(tmp_path)
    candidate = App(
        "current.id",
        "https://example.test/current",
        "Current",
        SourceType.HTML,
        (),
        Provenance("extras", "fixture"),
        eligibility=frozenset(Variant),
    )
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
        lambda root, inputs, report: [candidate],
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
    write_config(tmp_path)
    config = tmp_path / "config"
    for name, value in (
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
        lambda root, inputs, report: apps,
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


@pytest.mark.parametrize("reverse", [False, True])
def test_winning_tie_reports_original_selectors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    reverse: bool,
) -> None:
    write_config(tmp_path)
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
        lambda root, inputs, report: (
            list(reversed(candidates)) if reverse else candidates
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
        root: Path, inputs: BuildInputs, report: IngestionReport
    ) -> list[App]:
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
    "http_config",
    [
        None,
        b"not json",
        json.dumps(
            {
                "credentials": {
                    "raw.githubusercontent.com": "GITHUB_TOKEN",
                    "codeberg.org": "GITHUB_TOKEN",
                }
            }
        ).encode(),
    ],
    ids=["absent", "unreadable", "registered"],
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
        ("config/extras.json", "extras"),
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


@pytest.mark.parametrize(
    ("policy_bytes", "message"),
    [
        (b"{}", "schemaVersion must be integer 1"),
        (b"not json", "Expecting value: line 1 column 1 (char 0)"),
    ],
)
def test_malformed_composition_policy_error_names_its_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    policy_bytes: bytes,
    message: str,
) -> None:
    write_fixture_pipeline(tmp_path)
    (tmp_path / "config/composition.json").write_bytes(policy_bytes)

    def fetch(*_args: object) -> HttpResponse:
        pytest.fail("the build fetched a catalog after a malformed input")

    monkeypatch.setattr(HttpClient, "_urllib_transport", fetch)
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 1
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["stage"] == "ingestion"
    assert report["error"] == f"composition policy: {message}"
    assert report["error"] in capsys.readouterr().err
    assert not (tmp_path / "dist").exists()


def test_invalid_track_only_policy_preserves_prior_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path)
    (tmp_path / "config/composition.json").write_text(
        json.dumps(policy(candidates=[rule(family="app:example")]))
    )
    tracker = policy_candidate(additional_settings={"trackOnly": True})
    monkeypatch.setattr(
        cli, "_ingest_for_build", lambda root, inputs, report: [tracker]
    )
    paths = [
        tmp_path / "dist" / name for name in ("single-screen.json", "dual-screen.json")
    ]
    paths[0].parent.mkdir()
    before = b'{"apps": []}\n'
    for path in paths:
        path.write_bytes(before)
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 1
    assert all(path.read_bytes() == before for path in paths)
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["stage"] == "composition"
    assert "track-only" in report["error"]
    assert "org.example.old" in report["error"]


def test_build_then_report_displays_diagnostics_without_changing_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    responses = write_fixture_pipeline(tmp_path)
    (tmp_path / "config/deny.json").write_text(
        json.dumps(
            [
                {"id": "app.fixture", "reason": "excluded fixture"},
                {"id": "app.absent", "reason": "unmatched denial"},
            ]
        )
    )
    monkeypatch.setattr(HttpClient, "_urllib_transport", fixture_transport(responses))
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 0
    path = tmp_path / ".build/report.json"
    before = path.read_bytes()
    capsys.readouterr()
    assert main(["report"]) == 0
    output = capsys.readouterr().out
    assert "Change: dual added: app.generated" in output
    for variant in Variant:
        assert (
            f"Exclusion: {variant.value} app.fixture; family: package:app.fixture; reason: excluded fixture"
            in output
        )
    assert "Stale exclusion: app.absent; reason: unmatched denial" in output
    assert (
        "Admission: codm2000; URL: https://github.com/fixture/generated; kind: apk; committed id: app.generated"
        in output
    )
    assert path.read_bytes() == before


def selector(app: App) -> dict[str, str]:
    return {
        "source": app.provenance.source,
        "origin": app.origin,
        "id": app.original_id,
        "url": app.url,
    }


def family_rules(family: str, *apps: App) -> list[dict[str, object]]:
    return [
        {"match": selector(app), "family": family, "rationale": "test"} for app in apps
    ]


def build_candidate(
    package_id: str,
    source: str,
    origin: str,
    url: str,
    eligibility: frozenset[Variant] = frozenset(Variant),
) -> App:
    return App(
        package_id,
        url,
        f"{source} {package_id}",
        SourceType.HTML,
        (),
        Provenance(source, "https://example.test/catalog"),
        eligibility=eligibility,
        origin=origin,
    )


def run_build(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    candidates: list[App],
    rules: list[dict[str, object]],
) -> tuple[int, dict[str, Any]]:
    """Build candidates plus one denied and one stale denial under the rules."""
    write_config(root)
    removed = build_candidate(
        "removed.app", "extras", "extras", "https://example.test/removed"
    )
    config = root / "config"
    (config / "composition.json").write_text(
        json.dumps({"schemaVersion": 1, "candidates": rules, "pins": []})
    )
    (config / "deny.json").write_text(
        json.dumps(
            [
                {"id": "removed.app", "reason": "excluded"},
                {"id": "stale.app", "reason": "obsolete"},
            ]
        )
    )
    monkeypatch.setattr(
        cli, "_ingest_for_build", lambda root, inputs, report: [*candidates, removed]
    )
    monkeypatch.chdir(root)
    code = main(["build"])
    return code, json.loads((root / ".build/report.json").read_text())


def assert_denials_preserved(report: dict[str, Any]) -> None:
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


def test_joined_explicit_families_report_both_families_and_joining_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = build_candidate("shared", "rjny", "rjny-catalog", "https://example.test/x")
    second = build_candidate(
        "shared", "bboi", "bboi-standard-asset", "https://example.test/y"
    )
    code, report = run_build(
        tmp_path,
        monkeypatch,
        [first, second],
        [*family_rules("app:x", first), *family_rules("app:y", second)],
    )
    assert code == 1
    assert report["stage"] == "composition"
    assert report["error"] == (
        "explicit families 'app:x', 'app:y' join through a shared package id: "
        "('bboi', 'bboi-standard-asset', 'shared', 'example.test/y'); "
        "('rjny', 'rjny-catalog', 'shared', 'example.test/x')"
    )
    assert_denials_preserved(report)


def selected_builds_joined_by_losers() -> tuple[list[App], list[App], list[App]]:
    """Rules on losing builds only; the winners join their family by id."""
    ruled = [
        build_candidate("a", "rjny", "rjny-catalog", "https://example.test/X"),
        build_candidate("c", "rjny", "rjny-catalog", "https://example.test/W"),
    ]
    winners = [
        build_candidate("a", "extras", "extras", "https://example.test/Y"),
        build_candidate(
            "c",
            "bboi",
            "bboi-dual-asset",
            "https://example.test/V",
            frozenset({Variant.DUAL}),
        ),
    ]
    return [*ruled, *winners], ruled, winners


def test_family_whose_selected_builds_do_not_pair_fails_until_both_project_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidates, ruled, winners = selected_builds_joined_by_losers()
    code, report = run_build(
        tmp_path, monkeypatch, candidates, family_rules("app:x", *ruled)
    )
    assert code == 1
    assert report["stage"] == "composition"
    assert report["error"] == (
        "family 'app:x' selects single-screen ('a', 'example.test/Y') and "
        "dual-screen ('c', 'example.test/V'), which offline verification cannot "
        "pair; add a family rule assigning 'app:x' to ('a', 'example.test/Y') and "
        "('c', 'example.test/V')"
    )
    assert [
        (item["family"], item["variant"], item["source"])
        for item in report["selections"]
    ] == [("app:x", "single", "extras"), ("app:x", "dual", "bboi")]
    assert_denials_preserved(report)

    code, report = run_build(
        tmp_path, monkeypatch, candidates, family_rules("app:x", *ruled, *winners)
    )
    assert code == 0, report.get("error")
    assert report["offlineVerification"] == {"status": "success", "findings": []}
