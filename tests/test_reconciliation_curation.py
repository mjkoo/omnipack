from __future__ import annotations

import json
from pathlib import Path

from omnipack.model import Variant
from omnipack.render import render
from tests.current_config_support import (
    CurrentConfiguration,
    current_configuration_fixture,  # noqa: F401
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/curation/reconciliation.json"
OBSERVATIONS = ROOT / "tests/fixtures/reconciliation/selected-observations.json"
CTR_EVIDENCE = ROOT / "tests/fixtures/curation/ctr.json"


def read(path: Path):
    return json.loads(path.read_text())


def test_manifest_evidence_matches_configured_corrections():
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

    assert evidence["ghostship"]["package"] == "dev.net64.ghostship"
    assert set(ctr["variants"]) == {"single", "dual"}
    for item in ctr["variants"].values():
        [asset] = item["release"]["assets"]
        assert item["manifest"]["package"] == item["effective_id"] == "com.ctrnative"
        assert asset["browser_download_url"].startswith(item["source"] + "/releases/")
        assert item["release"]["tag_name"] == item["source_version"]


def test_full_reconciliation_holds_for_current_composition(
    current_configuration: CurrentConfiguration,
) -> None:
    expected = {new for _, new, _ in read(FIXTURE)["identity_corrections"]}
    result = current_configuration.result
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
            not {"com.raekwon1603.supermetroid", "com.raekwon1603.supermetroidds"} & ids
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
            [rendered_metroid] = json.loads(render([metroid[0]]))["apps"]
            settings = json.loads(rendered_metroid["additionalSettings"])
            assert settings["versionDetection"] is False
            assert settings["trackOnly"] is False
            assert settings["autoApkFilterByArch"] is False
            assert (
                settings["apkFilterRegEx"] == r"^MetroidArch-v[0-9]+(?:\.[0-9]+)+\.apk$"
            )
            assert settings["fallbackToOlderReleases"] is False
            assert settings["includePrereleases"] is False
            assert settings["includeZips"] is False
            assert settings["releaseTitleAsVersion"] is False
            assert settings["releaseDateAsVersion"] is False
            assert settings["versionExtractionRegEx"] == ""
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
        ctr_app = next(app for app in result.apps[variant] if app.family == "app:ctr")
        observation = expected_ctr[variant.value]
        assert ctr_app.id == observation["effective_id"] == "com.ctrnative"
        [ctr_selection] = [item for item in ctr if item.variant is variant]
        assert ctr_selection.original_id == observation["original_id"]
        assert ctr_app.url == observation["source"]
        [rendered_ctr] = json.loads(render([ctr_app]))["apps"]
        settings = json.loads(rendered_ctr["additionalSettings"])
        assert settings["versionDetection"] is False
        assert settings["versionExtractionRegEx"] == ""
        assert settings["releaseDateAsVersion"] is False
        assert settings["trackOnly"] is False
        assert settings["exemptFromBackgroundUpdates"] is False
        assert settings["skipUpdateNotifications"] is False
