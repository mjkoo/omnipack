from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from omnipack.catalog import generate_catalog
from omnipack.composition_policy import (
    parse_composition_policy,
)
from omnipack.merge import compose
from omnipack.model import Category, Variant
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
APK_FILTERS = {
    "org.citron.citron_emu": "^(?!.*8[.]Elite).*[.]apk$",
    "com.winlator.ludashi": "vanilla",
}


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


def test_every_committed_denial_excludes_its_project_when_present(
    current_configuration: CurrentConfiguration,
) -> None:
    # A denial can match nothing because a source dropped the project. The
    # build reports such a denial as stale rather than failing, so check that
    # every stale report is genuinely absent and every present project is
    # removed from both packs.
    denied = {
        normalize_project_url(entry["url"]) for entry in read(ROOT / "config/deny.json")
    }
    present = {
        normalize_project_url(app.url)
        for app in current_configuration.candidates
        if app.eligibility
    }
    report = current_configuration.result.report
    assert {item.url for item in report.stale_exclusions} == denied - present
    assert {item.url for item in report.removals} == denied & present
    for variant in Variant:
        selected = {
            normalize_project_url(app.url)
            for app in current_configuration.result.apps[variant]
        }
        assert not (selected & denied)


def corrected_id(record, overlay):
    """The id an overlay record at the record's project URL patches in, if any."""
    patches = {item.url: item.patch for item in overlay}
    return patches.get(normalize_project_url(record["url"]), {}).get("id", record["id"])


def historical_curated():
    """Apply maintained overlays to historical, already selected output records."""
    baseline = read(FIXTURES / "baseline-apps.json")
    overlay = parse_overlay(read(ROOT / "config/overlay.json"), "overlay")
    selected = {variant: [] for variant in Variant}
    for variant in Variant:
        for record in baseline[variant.value]:
            data = deepcopy(record)
            data["additionalSettings"] = json.loads(data["additionalSettings"])
            selected[variant].append(
                ComposedApp(normalize_project_url(data["url"]), data)
            )
    return {
        variant.value: json.loads(render(apply_overlay(apps, overlay)))["apps"]
        for variant, apps in selected.items()
    }


def test_policies_preserve_existing_entries_and_settings():
    baseline = read(FIXTURES / "baseline-apps.json")
    overlay = parse_overlay(read(ROOT / "config/overlay.json"), "overlay")
    apps = historical_curated()
    for variant, originals in baseline.items():
        actual = {a["id"]: a for a in apps[variant]}
        expected_ids = {corrected_id(a, overlay) for a in originals}
        assert set(actual) == expected_ids
        for old in originals:
            new = actual[corrected_id(old, overlay)]
            old_settings = json.loads(old["additionalSettings"])
            expected = deepcopy(old_settings)
            if old["id"] in APK_FILTERS:
                expected["apkFilterRegEx"] = APK_FILTERS[old["id"]]
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
            expected_record["id"] = corrected_id(old, overlay)
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
        normalize_project_url(record["url"])
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
            key = normalize_project_url(entry["url"])
            if key in protected:
                assert (
                    json.loads(entry["additionalSettings"])["versionDetection"] is False
                )
                observed.add(key)
    assert observed == protected


def test_current_composition_categorizes_every_entry_from_the_taxonomy(
    current_configuration: CurrentConfiguration,
) -> None:
    result = current_configuration.result
    assert result.report.uncategorized_families == []
    assert result.report.stale_category_assignments == []
    for values in result.apps.values():
        for app in values:
            assert app.data["categories"]
            assert set(app.data["categories"]) <= set(Category)
            track_only = app.data["additionalSettings"].get("trackOnly") is True
            assert (app.data["categories"] == [Category.TRACK_ONLY]) == track_only


def test_split_and_joined_families_ship_as_intended(
    current_configuration: CurrentConfiguration,
) -> None:
    """melonDS stable and nightly share a repository but ship separately, and
    Minish Cap and Cemu each ship one build per pack from different repositories.
    """
    apps = current_configuration.result.apps
    for variant in Variant:
        by_family: dict[str, list[str]] = {}
        for app in apps[variant]:
            by_family.setdefault(app.family, []).append(normalize_project_url(app.url))
        assert {
            app.id
            for app in apps[variant]
            if normalize_project_url(app.url)
            == "github.com/rafaelvcaetano/melonds-android"
        } == {"me.magnum.melonds", "me.magnum.melonds.nightly"}
        assert len(by_family["app:minish-cap"]) == 1
        assert [app.id for app in apps[variant]].count("dev.picori.tmc") == 1
        assert by_family["app:cemu"] == [
            "github.com/ssimco/cemu"
            if variant is Variant.SINGLE
            else "github.com/sapphirerhodonite/cemu"
        ]


def test_current_composition_records_no_repeat_gap_or_tie(
    current_configuration: CurrentConfiguration,
) -> None:
    report = current_configuration.result.report
    assert report.repeated_ids == []
    assert report.single_only_families == []
    assert report.same_rank_ties == []
