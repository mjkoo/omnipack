from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from omnipack.catalog import generate_catalog
from omnipack.composition_policy import parse_composition_policy
from omnipack.merge import compose
from omnipack.model import Provenance, Variant
from omnipack.overlay import ComposedApp, apply_overlay, parse_overlay
from omnipack.render import render
from omnipack.sources import rjny
from omnipack.sources.extras import fetch
from tests.test_sources import FakeHttp

ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures/curation"
SOURCE_IDS = {
    "com.simon358.ctrnative",
    "com.waterdish.shipwright",
    "org.citron.citron_emu",
    "org.vita3k.emulator",
    "xendroid.compose",
    "com.winlator.ludashi",
    "com.winlator.cmod",
    "xyz.blacksheep.mjolnir",
}
NUMERIC_IDS = {"com.aure.banjorecomp", "com.sergiomanzur.sotnrecomp"}


def read(path):
    return json.loads(path.read_text())


def test_upstream_pack_tracker_stays_excluded_after_refresh():
    source = read(ROOT / "config/sources.json")["rjny"]
    url = f"https://raw.githubusercontent.com/{source['repo']}/{source['branch']}/{source['path']}"
    records = read(ROOT / "tests/fixtures/rjny-applications.json")["apps"]
    selected = [r for r in records if r["id"] in {"904332840", "aenu.aps3e"}]
    assert len(selected) == 2
    policy = parse_composition_policy(
        {"schemaVersion": 1, "candidates": [], "pins": []}
    )
    exclusions = read(ROOT / "config/deny.json")
    for refresh in range(2):
        upstream = deepcopy(selected)
        upstream[0]["name"] += f" refresh {refresh}"
        apps = rjny.fetch(FakeHttp({url: json.dumps({"apps": upstream})}), source)
        assert {a.id for a in apps} == {"904332840", "aenu.aps3e"}
        result = compose(apps, exclusions, [], [], policy=policy)
        packs = {v: render(result.apps[v], {}).encode() for v in Variant}
        for pack in packs.values():
            assert [a["id"] for a in json.loads(pack)["apps"]] == ["aenu.aps3e"]
        catalog = generate_catalog(packs[Variant.SINGLE], packs[Variant.DUAL], policy)
        assert b"aPS3e" in catalog
        assert b"Obtainium-Emulation-Pack" not in catalog


def effective_id(record):
    corrections = {
        (rule["match"]["id"], rule["match"]["url"].lower()): rule["packageId"]
        for rule in read(ROOT / "config/composition.json")["candidates"]
        if "packageId" in rule
    }
    return corrections.get((record["id"], record["url"].lower()), record["id"])


def curated():
    """Apply maintained overlays to historical, already selected output records."""
    baseline = read(FIXTURES / "baseline-apps.json")
    selected = {variant: [] for variant in Variant}
    for variant in Variant:
        for record in baseline[variant.value]:
            data = deepcopy(record)
            data["additionalSettings"] = json.loads(data["additionalSettings"])
            data["id"] = effective_id(data)
            selected[variant].append(
                ComposedApp(
                    variant,
                    Provenance("fixture", data["url"]),
                    data,
                )
            )
    historical_extras = [
        entry
        for entry in read(ROOT / "config/extras.json")
        if entry["id"] == "com.game.cinderbox"
    ]
    for app in fetch(historical_extras):
        data = deepcopy(app.raw)
        data.update(
            id=app.id,
            url=app.url,
            name=app.name,
            overrideSource=app.source_type.value,
            categories=list(app.categories),
            additionalSettings=deepcopy(app.additional_settings),
        )
        for variant in app.eligibility:
            selected[variant].append(
                ComposedApp(variant, app.provenance, deepcopy(data))
            )
    overlay = parse_overlay(read(ROOT / "config/overlay.json"), "common overlay")
    return {
        variant.value: json.loads(render(apply_overlay(apps, overlay), {}))["apps"]
        for variant, apps in selected.items()
    }


def test_policies_preserve_existing_entries_and_settings():
    baseline = read(FIXTURES / "baseline-apps.json")
    apps = curated()
    for variant, originals in baseline.items():
        actual = {a["id"]: a for a in apps[variant]}
        expected_ids = {effective_id(a) for a in originals} | {"com.game.cinderbox"}
        assert set(actual) == expected_ids
        for old in originals:
            corrected_id = effective_id(old)
            new = actual[corrected_id]
            old_settings = json.loads(old["additionalSettings"])
            expected = deepcopy(old_settings)
            if old["id"] in SOURCE_IDS:
                expected["versionDetection"] = False
            elif old["id"] in NUMERIC_IDS:
                expected.update(
                    versionExtractionRegEx=r"[0-9]+(?:\.[0-9]+)+", matchGroupToUse="0"
                )
            elif old["id"] == "info.cemu.cemu":
                expected["releaseTitleAsVersion"] = False
            assert json.loads(new["additionalSettings"]) == expected
            expected_record = {
                k: v for k, v in old.items() if k != "additionalSettings"
            }
            expected_record["id"] = corrected_id
            assert {
                k: v for k, v in new.items() if k != "additionalSettings"
            } == expected_record


def test_ludashi_allows_its_manifest_package_to_differ():
    ludashi = [
        app
        for apps in curated().values()
        for app in apps
        if app["id"] == "com.winlator.ludashi"
    ]
    assert ludashi and all(app["allowIdChange"] is True for app in ludashi)


@pytest.mark.parametrize("variant", ["single", "dual"])
def test_cinderbox_retains_release_selection_settings(variant):
    matches = [a for a in curated()[variant] if a["id"] == "com.game.cinderbox"]
    assert len(matches) == 1
    app = matches[0]
    assert (app["name"], app["author"], app["categories"]) == (
        "Cinderbox",
        "Ekyso",
        ["PC Ports"],
    )
    settings = json.loads(app["additionalSettings"])
    assert settings["versionDetection"] and not settings["trackOnly"]
    assert not settings["includePrereleases"] and not settings["releaseDateAsVersion"]
    assert (
        not settings["versionExtractionRegEx"] and not settings["releaseTitleAsVersion"]
    )
    assert settings["fallbackToOlderReleases"] is True
