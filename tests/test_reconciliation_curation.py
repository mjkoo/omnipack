from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

import pytest

from omnipack.composition_policy import parse_composition_policy
from omnipack.http import HttpClient, HttpConfig
from omnipack.merge import compose
from omnipack.model import Variant
from omnipack.render import render
from omnipack.resolution.github import resolve_github
from omnipack.resolution.types import ResolutionError
from omnipack.sources import IngestionReport, bboi, codm, rjny
from omnipack.sources.extras import fetch as fetch_extras
from tests.test_composition_baseline import CapturedPackageResolver
from tests.test_resolution_github import GitHubTransport
from tests.test_sources import FakeHttp

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/curation/reconciliation.json"
OBSERVATIONS = ROOT / "tests/fixtures/reconciliation/selected-observations.json"
CTR_EVIDENCE = ROOT / "tests/fixtures/curation/ctr.json"
SNAPSHOTS = ROOT / "tests/fixtures/reconciliation"


def read(path: Path):
    return json.loads(path.read_text())


def test_reconciliation_evidence_is_real_and_configuration_is_complete():
    evidence = read(FIXTURE)
    observations = read(OBSERVATIONS)
    ctr = read(CTR_EVIDENCE)
    document = read(ROOT / "config/composition.json")
    rules = document["candidates"]

    expected = {
        (record["original_id"], item["package"], record["source"])
        for record in observations
        for item in record["observations"]
    }
    expected.add(
        (
            ctr["variants"]["single"]["original_id"],
            ctr["variants"]["single"]["effective_id"],
            ctr["variants"]["single"]["source"],
        )
    )
    assert set(map(tuple, evidence["identity_corrections"])) == expected
    for original, effective, url in expected:
        matches = [
            rule
            for rule in rules
            if rule["match"]["id"] == original and rule["match"]["url"] == url
        ]
        assert matches
        assert {rule.get("packageId") for rule in matches} == {effective}
        assert any(
            record["id"] == original and record["url"] == url
            for record in document["history"]
        )

    ghost = evidence["ghostship"]
    assert len(ghost["asset_sha256"]) == len(ghost["member_sha256"]) == 64
    assert ghost["package"] == "dev.net64.ghostship"
    assert ctr["observed_at"] == evidence["observed_at"] == "2026-09-10"
    assert set(ctr["variants"]) == {"single", "dual"}
    for item in ctr["variants"].values():
        [asset] = item["release"]["assets"]
        assert item["manifest"]["package"] == item["effective_id"] == "com.ctrnative"
        assert len(item["manifest"]["sha256"]) == 64
        assert asset["browser_download_url"].startswith(item["source"] + "/releases/")
        assert item["release"]["tag_name"] == item["source_version"]


def candidates(refresh: int):
    sources = read(ROOT / "config/sources.json")
    release = read(SNAPSHOTS / "bboi-release.json")
    standard = read(SNAPSHOTS / "bboi-standard.json")
    dual = read(SNAPSHOTS / "bboi-dual.json")
    rjny_document = read(SNAPSHOTS / "rjny.json")
    for document in (standard, dual, rjny_document):
        for app in document["apps"]:
            app["name"] = f"{app['name']} refresh {refresh}"
    standard_url, dual_url = (
        asset["browser_download_url"] for asset in release["assets"]
    )
    bboi_api = (
        "https://codeberg.org/api/v1/repos/"
        f"{sources['bboi']['codeberg_repo']}/releases/latest"
    )
    rjny_url = (
        f"https://raw.githubusercontent.com/{sources['rjny']['repo']}/"
        f"{sources['rjny']['branch']}/{sources['rjny']['path']}"
    )
    http = FakeHttp(
        {
            bboi_api: json.dumps(release),
            standard_url: json.dumps(standard),
            dual_url: json.dumps(dual),
            rjny_url: json.dumps(rjny_document),
            sources["codm"]["readme_url"]: (
                SNAPSHOTS / "codm-relevant-readme.md"
            ).read_text(),
        }
    )
    higher = bboi.fetch(http, sources["bboi"]) + rjny.fetch(http, sources["rjny"])
    extras = fetch_extras(read(ROOT / "config/extras.json"))
    report = IngestionReport()
    generated = codm.fetch(
        http,
        sources["codm"],
        CapturedPackageResolver(),
        [*higher, *extras],
        report,
    )
    assert not report.skipped
    return [*higher, *extras, *generated]


def test_ghostship_captured_release_selects_configured_outer_and_member():
    evidence = read(FIXTURE)["ghostship"]
    app = next(
        item
        for item in read(ROOT / "config/extras.json")
        if item["id"] == "dev.net64.ghostship"
    )
    [release] = read(SNAPSHOTS / "ghostship-releases.json")
    api = "https://api.github.com/repos/HarbourMasters/Ghostship"
    transport = GitHubTransport({api + "/releases?per_page=100": [release]})
    result = resolve_github(
        {**app, "additionalSettings": app["additionalSettings"]},
        HttpClient(HttpConfig({}), retries=0, transport=transport),
    )
    assert [candidate.name for candidate in result.candidates] == [evidence["asset"]]
    selected = result.candidates[0]
    assert selected.url == evidence["asset_url"]
    assert re.fullmatch(
        app["additionalSettings"]["zippedApkFilterRegEx"], evidence["member"]
    )


def test_full_reconciliation_survives_repeated_catalog_refresh():
    policy = parse_composition_policy(read(ROOT / "config/composition.json"))
    deny = read(ROOT / "config/deny.json")
    expected = {new for _, new, _ in read(FIXTURE)["identity_corrections"]}

    for refresh in range(2):
        result = compose(
            candidates(refresh),
            deny,
            read(ROOT / "config/overlay.json"),
            read(ROOT / "config/overlay.dual.json"),
            policy=policy,
        )
        for variant in Variant:
            apps = result.apps[variant]
            ids = {app.id for app in apps}
            assert len(ids) == len(apps)
            assert len({app.family for app in apps}) == len(apps)
            assert "dev.net64.ghostship" in ids
            assert "com.theboisclub.pokemonred" in ids
            assert "com.ghostship.android" not in ids
            assert "com.retroarch.aarch64" in ids
            assert (
                not {"com.raekwon1603.supermetroid", "com.raekwon1603.supermetroidds"}
                & ids
            )
            metroid = [app for app in apps if app.family == "app:super-metroid"]
            if variant is Variant.SINGLE:
                assert not metroid
            else:
                assert len(metroid) == 1
                assert metroid[0].id == "com.metroidarch.app.aarch64"
                assert metroid[0].url == "https://github.com/Raekwon1603/RetroArch"
                assert (
                    next(
                        selection.source
                        for selection in result.report.selections
                        if selection.family == "app:super-metroid"
                        and selection.variant is Variant.DUAL
                    )
                    == "extras"
                )
                settings = metroid[0].data["additionalSettings"]
                assert settings["versionDetection"] is False
                assert settings["trackOnly"] is False
                assert settings["autoApkFilterByArch"] is False
            required = expected - (
                {"org.openmw.ds", "dev.twilitrealm.dusk"}
                if variant is Variant.SINGLE
                else set()
            )
            assert required <= ids
            ghost = next(app for app in apps if app.id == "dev.net64.ghostship")
            assert ghost.url == "https://github.com/HarbourMasters/Ghostship"
            settings = ghost.data["additionalSettings"]
            assert settings["apkFilterRegEx"] == "^.*-Android\\.zip$"
            assert settings["zippedApkFilterRegEx"] == "^Ghostship\\.apk$"
            assert settings["includeZips"] is True
            gen1 = next(app for app in apps if app.id == "com.theboisclub.pokemonred")
            assert gen1.url == "https://github.com/bryanthaboi/gen1recomp"
            assert gen1.data["additionalSettings"]["versionDetection"] is True

        ctr = [
            selection
            for selection in result.report.selections
            if selection.family == "app:ctr"
        ]
        assert {(item.variant, item.source) for item in ctr} == {
            (Variant.SINGLE, "bboi"),
            (Variant.DUAL, "codm2000"),
        }
        expected_ctr = read(CTR_EVIDENCE)["variants"]
        for variant in Variant:
            ctr_app = next(
                app for app in result.apps[variant] if app.family == "app:ctr"
            )
            observation = expected_ctr[variant.value]
            assert ctr_app.id == observation["effective_id"] == "com.ctrnative"
            assert ctr_app.original_id == observation["original_id"]
            assert ctr_app.url == observation["source"]
            [rendered_ctr] = json.loads(render([ctr_app], {}))["apps"]
            settings = json.loads(rendered_ctr["additionalSettings"])
            assert settings["versionDetection"] is False
            assert settings["versionExtractionRegEx"] == ""
            assert settings["releaseDateAsVersion"] is False
            assert settings["trackOnly"] is False
            assert settings["exemptFromBackgroundUpdates"] is False
            assert settings["skipUpdateNotifications"] is False


@pytest.mark.parametrize("variant", list(Variant))
def test_ctr_variants_preserve_complete_captured_source_versions(variant: Variant):
    result = compose(
        candidates(0),
        read(ROOT / "config/deny.json"),
        read(ROOT / "config/overlay.json"),
        read(ROOT / "config/overlay.dual.json"),
        policy=parse_composition_policy(read(ROOT / "config/composition.json")),
    )
    app = next(item for item in result.apps[variant] if item.family == "app:ctr")
    evidence = read(CTR_EVIDENCE)["variants"][variant.value]
    api = app.url.replace("https://github.com/", "https://api.github.com/repos/")
    release = evidence["release"]
    transport = GitHubTransport(
        {
            api + "/releases?per_page=100": [release],
            api + "/releases/latest": release,
        }
    )

    resolved = resolve_github(
        app.data, HttpClient(HttpConfig({}), retries=0, transport=transport)
    )

    assert resolved.effective_version == evidence["source_version"]
    assert resolved.effective_version != evidence["manifest"]["versionName"]
    assert [candidate.url for candidate in resolved.candidates] == [
        release["assets"][0]["browser_download_url"]
    ]


@pytest.mark.parametrize("release_index", [0, 1])
def test_metroidarch_captured_releases_track_tags_and_only_matching_apks(release_index):
    evidence = read(ROOT / "tests/fixtures/curation/metroidarch.json")
    app = next(
        item
        for item in read(ROOT / "config/extras.json")
        if item["id"] == evidence["package"]
    )
    releases = deepcopy(evidence["releases"][release_index:])
    selected = releases[0]
    expected_asset = selected["assets"][0]
    for name in ("RetroArch.apk", "MetroidArch-v1.0.1.zip", "MetroidArch-debug.apk"):
        selected["assets"].append({**expected_asset, "name": name})
    prerelease = deepcopy(selected)
    prerelease.update(
        tag_name="v99.0.0", prerelease=True, published_at="2099-01-01T00:00:00Z"
    )
    prerelease["assets"] = [{**expected_asset, "name": "MetroidArch-v99.0.0.apk"}]
    transport = GitHubTransport(
        {
            "https://api.github.com/repos/Raekwon1603/RetroArch/releases?per_page=100": [
                prerelease,
                *releases,
            ]
        }
    )
    result = resolve_github(
        app, HttpClient(HttpConfig({}), retries=0, transport=transport)
    )
    assert result.effective_version == selected["tag_name"]
    assert result.effective_version != evidence["version_name"]
    assert [(item.name, item.url) for item in result.candidates] == [
        (expected_asset["name"], expected_asset["browser_download_url"])
    ]


def test_metroidarch_latest_asset_mismatch_does_not_select_older_release():
    evidence = read(ROOT / "tests/fixtures/curation/metroidarch.json")
    app = next(
        item
        for item in read(ROOT / "config/extras.json")
        if item["id"] == evidence["package"]
    )
    releases = deepcopy(evidence["releases"])
    releases[0]["assets"][0]["name"] = "RetroArch.apk"
    transport = GitHubTransport(
        {
            "https://api.github.com/repos/Raekwon1603/RetroArch/releases?per_page=100": releases
        }
    )
    with pytest.raises(ResolutionError) as raised:
        resolve_github(app, HttpClient(HttpConfig({}), retries=0, transport=transport))
    assert raised.value.code == "github-no-release"
