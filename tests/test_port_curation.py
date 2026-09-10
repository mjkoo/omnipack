from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from omnipack.catalog import generate_catalog
from omnipack.composition_policy import parse_composition_policy
from omnipack.http import HttpClient, HttpConfig
from omnipack.merge import compose
from omnipack.model import App, Provenance, Variant
from omnipack.overlay import ComposedApp, apply_overlay, parse_overlay
from omnipack.render import render
from omnipack.resolution.github import resolve_github
from omnipack.resolution.types import ResolutionError
from omnipack.sources.extras import fetch
from tests.test_resolution_github import GitHubTransport

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/curation/port-manifests.json"
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


def test_manifest_evidence_matches_curated_identity_and_release_policy():
    evidence = read(FIXTURE)["entries"]
    assert len(evidence) == 7
    assert all(len(item["sha256"]) == 64 for item in evidence)
    assert {item["packageId"] for item in evidence} == PORT_IDS
    idtech = next(item for item in evidence if item["project"] == "idTech4A++")
    assert idtech["release"] == "v1.1.0harmattan72"
    assert idtech["versionName"] == "1.1.0harmattan72lindaiyu"
    vcmi = [item for item in evidence if item["project"] == "VCMI"]
    assert {tuple(item["abis"]) for item in vcmi} == {
        ("arm64-v8a",),
        ("armeabi-v7a",),
        ("x86_64",),
    }


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


def test_composition_pins_keep_extras_when_dual_preferred_duplicates_appear():
    maintained = [app for app in extras() if app.id in PORT_IDS]
    duplicates = [
        App(
            app.id,
            app.url,
            "upstream duplicate",
            app.source_type,
            app.categories,
            Variant.DUAL,
            Provenance("codm2000", app.url),
            {},
            {},
            frozenset({Variant.DUAL}),
            True,
            "codm-generated",
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
    document["history"] = []
    result = compose(
        [*maintained, *duplicates],
        [],
        [],
        [],
        policy=parse_composition_policy(document),
    )
    for variant in Variant:
        chosen = [app for app in result.apps[variant] if app.data["id"] in PORT_IDS]
        assert len(chosen) == len(PORT_IDS)
        assert all(app.provenance.source == "extras" for app in chosen)


def _resolve_xash(releases):
    app = next(app for app in extras() if app.id == "su.xash.engine.test")
    data = deepcopy(app.raw)
    data.update(url=app.url, additionalSettings=app.additional_settings)
    api = "https://api.github.com/repos/FWGS/xash3d-fwgs"
    http = HttpClient(
        HttpConfig({}),
        retries=0,
        transport=GitHubTransport({api + "/releases?per_page=100": releases}),
    )
    return resolve_github(data, http)


def test_xash_uses_only_continuous_android_asset_timestamp():
    base = {
        "tag_name": "continuous",
        "name": "Xash3D FWGS Continuous master Build",
        "draft": False,
        "prerelease": True,
        "published_at": "2026-09-09T16:21:08Z",
        "assets": [
            {
                "name": "xash3d-fwgs-android.apk",
                "browser_download_url": "https://example.test/android.apk",
                "updated_at": "2026-09-09T16:21:02Z",
            },
            {
                "name": "xash3d-fwgs-linux-amd64.tar.gz",
                "browser_download_url": "https://example.test/linux",
                "updated_at": "2099-01-01T00:00:00Z",
            },
        ],
    }
    first = _resolve_xash([base])
    changed = deepcopy(base)
    changed_assets = changed["assets"]
    assert isinstance(changed_assets, list)
    assert isinstance(changed_assets[0], dict)
    changed_assets[0]["updated_at"] = "2026-09-10T16:21:02Z"
    second = _resolve_xash([changed])
    assert first.raw_version == second.raw_version == "continuous"
    assert first.effective_version < second.effective_version
    assert [item.name for item in first.candidates] == ["xash3d-fwgs-android.apk"]


def test_xash_does_not_fall_back_to_another_channel_or_missing_apk():
    other = {
        "tag_name": "continuous-freevgui",
        "name": "Xash3D FWGS Continuous freevgui Build",
        "draft": False,
        "prerelease": True,
        "published_at": "2099-01-01T00:00:00Z",
        "assets": [
            {
                "name": "xash3d-fwgs-android.apk",
                "browser_download_url": "https://example.test/other.apk",
                "updated_at": "2099-01-01T00:00:00Z",
            }
        ],
    }
    missing = {
        "tag_name": "continuous",
        "name": "Xash3D FWGS Continuous master Build",
        "draft": False,
        "prerelease": True,
        "published_at": "2026-09-09T16:21:08Z",
        "assets": [],
    }
    with pytest.raises(ResolutionError, match="no release qualifies"):
        _resolve_xash([missing, other])


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
    app = ComposedApp(Variant.DUAL, Provenance("codm2000", url), original)
    overlay = parse_overlay(read(ROOT / "config/overlay.json"), "common overlay")
    [curated] = apply_overlay([app], overlay)
    assert curated.data["id"] == package_id
    assert curated.data["url"] == url
    assert curated.data["name"] == name
    assert curated.data["categories"] == ["PC Ports"]
    assert limitation in curated.data["additionalSettings"]["about"]
    assert "user-supplied" in curated.data["additionalSettings"]["about"]
    assert curated.variant is Variant.DUAL
    catalog = generate_catalog(
        render([], {}).encode(),
        render([curated], {}).encode(),
        parse_composition_policy(read(ROOT / "config/composition.json")),
    )
    assert name.encode() in catalog
    assert b"PC Ports" in catalog
