from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from omnipack.catalog import generate_catalog
from omnipack.composition_policy import parse_composition_policy
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
# Each curated extra is the only extra in its family and wins the single-screen
# pack by source precedence. No build or offline check fails if single stops
# serving one, so these expectations are that guard.
CURATED_SINGLE_WINNERS = {
    "package:com.aurora.store": (
        "com.aurora.store",
        "https://gitlab.com/AuroraOSS/AuroraStore",
    ),
    "package:com.karin.idTech4Amm": (
        "com.karin.idTech4Amm",
        "https://github.com/glKarin/com.n0n3m4.diii4a",
    ),
    "package:is.xyz.vcmi": ("is.xyz.vcmi", "https://github.com/vcmi/vcmi"),
    "package:com.github.bvschaik.julius": (
        "com.github.bvschaik.julius",
        "https://github.com/bvschaik/julius",
    ),
    "package:su.xash.engine.test": (
        "su.xash.engine.test",
        "https://github.com/FWGS/xash3d-fwgs",
    ),
    "app:ghostship": (
        "dev.net64.ghostship",
        "https://github.com/HarbourMasters/Ghostship",
    ),
    "app:gen1recomp": (
        "com.theboisclub.pokemonred",
        "https://github.com/bryanthaboi/gen1recomp",
    ),
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
            item.source for item in result.report.selections if item.variant is variant
        } == {"extras"}
        expected = {app.id: app.additional_settings for app in maintained}
        for app in chosen:
            assert app.data["additionalSettings"] == expected[app.data["id"]]


def single_selections(
    extras_config: list[dict[str, object]], tmp_path: Path
) -> dict[str, tuple[str, str, str, str]]:
    """Compose the committed configuration over the captured upstream catalogs."""
    higher = captured_higher(extras_config)
    result = _compose_with_codm_catalog(_committed_codm_catalog(), tmp_path, higher)
    return {
        selection.family: (
            selection.effective_id,
            normalize_project_url(selection.url),
            selection.reason,
            selection.source,
        )
        for selection in result.report.selections
        if selection.variant is Variant.SINGLE
    }


def test_committed_configuration_selects_each_curated_extra_in_single(
    tmp_path: Path,
) -> None:
    selections = single_selections(read(ROOT / "config/extras.json"), tmp_path)
    for family, (package_id, url) in CURATED_SINGLE_WINNERS.items():
        assert selections.get(family) == (
            package_id,
            normalize_project_url(url),
            "source",
            "extras",
        ), family


@pytest.mark.parametrize(
    "family", sorted(CURATED_SINGLE_WINNERS), ids=lambda family: family
)
def test_curated_single_guard_fails_when_its_extra_becomes_dual_screen(
    tmp_path: Path, family: str
) -> None:
    package_id, url = CURATED_SINGLE_WINNERS[family]
    extras_config = read(ROOT / "config/extras.json")
    [entry] = [item for item in extras_config if item["id"] == package_id]
    entry["dualScreen"] = True
    selected = single_selections(extras_config, tmp_path).get(family)
    assert (
        selected is None
        or selected[:2] != (package_id, normalize_project_url(url))
        or selected[3] != "extras"
    )


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
        assert (app.data["url"], app.data["name"]) == expected[app.data["id"]]
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
