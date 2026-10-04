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
        "quiver": {"catalog": "config/catalogs/quiver.json"},
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
    (config / "catalogs/quiver.json").write_text('{"apps": []}')
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


FIXTURE_URLS = {
    "app.fixture": "example.test/app",
    "app.generated": "github.com/fixture/generated",
    "app.retained": "github.com/fixture/retained",
}


def changed(*ids: str) -> list[dict[str, str]]:
    return [{"id": id_, "url": FIXTURE_URLS[id_]} for id_ in ids]


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
    assert build_report["offlineVerification"] == {
        "status": "success",
        "findings": [],
        "nonfatalFindings": [],
    }
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
            "added": [{"id": id_, "url": FIXTURE_URLS[id_]} for id_ in expected_ids],
            "removed": [],
        }
    assert not (tmp_path / "dist/report.json").exists()
    assert main(["verify"]) == 0
    verification = json.loads((tmp_path / ".build/verify.json").read_text())
    assert (
        verification["status"],
        verification["errors"],
        verification["nonfatalFindings"],
    ) == ("success", [], [])
    capsys.readouterr()
    assert main(["report"]) == 0
    output = capsys.readouterr().out
    for variant in Variant:
        assert f"Selection: {variant.value} example.test/app -> " in output
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
            json.dumps(
                {
                    "apps": [
                        {
                            "id": "app.generated",
                            "url": "https://github.com/Fixture/generated",
                        }
                    ]
                }
            )
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

        real_render = build_module.render_pack

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

        monkeypatch.setattr(build_module, "render_pack", invalid_render)
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
    assert report["changes"]["single"] == {
        "added": changed("app.fixture"),
        "removed": [],
    }
    assert report["changes"]["dual"] == {
        "added": changed("app.fixture", "app.retained")
        if existing != "none"
        else changed("app.fixture", "app.generated", "app.retained"),
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
                    "family": None,
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
    assert "family" in error
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

        real_render = build_module.render_pack
        renders = 0

        def render(*args):
            nonlocal renders
            renders += 1
            if renders == 2:
                raise ValueError("injected rendering failure")
            return real_render(*args)

        monkeypatch.setattr(build_module, "render_pack", render)
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
        "nonfatalFindings": [],
    }
    assert report["changes"] == {
        variant.value: {
            "added": [{"id": "current.id", "url": "example.test/current"}],
            "removed": [
                {"id": "before.id", "url": "example.test/old"},
                {"id": "unknown.id", "url": "example.test/unknown"},
            ]
            if existing
            else [],
        }
        for variant in Variant
    }


# A category key no build can satisfy, so assignment always reports it stale.
ABSENT_CATEGORY_POLICY = {
    "schemaVersion": 1,
    "candidates": [],
    "pins": [],
    "categories": {"app:absent": "Emulator"},
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
                {"url": "https://example.test/removed", "reason": "excluded"},
                {"url": "https://example.test/stale", "reason": "obsolete"},
            ],
        ),
        (
            "overlay.json",
            [{"url": "https://example.com/missing", "patch": {"name": "Missing"}}],
        ),
        ("composition.json", ABSENT_CATEGORY_POLICY),
    ):
        (config / name).write_text(json.dumps(value), encoding="utf-8")
    apps = [
        App(
            package_id,
            url,
            source,
            SourceType.HTML,
            (),
            Provenance(source, "https://example.test/catalog"),
            eligibility=frozenset(Variant),
        )
        for package_id, source, url in (
            ("collision.app", "rjny", "https://example.test/app"),
            ("collision.app", "extras", "https://example.test/app"),
            ("removed.app", "extras", "https://example.test/removed"),
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
    assert "example.com/missing" in report["error"]
    assert report["selections"] == [
        {
            "family": "example.test/app",
            "variant": variant.value,
            "id": "collision.app",
            "url": "https://example.test/app",
            "source": "extras",
            "origin": "extras",
            "reason": "source" if variant is Variant.SINGLE else "ordinary-fallback",
            "considered": [
                {
                    "source": "rjny",
                    "origin": "rjny",
                    "id": "collision.app",
                    "url": "https://example.test/app",
                }
            ],
        }
        for variant in Variant
    ]
    assert report["denylistRemovals"] == [
        {
            "url": "example.test/removed",
            "reason": "excluded",
            "families": ["example.test/removed"],
        }
    ]
    assert report["staleExclusions"] == [
        {"url": "example.test/stale", "reason": "obsolete"}
    ]
    # The overlay failed before category assignment ran, so neither category
    # list holds anything, although assignment would have filled both, and the
    # later coverage and repeated-id checks did not run either.
    assert report["uncategorizedFamilies"] == []
    assert report["staleCategoryAssignments"] == []
    assert report["singleOnlyFamilies"] == []
    assert report["repeatedIds"] == []
    assert report["changes"] is None
    assert not (tmp_path / "dist").exists()


def test_nonfatal_findings_publish_and_are_recorded_and_displayed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_config(tmp_path)
    (tmp_path / "config/composition.json").write_text(
        json.dumps(ABSENT_CATEGORY_POLICY),
        encoding="utf-8",
    )

    def candidate(package_id: str, url: str, variants: set[Variant]) -> App:
        return App(
            package_id,
            url,
            package_id,
            SourceType.HTML,
            ("Dual Screen",),
            Provenance("rjny", "https://example.test/catalog"),
            eligibility=frozenset(variants),
        )

    single_only = candidate(
        "single.app", "https://example.test/single", {Variant.SINGLE}
    )
    first = candidate("shared.app", "https://example.test/first", {Variant.DUAL})
    second = candidate("shared.app", "https://example.test/second", {Variant.DUAL})
    monkeypatch.setattr(
        cli,
        "_ingest_for_build",
        lambda root, inputs, report: [single_only, first, second],
    )
    monkeypatch.chdir(tmp_path)
    readme_before = (tmp_path / "README.md").read_bytes()

    assert main(["build"]) == 0
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["status"] == "success"
    assert report["singleOnlyFamilies"] == [
        {
            "family": "example.test/single",
            "id": "single.app",
            "url": "https://example.test/single",
        }
    ]
    assert report["repeatedIds"] == [
        {
            "variant": "dual",
            "id": "shared.app",
            "entries": [
                {"family": "example.test/first", "url": "https://example.test/first"},
                {"family": "example.test/second", "url": "https://example.test/second"},
            ],
        }
    ]
    assert report["uncategorizedFamilies"] == [
        {"family": family, "variants": [variant]}
        for family, variant in (
            ("example.test/first", "dual"),
            ("example.test/second", "dual"),
            ("example.test/single", "single"),
        )
    ]
    assert report["staleCategoryAssignments"] == ["app:absent"]
    offline = report["offlineVerification"]
    assert (offline["status"], offline["findings"]) == ("success", [])
    nonfatal = [(item["variant"], item["code"]) for item in offline["nonfatalFindings"]]
    assert nonfatal == [
        ("dual", "repeated_package_id"),
        ("single", "single_only_coverage"),
    ]
    readme = (tmp_path / "README.md").read_bytes()
    assert readme != readme_before and b"single.app" in readme

    assert main(["verify"]) == 0
    verification = json.loads((tmp_path / ".build/verify.json").read_text())
    assert (verification["status"], verification["errors"]) == ("success", [])
    assert verification["nonfatalFindings"] == offline["nonfatalFindings"]

    capsys.readouterr()
    assert main(["report"]) == 0
    output = capsys.readouterr().out
    assert (
        "Single-only family: example.test/single; id: single.app; "
        "URL: https://example.test/single\n"
    ) in output
    assert "Repeated package id: dual shared.app; entries: " in output
    for item in offline["nonfatalFindings"]:
        line = (
            f"Nonfatal finding: [{item['variant']} / {item['entry_id']}] "
            f"{item['message']}\n"
        )
        assert output.count(line) == 2


@pytest.mark.parametrize("reverse", [False, True])
def test_winning_tie_publishes_one_build_and_reports_the_tie(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    reverse: bool,
) -> None:
    write_config(tmp_path)
    candidates = [
        App(
            package_id,
            "https://example.test/project",
            "Candidate",
            SourceType.HTML,
            (),
            Provenance("bboi", "fixture"),
            eligibility=frozenset(Variant),
            origin="bboi-standard-asset",
        )
        for package_id in ("same.stable", "same.nightly")
    ]
    monkeypatch.setattr(
        cli,
        "_ingest_for_build",
        lambda root, inputs, report: (
            list(reversed(candidates)) if reverse else candidates
        ),
    )
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 0
    report = json.loads((tmp_path / ".build/report.json").read_text())
    tied = [
        {
            "source": "bboi",
            "origin": "bboi-standard-asset",
            "id": package_id,
            "url": "example.test/project",
        }
        for package_id in ("same.nightly", "same.stable")
    ]
    assert report["sameRankTies"] == [
        {
            "family": "example.test/project",
            "variant": variant,
            "tied": tied,
            "winner": tied[0],
        }
        for variant in ("single", "dual")
    ]
    for variant in Variant:
        published = json.loads(
            (tmp_path / f"dist/{variant.value}-screen.json").read_text()
        )
        assert [app["id"] for app in published["apps"]] == ["same.nightly"]
    capsys.readouterr()
    assert main(["report"]) == 0
    assert (
        "Same-rank tie: single example.test/project; tied: "
        "bboi/bboi-standard-asset same.nightly at example.test/project | "
        "bboi/bboi-standard-asset same.stable at example.test/project; "
        "winner: bboi/bboi-standard-asset same.nightly at example.test/project\n"
    ) in capsys.readouterr().out


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
            [{"url": "https://example.test/app", "patch": {"name": "Edited"}}]
        ).encode(),
        "config/deny.json": json.dumps(
            [{"url": "https://example.test/app", "reason": "edited"}]
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
        (b"not json", "invalid JSON: Expecting value: line 1 column 1 (char 0)"),
        (
            (
                b'{"schemaVersion": 1, "candidates": [], "pins": [], '
                b'"categories": {}, "categories": {}}'
            ),
            "duplicate JSON key 'categories'",
        ),
        (
            (
                b'{"schemaVersion": 1, "pins": [], "candidates": [{"match": {}, '
                b'"rationale": "a", "rationale": "b"}]}'
            ),
            "duplicate JSON key 'rationale'",
        ),
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


def test_family_rule_on_a_track_only_candidate_builds(
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
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 0
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert {(item["family"], item["id"]) for item in report["selections"]} == {
        ("app:example", "org.example.old")
    }


def test_build_then_report_displays_diagnostics_without_changing_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    responses = write_fixture_pipeline(tmp_path)
    (tmp_path / "config/deny.json").write_text(
        json.dumps(
            [
                {"url": "https://example.test/app", "reason": "excluded fixture"},
                {"url": "https://example.test/absent", "reason": "unmatched denial"},
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
    assert (
        "Change: dual added: app.generated; URL: github.com/fixture/generated" in output
    )
    assert (
        "Exclusion: example.test/app; families: example.test/app; "
        "reason: excluded fixture\n"
    ) in output
    assert "Stale exclusion: example.test/absent; reason: unmatched denial" in output
    assert (
        "Admission: codm2000; URL: https://github.com/fixture/generated; kind: apk; committed id: app.generated"
        in output
    )
    assert path.read_bytes() == before
