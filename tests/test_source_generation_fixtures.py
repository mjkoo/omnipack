from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from omnipack.composition_policy import (
    apply_composition_policy,
    parse_composition_policy,
)
from omnipack.merge import CompositionResult, compose
from omnipack.model import App, Variant
from omnipack.render import render
from omnipack.sources import bboi, codm, rjny
from omnipack.sources.common import normalize_record
from omnipack.sources.extras import fetch as fetch_extras
from omnipack.urls import normalize_project_url
from tests.test_sources import FakeHttp

ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures/source-generation/codm"
EVIDENCE = FIXTURES / "reviewed-evidence"
CAPTURED = ROOT / "tests/fixtures/reconciliation"
PRE_MIGRATION = FIXTURES / "pre-migration-config"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def captured_pipeline() -> tuple[list[App], list[App]]:
    sources = load_json(PRE_MIGRATION / "sources.json")
    release = load_json(CAPTURED / "bboi-release.json")
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
            standard_url: (CAPTURED / "bboi-standard.json").read_text(),
            dual_url: (CAPTURED / "bboi-dual.json").read_text(),
            rjny_url: (CAPTURED / "rjny.json").read_text(),
            sources["codm"]["readme_url"]: (
                ROOT / "tests/fixtures/codm-readme.md"
            ).read_text(),
        }
    )
    policy = parse_composition_policy(load_json(PRE_MIGRATION / "composition.json"))
    higher = [
        *rjny.fetch(http, sources["rjny"]),
        *bboi.fetch(http, sources["bboi"]),
        *fetch_extras(load_json(PRE_MIGRATION / "extras.json")),
    ]
    eligible_higher = list(
        apply_composition_policy(policy, higher, require_all=False).candidates
    )
    covered = {
        normalize_project_url(app.url)
        for app in eligible_higher
        if Variant.DUAL in app.eligibility
    }
    generated = [
        normalize_record(
            record,
            source="codm2000",
            variant=Variant.DUAL,
            derive_type=True,
            eligibility=frozenset({Variant.DUAL}),
            dual_preferred=True,
            origin="codm-generated",
        )
        for record in load_json(PRE_MIGRATION / "admitted-catalog.json")["apps"]
        if normalize_project_url(record["url"]) not in covered
    ]
    return higher, generated


def compose_captured_baseline() -> CompositionResult:
    higher, generated = captured_pipeline()
    return compose(
        [*higher, *generated],
        load_json(PRE_MIGRATION / "deny.json"),
        load_json(PRE_MIGRATION / "overlay.json"),
        load_json(PRE_MIGRATION / "overlay.dual.json"),
        policy=parse_composition_policy(load_json(PRE_MIGRATION / "composition.json")),
    )


def test_inventory_is_derived_from_pre_migration_admission_and_coverage() -> None:
    inventory = load_json(FIXTURES / "migration-inventory.json")
    cached = load_json(PRE_MIGRATION / "package-ids.json")
    admitted = set(load_json(PRE_MIGRATION / "admitted-resolution-state.json"))
    higher, generated = captured_pipeline()
    policy = parse_composition_policy(load_json(PRE_MIGRATION / "composition.json"))
    eligible_higher = apply_composition_policy(
        policy, higher, require_all=False
    ).candidates
    readme_urls = {
        normalize_project_url(url)
        for url in re.findall(
            r"\[[^\]]+\]\((https?://[^)\s]+)\)",
            (ROOT / inventory["capturedReadme"]).read_text(),
        )
        if normalize_project_url(url).startswith("github.com/")
    }
    generated_urls = {normalize_project_url(app.url) for app in generated}
    unresolved_urls = (
        readme_urls
        - admitted
        - {
            normalize_project_url(app.url)
            for app in eligible_higher
            if Variant.DUAL in app.eligibility
        }
    )
    coverage: dict[str, dict[str, set[str]]] = {}
    for app in eligible_higher:
        url = normalize_project_url(app.url)
        if url not in readme_urls:
            continue
        by_source = coverage.setdefault(url, {})
        by_source.setdefault(app.provenance.source, set()).update(
            variant.value for variant in app.eligibility
        )

    expected = []
    for url in sorted(readme_urls):
        source_coverage = [
            {"source": source, "eligibility": sorted(eligibility)}
            for source, eligibility in sorted(coverage.get(url, {}).items())
        ]
        if url in generated_urls:
            admission = "admitted"
        elif url in unresolved_urls:
            admission = "unresolved"
        else:
            admission = "suppressed-by-dual-coverage"
            assert any("dual" in item["eligibility"] for item in source_coverage)
        expected.append(
            {
                "url": url,
                "previousAdmission": admission,
                "higherSourceCoverage": source_coverage,
                "packageIdCache": cached.get(url),
            }
        )

    assert inventory["projects"] == expected
    assert {
        item["url"] for item in expected if item["previousAdmission"] == "unresolved"
    } == {
        "github.com/averageconsumer/kanto-gear",
        "github.com/castdrian/showdown-ds",
        "github.com/mastercook777/heimdall-ayn-thor-assistant",
    }


def test_current_captured_baseline_reproduces_exact_exports_and_family_winners() -> (
    None
):
    index = load_json(FIXTURES / "baseline/index.json")
    result = compose_captured_baseline()
    settings = load_json(PRE_MIGRATION / "settings.json")

    for variant in Variant:
        output = render(result.apps[variant], settings).encode()
        expected = next(
            item for item in index["outputs"] if item["variant"] == variant.value
        )
        assert output == (FIXTURES / "baseline" / expected["file"]).read_bytes()
        assert len(result.apps[variant]) == expected["appCount"]
        assert hashlib.sha256(output).hexdigest() == expected["sha256"]

    derived_winners: dict[str, dict[str, str]] = {}
    for selection in result.report.selections:
        if selection.family in index["familyWinners"]:
            derived_winners.setdefault(selection.family, {})[
                selection.variant.value
            ] = normalize_project_url(selection.url)
    assert derived_winners == index["familyWinners"]


def test_committed_catalog_adds_only_reviewed_projects_to_frozen_exports(
    tmp_path: Path,
) -> None:
    higher, _ = captured_pipeline()
    policy = parse_composition_policy(load_json(ROOT / "config/composition.json"))
    eligible_higher = apply_composition_policy(
        policy, higher, require_all=False
    ).candidates
    captured_urls = {
        normalize_project_url(url)
        for url in re.findall(
            r"\[[^\]]+\]\((https?://[^)\s]+)\)",
            (ROOT / "tests/fixtures/codm-readme.md").read_text(),
        )
    }
    catalog = load_json(ROOT / "config/catalogs/codm.json")
    catalog["apps"] = [
        app
        for app in catalog["apps"]
        if normalize_project_url(app["url"]) in captured_urls
    ]
    (tmp_path / "codm.json").write_text(json.dumps(catalog))
    generated = codm.fetch(tmp_path, {"catalog": "codm.json"}, eligible_higher)
    result = compose(
        [*higher, *generated],
        load_json(ROOT / "config/deny.json"),
        load_json(ROOT / "config/overlay.json"),
        load_json(ROOT / "config/overlay.dual.json"),
        policy=policy,
    )
    settings = load_json(ROOT / "config/settings.json")
    baseline = {
        variant: json.loads(
            (FIXTURES / "baseline" / f"{variant.value}-screen.golden").read_bytes()
        )
        for variant in Variant
    }
    current = {
        variant: json.loads(render(result.apps[variant], settings))
        for variant in Variant
    }
    assert current[Variant.SINGLE] == baseline[Variant.SINGLE]
    old_dual = {app["id"]: app for app in baseline[Variant.DUAL]["apps"]}
    new_dual = {app["id"]: app for app in current[Variant.DUAL]["apps"]}
    assert {key: new_dual[key] for key in old_dual} == old_dual
    assert set(new_dual) - set(old_dual) == {
        "dev.adrian.showdown",
        "com.mastercook777.heimdall",
        "1845280017",
    }
    assert len(current[Variant.SINGLE]["apps"]) == 92
    assert len(current[Variant.DUAL]["apps"]) == 112


def test_live_catalog_growth_is_separate_from_frozen_regression() -> None:
    captured_urls = {
        normalize_project_url(url)
        for url in re.findall(
            r"\[[^\]]+\]\((https?://[^)\s]+)\)",
            (ROOT / "tests/fixtures/codm-readme.md").read_text(),
        )
    }
    live_urls = {
        normalize_project_url(app["url"])
        for app in load_json(ROOT / "config/catalogs/codm.json")["apps"]
    }
    assert live_urls - captured_urls == {
        "github.com/chimeragaming/pixelnavigator",
        "github.com/darkaxt/dualscreendex",
        "github.com/rexmont/pixel-guide-android",
        "github.com/rsigristc/dw3-ds-android",
    }


def test_committed_catalog_and_state_are_bound_to_reviewed_policy() -> None:
    catalog_bytes = (ROOT / "config/catalogs/codm.json").read_bytes()
    catalog = json.loads(catalog_bytes)
    metadata = load_json(ROOT / "config/catalogs/codm.source.json")
    state = load_json(ROOT / "config/package-ids.json")
    policy = load_json(ROOT / "config/codm-projects.json")["projects"]
    by_url = {normalize_project_url(app["url"]): app for app in catalog["apps"]}
    assert len(by_url) == 28 and len(state) == 27
    assert metadata["catalogSha256"] == hashlib.sha256(catalog_bytes).hexdigest()
    assert (
        metadata["projectPolicySha256"]
        == hashlib.sha256((ROOT / "config/codm-projects.json").read_bytes()).hexdigest()
    )
    assert by_url["github.com/averageconsumer/kanto-gear"]["id"] == "1845280017"
    assert "github.com/averageconsumer/kanto-gear" not in state
    assert (
        policy["github.com/emulnk/emulnk"]["additionalSettings"][
            "fallbackToOlderReleases"
        ]
        is False
    )
    assert (
        policy["github.com/castdrian/showdown-ds"]["additionalSettings"][
            "fallbackToOlderReleases"
        ]
        is False
    )
    assert (
        policy["github.com/mastercook777/heimdall-ayn-thor-assistant"][
            "additionalSettings"
        ]["fallbackToOlderReleases"]
        is True
    )


def test_baseline_index_binds_every_captured_input() -> None:
    index = load_json(FIXTURES / "baseline/index.json")
    for item in index["inputs"]:
        relative = Path(item["file"])
        contents = (
            PRE_MIGRATION / relative.name
            if relative.parts[0] == "config"
            else ROOT / relative
        ).read_bytes()
        assert hashlib.sha256(contents).hexdigest() == item["sha256"]


def test_accepted_state_fixtures_are_bound_and_define_candidate_layout() -> None:
    catalog_bytes = (FIXTURES / "accepted/catalog.json").read_bytes()
    catalog = json.loads(catalog_bytes)
    metadata = load_json(FIXTURES / "accepted/source.json")
    state = load_json(FIXTURES / "accepted/resolution-state.json")
    layout = load_json(FIXTURES / "candidate-layout.json")

    assert (
        metadata["readmeSha256"]
        == hashlib.sha256((FIXTURES / "accepted/README.md").read_bytes()).hexdigest()
    )
    assert metadata["catalogSha256"] == hashlib.sha256(catalog_bytes).hexdigest()
    by_url = {normalize_project_url(app["url"]): app for app in catalog["apps"]}
    assert set(by_url) == set(state)
    assert all(state[url]["packageId"] == app["id"] for url, app in by_url.items())
    assert layout["root"] == ".build/source-generation/codm"
    assert set(layout["publicationEligible"]) == {
        "catalog.json",
        "source.json",
        "resolution-state.json",
    }
    assert layout["diagnosticOnly"] == ["report.json"]


def test_generation_cases_encode_complete_input_and_expected_relationships() -> None:
    cases = load_json(FIXTURES / "cases.json")
    accepted = {
        normalize_project_url(app["url"])
        for app in load_json(FIXTURES / "accepted/catalog.json")["apps"]
    }
    state = set(load_json(FIXTURES / "accepted/resolution-state.json"))
    assert accepted == state

    new = cases["newProject"]
    unresolved_additions = set(new["revisionProjects"]) - accepted
    assert unresolved_additions == {new["url"]}
    assert new["expectedOutcome"] == "resolve-required"

    fallback = cases["acceptedFallback"]
    assert fallback["url"] in accepted
    assert fallback["resolution"]["status"] == "unresolved"
    retained = sorted(set(fallback["revisionProjects"]) & accepted)
    assert fallback["expectedCatalogProjects"] == retained

    covered = cases["coveredDualProject"]
    assert covered["url"] in covered["revisionProjects"]
    assert "dual" in covered["higherCandidate"]["eligibility"]
    generated = set(covered["revisionProjects"])
    ingested = (
        generated - {covered["url"]}
        if "dual" in covered["higherCandidate"]["eligibility"]
        else generated
    )
    assert covered["expectedGeneratedProjects"] == sorted(generated)
    assert covered["expectedIngestedProjects"] == sorted(ingested)

    single = cases["singleOnlyCoverage"]
    assert single["url"] in single["revisionProjects"]
    assert single["higherCandidate"]["eligibility"] == ["single"]
    generated = set(single["revisionProjects"])
    ingested = (
        generated - {single["url"]}
        if "dual" in single["higherCandidate"]["eligibility"]
        else generated
    )
    assert single["expectedGeneratedProjects"] == sorted(generated)
    assert single["expectedIngestedProjects"] == sorted(ingested)

    removal = cases["removal"]
    assert removal["url"] in accepted
    assert removal["url"] not in removal["revisionProjects"]
    assert (
        sorted(accepted - set(removal["revisionProjects"]))
        == removal["expectedDeletedProjects"]
    )

    conflict = cases["conflictingPackageIds"]
    counts = Counter(project["packageId"] for project in conflict["resolvedProjects"])
    assert {package_id for package_id, count in counts.items() if count > 1} == {
        conflict["expectedConflictPackageId"]
    }
    assert conflict["expectedOutcome"] == "validation-failure"


def test_reviewed_project_policy_is_hash_bound_to_captured_evidence() -> None:
    evidence = load_json(EVIDENCE / "index.json")
    policy_bytes = (EVIDENCE / "project-policy.json").read_bytes()
    policy = json.loads(policy_bytes)

    assert hashlib.sha256(policy_bytes).hexdigest() == evidence["policySha256"]
    assert all(
        hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest() == digest
        for name, digest in evidence["artifactSha256"].items()
    )
    assert set(policy["projects"]) == {
        "github.com/emulnk/emulnk",
        "github.com/castdrian/showdown-ds",
        "github.com/mastercook777/heimdall-ayn-thor-assistant",
        "github.com/averageconsumer/kanto-gear",
    }
    assert all(
        hashlib.sha256(
            json.dumps(rule, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == evidence["reviewedRuleSha256"][url]
        for url, rule in policy["projects"].items()
    )


def test_captured_release_and_manifest_observations_support_reviewed_rules() -> None:
    observations = load_json(EVIDENCE / "observations.json")
    policy = load_json(EVIDENCE / "project-policy.json")["projects"]
    apk_ids: set[str] = set()

    for url in (
        "github.com/emulnk/emulnk",
        "github.com/castdrian/showdown-ds",
        "github.com/mastercook777/heimdall-ayn-thor-assistant",
    ):
        observation = observations["projects"][url]
        assert observation["release"]["prerelease"] is True
        assert observation["release"]["draft"] is False
        assert observation["asset"]["name"].lower().endswith(".apk")
        assert re.fullmatch(r"[0-9a-f]{64}", observation["asset"]["sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", observation["manifest"]["sha256"])
        badging = (EVIDENCE / observation["manifest"]["badgingFile"]).read_text()
        package = re.search(
            r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'",
            badging,
        )
        assert package is not None
        assert package.groups() == (
            observation["manifest"]["packageId"],
            observation["manifest"]["versionCode"],
            observation["manifest"]["versionName"],
        )
        assert policy[url]["additionalSettings"]["includePrereleases"] is True
        apk_ids.add(observation["manifest"]["packageId"])

    assert apk_ids == {
        "com.emulnk",
        "dev.adrian.showdown",
        "com.mastercook777.heimdall",
    }
    heimdall = observations["projects"][
        "github.com/mastercook777/heimdall-ayn-thor-assistant"
    ]
    showdown_url = "github.com/castdrian/showdown-ds"
    showdown = observations["projects"][showdown_url]
    showdown_settings = policy[showdown_url]["additionalSettings"]
    assert re.fullmatch(showdown_settings["apkFilterRegEx"], showdown["asset"]["name"])
    showdown_version = re.fullmatch(
        showdown_settings["versionExtractionRegEx"], showdown["release"]["tag"]
    )
    assert showdown_version is not None
    assert (
        showdown_version.group(int(showdown_settings["matchGroupToUse"]))
        == showdown["manifest"]["versionName"]
    )

    heimdall_url = "github.com/mastercook777/heimdall-ayn-thor-assistant"
    heimdall_settings = policy[heimdall_url]["additionalSettings"]
    assert re.fullmatch(
        heimdall_settings["filterReleaseTitlesByRegEx"], heimdall["release"]["title"]
    )
    assert re.fullmatch(heimdall_settings["apkFilterRegEx"], heimdall["asset"]["name"])
    heimdall_version = re.fullmatch(
        heimdall_settings["versionExtractionRegEx"], heimdall["release"]["tag"]
    )
    assert heimdall_version is not None
    assert (
        heimdall_version.group(int(heimdall_settings["matchGroupToUse"]))
        == heimdall["manifest"]["versionName"]
    )
    assert heimdall["excludedRelease"]["title"] == "debug-latest"
    assert (
        re.fullmatch(
            heimdall_settings["filterReleaseTitlesByRegEx"],
            heimdall["excludedRelease"]["title"],
        )
        is None
    )

    kanto_url = "github.com/averageconsumer/kanto-gear"
    kanto = observations["projects"][kanto_url]
    kanto_policy = policy[kanto_url]
    assert kanto["asset"]["name"].endswith(".zip")
    assert kanto["archiveContainsApk"] is False
    assert (
        kanto["installation"]["hostUrl"] == "https://github.com/bryanthaboi/gen1recomp"
    )
    assert kanto["installation"]["methods"] == ["official-mod-index", "zip-import"]
    assert kanto_policy["kind"] == "track-only"
    assert kanto_policy["trackerId"] == "1845280017"
    assert kanto_policy["installation"] == (
        "Install or update through official Gen1Recomp at "
        "https://github.com/bryanthaboi/gen1recomp using its Mod Index or ZIP import."
    )
    assert kanto_policy["trackerId"] not in apk_ids


def test_expected_additions_are_separate_from_the_frozen_baseline() -> None:
    additions = load_json(EVIDENCE / "expected-additions.json")
    baseline_path = ROOT / additions["baseline"]["file"]
    baseline = load_json(baseline_path)

    assert (
        hashlib.sha256(baseline_path.read_bytes()).hexdigest()
        == additions["baseline"]["sha256"]
    )
    assert {item["variant"]: item["appCount"] for item in baseline["outputs"]} == {
        "single": 92,
        "dual": 109,
    }
    assert additions["single"] == []
    assert [(item["kind"], item["id"], item["url"]) for item in additions["dual"]] == [
        ("apk", "dev.adrian.showdown", "github.com/castdrian/showdown-ds"),
        (
            "apk",
            "com.mastercook777.heimdall",
            "github.com/mastercook777/heimdall-ayn-thor-assistant",
        ),
        (
            "track-only",
            "1845280017",
            "github.com/averageconsumer/kanto-gear",
        ),
    ]
    assert additions["expectedCounts"] == {"single": 92, "dual": 112}
    assert additions["preserveExistingEntriesExactly"] is True
    assert additions["preserveFamilyWinners"] is True
    assert additions["emulnkExpectedWinner"] == {
        "source": "rjny",
        "id": "com.emulnk",
        "url": "github.com/emulnk/emulnk",
        "includePrereleases": True,
    }
    kanto_addition = next(
        item for item in additions["dual"] if item["kind"] == "track-only"
    )
    kanto_policy = load_json(EVIDENCE / "project-policy.json")["projects"][
        kanto_addition["url"]
    ]
    assert kanto_addition["id"] == kanto_policy["trackerId"]
