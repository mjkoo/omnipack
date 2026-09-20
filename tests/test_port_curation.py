from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from omnipack.catalog import generate_catalog
from omnipack.composition_policy import (
    apply_composition_policy,
    candidate_selector,
    parse_composition_policy,
)
from omnipack.merge import compose
from omnipack.model import App, Provenance, Variant
from omnipack.render import render
from omnipack.sources.extras import fetch
from omnipack.urls import normalize_project_url
from tests.current_config_support import (
    CurrentConfiguration,
    current_configuration_fixture,  # noqa: F401
)

ROOT = Path(__file__).parents[1]
PORT_IDS = {
    "com.aurora.store",
    "com.karin.idTech4Amm",
    "is.xyz.vcmi",
    "com.github.bvschaik.julius",
    "su.xash.engine.test",
}


def read(path: Path):
    return json.loads(path.read_text())


def extras():
    return fetch(read(ROOT / "config/extras.json"))


@pytest.mark.parametrize("variant", list(Variant))
def test_curated_ports_are_present_once_with_maintained_policy(variant):
    selected = [
        app for app in extras() if variant in app.eligibility and app.id in PORT_IDS
    ]
    assert {app.id for app in selected} == PORT_IDS
    assert len(selected) == len(PORT_IDS)
    for app in selected:
        assert app.categories == (
            ("Utilities",) if app.id == "com.aurora.store" else ("PC Ports",)
        )
        assert app.additional_settings["trackOnly"] is False
    by_id = {app.id: app for app in selected}
    assert by_id["com.aurora.store"].source_type.value == "GitLab"
    assert (
        by_id["com.aurora.store"].additional_settings["apkFilterRegEx"]
        == r"^AuroraStore-[0-9]+(?:\.[0-9]+)+\.apk$"
    )
    assert (
        by_id["com.karin.idTech4Amm"].additional_settings["versionDetection"] is False
    )
    assert by_id["is.xyz.vcmi"].additional_settings["autoApkFilterByArch"] is True
    xash = by_id["su.xash.engine.test"].additional_settings
    assert (
        xash["filterReleaseTitlesByRegEx"] == r"^Xash3D FWGS Continuous master Build$"
    )
    assert xash["apkFilterRegEx"] == r"^xash3d-fwgs-android\.apk$"
    assert xash["useLatestAssetDateAsReleaseDate"] is True
    assert xash["releaseDateAsVersion"] is True
    assert xash["includePrereleases"] is True
    assert xash["verifyLatestTag"] is False
    assert xash["fallbackToOlderReleases"] is True
    aurora = by_id["com.aurora.store"].additional_settings
    assert aurora["versionDetection"] is True
    assert aurora["autoApkFilterByArch"] is False
    julius = by_id["com.github.bvschaik.julius"].additional_settings
    assert julius["apkFilterRegEx"] == r"^julius-.*-android\.apk$"
    assert julius["includePrereleases"] is False
    vcmi = by_id["is.xyz.vcmi"].additional_settings
    assert vcmi["apkFilterRegEx"] == r"^VCMI-Android-.*\.apk$"
    assert vcmi["includePrereleases"] is False


def test_composition_pins_keep_extras_when_dual_preferred_duplicates_appear():
    maintained = [app for app in extras() if app.id in PORT_IDS]
    duplicates = [
        App(
            app.id,
            app.url,
            "upstream duplicate",
            app.source_type,
            app.categories,
            Provenance("bboi", app.url),
            frozenset({Variant.DUAL}),
            {"apkFilterRegEx": "wrong.apk", "versionDetection": True},
            origin="bboi-dual-asset",
        )
        for app in maintained
    ]
    document = read(ROOT / "config/composition.json")
    document["candidates"] = [
        rule for rule in document["candidates"] if rule["match"]["id"] in PORT_IDS
    ]
    document["pins"] = [
        pin for pin in document["pins"] if pin["match"]["id"] in PORT_IDS
    ]
    unpinned = deepcopy(document)
    unpinned["pins"] = []
    ordinary = compose(
        [*maintained, *duplicates],
        [],
        [],
        policy=parse_composition_policy(unpinned),
    )
    assert {(item.variant, item.source) for item in ordinary.report.selections} == {
        (Variant.SINGLE, "extras"),
        (Variant.DUAL, "bboi"),
    }
    result = compose(
        [*maintained, *duplicates],
        [],
        [],
        policy=parse_composition_policy(document),
    )
    for variant in Variant:
        chosen = [app for app in result.apps[variant] if app.data["id"] in PORT_IDS]
        assert len(chosen) == len(PORT_IDS)
        assert {
            (item.source, item.reason)
            for item in result.report.selections
            if item.variant is variant
        } == {("extras", "source" if variant is Variant.SINGLE else "pin")}
        expected = {app.id: app.additional_settings for app in maintained}
        for app in chosen:
            assert app.data["additionalSettings"] == expected[app.data["id"]]


def _extra_selector(entry: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        "extras",
        "extras",
        str(entry["id"]),
        normalize_project_url(str(entry["url"])),
    )


def _single_pin_exemptions(
    extras_config: list[dict[str, Any]], policy_document: dict[str, Any]
) -> set[tuple[str, str, str, str]]:
    single_pins = {
        pin["family"]
        for pin in policy_document["pins"]
        if pin["variant"] == Variant.SINGLE.value
    }
    if not single_pins:
        return set()

    rules = {
        (
            rule["match"]["source"],
            rule["match"]["origin"],
            rule["match"]["id"],
            normalize_project_url(rule["match"]["url"]),
        ): rule
        for rule in policy_document["candidates"]
    }
    exemptions = set()
    for entry in extras_config:
        selector = _extra_selector(entry)
        rule = rules.get(selector, {})
        family = rule.get("family") or f"package:{rule.get('packageId', entry['id'])}"
        if family in single_pins:
            exemptions.add(selector)
    return exemptions


def test_committed_configuration_selects_each_baseline_extra_in_single(
    current_configuration: CurrentConfiguration,
) -> None:
    expected = {
        _extra_selector(entry)
        for entry in current_configuration.extras
        if not entry.get("dualScreen", False)
    }
    expected -= _single_pin_exemptions(
        current_configuration.extras, current_configuration.policy
    )
    selected = {
        (
            item.source,
            item.origin,
            item.original_id,
            normalize_project_url(item.url),
        )
        for item in current_configuration.result.report.selections
        if item.variant is Variant.SINGLE
    }
    families = {
        candidate_selector(app).key: app.family or f"package:{app.id}"
        for app in apply_composition_policy(
            parse_composition_policy(current_configuration.policy),
            current_configuration.candidates,
        )
    }
    missing = sorted(families[selector] for selector in expected - selected)
    assert not missing, f"curated extras not selected in single: {missing}"


def test_hollow_knight_source_composition_preserves_dual_only_catalog(
    current_configuration: CurrentConfiguration,
):
    ids = {"igawa6.dualsouls", "com.jakobkhansen.silksong"}
    candidates = [app for app in current_configuration.candidates if app.id in ids]
    assert {app.id for app in candidates} == ids
    assert all(app.eligibility == frozenset({Variant.DUAL}) for app in candidates)
    result = current_configuration.result
    selected = [app for app in result.apps[Variant.DUAL] if app.data["id"] in ids]
    assert len(selected) == 2
    assert {app.data["id"] for app in selected} == ids
    assert not any(app.data["id"] in ids for app in result.apps[Variant.SINGLE])
    expected = {
        "igawa6.dualsouls": (
            "https://github.com/igawa6/dualsouls",
            "Hollow Knight: Dual Souls",
        ),
        "com.jakobkhansen.silksong": (
            "https://github.com/jakobkhansen/SilksongAndroid",
            "Hollow Knight: Silksong",
        ),
    }
    for app in selected:
        url, name = expected[app.data["id"]]
        # Overlay records find their targets by normalized project URL.
        assert normalize_project_url(app.data["url"]) == normalize_project_url(url)
        assert app.data["name"] == name
        assert app.data["categories"] == ["PC Ports"]
        about = app.data["additionalSettings"]["about"]
        assert "user-supplied" in about
        if app.data["id"] == "igawa6.dualsouls":
            assert "second screen" in about
        else:
            assert "Android 13 only" in app.data["additionalSettings"]["about"]
            assert (
                "Android 15 is unsupported" in app.data["additionalSettings"]["about"]
            )
    catalog = generate_catalog(
        render(result.apps[Variant.SINGLE]).encode(),
        render(result.apps[Variant.DUAL]).encode(),
        parse_composition_policy(current_configuration.policy),
    ).decode()
    ports_section = catalog.split("<summary>PC Ports</summary>", 1)[1].split(
        "</details>", 1
    )[0]
    for _, name in expected.values():
        rows = [line for line in catalog.splitlines() if name in line]
        assert len(rows) == 1
        assert rows[0].startswith(f"| {name} | - | <a href=")
        assert rows[0] in ports_section
