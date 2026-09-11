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
from omnipack.package_id import PackageIdCache, ResolutionResult, ResolutionStatus
from omnipack.render import render
from omnipack.sources import IngestionReport, bboi, codm, rjny
from omnipack.sources.extras import fetch as fetch_extras
from omnipack.urls import normalize_project_url
from tests.test_sources import FakeHttp

ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures/source-generation/codm"
CAPTURED = ROOT / "tests/fixtures/reconciliation"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


class CapturedResolver:
    def __init__(self) -> None:
        self.cache = PackageIdCache(ROOT / "config/package-ids.json")
        self.calls: list[str] = []

    def resolve(self, project_url: str, /) -> ResolutionResult:
        self.calls.append(normalize_project_url(project_url))
        cached = self.cache.get(project_url)
        if cached is None:
            return ResolutionResult(
                None,
                ResolutionStatus.UNRESOLVED,
                None,
                "captured cache has no previously resolved package ID",
            )
        return ResolutionResult(
            cached.package_id, ResolutionStatus.REUSED, cached.release_id
        )


def captured_pipeline() -> tuple[
    list[App], list[App], IngestionReport, CapturedResolver
]:
    sources = load_json(ROOT / "config/sources.json")
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
    policy = parse_composition_policy(load_json(ROOT / "config/composition.json"))
    higher = [
        *rjny.fetch(http, sources["rjny"]),
        *bboi.fetch(http, sources["bboi"]),
        *fetch_extras(load_json(ROOT / "config/extras.json")),
    ]
    eligible_higher = list(
        apply_composition_policy(policy, higher, require_all=False).candidates
    )
    resolver = CapturedResolver()
    report = IngestionReport()
    generated = codm.fetch(http, sources["codm"], resolver, eligible_higher, report)
    return higher, generated, report, resolver


def compose_captured_baseline() -> CompositionResult:
    higher, generated, _, _ = captured_pipeline()
    return compose(
        [*higher, *generated],
        load_json(ROOT / "config/deny.json"),
        load_json(ROOT / "config/overlay.json"),
        load_json(ROOT / "config/overlay.dual.json"),
        policy=parse_composition_policy(load_json(ROOT / "config/composition.json")),
    )


def test_inventory_is_derived_from_pre_migration_admission_and_coverage() -> None:
    inventory = load_json(FIXTURES / "migration-inventory.json")
    cached = load_json(ROOT / "config/package-ids.json")
    higher, generated, report, resolver = captured_pipeline()
    policy = parse_composition_policy(load_json(ROOT / "config/composition.json"))
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
    unresolved_urls = {normalize_project_url(item["url"]) for item in report.unresolved}
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
    assert set(resolver.calls) == generated_urls | unresolved_urls
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
    settings = load_json(ROOT / "config/settings.json")

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


def test_baseline_index_binds_every_captured_input() -> None:
    index = load_json(FIXTURES / "baseline/index.json")
    for item in index["inputs"]:
        contents = (ROOT / item["file"]).read_bytes()
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
