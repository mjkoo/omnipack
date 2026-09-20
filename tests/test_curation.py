from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from omnipack.catalog import generate_catalog
from omnipack.composition_policy import parse_composition_policy
from omnipack.merge import compose
from omnipack.model import Variant
from omnipack.overlay import ComposedApp, apply_overlay, parse_overlay
from omnipack.render import render
from omnipack.urls import normalize_project_url
from tests.current_config_support import (
    CurrentConfiguration,
    current_configuration_fixture,  # noqa: F401
)

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


def test_upstream_pack_tracker_stays_excluded_from_current_composition(
    current_configuration: CurrentConfiguration,
) -> None:
    rjny_candidates = {
        app.id
        for app in current_configuration.candidates
        if app.provenance.source == "rjny"
    }
    assert {"904332840", "aenu.aps3e"} <= rjny_candidates
    packs = {
        variant: render(current_configuration.result.apps[variant]).encode()
        for variant in Variant
    }
    for pack in packs.values():
        ids = {app["id"] for app in json.loads(pack)["apps"]}
        assert "aenu.aps3e" in ids
        assert "904332840" not in ids
    catalog = generate_catalog(
        packs[Variant.SINGLE],
        packs[Variant.DUAL],
        parse_composition_policy(current_configuration.policy),
    )
    assert b"aPS3e" in catalog
    assert b"Obtainium-Emulation-Pack" not in catalog


def test_every_committed_denial_removes_a_current_candidate(
    current_configuration: CurrentConfiguration,
) -> None:
    # An unmatched denial is reported stale and does not fail the build, so a
    # denial whose upstream drops the id would quietly stop excluding anything.
    denied = {entry["id"] for entry in read(ROOT / "config/deny.json")}
    report = current_configuration.result.report
    stale = {item.package_id for item in report.stale_exclusions}
    assert stale == set(), f"denials matching no candidate: {sorted(stale)}"
    assert {item.package_id for item in report.removals} == denied


def effective_id(record):
    corrections = {
        (rule["match"]["id"], rule["match"]["url"].lower()): rule["packageId"]
        for rule in read(ROOT / "config/composition.json")["candidates"]
        if "packageId" in rule
    }
    return corrections.get((record["id"], record["url"].lower()), record["id"])


def historical_curated():
    """Apply maintained overlays to historical, already selected output records."""
    baseline = read(FIXTURES / "baseline-apps.json")
    selected = {variant: [] for variant in Variant}
    for variant in Variant:
        for record in baseline[variant.value]:
            data = deepcopy(record)
            data["additionalSettings"] = json.loads(data["additionalSettings"])
            data["id"] = effective_id(data)
            selected[variant].append(ComposedApp(f"package:{data['id']}", data))
    overlay = parse_overlay(read(ROOT / "config/overlay.json"), "overlay")
    return {
        variant.value: json.loads(render(apply_overlay(apps, overlay)))["apps"]
        for variant, apps in selected.items()
    }


def test_policies_preserve_existing_entries_and_settings():
    baseline = read(FIXTURES / "baseline-apps.json")
    apps = historical_curated()
    for variant, originals in baseline.items():
        actual = {a["id"]: a for a in apps[variant]}
        expected_ids = {effective_id(a) for a in originals}
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


def test_cinderbox_retains_release_selection_settings(
    current_configuration: CurrentConfiguration,
) -> None:
    for variant in Variant:
        document = json.loads(render(current_configuration.result.apps[variant]))
        matches = [app for app in document["apps"] if app["id"] == "com.game.cinderbox"]
        assert len(matches) == 1
        app = matches[0]
        assert (app["name"], app["author"], app["categories"]) == (
            "Cinderbox",
            "Ekyso",
            ["PC Ports"],
        )
        settings = json.loads(app["additionalSettings"])
        assert settings["versionDetection"] and not settings["trackOnly"]
        assert not settings["includePrereleases"]
        assert not settings["releaseDateAsVersion"]
        assert not settings["versionExtractionRegEx"]
        assert not settings["releaseTitleAsVersion"]
        assert settings["fallbackToOlderReleases"] is True


def test_maintained_version_override_survives_refreshed_source_settings(
    current_configuration: CurrentConfiguration,
) -> None:
    overlay = read(ROOT / "config/overlay.json")
    protected = {
        (record["id"], normalize_project_url(record["url"]))
        for record in overlay
        if record["patch"].get("additionalSettings", {}).get("versionDetection")
        is False
    }
    assert protected
    refreshed = [
        replace(
            app,
            additional_settings={**app.additional_settings, "versionDetection": True},
        )
        for app in current_configuration.candidates
    ]
    result = compose(
        refreshed,
        read(ROOT / "config/deny.json"),
        overlay,
        policy=parse_composition_policy(current_configuration.policy),
    )
    observed = set()
    for variant in Variant:
        for entry in json.loads(render(result.apps[variant]))["apps"]:
            key = (entry["id"], normalize_project_url(entry["url"]))
            if key in protected:
                assert (
                    json.loads(entry["additionalSettings"])["versionDetection"] is False
                )
                observed.add(key)
    assert observed == protected
