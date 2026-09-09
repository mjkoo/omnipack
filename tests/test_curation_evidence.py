from __future__ import annotations

import pytest

from tests.test_curation import FIXTURES, curated, read, resolve


def test_selected_candidates_have_manifest_evidence_and_known_identity_mismatches():
    manifests = read(FIXTURES / "manifests.json")["assets"]
    by_url = {manifest["url"]: manifest for manifest in manifests}
    assert len(by_url) == len(manifests)
    baseline = read(FIXTURES / "baseline-apps.json")
    mismatches = set()
    selected_urls = set()
    for variant, apps in curated().items():
        originals = {app["url"].lower(): app for app in baseline[variant]}
        for app in apps:
            original = originals.get(app["url"].lower())
            if original is not None:
                expected_id = (
                    "com.ctrnative"
                    if original["id"] == "com.simon358.ctrnative"
                    else original["id"]
                )
                assert app["id"] == expected_id
            for candidate in resolve(app).candidates:
                manifest = by_url[candidate.url]
                selected_urls.add(candidate.url)
                assert manifest["id"] == (
                    original["id"] if original is not None else app["id"]
                )
                if manifest["package"] != app["id"]:
                    mismatches.add((app["id"], manifest["package"]))
    assert mismatches == {
        ("com.sergiomanzur.sotnrecomp", "com.blacklabelhq.sotn"),
        ("com.waterdish.shipwright", "com.dishii.soh"),
        ("com.winlator.ludashi", "com.winlator.vanilla"),
    }
    xendroid_urls = {m["url"] for m in manifests if m["id"] == "xendroid.compose"}
    assert set(by_url) == selected_urls | xendroid_urls


@pytest.mark.parametrize("version", ["0b11201", "c4f6863"])
def test_xendroid_observations_match_release_assets_and_hash_versions(version):
    app = next(a for a in curated()["single"] if a["id"] == "xendroid.compose")
    records = read(FIXTURES / "releases.json")["sources"][app["url"]]
    release = next(r for r in records if r["tag_name"] == f"XenDroid-{version}")
    result = resolve(app, [release])
    assert result.effective_version == f"XenDroid-{version}"
    assert len(result.candidates) == 1
    manifests = read(FIXTURES / "manifests.json")["assets"]
    observed = [m for m in manifests if m["url"] == result.candidates[0].url]
    assert len(observed) == 1
    manifest = observed[0]
    assert (manifest["id"], manifest["package"], manifest["versionName"]) == (
        app["id"],
        app["id"],
        version,
    )
    assert manifest["effective"] == result.effective_version
    assert manifest["versionCode"] == 1


@pytest.mark.parametrize("variant", ["single", "dual"])
def test_cinderbox_selected_apk_has_expected_package_and_version(variant):
    app = next(a for a in curated()[variant] if a["id"] == "com.game.cinderbox")
    result = resolve(app)
    assert len(result.candidates) == 1
    manifests = read(FIXTURES / "manifests.json")["assets"]
    observed = [m for m in manifests if m["url"] == result.candidates[0].url]
    assert len(observed) == 1
    manifest = observed[0]
    assert manifest["package"] == app["id"] == "com.game.cinderbox"
    assert manifest["versionName"] == result.effective_version == "0.8.1"
    assert manifest["effective"] == result.effective_version
    assert manifest["versionCode"] == 113
