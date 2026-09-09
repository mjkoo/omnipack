from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from omnipack.composition_policy import (
    apply_composition_policy,
    parse_composition_policy,
)
from omnipack.merge import compose
from omnipack.model import App, Variant
from omnipack.overlay import parse_overlay
from omnipack.package_id import PackageIdCache, ResolutionResult, ResolutionStatus
from omnipack.sources import IngestionReport, bboi, codm
from tests.test_sources import FakeHttp

FIXTURES = Path(__file__).parent / "fixtures/composition-baseline"
ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    ("variant", "count"), [("single-screen", 88), ("dual-screen", 111)]
)
def test_baseline_output_fixture_preserves_committed_pack(
    variant: str, count: int
) -> None:
    baseline = (FIXTURES / f"{variant}.json").read_bytes()
    rendered = json.loads(baseline)
    assert len(rendered["apps"]) == count
    assert rendered["settings"]["categories"]
    assert all(
        {"id", "url", "additionalSettings"} <= app.keys() for app in rendered["apps"]
    )


def test_baseline_index_records_output_integrity_and_source_origins() -> None:
    index = json.loads((FIXTURES / "index.json").read_text())

    for output in index["outputs"]:
        contents = (FIXTURES / output["file"]).read_bytes()
        rendered = json.loads(contents)
        assert hashlib.sha256(contents).hexdigest() == output["sha256"]
        assert len(rendered["apps"]) == output["appCount"]
        assert rendered["settings"] == output["settings"]

    candidates = index["representativeCandidates"]
    assert {candidate["origin"] for candidate in candidates} == {
        "rjny-catalog",
        "bboi-standard-asset",
        "bboi-dual-asset",
        "extras",
        "codm-generated",
    }
    assert {candidate["origin"]: candidate["source"] for candidate in candidates} == {
        "rjny-catalog": "rjny",
        "bboi-standard-asset": "bboi",
        "bboi-dual-asset": "bboi",
        "extras": "extras",
        "codm-generated": "codm2000",
    }
    assert all(
        {"source", "origin", "id", "url", "eligible", "selectedIn"} <= candidate.keys()
        for candidate in candidates
    )

    selected = {
        variant: {
            (app["id"], app["url"])
            for app in json.loads((FIXTURES / f"{variant}-screen.json").read_text())[
                "apps"
            ]
        }
        for variant in ("single", "dual")
    }
    for candidate in candidates:
        for variant in candidate["selectedIn"]:
            assert (candidate["id"], candidate["url"]) in selected[variant]

    ludashi = next(
        candidate
        for candidate in candidates
        if candidate["id"] == "com.winlator.ludashi"
    )
    assert ludashi["selectedRelease"] == "v3.1.h"
    assert ludashi["selectedAsset"] == "bionic-vanilla.apk"
    assert ludashi["settings"]["apkFilterRegEx"] == "bionic-vanilla"
    assert ludashi["settings"]["versionDetection"] is False


def test_different_package_build_pairs_preserve_original_source_records() -> None:
    document = json.loads((FIXTURES / "replacement-candidates.json").read_text())
    assert document["source"] == "bboi"
    assert document["releaseUrl"].startswith("https://codeberg.org/")
    assert {pair["family"] for pair in document["pairs"]} == {
        "app:openmw",
        "app:super-metroid",
        "app:dusklight",
    }
    for pair in document["pairs"]:
        standard, dual = pair["standard"], pair["dual"]
        assert standard["id"] != dual["id"]
        for candidate in (standard, dual):
            assert candidate["url"].startswith("https://github.com/")
            assert isinstance(json.loads(candidate["additionalSettings"]), dict)
            assert candidate["name"]


def test_ctr_origin_matches_captured_standard_asset_record() -> None:
    index = json.loads((FIXTURES / "index.json").read_text())
    candidate = next(
        item
        for item in index["representativeCandidates"]
        if item["id"] == "com.simon358.ctrnative"
    )
    assert (candidate["source"], candidate["origin"]) == (
        "bboi",
        "bboi-standard-asset",
    )
    document = json.loads((FIXTURES / "replacement-candidates.json").read_text())
    record = document["identityConflictCandidates"][0]
    assert (candidate["id"], candidate["url"]) == (record["id"], record["url"])


def test_maintained_policy_and_overlays_cover_the_migrated_selection() -> None:
    document = json.loads((ROOT / "config/composition.json").read_text())
    policy = parse_composition_policy(document)
    assert len(policy.candidate_rules) == 8
    assert len(policy.history) == 113
    assert not policy.pins

    rules = {(rule.match.id, rule.match.url): rule for rule in policy.candidate_rules}
    standard_ctr = rules[
        ("com.simon358.ctrnative", "github.com/simon358/ctr-native-android")
    ]
    dual_ctr = rules[("com.ctrnative", "github.com/igawa6/ctr-native-android")]
    assert standard_ctr.family == dual_ctr.family == "app:ctr"
    assert standard_ctr.package_id == "com.ctrnative"

    common = parse_overlay(
        json.loads((ROOT / "config/overlay.json").read_text()), "common overlay"
    )
    dual = parse_overlay(
        json.loads((ROOT / "config/overlay.dual.json").read_text()), "dual overlay"
    )
    assert len(common) == 12
    assert not dual
    assert {item.url for item in common if item.package_id == "info.cemu.cemu"} == {
        "github.com/ssimco/cemu",
        "github.com/sapphirerhodonite/cemu",
    }


class CapturedPackageResolver:
    """Supply the maintained cached identity without claiming a fresh APK lookup."""

    def resolve(self, project_url: str, /) -> ResolutionResult:
        cached = PackageIdCache(ROOT / "config/package-ids.json").get(project_url)
        assert cached is not None
        return ResolutionResult(
            cached.package_id, ResolutionStatus.REUSED, cached.release_id
        )


@pytest.fixture
def replacement_candidates() -> list[App]:
    document = json.loads((FIXTURES / "replacement-candidates.json").read_text())
    sources = json.loads((ROOT / "config/sources.json").read_text())
    release = json.loads((FIXTURES.parent / "codeberg-release.json").read_text())
    standard_url, dual_url = (
        asset["browser_download_url"] for asset in release["assets"]
    )
    api = (
        "https://codeberg.org/api/v1/repos/"
        f"{sources['bboi']['codeberg_repo']}/releases/latest"
    )
    http = FakeHttp(
        {
            api: json.dumps(release),
            standard_url: json.dumps(
                {
                    "apps": [pair["standard"] for pair in document["pairs"]]
                    + document["identityConflictCandidates"]
                }
            ),
            dual_url: json.dumps(
                {"apps": [pair["dual"] for pair in document["pairs"]]}
            ),
            sources["codm"]["readme_url"]: (
                FIXTURES / "codm-ctr-readme.md"
            ).read_text(),
        }
    )
    candidates = bboi.fetch(http, sources["bboi"])
    policy = parse_composition_policy(
        json.loads((ROOT / "config/composition.json").read_text())
    )
    higher = apply_composition_policy(policy, candidates, require_all=False)
    report = IngestionReport()
    generated = codm.fetch(
        http, sources["codm"], CapturedPackageResolver(), higher.candidates, report
    )
    assert not report.skipped
    assert len(generated) == 1
    assert set(http.urls) == {
        api,
        standard_url,
        dual_url,
        sources["codm"]["readme_url"],
    }
    return candidates + generated


@pytest.mark.parametrize("variant", list(Variant))
def test_maintained_policy_composes_captured_replacement_families(
    replacement_candidates: list[App], variant: Variant
) -> None:
    policy = parse_composition_policy(
        json.loads((ROOT / "config/composition.json").read_text())
    )
    # Version curation has separate postselection coverage. Here the complete
    # maintained policy must select whole builds from actual source records.
    result = compose(replacement_candidates, [], [], [], policy=policy)
    selected = {app.family: app for app in result.apps[variant]}
    document = json.loads((FIXTURES / "replacement-candidates.json").read_text())
    expected = {
        pair["family"]: pair["standard" if variant is Variant.SINGLE else "dual"]
        for pair in document["pairs"]
    }
    expected["app:ctr"] = (
        document["identityConflictCandidates"][0]
        if variant is Variant.SINGLE
        else {
            "id": "com.ctrnative",
            "url": "https://github.com/igawa6/ctr-native-android",
            "name": "ctr-native-android",
            "author": "igawa6",
            "overrideSource": "GitHub",
            "categories": [],
            "additionalSettings": "{}",
        }
    )
    assert set(selected) == set(expected)
    assert len(result.apps[variant]) == len(expected)
    for family, record in expected.items():
        winner = selected[family]
        data = {
            **record,
            "additionalSettings": json.loads(record["additionalSettings"]),
        }
        if family == "app:ctr":
            data["id"] = "com.ctrnative"
        assert winner.data == data
        assert winner.original_id == record["id"]
        generated = family == "app:ctr" and variant is Variant.DUAL
        assert winner.provenance.source == ("codm2000" if generated else "bboi")
        assert winner.origin == (
            "codm-generated"
            if generated
            else document[
                "standardOrigin" if variant is Variant.SINGLE else "dualOrigin"
            ]
        )
        selection = next(
            item
            for item in result.report.selections
            if item.family == family and item.variant is variant
        )
        assert selection.original_id == record["id"]
        assert selection.effective_id == data["id"]
        assert len(selection.alternatives) == 1
        if variant is Variant.DUAL:
            assert selection.dual_preferred
            assert selection.reason == "dual-preferred"
            assert not selection.alternatives[0].dual_preferred
