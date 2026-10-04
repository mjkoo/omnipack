from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from omnipack.composition_policy import parse_composition_policy
from omnipack.merge import CompositionResult, compose
from omnipack.model import Variant
from omnipack.package_id import _is_valid_package_id
from omnipack.source_catalog import render_catalog
from omnipack.sources import codm
from omnipack.sources.extras import fetch as fetch_extras
from omnipack.urls import normalize_project_url
from tests.current_config_support import (
    CurrentConfiguration,
    current_configuration_fixture,  # noqa: F401
)

ROOT = Path(__file__).parents[1]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


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
    assert render_catalog(catalog["apps"]) == raw
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
        generated = codm.fetch(directory, {"catalog": "codm.json"})
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
    higher = fetch_extras(
        [
            {"id": "com.example.host", "url": host_url, "name": "Host"},
        ]
    )
    policy = parse_composition_policy(
        {"schemaVersion": 1, "candidates": [], "pins": []}
    )

    def compose_catalog(
        apps: list[dict[str, Any]], directory: Path
    ) -> CompositionResult:
        directory.mkdir()
        (directory / "codm.json").write_text(json.dumps({"apps": apps}))
        generated = codm.fetch(directory, {"catalog": "codm.json"})
        return compose([*higher, *generated], [], [], policy=policy)

    baseline = compose_catalog([], tmp_path / "baseline")
    before = {(item.family, item.variant): item for item in baseline.report.selections}
    assert set(before) == {("github.com/example/host", variant) for variant in Variant}
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
    ]
    result = compose_catalog(catalog, tmp_path / "fixture")
    after = {(item.family, item.variant): item for item in result.report.selections}
    settings = {
        (app.data["id"], variant): app.data["additionalSettings"]
        for variant in Variant
        for app in result.apps[variant]
    }

    # The tracked host's selections are unchanged in both packs.
    assert {key: after[key] for key in before} == before
    assert set(after) - set(before) == {
        ("github.com/example/prerelease-app", Variant.DUAL),
        ("github.com/example/fixture-mod", Variant.DUAL),
    }

    prerelease = after[("github.com/example/prerelease-app", Variant.DUAL)]
    assert (prerelease.source, prerelease.origin, prerelease.id) == (
        "codm2000",
        "codm-generated",
        "com.example.prerelease",
    )
    admitted = settings[("com.example.prerelease", Variant.DUAL)]
    assert {key: admitted[key] for key in prerelease_settings} == prerelease_settings
    assert ("com.example.prerelease", Variant.SINGLE) not in settings

    tracker = after[("github.com/example/fixture-mod", Variant.DUAL)]
    assert (tracker.source, tracker.id) == ("codm2000", "1234567890")
    tracked = settings[("1234567890", Variant.DUAL)]
    assert tracked["trackOnly"] is True
    assert tracked["about"] == tracker_about
    assert ("1234567890", Variant.SINGLE) not in settings
