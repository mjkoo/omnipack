from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request

import pytest

from omnipack import cli
from omnipack.composition_policy import parse_composition_policy
from omnipack.http import HttpClient, HttpResponse
from omnipack.merge import _import_data, compose
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
    quiver,
    rjny,
)
from omnipack.urls import gitlab_project_path, normalize_project_url

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


def test_rjny_cemu_builds_at_two_urls_form_two_url_families() -> None:
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
        variant: (item.family, item.url, item.reason)
        for variant, item in selections.items()
    } == {
        Variant.SINGLE: (
            "github.com/ssimco/cemu",
            "https://github.com/SSimco/Cemu",
            "source",
        ),
        Variant.DUAL: (
            "github.com/sapphirerhodonite/cemu",
            "https://github.com/sapphirerhodonite/cemu",
            "dual-preferred",
        ),
    }
    assert selections[Variant.DUAL].considered == ()


def test_rjny_build_kept_out_of_dual_leaves_dual_to_its_family_s_dual_build() -> None:
    url = "https://raw.githubusercontent.com/fixture/rjny/main/apps.json"
    project = "https://github.com/example/app"

    def record(package_id: str, meta: dict[str, object]) -> dict[str, object]:
        return {
            "id": package_id,
            "url": project,
            "name": "App",
            "overrideSource": "GitHub",
            "categories": ["Emulator"],
            "additionalSettings": {},
            "meta": meta,
        }

    catalog = {
        "apps": [
            record("org.example.app", {"includeInDualScreen": False}),
            record("org.example.app.dual", {"includeInStandard": False}),
        ]
    }
    apps = rjny.fetch(
        FakeHttp({url: json.dumps(catalog)}),
        {"repo": "fixture/rjny", "branch": "main", "path": "apps.json"},
    )
    assert {(app.id, app.eligibility) for app in apps} == {
        ("org.example.app", frozenset({Variant.SINGLE})),
        ("org.example.app.dual", frozenset({Variant.DUAL})),
    }
    result = compose(
        apps,
        [],
        [],
        policy=parse_composition_policy(
            {"schemaVersion": 1, "candidates": [], "pins": []}
        ),
    )
    assert {
        (item.variant, item.family, item.id) for item in result.report.selections
    } == {
        (Variant.SINGLE, "github.com/example/app", "org.example.app"),
        (Variant.DUAL, "github.com/example/app", "org.example.app.dual"),
    }


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
    for variant, export_name in (
        (Variant.SINGLE, "rjny-single.json"),
        (Variant.DUAL, "rjny-dual.json"),
    ):
        expected = json.loads(fixture(export_name))["apps"]
        eligible = [app for app in apps if variant in app.eligibility]
        assert len(eligible) == len(expected)
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


@pytest.mark.parametrize(
    "url",
    [
        "http://gitlab.com/a/b",
        "https://example.com/a/b",
        "https://gitlab.com/one",
        "https://user@gitlab.com/a/b",
        "https://user:password@gitlab.com/a/b",
        "https://www.gitlab.com/a/b",
        "https://gitlab.com:443/a/b",
        "https://gitlab.com/a/b?query=1",
        "https://gitlab.com/a/b#fragment",
        "https://gitlab.com/a/-/b",
        "https://gitlab.com/" + "/".join(f"Group{i}" for i in range(22)),
        "https://gitlab.com:invalid/a/b",
    ],
)
def test_explicit_gitlab_extra_rejects_urls_outside_public_boundary(url: str) -> None:
    with pytest.raises(SourceError) as error:
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
    assert "entry 'Bad'" in str(error.value)
    assert "invalid GitLab URL" in str(error.value)
    assert repr(url) in str(error.value)


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


def _record_with(field: str, value: object) -> dict[str, object]:
    return {
        "id": "app.entry",
        "name": "Entry",
        "url": "https://github.com/owner/entry",
        "overrideSource": "GitHub",
        field: value,
    }


def _fetch_rjny(records: list[dict[str, object]]) -> list[App]:
    url = "https://raw.githubusercontent.com/r/main/p"
    return rjny.fetch(
        FakeHttp({url: json.dumps({"apps": records})}),
        {"repo": "r", "branch": "main", "path": "p"},
    )


def _fetch_bboi(
    standard: list[dict[str, object]], dual: list[dict[str, object]]
) -> list[App]:
    api = "https://codeberg.org/api/v1/repos/a/b/releases/latest"
    single_url, dual_url = "https://asset/single.json", "https://asset/dual.json"
    release = {
        "assets": [
            {"name": "single.json", "browser_download_url": single_url},
            {"name": "dual.json", "browser_download_url": dual_url},
        ]
    }
    return bboi.fetch(
        FakeHttp(
            {
                api: json.dumps(release),
                single_url: json.dumps({"apps": standard}),
                dual_url: json.dumps({"apps": dual}),
            }
        ),
        {
            "codeberg_repo": "a/b",
            "single_asset_pattern": "single.json",
            "dual_asset_pattern": "dual.json",
        },
    )


def _fetch_codm(tmp_path: Path, records: list[dict[str, object]]) -> list[App]:
    (tmp_path / "catalog.json").write_text(json.dumps({"apps": records}))
    return codm.fetch(tmp_path, {"catalog": "catalog.json"})


@pytest.mark.parametrize("field", ["family", "variant"])
@pytest.mark.parametrize("value", ["assigned", None], ids=["assigned", "null"])
@pytest.mark.parametrize(
    ("source", "fetch"),
    [
        pytest.param("rjny", lambda record, _: _fetch_rjny([record]), id="rjny"),
        pytest.param(
            "bboi", lambda record, _: _fetch_bboi([record], []), id="bboi-standard"
        ),
        pytest.param(
            "bboi", lambda record, _: _fetch_bboi([], [record]), id="bboi-dual"
        ),
        pytest.param(
            "codm2000",
            lambda record, tmp_path: _fetch_codm(tmp_path, [record]),
            id="codm2000",
        ),
        pytest.param("extras", lambda record, _: extras.fetch([record]), id="extras"),
    ],
)
def test_source_record_rejects_composition_policy_fields(
    source: str,
    fetch: Callable[[dict[str, object], Path], list[App]],
    field: str,
    value: object,
    tmp_path: Path,
) -> None:
    with pytest.raises(SourceError) as excinfo:
        fetch(_record_with(field, value), tmp_path)
    message = str(excinfo.value)
    assert message.startswith(f"{source}: entry 'Entry' field {field!r} ")
    assert "cannot come from a source record" in message
    assert (
        "composition policy in config/composition.json owns app families "
        "and per-pack selection"
    ) in message
    # Policy cannot override a source record, so nothing points there as a fix.
    assert not any(
        verb in message.lower() for verb in ("edit", "update", "change", "add ", "fix")
    )


@pytest.mark.parametrize(
    "flags",
    [
        {"includeInStandard": True},
        {"includeInDualScreen": True},
        {"includeInStandard": True, "includeInDualScreen": True},
        {"includeInStandard": False},
        {"includeInDualScreen": False},
    ],
)
def test_rjny_entry_excluded_from_export_is_dropped_whatever_its_other_flags(
    flags: dict[str, bool],
) -> None:
    excluded = _record_with("meta", {"excludeFromExport": True, **flags})
    kept = {**_record_with("meta", {}), "id": "app.kept"}
    assert [app.id for app in _fetch_rjny([excluded, kept])] == ["app.kept"]


def test_rjny_excluded_record_is_not_guarded_but_neither_pack_record_is() -> None:
    excluded = _record_with("family", None)
    excluded["meta"] = {"excludeFromExport": True}
    assert _fetch_rjny([excluded]) == []

    neither_pack = _record_with("family", None)
    neither_pack["meta"] = {
        "includeInStandard": False,
        "includeInDualScreen": False,
    }
    with pytest.raises(SourceError, match="^rjny: entry 'Entry' field 'family' "):
        _fetch_rjny([neither_pack])


def test_unmodeled_fields_pass_through_upstream_and_extras() -> None:
    upstream = _record_with("origin", "upstream-value")
    upstream["dualScreen"] = {"unknown": True}
    [upstream_app] = _fetch_rjny([upstream])
    [extra_app] = extras.fetch(
        [
            {
                "id": "app.extra",
                "name": "Extra",
                "url": "https://example.test/extra",
                "origin": "extra-value",
                "dualScreen": True,
            }
        ]
    )
    assert upstream_app.raw == {
        "origin": "upstream-value",
        "dualScreen": {"unknown": True},
    }
    assert extra_app.raw == {"origin": "extra-value"}
    assert extra_app.eligibility == frozenset({Variant.DUAL})
    assert extra_app.dual_preferred
    rendered = {
        entry["id"]: entry
        for entry in json.loads(
            render(
                [
                    ComposedApp("example.test/entry", _import_data(upstream_app)),
                    ComposedApp("example.test/extra", _import_data(extra_app)),
                ]
            )
        )["apps"]
    }
    assert rendered["app.entry"]["origin"] == "upstream-value"
    assert rendered["app.entry"]["dualScreen"] == {"unknown": True}
    assert rendered["app.extra"]["origin"] == "extra-value"
    assert "dualScreen" not in rendered["app.extra"]


def test_package_id_field_is_ingested_and_rendered_unchanged() -> None:
    [upstream_app] = _fetch_rjny([_record_with("packageId", "org.example.declared")])
    assert upstream_app.raw == {"packageId": "org.example.declared"}
    [rendered] = json.loads(
        render([ComposedApp("example.test/entry", _import_data(upstream_app))])
    )["apps"]
    assert rendered["packageId"] == "org.example.declared"
    assert rendered["id"] == upstream_app.id


def _fetch_quiver(tmp_path: Path, records: list[dict[str, object]]) -> list[App]:
    (tmp_path / "quiver.json").write_text(json.dumps({"apps": records}))
    return quiver.fetch(tmp_path, {"catalog": "quiver.json"})


EVERY_SOURCE_FETCH = [
    pytest.param(lambda record, _: _fetch_rjny([record]), id="rjny"),
    pytest.param(lambda record, _: _fetch_bboi([record], []), id="bboi-standard"),
    pytest.param(lambda record, _: _fetch_bboi([], [record]), id="bboi-dual"),
    pytest.param(lambda record, path: _fetch_codm(path, [record]), id="codm2000"),
    pytest.param(lambda record, path: _fetch_quiver(path, [record]), id="quiver"),
    pytest.param(lambda record, _: extras.fetch([record]), id="extras"),
]


@pytest.mark.parametrize("fetch", EVERY_SOURCE_FETCH)
def test_catalog_metadata_is_dropped_but_unmodeled_fields_render(
    fetch: Callable[[dict[str, object], Path], list[App]], tmp_path: Path
) -> None:
    record: dict[str, object] = {
        "id": "org.example.entry",
        "name": "Entry",
        "url": "https://github.com/owner/entry",
        "overrideSource": "GitHub",
        "meta": {"presentation": "catalog-only"},
        "unmodeled": {"retained": True},
    }
    [app] = fetch(record, tmp_path)
    assert app.raw == {"unmodeled": {"retained": True}}

    [rendered] = json.loads(
        render([ComposedApp(normalize_project_url(app.url), _import_data(app))])
    )["apps"]
    assert "meta" not in rendered
    assert rendered["unmodeled"] == {"retained": True}


def test_codm_declared_source_type_wins_and_omitted_type_is_derived(
    tmp_path: Path,
) -> None:
    declared = _record_with("ordinary", True)
    declared["overrideSource"] = "HTML"
    inferred = {**declared, "id": "app.inferred", "name": "Inferred"}
    del inferred["overrideSource"]

    apps = _fetch_codm(tmp_path, [declared, inferred])

    assert [(app.id, app.source_type) for app in apps] == [
        ("app.entry", SourceType.HTML),
        ("app.inferred", SourceType.GITHUB),
    ]


@pytest.mark.parametrize(
    ("source", "fetch"),
    [
        pytest.param("rjny", lambda record: _fetch_rjny([record]), id="rjny"),
        pytest.param("bboi", lambda record: _fetch_bboi([record], []), id="bboi34"),
    ],
)
def test_upstream_record_without_declared_source_type_is_rejected(
    source: str, fetch: Callable[[dict[str, object]], list[App]]
) -> None:
    record = _record_with("ordinary", True)
    del record["overrideSource"]

    with pytest.raises(SourceError) as excinfo:
        fetch(record)

    assert str(excinfo.value) == (
        f"{source}: entry 'Entry' has unsupported source type None"
    )


@pytest.mark.parametrize(
    ("source", "fetch"),
    [
        pytest.param(
            "bboi",
            lambda tmp_path: bboi.fetch(
                FakeHttp({}),
                {
                    "codeberg_repo": "",
                    "single_asset_pattern": "single.json",
                    "dual_asset_pattern": "dual.json",
                },
            ),
            id="bboi34",
        ),
        pytest.param(
            "codm",
            lambda tmp_path: codm.fetch(tmp_path, {"catalog": ""}),
            id="codm2000",
        ),
    ],
)
def test_empty_configured_location_names_source(
    source: str, fetch: Callable[[Path], list[App]], tmp_path: Path
) -> None:
    with pytest.raises(SourceError) as excinfo:
        fetch(tmp_path)

    assert str(excinfo.value) == f"{source}: configured location is empty"


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


def test_codm_loads_every_committed_entry_and_reports_admission(
    tmp_path: Path,
) -> None:
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
    apps = codm.fetch(tmp_path, {"catalog": "catalog.json"}, report)
    urls = {app.url for app in apps}
    assert "https://github.com/samyost1/zelda3-android" in urls
    assert "https://github.com/igawa6/dusklight" in urls
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
    assert apps[2].additional_settings == {"includePrereleases": True}
    assert len(urls) == 3
    assert report.admitted == [
        {"source": "codm2000", "url": record["url"], "kind": "apk", "id": record["id"]}
        for record in catalog["apps"]
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
    codm.fetch(tmp_path, {"catalog": "catalog.json"}, report)
    assert [(item["kind"], item["id"]) for item in report.admitted] == [
        ("apk", "app.apk"),
        ("track-only", "123"),
    ]


def test_build_keeps_tracking_resource_beside_the_app_it_extends(
    tmp_path: Path,
) -> None:
    [app] = extras.fetch(
        [
            {
                "id": "app.host",
                "url": "https://github.com/owner/host",
                "name": "Host",
            }
        ]
    )
    description = "Install this resource manually through Host."
    [tracker] = _fetch_codm(
        tmp_path,
        [
            {
                "id": "resource.release-feed",
                "url": "https://github.com/owner/resource",
                "name": "Resource",
                "additionalSettings": {
                    "trackOnly": True,
                    "about": description,
                },
            }
        ],
    )
    result = compose(
        [app, tracker],
        [],
        [],
        policy=parse_composition_policy(
            {"schemaVersion": 1, "candidates": [], "pins": []}
        ),
    )

    rendered = {
        variant: {
            entry["id"]: entry
            for entry in json.loads(render(result.apps[variant]))["apps"]
        }
        for variant in Variant
    }
    assert set(rendered[Variant.SINGLE]) == {"app.host"}
    assert set(rendered[Variant.DUAL]) == {
        "app.host",
        "resource.release-feed",
    }
    resource_settings = json.loads(
        rendered[Variant.DUAL]["resource.release-feed"]["additionalSettings"]
    )
    assert resource_settings["trackOnly"] is True
    assert resource_settings["about"] == description


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
    with pytest.raises(SourceError, match="duplicate id.*same.*repo0.*repo1"):
        codm.fetch(tmp_path, {"catalog": "catalog.json"})


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
    (tmp_path / "quiver.json").write_text(json.dumps({"apps": []}))
    monkeypatch.setattr(rjny, "fetch", lambda *_args: higher)
    monkeypatch.setattr(bboi, "fetch", lambda *_args: [])
    monkeypatch.setattr(extras, "fetch", lambda *_args: [])
    return ingest_all(
        tmp_path,
        FakeHttp({}),
        {
            "rjny": {},
            "bboi": {},
            "codm": {"catalog": "codm.json"},
            "quiver": {"catalog": "quiver.json"},
        },
        [],
        IngestionReport(),
    )


def test_codm_url_overlap_keeps_both_candidates_and_composition_selects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = ingest_over_codm_entry(
        tmp_path, monkeypatch, [rjny_candidate(frozenset(Variant))]
    )
    assert [app.id for app in candidates] == ["app.standard", "app.generated"]
    result = compose(
        candidates,
        [],
        [],
        policy=parse_composition_policy(
            {"schemaVersion": 1, "candidates": [], "pins": []}
        ),
    )
    # One project URL forms one family, so the dual-screen build replaces the
    # baseline build in dual.
    assert {app.data["id"] for app in result.apps[Variant.DUAL]} == {"app.generated"}
    assert {app.data["id"] for app in result.apps[Variant.SINGLE]} == {"app.standard"}


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
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["status"] == "failed"
    assert report["stage"] == "ingestion"
    assert report["offlineVerification"] == {
        "status": "not-run",
        "findings": [],
        "nonfatalFindings": [],
    }
    assert report["changes"] is None
    assert "rjny" in report["error"]
    assert (
        "failed after" if failure == "unreachable" else "Expecting value"
    ) in report["error"]


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
        ("https://gitlab.com/a/b", SourceType.HTML),
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
def test_codm_malformed_catalog_names_source(tmp_path: Path, body: str) -> None:
    (tmp_path / "catalog.json").write_text(body)
    with pytest.raises(SourceError, match="codm"):
        codm.fetch(tmp_path, {"catalog": "catalog.json"})


def test_codm_missing_catalog_names_source(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="codm"):
        codm.fetch(tmp_path, {"catalog": "missing.json"})


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
    assert (selection.variant, selection.id, selection.reason) == (
        Variant.DUAL,
        "com.example.companion",
        "dual-preferred",
    )


@pytest.mark.parametrize("prefix", ["https://gitlab.com", "HTTPS://GitLab.com"])
@pytest.mark.parametrize(
    ("path", "project_path"),
    [
        ("Group/Project", "Group/Project"),
        ("/Group//Sub%47roup/Project/", "Group/Sub%47roup/Project"),
    ],
)
def test_gitlab_acceptance_preserves_path_case_and_encoding(
    prefix: str, path: str, project_path: str
) -> None:
    url = f"{prefix}/{path}"
    [app] = extras.fetch(
        [
            {
                "id": "com.example.app",
                "name": "Example",
                "url": url,
                "overrideSource": "GitLab",
            }
        ]
    )
    assert app.url == url
    assert app.source_type is SourceType.GITLAB
    assert gitlab_project_path(url) == project_path


@pytest.mark.parametrize("pattern", ["single*.json", "dual*.json"])
@pytest.mark.parametrize("count", [0, 2])
def test_bboi_requires_exactly_one_asset_per_configured_pattern(
    pattern: str, count: int
) -> None:
    api = "https://codeberg.org/api/v1/repos/a/b/releases/latest"
    assets = [
        {
            "name": f"{kind}{i}.json",
            "browser_download_url": f"https://asset/{kind}{i}.json",
        }
        for kind in ("single", "dual")
        for i in range(count if pattern.startswith(kind) else 1)
    ]
    http = FakeHttp({api: json.dumps({"assets": assets})})
    with pytest.raises(SourceError) as error:
        bboi.fetch(
            http,
            {
                "codeberg_repo": "a/b",
                "single_asset_pattern": "single*.json",
                "dual_asset_pattern": "dual*.json",
            },
        )
    assert (
        str(error.value)
        == f"bboi: expected exactly one release asset matching {pattern!r}"
    )
    assert http.urls == [api]


@pytest.mark.parametrize("source", ["rjny", "bboi"])
def test_upstream_duplicate_package_ids_survive_ingestion(source: str) -> None:
    records = [
        _record_with("url", f"https://github.com/owner/repo{i}") for i in range(2)
    ]
    apps = _fetch_rjny(records) if source == "rjny" else _fetch_bboi(records, [])
    assert [(app.id, app.url) for app in apps] == [
        (record["id"], record["url"]) for record in records
    ]


def test_bboi_reads_the_current_latest_release_on_every_run() -> None:
    api = "https://codeberg.org/api/v1/repos/a/b/releases/latest"
    http = FakeHttp({})
    config = {
        "codeberg_repo": "a/b",
        "single_asset_pattern": "single*.json",
        "dual_asset_pattern": "dual*.json",
    }
    for version in (9, 1):
        assets = [
            {
                "name": f"{kind}{version}.json",
                "browser_download_url": f"https://asset/{kind}{version}.json",
            }
            for kind in ("single", "dual")
        ]
        http.responses[api] = json.dumps({"assets": assets})
        for asset in assets:
            http.responses[asset["browser_download_url"]] = json.dumps(
                {"apps": [_record_with("name", f"Release {version}")]}
            )
        assert [app.name for app in bboi.fetch(http, config)] == [
            f"Release {version}"
        ] * 2
    assert http.urls == [
        api,
        "https://asset/single9.json",
        "https://asset/dual9.json",
        api,
        "https://asset/single1.json",
        "https://asset/dual1.json",
    ]
