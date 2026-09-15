from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

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
from tests.current_config_support import (
    CurrentConfiguration,
    current_configuration_fixture,  # noqa: F401
)
from tests.test_sources import FakeHttp

ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures/source-generation/codm"
CAPTURED = ROOT / "tests/fixtures/reconciliation"
PRE_MIGRATION = FIXTURES / "pre-migration-config"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def captured_higher() -> list[App]:
    """Ingest the captured upstream catalogs with the frozen extras."""
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
        }
    )
    return [
        *rjny.fetch(http, sources["rjny"]),
        *bboi.fetch(http, sources["bboi"]),
        *fetch_extras(load_json(PRE_MIGRATION / "extras.json")),
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


def test_frozen_captured_baseline_reproduces_exact_exports_and_family_winners() -> None:
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


def test_committed_catalog_is_valid_canonical_and_composable(
    current_configuration: CurrentConfiguration,
) -> None:
    catalog = current_configuration.catalog
    ids = [app["id"] for app in catalog["apps"]]
    urls = [normalize_project_url(app["url"]) for app in catalog["apps"]]
    assert len(ids) == len(set(ids))
    assert len(urls) == len(set(urls))
    for app in catalog["apps"]:
        settings = json.loads(app["additionalSettings"])
        if settings.get("trackOnly"):
            assert app["id"].isdecimal()
            assert settings["versionDetection"] is False
            assert settings["includeZips"] is False
            assert settings["autoApkFilterByArch"] is False
        else:
            assert settings.get("trackOnly", False) is False
            assert _is_valid_package_id(app["id"])
    raw = (ROOT / "config/catalogs/codm.json").read_bytes()
    assert _render_catalog(catalog["apps"]) == raw
    assert current_configuration.result.apps[Variant.DUAL]


def test_catalog_addition_and_removal_leave_single_screen_selection_unchanged(
    tmp_path: Path,
) -> None:
    higher = fetch_extras(
        [
            {
                "id": "com.example.base",
                "url": "https://github.com/example/base",
                "name": "Base",
            }
        ]
    )
    results = []
    for name in ("removed", "added"):
        directory = tmp_path / name
        directory.mkdir()
        entry = _codm_entry(
            f"com.example.{name}", f"https://github.com/example/{name}", name, {}
        )
        (directory / "codm.json").write_text(json.dumps({"apps": [entry]}))
        generated = codm.fetch(directory, {"catalog": "codm.json"}, higher)
        results.append(
            compose(
                [*higher, *generated],
                [],
                [],
                policy=parse_composition_policy(
                    {"schemaVersion": 1, "candidates": [], "pins": []}
                ),
            )
        )
    before, after = results
    assert [app.id for app in before.apps[Variant.SINGLE]] == ["com.example.base"]
    assert before.apps[Variant.SINGLE] == after.apps[Variant.SINGLE]
    assert {app.id for app in before.apps[Variant.DUAL]} == {
        "com.example.base",
        "com.example.removed",
    }
    assert {app.id for app in after.apps[Variant.DUAL]} == {
        "com.example.base",
        "com.example.added",
    }


def _codm_entry(
    package_id: str, url: str, name: str, settings: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": package_id,
        "url": url,
        "author": "example",
        "name": name,
        "additionalSettings": json.dumps(settings),
        "categories": [],
        "overrideSource": "GitHub",
    }


def test_codm_catalog_entries_keep_their_source_semantics_in_composition(
    tmp_path: Path,
) -> None:
    host_url = "https://github.com/example/host"
    covering_url = "https://github.com/example/covered"
    higher = fetch_extras(
        [
            {"id": "com.example.host", "url": host_url, "name": "Host"},
            {"id": "com.example.higher", "url": covering_url, "name": "Covering App"},
        ]
    )
    policy = parse_composition_policy(
        {"schemaVersion": 1, "candidates": [], "pins": []}
    )

    def compose_catalog(
        apps: list[dict[str, Any]], directory: Path
    ) -> tuple[list[App], CompositionResult]:
        directory.mkdir()
        (directory / "codm.json").write_text(json.dumps({"apps": apps}))
        generated = codm.fetch(directory, {"catalog": "codm.json"}, higher)
        return generated, compose([*higher, *generated], [], [], policy=policy)

    _, baseline = compose_catalog([], tmp_path / "baseline")
    before = {(item.family, item.variant): item for item in baseline.report.selections}
    assert set(before) == {
        (f"package:{package_id}", variant)
        for package_id in ("com.example.host", "com.example.higher")
        for variant in Variant
    }
    prerelease_settings = {
        "includePrereleases": True,
        "apkFilterRegEx": r"^Fixture-v[0-9.]+-rc[0-9]+\.apk$",
        "trackOnly": False,
    }
    tracker_about = (
        f"A mod for the app at {host_url}. Install or update it through that app."
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
            covering_url,
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
    # Every earlier selection is unchanged, which covers the covering project's
    # and the tracked host's selections in both packs.
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
