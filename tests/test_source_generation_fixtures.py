from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from omnipack.composition_policy import parse_composition_policy
from omnipack.merge import CompositionResult, compose
from omnipack.model import App, Variant
from omnipack.package_id import _is_valid_package_id
from omnipack.render import render
from omnipack.source_generation import _render_catalog
from omnipack.sources import bboi, codm, rjny
from omnipack.sources.common import normalize_record
from omnipack.sources.extras import fetch as fetch_extras
from omnipack.urls import normalize_project_url
from tests.test_sources import FakeHttp

ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures/source-generation/codm"
CAPTURED = ROOT / "tests/fixtures/reconciliation"
PRE_MIGRATION = FIXTURES / "pre-migration-config"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def captured_higher(extras: list[dict[str, Any]] | None = None) -> list[App]:
    """Ingest the captured upstream catalogs with the frozen or the given extras."""
    sources = load_json(PRE_MIGRATION / "sources.json")
    release = load_json(CAPTURED / "bboi-release.json")
    standard_url, dual_url = (
        asset["browser_download_url"] for asset in release["assets"]
    )
    bboi_api = (
        "https://codeberg.org/api/v1/repos/"
        f"{sources['bboi']['codeberg_repo']}/releases/latest"
    )
    rjny_url = (
        f"https://raw.githubusercontent.com/{sources['rjny']['repo']}/"
        f"{sources['rjny']['branch']}/{sources['rjny']['path']}"
    )
    http = FakeHttp(
        {
            bboi_api: json.dumps(release),
            standard_url: (CAPTURED / "bboi-standard.json").read_text(),
            dual_url: (CAPTURED / "bboi-dual.json").read_text(),
            rjny_url: (CAPTURED / "rjny.json").read_text(),
            sources["codm"]["readme_url"]: (
                ROOT / "tests/fixtures/codm-readme.md"
            ).read_text(),
        }
    )
    return [
        *rjny.fetch(http, sources["rjny"]),
        *bboi.fetch(http, sources["bboi"]),
        *fetch_extras(
            load_json(PRE_MIGRATION / "extras.json") if extras is None else extras
        ),
    ]


def captured_pipeline() -> tuple[list[App], list[App]]:
    higher = captured_higher()
    covered = {
        normalize_project_url(app.url)
        for app in higher
        if Variant.DUAL in app.eligibility
    }
    generated = [
        normalize_record(
            record,
            source="codm2000",
            derive_type=True,
            eligibility=frozenset({Variant.DUAL}),
            origin="codm-generated",
        )
        for record in load_json(PRE_MIGRATION / "admitted-catalog.json")["apps"]
        if normalize_project_url(record["url"]) not in covered
    ]
    return higher, generated


def compose_captured_baseline() -> CompositionResult:
    higher, generated = captured_pipeline()
    return compose(
        [*higher, *generated],
        load_json(PRE_MIGRATION / "deny.json"),
        load_json(PRE_MIGRATION / "overlay.json"),
        policy=parse_composition_policy(load_json(PRE_MIGRATION / "composition.json")),
    )


def test_current_captured_baseline_reproduces_exact_exports_and_family_winners() -> (
    None
):
    index = load_json(FIXTURES / "baseline/index.json")
    result = compose_captured_baseline()

    for variant in Variant:
        output = render(result.apps[variant]).encode()
        expected = next(
            item for item in index["outputs"] if item["variant"] == variant.value
        )
        assert output == (FIXTURES / "baseline" / expected["file"]).read_bytes()
        assert len(result.apps[variant]) == expected["appCount"]
        assert hashlib.sha256(output).hexdigest() == expected["sha256"]

    derived_winners: dict[str, dict[str, str]] = {}
    for selection in result.report.selections:
        if selection.family in index["familyWinners"]:
            derived_winners.setdefault(selection.family, {})[
                selection.variant.value
            ] = normalize_project_url(selection.url)
    assert derived_winners == index["familyWinners"]


def _committed_codm_catalog() -> dict[str, Any]:
    return load_json(ROOT / "config/catalogs/codm.json")


ADDED_ID = "com.example.testinvariant.added"


def _catalog_with_one_project_added_and_one_removed() -> dict[str, Any]:
    """Vary the committed catalog the way a source proposal might.

    The removed entry is the last one composition does not depend on: no
    candidate rule, pin or overlay record targets it, and no higher-source
    candidate or identity correction carries its package ID, so it cannot be a
    family's only dual-screen build. When every entry is depended on, nothing
    is removed.
    """
    apps = list(_committed_codm_catalog()["apps"])
    policy = load_json(ROOT / "config/composition.json")
    targeted = {
        (rule["match"]["id"], normalize_project_url(rule["match"]["url"]))
        for rule in [*policy["candidates"], *policy["pins"]]
        if rule["match"]["source"] == "codm2000"
    } | {
        (record["id"], normalize_project_url(record["url"]))
        for record in load_json(ROOT / "config/overlay.json")
    }
    higher, _ = captured_pipeline()
    carried = {app.id for app in higher} | {
        rule["packageId"] for rule in policy["candidates"] if "packageId" in rule
    }
    removable = [
        app
        for app in apps
        if (app["id"], normalize_project_url(app["url"])) not in targeted
        and app["id"] not in carried
    ]
    if removable:
        apps.remove(removable[-1])
    # The added project copies an APK entry, chosen for its kind rather than
    # its position, under an ID and URL the catalog does not already use.
    template = next(
        (
            app
            for app in apps
            if not json.loads(app["additionalSettings"]).get("trackOnly", False)
        ),
        {"additionalSettings": json.dumps({"trackOnly": False}), "categories": []},
    )
    added_id, added_url = ADDED_ID, "https://github.com/example/testinvariant-added"
    while added_id in {app["id"] for app in apps} or normalize_project_url(
        added_url
    ) in {normalize_project_url(app["url"]) for app in apps}:
        added_id, added_url = f"{added_id}x", f"{added_url}x"
    added = {
        **template,
        "id": added_id,
        "url": added_url,
        "name": "Test Invariant Added",
        "author": "example",
    }
    # Route through the generator's own serializer so the variant is itself a
    # canonical catalog, matching what a real generation run would commit.
    return json.loads(_render_catalog([*apps, added]))


@pytest.fixture(params=["committed", "one-added-one-removed"])
def codm_catalog(request: pytest.FixtureRequest) -> dict[str, Any]:
    if request.param == "committed":
        return _committed_codm_catalog()
    return _catalog_with_one_project_added_and_one_removed()


def _compose_with_codm_catalog(
    catalog: dict[str, Any],
    tmp_path: Path,
    higher: list[App],
    *,
    policy_document: dict[str, Any] | None = None,
    denials: list[dict[str, str]] | None = None,
) -> CompositionResult:
    """Compose the committed configuration, or the given policy, over a catalog.

    `denials` are added to the committed denials.
    """
    policy = parse_composition_policy(
        load_json(ROOT / "config/composition.json")
        if policy_document is None
        else policy_document
    )
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "codm.json").write_text(json.dumps(catalog))
    generated = codm.fetch(tmp_path, {"catalog": "codm.json"}, higher)
    return compose(
        [*higher, *generated],
        [*load_json(ROOT / "config/deny.json"), *(denials or [])],
        load_json(ROOT / "config/overlay.json"),
        policy=policy,
    )


def test_committed_catalog_entries_have_unique_ids_and_urls(
    codm_catalog: dict[str, Any],
) -> None:
    ids = [app["id"] for app in codm_catalog["apps"]]
    urls = [normalize_project_url(app["url"]) for app in codm_catalog["apps"]]
    assert len(ids) == len(set(ids))
    assert len(urls) == len(set(urls))


def test_committed_catalog_entries_have_kind_appropriate_ids_and_flags(
    codm_catalog: dict[str, Any],
) -> None:
    for app in codm_catalog["apps"]:
        settings = json.loads(app["additionalSettings"])
        if settings.get("trackOnly"):
            assert app["id"].isdecimal()
            assert settings["versionDetection"] is False
            assert settings["includeZips"] is False
            assert settings["autoApkFilterByArch"] is False
        else:
            assert settings.get("trackOnly", False) is False
            assert _is_valid_package_id(app["id"])


def _is_canonical_catalog(path: Path) -> bool:
    raw = path.read_bytes()
    return _render_catalog(json.loads(raw)["apps"]) == raw


def test_committed_catalog_bytes_are_the_canonical_rendering_of_its_entries() -> None:
    assert _is_canonical_catalog(ROOT / "config/catalogs/codm.json")


def test_a_pretty_printed_catalog_is_not_canonical(tmp_path: Path) -> None:
    path = tmp_path / "codm.json"
    path.write_text(
        json.dumps(_committed_codm_catalog(), ensure_ascii=False, indent=2) + "\n"
    )
    assert not _is_canonical_catalog(path)


def test_committed_catalog_composes_with_frozen_captured_sources_without_errors(
    codm_catalog: dict[str, Any], tmp_path: Path
) -> None:
    higher, _ = captured_pipeline()
    result = _compose_with_codm_catalog(codm_catalog, tmp_path, higher)
    assert result.apps[Variant.DUAL]
    added = {app["id"] for app in codm_catalog["apps"]} - {
        app["id"] for app in _committed_codm_catalog()["apps"]
    }
    assert added <= {app.id for app in result.apps[Variant.DUAL]}


def test_committed_catalog_leaves_the_single_screen_pack_unchanged(
    tmp_path: Path,
) -> None:
    higher, _ = captured_pipeline()
    committed = _compose_with_codm_catalog(
        _committed_codm_catalog(), tmp_path / "committed", higher
    )
    modified = _compose_with_codm_catalog(
        _catalog_with_one_project_added_and_one_removed(),
        tmp_path / "modified",
        higher,
    )
    assert committed.apps[Variant.SINGLE] == modified.apps[Variant.SINGLE]


def _codm_entry(
    package_id: str, url: str, name: str, settings: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": package_id,
        "url": url,
        "author": url.split("/")[3],
        "name": name,
        "additionalSettings": json.dumps(settings),
        "categories": [],
        "overrideSource": "GitHub",
    }


def test_codm_catalog_entries_keep_their_source_semantics_in_composition(
    tmp_path: Path,
) -> None:
    higher, _ = captured_pipeline()
    # Rules and pins that name codm2000 candidates, and the overlay records,
    # target entries this fixture catalog does not carry.
    policy_document = load_json(PRE_MIGRATION / "composition.json")
    for key in ("candidates", "pins"):
        policy_document[key] = [
            item
            for item in policy_document[key]
            if item["match"]["source"] != "codm2000"
        ]
    policy = parse_composition_policy(policy_document)
    deny = load_json(PRE_MIGRATION / "deny.json")

    def compose_catalog(
        apps: list[dict[str, Any]], directory: Path
    ) -> tuple[list[App], CompositionResult]:
        directory.mkdir()
        (directory / "codm.json").write_text(json.dumps({"apps": apps}))
        generated = codm.fetch(directory, {"catalog": "codm.json"}, higher)
        return generated, compose([*higher, *generated], deny, [], policy=policy)

    _, baseline = compose_catalog([], tmp_path / "baseline")
    before = {(item.family, item.variant): item for item in baseline.report.selections}
    host_family = min(
        family for family, variant in before if (family, Variant.SINGLE) in before
    )
    host = before[(host_family, Variant.SINGLE)]
    covering = min(
        (
            app
            for app in higher
            if Variant.DUAL in app.eligibility
            and app.url.startswith("https://github.com/")
        ),
        key=lambda app: normalize_project_url(app.url),
    )
    prerelease_settings = {
        "includePrereleases": True,
        "apkFilterRegEx": r"^Fixture-v[0-9.]+-rc[0-9]+\.apk$",
        "trackOnly": False,
    }
    tracker_about = (
        f"A mod for the app at {host.url}. Install or update it through that app."
    )
    catalog = [
        _codm_entry(
            "com.example.prerelease",
            "https://github.com/example/prerelease-app",
            "Prerelease App",
            prerelease_settings,
        ),
        _codm_entry(
            "1234567890",
            "https://github.com/example/fixture-mod",
            "Fixture Mod (mod updates)",
            {
                "trackOnly": True,
                "versionDetection": False,
                "includeZips": False,
                "autoApkFilterByArch": False,
                "about": tracker_about,
            },
        ),
        _codm_entry(
            "com.example.covered",
            covering.url,
            "Covered App",
            {"includePrereleases": True, "trackOnly": False},
        ),
    ]
    generated, result = compose_catalog(catalog, tmp_path / "fixture")
    after = {(item.family, item.variant): item for item in result.report.selections}
    settings = {
        (app.data["id"], variant): app.data["additionalSettings"]
        for variant in Variant
        for app in result.apps[variant]
    }

    # A dual-eligible higher-source candidate already supplies the covered
    # project, so its codm2000 entry is suppressed before selection: it neither
    # competes in nor changes any family's selection.
    assert "com.example.covered" not in {app.id for app in generated}
    assert {key: after[key] for key in before} == before
    assert set(after) - set(before) == {
        ("package:com.example.prerelease", Variant.DUAL),
        ("package:1234567890", Variant.DUAL),
    }

    prerelease = after[("package:com.example.prerelease", Variant.DUAL)]
    assert (
        prerelease.source,
        prerelease.origin,
        prerelease.original_id,
        prerelease.effective_id,
    ) == (
        "codm2000",
        "codm-generated",
        "com.example.prerelease",
        "com.example.prerelease",
    )
    admitted = settings[("com.example.prerelease", Variant.DUAL)]
    assert {key: admitted[key] for key in prerelease_settings} == prerelease_settings
    assert ("com.example.prerelease", Variant.SINGLE) not in settings

    tracker = after[("package:1234567890", Variant.DUAL)]
    assert (tracker.source, tracker.original_id, tracker.effective_id) == (
        "codm2000",
        "1234567890",
        "1234567890",
    )
    tracked = settings[("1234567890", Variant.DUAL)]
    assert tracked["trackOnly"] is True
    assert tracked["about"] == tracker_about
    assert ("1234567890", Variant.SINGLE) not in settings
    for variant in Variant:
        assert after[(host_family, variant)] == before[(host_family, variant)]


def test_reviewed_policy_sets_fallback_for_named_projects() -> None:
    policy = load_json(ROOT / "config/codm-projects.json")["projects"]
    assert (
        policy["github.com/emulnk/emulnk"]["additionalSettings"][
            "fallbackToOlderReleases"
        ]
        is False
    )
    assert (
        policy["github.com/castdrian/showdown-ds"]["additionalSettings"][
            "fallbackToOlderReleases"
        ]
        is False
    )
    assert (
        policy["github.com/mastercook777/heimdall-ayn-thor-assistant"][
            "additionalSettings"
        ]["fallbackToOlderReleases"]
        is True
    )


def test_baseline_index_binds_every_captured_input() -> None:
    index = load_json(FIXTURES / "baseline/index.json")
    for item in index["inputs"]:
        relative = Path(item["file"])
        contents = (
            PRE_MIGRATION / relative.name
            if relative.parts[0] == "config"
            else ROOT / relative
        ).read_bytes()
        assert hashlib.sha256(contents).hexdigest() == item["sha256"]
