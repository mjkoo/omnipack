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
    catalog = _committed_codm_catalog()
    apps = list(catalog["apps"])
    apps.pop()
    # The added project copies the settings of an APK entry, chosen for its
    # kind rather than its position, under a new ID and URL.
    template = next(
        app
        for app in apps
        if not json.loads(app["additionalSettings"]).get("trackOnly", False)
    )
    added = {
        **template,
        "id": ADDED_ID,
        "url": "https://github.com/example/testinvariant-added",
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
    if any(app["id"] == ADDED_ID for app in codm_catalog["apps"]):
        assert ADDED_ID in {app.id for app in result.apps[Variant.DUAL]}


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


def test_committed_codm_entries_keep_their_source_semantics_in_composition(
    tmp_path: Path,
) -> None:
    higher, _ = captured_pipeline()
    result = _compose_with_codm_catalog(_committed_codm_catalog(), tmp_path, higher)
    selections = {
        (item.effective_id, item.variant): item for item in result.report.selections
    }
    settings = {
        (app.id, variant): app.data["additionalSettings"]
        for variant in Variant
        for app in result.apps[variant]
    }

    # A higher source already covers EmuLnk in dual, so its codm entry is
    # suppressed and the higher source's build and settings win.
    emulnk = selections[("com.emulnk", Variant.DUAL)]
    assert emulnk.source == "rjny"
    assert all(item.source != "codm2000" for item in emulnk.considered)
    assert settings[("com.emulnk", Variant.DUAL)]["includePrereleases"] is True

    for package_id in ("dev.adrian.showdown", "com.mastercook777.heimdall"):
        selection = selections[(package_id, Variant.DUAL)]
        assert (selection.source, selection.origin, selection.original_id) == (
            "codm2000",
            "codm-generated",
            package_id,
        )
        assert settings[(package_id, Variant.DUAL)]["includePrereleases"] is True
        assert (package_id, Variant.SINGLE) not in settings

    kanto = selections[("1845280017", Variant.DUAL)]
    assert (kanto.source, kanto.original_id) == ("codm2000", "1845280017")
    assert settings[("1845280017", Variant.DUAL)]["trackOnly"] is True
    assert "Gen1Recomp" in settings[("1845280017", Variant.DUAL)]["about"]
    assert ("1845280017", Variant.SINGLE) not in settings
    for variant in Variant:
        host = selections[("com.theboisclub.pokemonred", variant)]
        assert (host.source, normalize_project_url(host.url)) == (
            "extras",
            normalize_project_url("https://github.com/bryanthaboi/gen1recomp"),
        )


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
