from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from omnipack.catalog import generate_catalog
from omnipack.composition_policy import candidate_selector, parse_composition_policy
from omnipack.merge import compose
from omnipack.model import App, Provenance, Variant
from omnipack.overlay import ComposedApp, apply_overlay, parse_overlay
from omnipack.render import render
from omnipack.sources import codm
from omnipack.sources.extras import fetch
from omnipack.urls import normalize_project_url
from tests.test_source_generation_fixtures import (
    _committed_codm_catalog,
    _compose_with_codm_catalog,
    captured_higher,
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


def designated_single_winners(
    extras_config: list[dict[str, Any]], policy_document: dict[str, Any]
) -> dict[str, tuple[str, str]]:
    """Map each designated curated extra's family to its expected single winner.

    An extra is designated when it is eligible for the single-screen pack and
    no single pin selects for its family. It then has the highest source
    precedence in its family, and no build or offline check fails if single
    stops serving it. Its family and effective package id follow the candidate
    rule composition applies to it, so an extra that composition no longer
    selects still names its family. The winner is (effective id, normalized
    project URL).
    """
    policy = parse_composition_policy(policy_document)
    rules = {rule.match.key: rule for rule in policy.candidate_rules}
    single_pinned = {pin.family for pin in policy.pins if pin.variant is Variant.SINGLE}
    designated: dict[str, tuple[str, str]] = {}
    for app in fetch(extras_config):
        if Variant.SINGLE not in app.eligibility:
            continue
        rule = rules.get(candidate_selector(app).key)
        effective_id = (rule.package_id if rule else None) or app.id
        family = (rule.family if rule else None) or f"package:{effective_id}"
        if family not in single_pinned:
            designated[family] = (effective_id, normalize_project_url(app.url))
    return designated


def unpinned_designated_families(
    extras_config: list[dict[str, Any]], policy_document: dict[str, Any]
) -> dict[str, str]:
    """Map each designated family whose extra no pin selects to its package id.

    Composition accepts a denial of such an extra's package id, since it
    rejects only a denial that removes a pinned candidate.
    """
    pinned_ids = {
        package_id
        for package_id, _ in parse_composition_policy(
            policy_document
        ).projected_pins.values()
    }
    return {
        family: package_id
        for family, (package_id, _) in designated_single_winners(
            extras_config, policy_document
        ).items()
        if package_id not in pinned_ids
    }


def curated_single_mismatches(
    extras_config: list[dict[str, Any]],
    tmp_path: Path,
    *,
    policy_document: dict[str, Any] | None = None,
    denials: list[dict[str, str]] | None = None,
) -> set[str]:
    """Name each designated family whose single-screen winner is not its extra.

    Composes the committed configuration, with any given policy and added
    denials, over the captured upstream catalogs.
    """
    if policy_document is None:
        policy_document = read(ROOT / "config/composition.json")
    higher = captured_higher(extras_config)
    result = _compose_with_codm_catalog(
        _committed_codm_catalog(),
        tmp_path,
        higher,
        policy_document=policy_document,
        denials=denials,
    )
    selections = {
        selection.family: (
            selection.effective_id,
            normalize_project_url(selection.url),
            selection.reason,
            selection.source,
        )
        for selection in result.report.selections
        if selection.variant is Variant.SINGLE
    }
    return {
        family
        for family, (package_id, url) in designated_single_winners(
            extras_config, policy_document
        ).items()
        if selections.get(family) != (package_id, url, "source", "extras")
    }


def test_committed_configuration_selects_each_curated_extra_in_single(
    tmp_path: Path,
) -> None:
    extras_config = read(ROOT / "config/extras.json")
    assert curated_single_mismatches(extras_config, tmp_path) == set()


def test_designated_single_set_is_derived_from_extras_and_single_pins() -> None:
    extras_config = read(ROOT / "config/extras.json")
    policy_document = read(ROOT / "config/composition.json")
    designated = designated_single_winners(extras_config, policy_document)
    assert {"package:com.game.cinderbox", "package:809443320"} <= set(designated)

    [cinderbox] = [e for e in extras_config if e["id"] == "com.game.cinderbox"]
    pinned = deepcopy(policy_document)
    pinned["pins"].append(
        {
            "family": "package:com.game.cinderbox",
            "variant": "single",
            "match": {
                "source": "extras",
                "origin": "extras",
                "id": cinderbox["id"],
                "url": cinderbox["url"],
            },
            "rationale": "Test pin.",
        }
    )
    assert set(designated_single_winners(extras_config, pinned)) == set(designated) - {
        "package:com.game.cinderbox"
    }

    cinderbox["dualScreen"] = True
    assert "package:com.game.cinderbox" not in designated_single_winners(
        extras_config, policy_document
    )


UNPINNED_DESIGNATED = unpinned_designated_families(
    read(ROOT / "config/extras.json"), read(ROOT / "config/composition.json")
)


@pytest.mark.parametrize("family", sorted(UNPINNED_DESIGNATED))
@pytest.mark.parametrize(
    "correction",
    [
        {"packageId": "com.example.corrected"},
        {"family": "app:corrected", "packageId": "com.example.corrected"},
    ],
    ids=["package-id", "family-and-package-id"],
)
def test_designated_family_follows_a_package_id_correction(
    family: str, correction: dict[str, str], tmp_path: Path
) -> None:
    extras_config = read(ROOT / "config/extras.json")
    policy_document = read(ROOT / "config/composition.json")
    package_id = UNPINNED_DESIGNATED[family]
    [entry] = [e for e in extras_config if e["id"] == package_id]
    match = {
        "source": "extras",
        "origin": "extras",
        "id": entry["id"],
        "url": entry["url"],
    }
    policy_document["candidates"] = [
        rule
        for rule in policy_document["candidates"]
        if (rule["match"]["source"], rule["match"]["origin"], rule["match"]["id"])
        != ("extras", "extras", entry["id"])
    ]
    policy_document["candidates"].append(
        {"match": match, **correction, "rationale": "Test correction."}
    )
    expected = correction.get("family", "package:com.example.corrected")

    designated = designated_single_winners(extras_config, policy_document)
    assert family not in designated
    assert designated[expected] == (
        "com.example.corrected",
        normalize_project_url(entry["url"]),
    )
    assert (
        curated_single_mismatches(
            extras_config, tmp_path, policy_document=policy_document
        )
        == set()
    )


@pytest.mark.parametrize("family", sorted(UNPINNED_DESIGNATED))
def test_curated_single_guard_fails_when_a_designated_extra_is_denied(
    family: str, tmp_path: Path
) -> None:
    extras_config = read(ROOT / "config/extras.json")
    denial = {"id": UNPINNED_DESIGNATED[family], "reason": "Test displacement."}
    assert curated_single_mismatches(extras_config, tmp_path, denials=[denial]) == {
        family
    }


@pytest.mark.parametrize(
    "package_id,url,name,limitation",
    [
        (
            "igawa6.dualsouls",
            "https://github.com/igawa6/dualsouls",
            "Hollow Knight: Dual Souls",
            "second screen",
        ),
        (
            "com.jakobkhansen.silksong",
            "https://github.com/jakobkhansen/SilksongAndroid",
            "Hollow Knight: Silksong",
            "Android 13",
        ),
    ],
)
def test_hollow_knight_overlay_preserves_dual_identity_and_adds_setup(
    package_id, url, name, limitation
):
    original = {
        "id": package_id,
        "url": url,
        "name": "raw project name",
        "author": "upstream",
        "overrideSource": "GitHub",
        "categories": ["Games"],
        "additionalSettings": {},
    }
    app = ComposedApp(f"package:{package_id}", original)
    overlay = parse_overlay(read(ROOT / "config/overlay.json"), "overlay")
    [curated] = apply_overlay([app], overlay)
    assert curated.data["id"] == package_id
    assert curated.data["url"] == url
    assert curated.data["name"] == name
    assert curated.data["categories"] == ["PC Ports"]
    assert limitation in curated.data["additionalSettings"]["about"]
    assert "user-supplied" in curated.data["additionalSettings"]["about"]
    catalog = generate_catalog(
        render([]).encode(),
        render([curated]).encode(),
        parse_composition_policy(read(ROOT / "config/composition.json")),
    )
    assert name.encode() in catalog
    assert b"PC Ports" in catalog


def test_hollow_knight_source_composition_preserves_dual_only_catalog():
    config = read(ROOT / "config/sources.json")["codm"]
    candidates = codm.fetch(ROOT, config, [])
    ids = {"igawa6.dualsouls", "com.jakobkhansen.silksong"}
    selected = [app for app in candidates if app.id in ids]
    assert {app.id for app in selected} == ids
    assert all(app.eligibility == frozenset({Variant.DUAL}) for app in selected)
    policy_document = read(ROOT / "config/composition.json")
    policy_document["candidates"] = [
        rule for rule in policy_document["candidates"] if rule["match"]["id"] in ids
    ]
    policy_document["pins"] = [
        rule for rule in policy_document["pins"] if rule["match"]["id"] in ids
    ]
    policy = parse_composition_policy(policy_document)
    overlays = [
        rule for rule in read(ROOT / "config/overlay.json") if rule["id"] in ids
    ]
    result = compose(selected, [], overlays, policy=policy)
    assert result.apps[Variant.SINGLE] == []
    assert len(result.apps[Variant.DUAL]) == 2
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
    for app in result.apps[Variant.DUAL]:
        url, name = expected[app.data["id"]]
        # Overlay records find their targets by normalized project URL.
        assert normalize_project_url(app.data["url"]) == normalize_project_url(url)
        assert app.data["name"] == name
        assert app.data["categories"] == ["PC Ports"]
        if app.data["id"] == "com.jakobkhansen.silksong":
            assert "Android 13 only" in app.data["additionalSettings"]["about"]
            assert (
                "Android 15 is unsupported" in app.data["additionalSettings"]["about"]
            )
    catalog = generate_catalog(
        render(result.apps[Variant.SINGLE]).encode(),
        render(result.apps[Variant.DUAL]).encode(),
        policy,
    ).decode()
    for _, name in expected.values():
        rows = [line for line in catalog.splitlines() if name in line]
        assert len(rows) == 1
        assert rows[0].startswith(f"| {name} | - | <a href=")
