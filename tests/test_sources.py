from __future__ import annotations

import json
import shutil
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request

import pytest

from omnipack import cli
from omnipack.composition_policy import parse_composition_policy
from omnipack.http import HttpClient, HttpError, HttpResponse
from omnipack.merge import CompositionError, _import_data, compose
from omnipack.model import App, Provenance, SourceType, Variant
from omnipack.overlay import ComposedApp
from omnipack.render import render
from omnipack.sources import (
    IngestionReport,
    SourceError,
    bboi,
    codm,
    extras,
    ingest_all,
    rjny,
)

FIXTURES = Path(__file__).parent / "fixtures"


class FakeHttp:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def get(self, url: str, **_kwargs: Any) -> HttpResponse:
        self.urls.append(url)
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        body = value if isinstance(value, bytes) else value.encode()
        return HttpResponse(url, 200, Message(), body)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_rjny_applies_export_flags_and_ignores_presentation_overrides() -> None:
    url = "https://raw.githubusercontent.com/RJNY/Obtainium-Emulation-Pack/main/src/applications.json"
    apps = rjny.fetch(
        FakeHttp({url: fixture("rjny-applications.json")}),
        {
            "repo": "RJNY/Obtainium-Emulation-Pack",
            "branch": "main",
            "path": "src/applications.json",
        },
    )
    cemu = [app for app in apps if app.id == "info.cemu.cemu"]
    assert {(app.eligibility, app.url) for app in cemu} == {
        (frozenset({Variant.SINGLE}), "https://github.com/SSimco/Cemu"),
        (frozenset({Variant.DUAL}), "https://github.com/sapphirerhodonite/cemu"),
    }
    assert all(app.name == "Citra" for app in apps if app.id == "org.citra.emu")
    assert not any("Dev build" in app.name for app in apps)
    assert all(isinstance(app.additional_settings, dict) for app in apps)


def test_rjny_build_kept_out_of_dual_leaves_dual_to_its_family_s_dual_only_build() -> (
    None
):
    url = "https://raw.githubusercontent.com/RJNY/Obtainium-Emulation-Pack/main/src/applications.json"
    apps = rjny.fetch(
        FakeHttp({url: fixture("rjny-applications.json")}),
        {
            "repo": "RJNY/Obtainium-Emulation-Pack",
            "branch": "main",
            "path": "src/applications.json",
        },
    )
    cemu = [app for app in apps if app.id == "info.cemu.cemu"]
    result = compose(
        cemu,
        [],
        [],
        policy=parse_composition_policy(
            {"schemaVersion": 1, "candidates": [], "pins": []}
        ),
    )
    selections = {item.variant: item for item in result.report.selections}
    assert {
        variant: (item.url, item.reason) for variant, item in selections.items()
    } == {
        Variant.SINGLE: ("https://github.com/SSimco/Cemu", "source"),
        Variant.DUAL: ("https://github.com/sapphirerhodonite/cemu", "dual-preferred"),
    }
    assert selections[Variant.DUAL].considered == ()


def test_rjny_matches_both_upstream_exports() -> None:
    catalog_url = "https://raw.githubusercontent.com/RJNY/Obtainium-Emulation-Pack/main/src/applications.json"
    apps = rjny.fetch(
        FakeHttp({catalog_url: fixture("rjny-applications.json")}),
        {
            "repo": "RJNY/Obtainium-Emulation-Pack",
            "branch": "main",
            "path": "src/applications.json",
        },
    )
    for variant, export_name, count in (
        (Variant.SINGLE, "rjny-single.json", 62),
        (Variant.DUAL, "rjny-dual.json", 66),
    ):
        expected = json.loads(fixture(export_name))["apps"]
        assert len(expected) == count
        eligible = [app for app in apps if variant in app.eligibility]
        assert len(eligible) == count
        assert {(app.id, app.url) for app in eligible} == {
            (entry["id"], entry["url"]) for entry in expected
        }


def test_rjny_rejects_empty_location_and_unsupported_source() -> None:
    with pytest.raises(SourceError, match="rjny"):
        rjny.fetch(FakeHttp({}), {"repo": "", "branch": "main", "path": "x"})
    record = json.loads(fixture("rjny-applications.json"))
    record["apps"][0]["overrideSource"] = "F-Droid Third Party Repo"
    url = "https://raw.githubusercontent.com/r/main/p"
    with pytest.raises(SourceError, match="rjny.*F-Droid Third Party Repo"):
        rjny.fetch(
            FakeHttp({url: json.dumps(record)}),
            {"repo": "r", "branch": "main", "path": "p"},
        )


@pytest.mark.parametrize(
    "path", ["Case/Parent/Project", "/".join(f"Group{i}" for i in range(21))]
)
def test_explicit_gitlab_extra_precedes_url_inference_and_preserves_subgroups(
    path: str,
) -> None:
    [app] = extras.fetch(
        [
            {
                "id": "com.example.app",
                "name": "Example",
                "url": f"https://gitlab.com/{path}",
                "overrideSource": "GitLab",
                "additionalSettings": {"apkFilterRegEx": "ordinary\\.apk$"},
            }
        ]
    )
    assert app.source_type is SourceType.GITLAB
    assert app.url == f"https://gitlab.com/{path}"


def test_undeclared_extra_keeps_existing_url_inference() -> None:
    records = [
        {"id": "github", "name": "GitHub", "url": "https://github.com/a/b"},
        {"id": "other", "name": "Other", "url": "https://gitlab.com/a/b"},
    ]
    assert [app.source_type for app in extras.fetch(records)] == [
        SourceType.GITHUB,
        SourceType.HTML,
    ]


@pytest.mark.parametrize(
    "url",
    [
        "http://gitlab.com/a/b",
        "https://example.com/a/b",
        "https://gitlab.com/one",
        "https://user@gitlab.com/a/b",
        "https://gitlab.com/" + "/".join(f"Group{i}" for i in range(22)),
        "https://gitlab.com:invalid/a/b",
    ],
)
def test_explicit_gitlab_extra_rejects_urls_outside_public_boundary(url: str) -> None:
    with pytest.raises(SourceError, match="GitLab.*URL|URL.*GitLab"):
        extras.fetch(
            [
                {
                    "id": "bad",
                    "name": "Bad",
                    "url": url,
                    "overrideSource": "GitLab",
                }
            ]
        )


def test_rjny_entry_out_of_both_exports_contributes_to_neither_pack() -> None:
    url = "https://raw.githubusercontent.com/r/main/p"
    records = [
        {
            "id": "app.disabled",
            "name": "Disabled",
            "url": "https://github.com/owner/disabled",
            "overrideSource": "GitHub",
            "meta": {"includeInStandard": False, "includeInDualScreen": False},
        },
        {
            "id": "app.excluded",
            "name": "Excluded",
            "url": "https://github.com/owner/excluded",
            "overrideSource": "GitHub",
            "meta": {"excludeFromExport": True},
        },
    ]
    apps = rjny.fetch(
        FakeHttp({url: json.dumps({"apps": records})}),
        {"repo": "r", "branch": "main", "path": "p"},
    )
    assert [(app.id, app.eligibility) for app in apps] == [
        ("app.disabled", frozenset())
    ]
    result = compose(
        apps,
        [],
        [],
        policy=parse_composition_policy(
            {"schemaVersion": 1, "candidates": [], "pins": []}
        ),
    )
    assert result.apps == {Variant.SINGLE: [], Variant.DUAL: []}


@pytest.mark.parametrize("response", [HttpError("offline"), "not json"])
def test_rjny_fetch_and_parse_failures_name_source(response: object) -> None:
    url = "https://raw.githubusercontent.com/r/main/p"
    with pytest.raises(SourceError, match="rjny"):
        rjny.fetch(
            FakeHttp({url: response}), {"repo": "r", "branch": "main", "path": "p"}
        )


def test_bboi_latest_release_retains_both_asset_origins() -> None:
    api = "https://codeberg.org/api/v1/repos/BBoi34/Obtainium-Recomp-Decomp/releases/latest"
    release = json.loads(fixture("codeberg-release.json"))
    single_url, dual_url = (
        asset["browser_download_url"] for asset in release["assets"]
    )
    apps = bboi.fetch(
        FakeHttp(
            {
                api: json.dumps(release),
                single_url: fixture("bboi-single.json"),
                dual_url: fixture("bboi-dual.json"),
            }
        ),
        {
            "codeberg_repo": "BBoi34/Obtainium-Recomp-Decomp",
            "single_asset_pattern": "Decomp-Recomp.V*.json",
            "dual_asset_pattern": "Dual-Screen-Decomp-Recomp.V*.json",
        },
    )
    overlapping_ids = {
        "com.aure.banjorecomp",
        "com.igawa6.harvestmoon64",
        "com.samyost1.zelda3android",
        "com.samyost1.tmcandroid",
    }
    for origin, asset, eligibility, preferred in (
        (
            "bboi-standard-asset",
            "bboi-single.json",
            frozenset(Variant),
            False,
        ),
        (
            "bboi-dual-asset",
            "bboi-dual.json",
            frozenset({Variant.DUAL}),
            True,
        ),
    ):
        expected = {entry["id"]: entry for entry in json.loads(fixture(asset))["apps"]}
        actual = {app.id: app for app in apps if app.origin == origin}
        assert set(actual) == set(expected) == overlapping_ids
        for app_id in overlapping_ids:
            entry, app = expected[app_id], actual[app_id]
            assert app.name == entry["name"]
            assert app.url == entry["url"]
            assert app.categories == tuple(entry["categories"])
            assert app.source_type is SourceType(entry["overrideSource"])
            assert app.additional_settings == json.loads(entry["additionalSettings"])
            assert app.eligibility == eligibility
            assert app.dual_preferred is preferred


def test_bboi_rejects_malformed_settings() -> None:
    document = json.loads(fixture("bboi-single.json"))
    document["apps"][0]["additionalSettings"] = "not json"
    api, asset = (
        "https://codeberg.org/api/v1/repos/a/b/releases/latest",
        "https://asset/s.json",
    )
    release = {
        "assets": [
            {"name": "single.json", "browser_download_url": asset},
            {"name": "dual.json", "browser_download_url": asset},
        ]
    }
    with pytest.raises(SourceError, match="bboi"):
        bboi.fetch(
            FakeHttp({api: json.dumps(release), asset: json.dumps(document)}),
            {
                "codeberg_repo": "a/b",
                "single_asset_pattern": "single.json",
                "dual_asset_pattern": "dual.json",
            },
        )


def test_codm_loads_committed_catalog_and_suppresses_dual_coverage(
    tmp_path: Path,
) -> None:
    higher = [
        App(
            "x",
            "https://www.github.com/SAMYOST1/ZELDA3-ANDROID.git/",
            "x",
            SourceType.GITHUB,
            (),
            Provenance("x", "x"),
            eligibility=frozenset({Variant.DUAL}),
        ),
        App(
            "y",
            "http://github.com/igawa6/DUSKLIGHT",
            "y",
            SourceType.GITHUB,
            (),
            Provenance("x", "x"),
            eligibility=frozenset({Variant.DUAL}),
        ),
        App(
            "z",
            "https://github.com/Josh-Daniels/OpenMW-DS",
            "z",
            SourceType.GITHUB,
            (),
            Provenance("x", "x"),
            eligibility=frozenset({Variant.SINGLE}),
        ),
    ]
    catalog = {
        "apps": [
            {
                "id": "zelda",
                "url": "https://github.com/samyost1/zelda3-android",
                "name": "Zelda",
                "overrideSource": "GitHub",
            },
            {
                "id": "dusk",
                "url": "https://github.com/igawa6/dusklight",
                "name": "Dusk",
                "overrideSource": "GitHub",
            },
            {
                "id": "openmw",
                "url": "https://github.com/Josh-Daniels/OpenMW-DS",
                "name": "OpenMW-DS",
                "overrideSource": "GitHub",
                "additionalSettings": {"includePrereleases": True},
            },
        ]
    }
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog))
    report = IngestionReport()
    apps = codm.fetch(tmp_path, {"catalog": "catalog.json"}, higher, report)
    urls = {app.url for app in apps}
    assert "https://github.com/samyost1/zelda3-android" not in urls
    assert "https://github.com/igawa6/dusklight" not in urls
    assert "https://github.com/Josh-Daniels/OpenMW-DS" in urls
    assert all(
        app.eligibility == frozenset({Variant.DUAL})
        and app.dual_preferred
        and app.origin == "codm-generated"
        and not app.categories
        for app in apps
    )
    assert all(app.source_type is SourceType.GITHUB for app in apps)
    assert (
        next(app for app in apps if app.url.endswith("OpenMW-DS")).name == "OpenMW-DS"
    )
    assert apps[0].additional_settings == {"includePrereleases": True}
    assert len(urls) == 1
    assert report.admitted == [
        {
            "source": "codm2000",
            "url": "https://github.com/Josh-Daniels/OpenMW-DS",
            "kind": "apk",
            "id": "openmw",
        }
    ]


def test_codm_reports_committed_apk_and_tracker_identities(tmp_path: Path) -> None:
    records = [
        {
            "id": "app.apk",
            "url": "https://github.com/owner/app",
            "name": "App",
            "overrideSource": "GitHub",
        },
        {
            "id": "123",
            "url": "https://github.com/owner/mod",
            "name": "Mod",
            "overrideSource": "GitHub",
            "additionalSettings": {"trackOnly": True},
        },
    ]
    (tmp_path / "catalog.json").write_text(json.dumps({"apps": records}))
    report = IngestionReport()
    codm.fetch(tmp_path, {"catalog": "catalog.json"}, [], report)
    assert [(item["kind"], item["id"]) for item in report.admitted] == [
        ("apk", "app.apk"),
        ("track-only", "123"),
    ]


def test_codm_rejects_duplicate_ids(tmp_path: Path) -> None:
    records = [
        {
            "id": "same",
            "url": f"https://github.com/owner/repo{i}",
            "name": f"Repo {i}",
            "overrideSource": "GitHub",
        }
        for i in range(2)
    ]
    (tmp_path / "catalog.json").write_text(json.dumps({"apps": records}))
    with pytest.raises(SourceError, match="duplicate id.*repo0.*repo1"):
        codm.fetch(tmp_path, {"catalog": "catalog.json"}, [])


PROJECT = "https://github.com/owner/project"


def rjny_candidate(eligibility: frozenset[Variant]) -> App:
    return App(
        "app.standard",
        "https://www.github.com/owner/project.git/",
        "Standard",
        SourceType.GITHUB,
        (),
        Provenance("rjny", "catalog"),
        eligibility=eligibility,
        origin="rjny-catalog",
    )


def ingest_over_codm_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, higher: list[App]
) -> list[App]:
    """Ingest stubbed higher-precedence candidates over one codm2000 entry."""
    entry = {
        "id": "app.generated",
        "url": PROJECT,
        "name": "project",
        "overrideSource": "GitHub",
    }
    (tmp_path / "codm.json").write_text(json.dumps({"apps": [entry]}))
    monkeypatch.setattr(rjny, "fetch", lambda *_args: higher)
    monkeypatch.setattr(bboi, "fetch", lambda *_args: [])
    monkeypatch.setattr(extras, "fetch", lambda *_args: [])
    return ingest_all(
        tmp_path,
        FakeHttp({}),
        {"rjny": {}, "bboi": {}, "codm": {"catalog": "codm.json"}},
        [],
        IngestionReport(),
    )


def test_ingestion_preserves_candidate_ids_and_unassigned_families(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    higher = rjny_candidate(frozenset({Variant.SINGLE}))
    result = ingest_over_codm_entry(tmp_path, monkeypatch, [higher])
    assert [(app.id, app.family) for app in result] == [
        ("app.standard", None),
        ("app.generated", None),
    ]


@pytest.mark.parametrize(
    ("eligibility", "suppressed"),
    [
        (frozenset(Variant), True),
        (frozenset({Variant.DUAL}), True),
        (frozenset({Variant.SINGLE}), False),
    ],
    ids=["both-exports", "dual-export-only", "left-out-of-dual"],
)
def test_codm_suppression_follows_source_dual_eligibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    eligibility: frozenset[Variant],
    suppressed: bool,
) -> None:
    result = ingest_over_codm_entry(
        tmp_path, monkeypatch, [rjny_candidate(eligibility)]
    )
    assert ("app.generated" not in {app.id for app in result}) is suppressed


@pytest.mark.parametrize(
    ("selector_kind", "message"),
    [("rule", "matched no candidate"), ("pin", "missing or ambiguous")],
)
def test_policy_naming_a_suppressed_codm_entry_fails_in_composition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selector_kind: str,
    message: str,
) -> None:
    result = ingest_over_codm_entry(
        tmp_path, monkeypatch, [rjny_candidate(frozenset(Variant))]
    )
    required = {
        "match": {
            "source": "codm2000",
            "origin": "codm-generated",
            "id": "app.generated",
            "url": PROJECT,
        },
        "rationale": "Required generated candidate.",
    }
    pin = {**required, "family": "package:app.generated", "variant": "dual"}
    policy = parse_composition_policy(
        {
            "schemaVersion": 1,
            "candidates": [required] if selector_kind == "rule" else [],
            "pins": [pin] if selector_kind == "pin" else [],
        }
    )
    with pytest.raises(CompositionError, match=message):
        compose(result, [], [], policy=policy)


@pytest.mark.parametrize("missing", ["id", "url", "name"])
def test_extras_requires_named_fields(missing: str) -> None:
    entry: dict[str, Any] = {
        "id": "app.id",
        "url": "https://example.test/app",
        "name": "Example",
    }
    del entry[missing]
    with pytest.raises(SourceError, match="extras.*(Example|app.id|entry 1)"):
        extras.fetch([entry])


def test_extras_entry_missing_every_name_source_is_identified_by_index() -> None:
    with pytest.raises(SourceError, match=r"extras: entry 'entry 1' is missing id"):
        extras.fetch([{}])


def test_extras_dual_screen_flag_decides_eligibility_and_preference() -> None:
    apps = extras.fetch(
        [
            {"id": "a", "url": "https://github.com/o/r", "name": "GitHub"},
            {
                "id": "b",
                "url": "https://elsewhere/app",
                "name": "Dual",
                "dualScreen": True,
            },
            {
                "id": "c",
                "url": "https://elsewhere/other",
                "name": "Explicit",
                "dualScreen": False,
            },
        ]
    )
    assert {
        (app.id, app.eligibility, app.dual_preferred, app.source_type) for app in apps
    } == {
        ("a", frozenset(Variant), False, SourceType.GITHUB),
        ("b", frozenset({Variant.DUAL}), True, SourceType.HTML),
        ("c", frozenset(Variant), False, SourceType.HTML),
    }


@pytest.mark.parametrize("value", [1, "true", None])
def test_extras_rejects_non_boolean_dual_screen(value: object) -> None:
    with pytest.raises(SourceError, match="extras.*Typed.*dualScreen must be boolean"):
        extras.fetch(
            [{"id": "b", "url": "https://x", "name": "Typed", "dualScreen": value}]
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("variants", ["single", "dual"]),
        ("variants", ["dual"]),
        ("dualPreferred", True),
        ("dualPreferred", False),
    ],
)
def test_extras_rejects_retired_fields_naming_entry_and_field(
    field: str, value: object
) -> None:
    with pytest.raises(SourceError, match=f"extras.*Retired.*unknown field '{field}'"):
        extras.fetch([{"id": "r", "url": "https://x", "name": "Retired", field: value}])


def test_extras_composition_fields_stay_out_of_the_rendered_record() -> None:
    [app] = extras.fetch(
        [
            {
                "id": "d",
                "url": "https://x",
                "name": "Preferred",
                "dualScreen": True,
                "family": "app:ignored",
                "origin": "ignored",
                "originalId": "ignored",
                "provenance": {"source": "ignored"},
            }
        ]
    )
    assert app.dual_preferred
    assert not app.raw.keys() & {
        "dualScreen",
        "family",
        "origin",
        "originalId",
        "provenance",
    }
    [rendered] = json.loads(
        render([ComposedApp(f"package:{app.id}", _import_data(app))])
    )["apps"]
    assert "dualScreen" not in rendered
    assert "dualScreen" not in json.loads(rendered["additionalSettings"])


def test_additional_settings_string_must_decode_to_object() -> None:
    with pytest.raises(SourceError, match="extras.*Settings"):
        extras.fetch(
            [
                {
                    "id": "x",
                    "url": "https://x",
                    "name": "Settings",
                    "additionalSettings": "[]",
                }
            ]
        )


@pytest.mark.parametrize("failure", ["unreachable", "malformed"])
def test_build_ingestion_failure_leaves_existing_outputs_untouched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    single, dual = dist / "single-screen.json", dist / "dual-screen.json"
    single.write_text("old single", encoding="utf-8")
    dual.write_text("old dual", encoding="utf-8")
    shutil.copytree(Path(__file__).parents[1] / "config", tmp_path / "config")
    (tmp_path / "config/composition.json").write_text(
        '{"schemaVersion":1,"candidates":[],"pins":[]}', encoding="utf-8"
    )
    before = {path.name: path.read_bytes() for path in dist.iterdir()}
    monkeypatch.chdir(tmp_path)
    requests: list[str] = []

    def transport(
        _client: HttpClient, request: Request, timeout: float
    ) -> HttpResponse:
        requests.append(request.full_url)
        if failure == "unreachable":
            raise URLError("source unreachable")
        return HttpResponse(request.full_url, 200, Message(), b"not json")

    monkeypatch.setattr(HttpClient, "_urllib_transport", transport)
    assert cli.main(["build"]) == 1
    assert "rjny" in capsys.readouterr().err
    assert requests and set(requests) == {
        "https://raw.githubusercontent.com/RJNY/Obtainium-Emulation-Pack/main/src/applications.json"
    }
    assert {path.name: path.read_bytes() for path in dist.iterdir()} == before
    assert single.read_text(encoding="utf-8") == "old single"
    assert dual.read_text(encoding="utf-8") == "old dual"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com", SourceType.HTML),
        ("https://github.com/owner", SourceType.HTML),
        ("https://github.com/topics/android", SourceType.HTML),
        ("https://github.com/orgs/example/repositories", SourceType.HTML),
        ("https://github.com/settings/profile", SourceType.HTML),
        ("https://github.com/features/actions", SourceType.HTML),
        ("https://github.com/codespaces/new", SourceType.HTML),
        ("https://github.com/stars/example", SourceType.HTML),
        ("https://github.com/owner/repo", SourceType.GITHUB),
        ("https://www.github.com/owner/repo/releases/latest", SourceType.GITHUB),
        ("https://github.com/owner/repo/tree/main", SourceType.GITHUB),
    ],
)
def test_extras_derives_github_only_for_repository_urls(
    url: str, expected: SourceType
) -> None:
    apps = extras.fetch([{"id": "app.test", "url": url, "name": "Example"}])
    assert {app.source_type for app in apps} == {expected}


@pytest.mark.parametrize("declared", [SourceType.GITHUB, SourceType.HTML])
def test_upstream_declared_source_type_is_preserved(declared: SourceType) -> None:
    url = "https://raw.githubusercontent.com/r/main/p"
    record = {
        "id": "app.test",
        "name": "Example",
        "url": "https://github.com/owner/repo",
        "overrideSource": declared.value,
    }
    apps = rjny.fetch(
        FakeHttp({url: json.dumps({"apps": [record]})}),
        {"repo": "r", "branch": "main", "path": "p"},
    )
    assert len(apps) == 1
    assert all(app.source_type is declared for app in apps)


@pytest.mark.parametrize("body", ["null", "[]", '{"apps":"bad"}'])
def test_codm_malformed_catalog_aborts_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    before = {
        name: (name + " previous").encode()
        for name in ("single-screen.json", "dual-screen.json")
    }
    for name, content in before.items():
        (dist / name).write_bytes(content)

    def ingest(root: Path, _inputs: object, report: IngestionReport) -> list[App]:
        (root / "catalog.json").write_text(body)
        return codm.fetch(root, {"catalog": "catalog.json"}, [])

    shutil.copytree(Path(__file__).parents[1] / "config", tmp_path / "config")
    monkeypatch.setattr(cli, "_ingest_for_build", ingest)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["build"]) == 1
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert "codm" in report["error"]
    assert {path.name: path.read_bytes() for path in dist.iterdir()} == before


def test_codm_missing_catalog_names_source(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="codm"):
        codm.fetch(tmp_path, {"catalog": "missing.json"}, [])


def test_explicit_null_extra_source_is_not_inferred():
    with pytest.raises(SourceError, match="Example.*None"):
        extras.fetch(
            [
                {
                    "id": "com.example.app",
                    "name": "Example",
                    "url": "https://github.com/a/b",
                    "overrideSource": None,
                }
            ]
        )


def test_dual_screen_extra_wins_dual_over_a_lower_source_dual_screen_build() -> None:
    [extra] = extras.fetch(
        [
            {
                "id": "com.example.companion",
                "url": "https://github.com/example/companion",
                "name": "Companion",
                "dualScreen": True,
            }
        ]
    )
    fork = App(
        "com.example.fork",
        "https://github.com/fork/companion",
        "Fork",
        SourceType.GITHUB,
        (),
        Provenance("bboi", "asset"),
        frozenset({Variant.DUAL}),
        origin="bboi-dual-asset",
    )
    rules = [
        {
            "match": {"source": source, "origin": origin, "id": app.id, "url": app.url},
            "family": "app:companion",
            "rationale": "Builds of one companion app.",
        }
        for source, origin, app in (
            ("extras", "extras", extra),
            ("bboi", "bboi-dual-asset", fork),
        )
    ]
    policy = parse_composition_policy(
        {"schemaVersion": 1, "candidates": rules, "pins": []}
    )
    result = compose([extra, fork], [], [], policy=policy)
    assert result.apps[Variant.SINGLE] == []
    [selection] = result.report.selections
    assert (selection.variant, selection.effective_id, selection.reason) == (
        Variant.DUAL,
        "com.example.companion",
        "dual-preferred",
    )
