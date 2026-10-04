from __future__ import annotations

import json
from pathlib import Path

from omnipack.composition_policy import (
    apply_composition_policy,
    candidate_selector,
    parse_composition_policy,
)
from omnipack.model import Variant
from omnipack.render import render
from omnipack.urls import normalize_project_url
from tests.current_config_support import (
    CurrentConfiguration,
    current_configuration_fixture,  # noqa: F401
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/curation/reconciliation.json"
OBSERVATIONS = ROOT / "tests/fixtures/reconciliation/selected-observations.json"
CTR_EVIDENCE = ROOT / "tests/fixtures/curation/ctr.json"
FORMED_FAMILIES = ROOT / "tests/fixtures/reconciliation/formed-families.json"


def read(path: Path):
    return json.loads(path.read_text())


def test_identity_correction_evidence_agrees_across_fixtures() -> None:
    evidence = read(FIXTURE)
    observations = read(OBSERVATIONS)
    ctr = read(CTR_EVIDENCE)

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
        assert len({app.family for app in apps}) == len(apps)
        assert "dev.net64.ghostship" in ids
        assert "com.theboisclub.pokemonred" in ids
        assert "com.ghostship.android" not in ids
        assert "com.retroarch.aarch64" in ids
        assert (
            not {
                "com.raekwon1603.supermetroid",
                "com.raekwon1603.supermetroidds",
                "com.raekwon.supermetroid",
            }
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

    for family in (
        "github.com/rexmont/pixel-guide-android",
        "github.com/emulnk/emulnk",
    ):
        selection = next(
            item
            for item in result.report.selections
            if item.family == family and item.variant is Variant.DUAL
        )
        assert selection.source == "rjny"
        assert selection.origin == "rjny-catalog"
        assert selection.reason == "pin"

    ctr = [
        selection
        for selection in result.report.selections
        if selection.family == "app:ctr"
    ]
    assert {(item.variant, item.source) for item in ctr} == {
        (Variant.SINGLE, "quiver"),
        (Variant.DUAL, "codm2000"),
    }
    expected_ctr = read(CTR_EVIDENCE)["variants"]
    for variant in Variant:
        ctr_app = next(app for app in result.apps[variant] if app.family == "app:ctr")
        observation = expected_ctr[variant.value]
        assert ctr_app.id == observation["effective_id"] == "com.ctrnative"
        assert ctr_app.url == observation["source"]
        [rendered_ctr] = json.loads(render([ctr_app]))["apps"]
        settings = json.loads(rendered_ctr["additionalSettings"])
        assert settings["versionDetection"] is False
        assert settings["versionExtractionRegEx"] == ""
        assert settings["releaseDateAsVersion"] is False
        assert settings["trackOnly"] is False
        assert settings["exemptFromBackgroundUpdates"] is False
        assert settings["skipUpdateNotifications"] is False


def test_captured_candidates_form_the_recorded_families(
    current_configuration: CurrentConfiguration,
) -> None:
    """Every surviving candidate is a winner or considered in some variant."""
    families: dict[str, set[tuple[str, str, str, str]]] = {}
    for selection in current_configuration.result.report.selections:
        members = families.setdefault(selection.family, set())
        members.add(
            (
                selection.source,
                selection.origin,
                selection.id,
                normalize_project_url(selection.url),
            )
        )
        members.update(
            (
                item.source,
                item.origin,
                item.id,
                normalize_project_url(item.url),
            )
            for item in selection.considered
        )
    actual_family = {
        member: family for family, members in families.items() for member in members
    }
    applied = apply_composition_policy(
        parse_composition_policy(current_configuration.policy),
        current_configuration.candidates,
    )
    denied = {
        normalize_project_url(item["url"]) for item in read(ROOT / "config/deny.json")
    }
    surviving = {
        candidate_selector(app).key
        for app in applied
        if app.eligibility and normalize_project_url(app.url) not in denied
    }
    assert set(actual_family) == surviving

    # The recorded groups are the families joining several captured candidates
    # that no committed generated catalog decides. They must stay partitioned
    # exactly as recorded: a merge of two of them or a split of one fails.
    recorded = read(FORMED_FAMILIES)
    recorded_partition = {
        frozenset(tuple(member) for member in members) for members in recorded.values()
    }
    actual_partition: dict[str, set[tuple[str, str, str, str]]] = {}
    for members in recorded_partition:
        for member in members:
            assert member in actual_family, member
            actual_partition.setdefault(actual_family[member], set()).add(member)
    assert {frozenset(members) for members in actual_partition.values()} == (
        recorded_partition
    )


def test_selected_entries_already_listing_their_apk_package_ship_it(
    current_configuration: CurrentConfiguration,
) -> None:
    # These projects need no overlay id patch because the entry the packs
    # select already lists the package its APK declares.
    expected = {
        "github.com/matteo842/crashbandicoot-launcher": (
            "io.github.matteo842.crashlauncher.runtime"
        ),
        "github.com/simon358/ctr-native-android": "com.ctrnative",
        "github.com/chrissotraidis/kartpad": "dev.kartpad.android",
        "github.com/slickamogus/silent-hill-decomp": "com.silenthill.port",
        "github.com/twilitrealm/dusklight": "dev.twilitrealm.dusk",
    }
    shipped = {
        (normalize_project_url(app.data["url"]), app.id)
        for variant in Variant
        for app in current_configuration.result.apps[variant]
        if normalize_project_url(app.data["url"]) in expected
    }
    assert {url for url, _ in shipped} == set(expected)
    assert shipped == set(expected.items())
