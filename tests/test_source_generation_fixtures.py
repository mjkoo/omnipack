from __future__ import annotations

import hashlib
import json
import re
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
