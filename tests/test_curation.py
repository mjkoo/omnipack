from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from obtainium_pack.http import HttpClient, HttpConfig
from obtainium_pack.live import VersionClass, classify_version
from obtainium_pack.merge import compose
from obtainium_pack.model import Variant
from obtainium_pack.render import render
from obtainium_pack.resolution.github import resolve_github
from obtainium_pack.resolution.types import ResolutionError
from obtainium_pack.sources.common import normalize_record
from obtainium_pack.sources.extras import fetch
from tests.test_resolution_github import GitHubTransport

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


def curated():
    baseline = read(FIXTURES / "baseline-apps.json")
    candidates = [
        normalize_record(a, source="rjny", variant=Variant(v))
        for v, apps in baseline.items()
        for a in apps
    ]
    candidates.extend(fetch(read(ROOT / "config/extras.json")))
    result = compose(candidates, [], read(ROOT / "config/overlay.json"), {})
    return {v.value: json.loads(render(result.apps[v], {}))["apps"] for v in Variant}


def resolve(app, releases=None):
    records = deepcopy(
        releases
        if releases is not None
        else read(FIXTURES / "releases.json")["sources"][app["url"]]
    )
    api = app["url"].replace("https://github.com/", "https://api.github.com/repos/")
    transport = GitHubTransport(
        {
            api + "/releases?per_page=100": records,
            api + "/releases/latest": next(r for r in records if not r["prerelease"]),
        }
    )
    return resolve_github(
        app, HttpClient(HttpConfig({}), retries=0, transport=transport)
    )


def test_policies_preserve_existing_entries_and_asset_selection():
    baseline = read(FIXTURES / "baseline-apps.json")
    apps = curated()
    warnings_before = 0
    for variant, originals in baseline.items():
        actual = {a["id"]: a for a in apps[variant]}
        assert set(actual) == {a["id"] for a in originals} | {"com.game.cinderbox"}
        for old in originals:
            new = actual[old["id"]]
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
            assert {k: v for k, v in new.items() if k != "additionalSettings"} == {
                k: v for k, v in old.items() if k != "additionalSettings"
            }
            before, after = resolve(old), resolve(new)
            assert before.candidates == after.candidates
            # Count the historical dotted-only format baseline, including RPCSX.
            warnings_before += (
                classify_version("GitHub", old_settings, before)[1] is not None
                or old["id"] == "net.rpcsx"
            )
            classification, warning = classify_version("GitHub", expected, after)
            assert warning is None
            if old["id"] in SOURCE_IDS:
                assert classification is VersionClass.DETECTION_DISABLED
                assert after.effective_version == before.raw_version
            elif old["id"] == "info.cemu.cemu":
                assert (
                    after.effective_version
                    == {"single": "0.5", "dual": "0.5.2"}[variant]
                )
            elif old["id"] == "net.rpcsx":
                assert after.effective_version == "v20250425"
    assert warnings_before == 23


@pytest.mark.parametrize("variant", ["single", "dual"])
def test_cinderbox_excludes_newer_dependency_prerelease(variant):
    matches = [a for a in curated()[variant] if a["id"] == "com.game.cinderbox"]
    assert len(matches) == 1
    app = matches[0]
    assert (app["name"], app["author"], app["categories"]) == (
        "Cinderbox",
        "Ekyso",
        ["PC Ports"],
    )
    settings = json.loads(app["additionalSettings"])
    assert settings["versionDetection"] and not settings["trackOnly"]
    assert not settings["includePrereleases"] and not settings["releaseDateAsVersion"]
    assert (
        not settings["versionExtractionRegEx"] and not settings["releaseTitleAsVersion"]
    )
    records = read(FIXTURES / "releases.json")["sources"][app["url"]]
    dependency = deepcopy(next(r for r in records if r["prerelease"]))
    dependency["published_at"] = "2099-01-01T00:00:00Z"
    dependency["assets"] = deepcopy(records[0]["assets"])
    result = resolve(app, [dependency, *records])
    assert result.effective_version == "0.8.1"
    assert [a.name for a in result.candidates] == ["Cinderbox-v0.8.1.apk"]


@pytest.mark.parametrize(
    "package_id, expected",
    [
        ("com.aure.banjorecomp", ["0.1.2", "0.1.1"]),
        ("com.sergiomanzur.sotnrecomp", ["0.10.1", "0.10", "0.9.1", "0.9"]),
        ("com.waterdish.shipwright", ["v9.0.2P2", "v9.0.2P1", "v9.0.2"]),
    ],
)
def test_release_histories_preserve_distinct_versions(package_id, expected):
    app = next(a for a in curated()["single"] if a["id"] == package_id)
    records = read(FIXTURES / "releases.json")["sources"][app["url"]][: len(expected)]
    for record in records:
        record["prerelease"] = False
    assert [resolve(app, [r]).effective_version for r in records] == expected
    if package_id in NUMERIC_IDS:
        records[0]["tag_name"] = "rolling"
        with pytest.raises(ResolutionError, match="did not match"):
            resolve(app, [records[0]])
