from __future__ import annotations

import pytest

from tests.test_curation import FIXTURES, curated, effective_id, read


def test_manifest_evidence_records_known_identity_relationships() -> None:
    manifests = read(FIXTURES / "manifests.json")["assets"]
    by_url = {manifest["url"]: manifest for manifest in manifests}
    assert len(by_url) == len(manifests)
    baseline = read(FIXTURES / "baseline-apps.json")
    configured = {app["url"]: app for apps in curated().values() for app in apps}
    for variant, originals in baseline.items():
        actual = {app["url"].lower(): app for app in curated()[variant]}
        for original in originals:
            assert actual[original["url"].lower()]["id"] == effective_id(original)
    assert {
        (record["id"], record["package"])
        for record in manifests
        if record["package"] != record["id"]
    } == {
        ("com.sergiomanzur.sotnrecomp", "com.blacklabelhq.sotn"),
        ("com.simon358.ctrnative", "com.ctrnative"),
        ("com.waterdish.shipwright", "com.dishii.soh"),
        ("com.winlator.ludashi", "com.winlator.vanilla"),
    }
    ludashi = next(
        app for app in configured.values() if app["id"] == "com.winlator.ludashi"
    )
    assert ludashi["allowIdChange"] is True


@pytest.mark.parametrize("version", ["0b11201", "c4f6863"])
def test_xendroid_dated_observations_preserve_hash_versions(version: str) -> None:
    app = next(a for a in curated()["single"] if a["id"] == "xendroid.compose")
    manifests = read(FIXTURES / "manifests.json")["assets"]
    observed = [
        item
        for item in manifests
        if item["id"] == app["id"] and item["versionName"] == version
    ]
    assert len(observed) == 1
    assert observed[0]["package"] == app["id"]
    assert observed[0]["effective"] == f"XenDroid-{version}"
    assert observed[0]["versionCode"] == 1


@pytest.mark.parametrize("variant", ["single", "dual"])
def test_cinderbox_dated_observation_matches_curated_identity(variant: str) -> None:
    app = next(a for a in curated()[variant] if a["id"] == "com.game.cinderbox")
    manifests = read(FIXTURES / "manifests.json")["assets"]
    [observed] = [item for item in manifests if item["id"] == app["id"]]
    assert observed["package"] == app["id"]
    assert observed["versionName"] == "0.8.1"
    assert observed["effective"] == "0.8.1"
    assert observed["versionCode"] == 113
