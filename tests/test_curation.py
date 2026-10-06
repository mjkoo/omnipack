from __future__ import annotations

import json
import re
from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from omnipack.catalog import generate_catalog
from omnipack.composition_policy import (
    parse_composition_policy,
)
from omnipack.merge import CompositionResult, compose
from omnipack.model import App, Category, Provenance, Variant
from omnipack.overlay import ComposedApp, apply_overlay, parse_overlay
from omnipack.render import render
from omnipack.urls import normalize_project_url
from tests import current_config_support
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
    # every stale report has no candidate at all at its URL, that every denial
    # of an eligible candidate is reported as a removal, and that no denied
    # project reaches either pack.
    denied = {
        normalize_project_url(entry["url"]) for entry in read(ROOT / "config/deny.json")
    }
    present = {
        normalize_project_url(app.url) for app in current_configuration.candidates
    }
    eligible = {
        normalize_project_url(app.url)
        for app in current_configuration.candidates
        if app.eligibility
    }
    report = current_configuration.result.report
    assert {item.url for item in report.stale_exclusions} == denied - present
    assert {item.url for item in report.removals} == denied & eligible
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


def assert_categories_follow_the_taxonomy(result: CompositionResult) -> None:
    """Every selected entry carries taxonomy categories, Track Only exactly when
    it is track-only, or none while the build reports its family uncategorized.

    A family without a category key and a key without a selected family are
    reported by the build, not failed, so a valid generated catalog that adds
    or removes a project needs no other edit to be accepted.
    """
    uncategorized = {
        (item.family, variant)
        for item in result.report.uncategorized_families
        for variant in item.variants
    }
    for variant, values in result.apps.items():
        for app in values:
            categories = app.data["categories"]
            assert bool(categories) != ((app.family, variant) in uncategorized)
            assert set(categories) <= set(Category)
            track_only = app.data["additionalSettings"].get("trackOnly") is True
            if categories:
                assert (categories == [Category.TRACK_ONLY]) == track_only


def test_current_composition_categorizes_every_entry_from_the_taxonomy(
    current_configuration: CurrentConfiguration,
) -> None:
    assert_categories_follow_the_taxonomy(current_configuration.result)


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


def test_open_nectar_entries_keep_their_published_id(
    current_configuration: CurrentConfiguration,
) -> None:
    url = "github.com/ssunnking/open-nectar---pikmin-native-pc-port"
    for variant in Variant:
        assert {
            app.data["id"]
            for app in current_configuration.result.apps[variant]
            if normalize_project_url(app.url) == url
        } <= {"org.opennectar"}


GENERATED_ORIGINS = {"codm-generated", "quiver-generated"}
KANTO_GEAR_ABOUT = (
    "Kanto Gear is a Gen1Recomp Lua mod distributed as a ZIP, not an Android "
    "application. Install or update through official Gen1Recomp at "
    "https://github.com/bryanthaboi/gen1recomp using its Mod Index or ZIP import. "
    "Obtainium only tracks release notifications; acknowledgement does not install "
    "the resource or detect its installed version."
)
# Per-app choices for generated entries, kept as overlay records so they hold
# whatever settings and names a regenerated catalog carries.
GENERATED_OVERRIDES = {
    "github.com/castdrian/showdown-ds": (
        "Showdown!",
        {
            "includePrereleases": True,
            "apkFilterRegEx": r"^showdown-v[0-9].*\.apk$",
            "versionExtractionRegEx": "^v?(.+)$",
            "matchGroupToUse": "1",
            "fallbackToOlderReleases": False,
        },
    ),
    "github.com/mastercook777/heimdall-ayn-thor-assistant": (
        "Heimdall",
        {
            "includePrereleases": True,
            "filterReleaseTitlesByRegEx": (
                r"^Heimdall v[0-9]+\.[0-9]+\.[0-9]+(?:-(?:alpha|beta)\.[0-9]+)?$"
            ),
            "apkFilterRegEx": r"^heimdall-v[0-9].*\.apk$",
            "versionExtractionRegEx": "^v?(.+)$",
            "matchGroupToUse": "1",
        },
    ),
    "github.com/rsigristc/dw3-ds-android": (
        "DW2003 Dual Screen",
        {"apkFilterRegEx": r"^DW2003-Dual-Screen-v[0-9].*\.apk$"},
    ),
    "github.com/averageconsumer/kanto-gear": (
        "Kanto Gear (mod updates)",
        {
            "trackOnly": True,
            "versionDetection": False,
            "includeZips": False,
            "autoApkFilterByArch": False,
            "about": KANTO_GEAR_ABOUT,
        },
    ),
    "github.com/999sian/melee-pc": ("Melee PC", {"includePrereleases": True}),
    "github.com/slickamogus/silent-hill-decomp": (
        "Silent Hill Decomp",
        {"apkFilterRegEx": "^(?!.*_OLD[.]apk$).*"},
    ),
    "github.com/isledecomp/isle-portable": (
        "LEGO Island Portable",
        {"apkFilterRegEx": "^app-release[.]apk$"},
    ),
}


def test_generated_entries_take_their_settings_and_categories_from_configuration(
    current_configuration: CurrentConfiguration,
) -> None:
    # Generated entries lose their names, settings and categories, so every
    # value checked below can only come from configuration.
    regenerated = [
        replace(app, name="regenerated", additional_settings={}, categories=())
        if app.origin in GENERATED_ORIGINS
        else app
        for app in current_configuration.candidates
    ]
    result = compose(
        regenerated,
        read(ROOT / "config/deny.json"),
        read(ROOT / "config/overlay.json"),
        policy=parse_composition_policy(current_configuration.policy),
    )
    assert_categories_follow_the_taxonomy(result)
    origins = {
        (normalize_project_url(selection.url), selection.variant): selection.origin
        for selection in result.report.selections
    }
    for variant in Variant:
        for entry in json.loads(render(result.apps[variant]))["apps"]:
            key = normalize_project_url(entry["url"])
            if key not in GENERATED_OVERRIDES:
                continue
            assert origins[key, variant] in GENERATED_ORIGINS, key
            name, settings = GENERATED_OVERRIDES[key]
            actual = json.loads(entry["additionalSettings"])
            assert entry["name"] == name, key
            assert {setting: actual[setting] for setting in settings} == settings, key


def test_configuration_names_only_files_that_exist() -> None:
    for path in sorted((ROOT / "config").rglob("*.json")):
        for named in sorted(
            set(re.findall(r"config/[\w./-]+\.json", path.read_text()))
        ):
            assert (ROOT / named).is_file(), f"{path.name} names missing {named}"


def _with_quiver_catalog(
    monkeypatch: pytest.MonkeyPatch, change: Callable[[list[App]], list[App]]
) -> CurrentConfiguration:
    fetch = current_config_support.quiver.fetch
    monkeypatch.setattr(
        current_config_support.quiver, "fetch", lambda *args: change(fetch(*args))
    )
    return current_config_support.build_current_configuration()


def test_catalog_only_addition_of_an_uncategorized_family_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://example.test/regression/new-port"
    added = App(
        "a1b2c3d4e5f6",
        url,
        "New Port",
        None,
        (),
        Provenance("quiver", url),
        frozenset(Variant),
        origin="quiver-generated",
    )
    current = _with_quiver_catalog(monkeypatch, lambda apps: [*apps, added])
    assert_categories_follow_the_taxonomy(current.result)
    assert ("example.test/regression/new-port", (Variant.SINGLE, Variant.DUAL)) in [
        (item.family, item.variants)
        for item in current.result.report.uncategorized_families
    ]


def test_catalog_only_removal_of_a_categorized_entry_is_reported(
    current_configuration: CurrentConfiguration, monkeypatch: pytest.MonkeyPatch
) -> None:
    overlaid = {
        normalize_project_url(record["url"])
        for record in read(ROOT / "config/overlay.json")
    }
    # A family only a Quiver entry serves and a category key categorizes,
    # whatever the committed catalog holds.
    selections = current_configuration.result.report.selections
    family = min(
        selection.family
        for selection in selections
        if selection.family in current_configuration.policy["categories"]
        and selection.family not in overlaid
        and all(
            other.source == "quiver"
            and other.family == normalize_project_url(other.url)
            for other in selections
            if other.family == selection.family
        )
    )
    current = _with_quiver_catalog(
        monkeypatch,
        lambda apps: [app for app in apps if normalize_project_url(app.url) != family],
    )
    assert_categories_follow_the_taxonomy(current.result)
    assert family in current.result.report.stale_category_assignments
