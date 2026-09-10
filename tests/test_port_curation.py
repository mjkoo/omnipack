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
from omnipack.resolution.gitlab import resolve_gitlab
from omnipack.resolution.types import ResolutionError
from omnipack.sources import IngestionReport, codm
from omnipack.sources.extras import fetch
from tests.test_composition_baseline import CapturedPackageResolver
from tests.test_resolution_github import GitHubTransport
from tests.test_resolution_gitlab import FakeHttp as GitLabHttp
from tests.test_sources import FakeHttp as SourceHttp

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
            Provenance("bboi", app.url),
            {"apkFilterRegEx": "wrong.apk", "versionDetection": True},
            {},
            frozenset({Variant.DUAL}),
            True,
            "bboi-dual-asset",
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
    unpinned = deepcopy(document)
    unpinned["pins"] = []
    ordinary = compose(
        [*maintained, *duplicates],
        [],
        [],
        [],
        policy=parse_composition_policy(unpinned),
    )
    assert all(
        app.provenance.source == "extras" for app in ordinary.apps[Variant.SINGLE]
    )
    assert all(app.provenance.source == "bboi" for app in ordinary.apps[Variant.DUAL])
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
        expected = {app.id: app.additional_settings for app in maintained}
        for app in chosen:
            assert app.data["additionalSettings"] == expected[app.data["id"]]


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


@pytest.mark.parametrize("package_id", sorted(PORT_IDS))
def test_captured_release_filters_select_manifest_inspected_assets(package_id):
    app = next(app for app in extras() if app.id == package_id)
    captures = read(FIXTURE.with_name("port-releases.json"))["entries"]
    capture = next(item for item in captures if item["sourceUrl"] == app.url)
    release = capture["release"]
    data = {**app.raw, "url": app.url, "additionalSettings": app.additional_settings}
    if app.source_type.value == "GitLab":
        api = "https://gitlab.com/api/v4/projects/AuroraOSS%2FAuroraStore"
        assert release["assets"]["links"] == []
        assert "AuroraStore-hw-4.8.4.apk" in release["description"]
        assert "AuroraStore-preload-4.8.4.apk" in release["description"]
        result = resolve_gitlab(
            data,
            GitLabHttp(
                {
                    api: {"id": capture["projectId"]},
                    api + "/releases?per_page=100": [release],
                }
            ),
        )
    else:
        api = app.url.replace("https://github.com/", "https://api.github.com/repos/")
        responses = {
            api + "/releases?per_page=100": [release],
            api + "/releases/latest": release,
        }
        result = resolve_github(
            data,
            HttpClient(HttpConfig({}), retries=0, transport=GitHubTransport(responses)),
        )
    manifests = [
        item for item in read(FIXTURE)["entries"] if item["sourceUrl"] == app.url
    ]
    assert {candidate.name for candidate in result.candidates} == {
        item["asset"] for item in manifests
    }
    assert {item["packageId"] for item in manifests} == {app.id}
    assert {item["release"] for item in manifests} == {result.raw_version}
    if package_id == "is.xyz.vcmi":
        # The resolver returns all eligible ABIs; Obtainium chooses on-device.
        selected_names = {candidate.name for candidate in result.candidates}
        assert {
            tuple(item["abis"]) for item in manifests if item["asset"] in selected_names
        } == {("arm64-v8a",), ("armeabi-v7a",), ("x86_64",)}
        assert app.additional_settings["autoApkFilterByArch"] is True
    if package_id == "com.karin.idTech4Amm":
        names = {asset["name"] for asset in release["assets"]}
        assert any("_arm64" in name for name in names)
        assert any("_armv7" in name for name in names)
        assert result.effective_version == "v1.1.0harmattan72"
        assert manifests[0]["versionName"] == "1.1.0harmattan72lindaiyu"


def test_xash_scans_past_unrelated_channels_without_cross_channel_fallback():
    capture = next(
        item
        for item in read(FIXTURE.with_name("port-releases.json"))["entries"]
        if item["sourceUrl"] == "https://github.com/FWGS/xash3d-fwgs"
    )
    master = capture["release"]
    other = deepcopy(master)
    other.update(
        tag_name="continuous-freevgui", name="Xash3D FWGS Continuous freevgui Build"
    )
    for asset in other["assets"]:
        asset["updated_at"] = "2099-01-01T00:00:00Z"
    baseline = _resolve_xash([master])
    assert (
        _resolve_xash([other, master]).effective_version == baseline.effective_version
    )
    app = next(app for app in extras() if app.id == "su.xash.engine.test")
    assert app.additional_settings["fallbackToOlderReleases"] is True
    for releases in ([other], []):
        with pytest.raises(ResolutionError):
            _resolve_xash(releases)
    missing_apk = deepcopy(master)
    missing_apk["assets"] = [
        asset
        for asset in master["assets"]
        if asset["name"] != "xash3d-fwgs-android.apk"
    ]
    with pytest.raises(ResolutionError):
        _resolve_xash([other, missing_apk])
    changed_platform = deepcopy(master)
    for asset in changed_platform["assets"]:
        if asset["name"] != "xash3d-fwgs-android.apk":
            asset["updated_at"] = "2099-01-01T00:00:00Z"
    assert (
        _resolve_xash([other, changed_platform]).effective_version
        == baseline.effective_version
    )


def test_hollow_knight_source_composition_preserves_dual_only_catalog():
    config = read(ROOT / "config/sources.json")["codm"]
    source = (ROOT / "tests/fixtures/codm-readme.md").read_text()
    source = "\n".join(
        line
        for line in source.splitlines()
        if any(
            marker in line
            for marker in (
                "| Project",
                "|---",
                "| ---",
                "github.com/igawa6/dualsouls",
                "github.com/jakobkhansen/SilksongAndroid",
            )
        )
    )
    report = IngestionReport()
    candidates = codm.fetch(
        SourceHttp({config["readme_url"]: source}),
        config,
        CapturedPackageResolver(),
        [],
        report,
    )
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
    result = compose(selected, [], overlays, [], policy=policy)
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
        render(result.apps[Variant.SINGLE], {}).encode(),
        render(result.apps[Variant.DUAL], {}).encode(),
        policy,
    ).decode()
    for _, name in expected.values():
        rows = [line for line in catalog.splitlines() if name in line]
        assert len(rows) == 1
        assert rows[0].startswith(f"| {name} | - | <a href=")
