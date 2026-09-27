"""Reviewed first-admission choices against the committed source snapshots."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from omnipack.catalog import generate_catalog, replace_catalog, split_catalog
from omnipack.composition_policy import parse_composition_policy
from omnipack.merge import compose
from omnipack.model import Variant
from omnipack.quiver_generation import generate_quiver
from omnipack.render import render
from omnipack.source_catalog import render_catalog
from omnipack.sources import quiver
from omnipack.urls import normalize_project_url
from tests.current_config_support import (
    CurrentConfiguration,
    current_configuration_fixture,  # noqa: F401
)
from tests.test_quiver_generation import (
    API,
    OUTPUT,
    ScenarioHttp,
    set_policy,
    setup,
)

ROOT = Path(__file__).resolve().parents[1]
QUIVER_EMERALD = "https://github.com/mstan/EmeraldRecomp"
CODM_EMERALD = "https://github.com/Goldoire/pokeemerald-dualscreen"


def _apps(variant: Variant, current: CurrentConfiguration) -> dict[str, dict]:
    return {
        app["id"]: app
        for app in json.loads(render(current.result.apps[variant]))["apps"]
    }


def test_emerald_family_pairs_new_baseline_with_existing_dual(
    current_configuration: CurrentConfiguration,
) -> None:
    current = current_configuration
    quiver_apps = quiver.fetch(
        ROOT, json.loads((ROOT / "config/sources.json").read_text())["quiver"]
    )
    [emerald] = [
        app
        for app in quiver_apps
        if normalize_project_url(app.url) == normalize_project_url(QUIVER_EMERALD)
    ]
    assert emerald.id == "com.mstan.emeraldrecomp"
    [codm] = [
        app
        for app in current.candidates
        if app.provenance.source == "codm2000" and app.url == CODM_EMERALD
    ]
    assert codm.id == "com.pokeemerald.dualscreen"
    chosen = {
        variant: next(
            app
            for app in current.result.apps[variant]
            if app.family == "app:pokemon-emerald"
        )
        for variant in Variant
    }
    assert (chosen[Variant.SINGLE].id, chosen[Variant.SINGLE].url) == (
        emerald.id,
        emerald.url,
    )
    assert (chosen[Variant.DUAL].id, chosen[Variant.DUAL].url) == (codm.id, codm.url)
    assert any(
        selection.family == "app:pokemon-emerald"
        and selection.variant is Variant.DUAL
        and selection.source == "codm2000"
        for selection in current.result.report.selections
    )


def test_initial_admission_keeps_preexisting_pack_entries(
    current_configuration: CurrentConfiguration,
) -> None:
    baseline_policy = {
        **current_configuration.policy,
        "candidates": [
            rule
            for rule in current_configuration.policy["candidates"]
            if rule["match"]["source"] != "quiver"
        ],
    }
    baseline = compose(
        [
            app
            for app in current_configuration.candidates
            if app.provenance.source != "quiver"
        ],
        json.loads((ROOT / "config/deny.json").read_text()),
        json.loads((ROOT / "config/overlay.json").read_text()),
        policy=parse_composition_policy(baseline_policy),
    )
    for variant in Variant:
        before = {
            app["id"]: app for app in json.loads(render(baseline.apps[variant]))["apps"]
        }
        current = _apps(variant, current_configuration)
        assert not (before.keys() - current.keys())
        assert {
            package_id: (old, current[package_id])
            for package_id, old in before.items()
            if old != current[package_id]
        } == {}


@pytest.mark.parametrize(
    "membership",
    ["committed", "fixture-overlaps", "dev.kartpad.android", "com.silenthill.port"],
)
def test_existing_bboi_port_settings_win_over_same_project_quiver_entries(
    current_configuration: CurrentConfiguration,
    tmp_path: Path,
    membership: str,
) -> None:
    overlaps = (
        ("com.chrissotraidis.kartpad", "dev.kartpad.android"),
        ("com.slickamogus.silenthill", "com.silenthill.port"),
    )
    replaced_ids = (
        {effective for _, effective in overlaps}
        if membership == "fixture-overlaps"
        else {membership}
    )
    candidates = [
        app
        for app in current_configuration.candidates
        if not (app.provenance.source == "quiver" and app.id in replaced_ids)
    ]
    if membership == "fixture-overlaps":
        entries = [
            {
                "id": effective_id,
                "url": original.url,
                "name": original.name,
                "overrideSource": "GitHub",
                "additionalSettings": {"includePrereleases": True},
            }
            for original_id, effective_id in overlaps
            for original in candidates
            if original.provenance.source == "bboi" and original.id == original_id
        ]
        assert len(entries) == len(overlaps)
        (tmp_path / "quiver.json").write_bytes(render_catalog(entries))
        candidates.extend(quiver.fetch(tmp_path, {"catalog": "quiver.json"}))
    result = compose(
        candidates,
        json.loads((ROOT / "config/deny.json").read_text()),
        json.loads((ROOT / "config/overlay.json").read_text()),
        policy=parse_composition_policy(current_configuration.policy),
    )
    for variant in Variant:
        assert render(result.apps[variant]) == render(
            current_configuration.result.apps[variant]
        )
    for original_id, effective_id in overlaps:
        [original] = [
            app
            for app in candidates
            if app.provenance.source == "bboi" and app.id == original_id
        ]
        for variant in Variant:
            [selection] = [
                item
                for item in result.report.selections
                if item.variant is variant and item.effective_id == effective_id
            ]
            assert selection.source == "bboi"
            assert selection.original_id == original_id
            has_quiver_overlap = any(
                app.provenance.source == "quiver" and app.id == effective_id
                for app in candidates
            )
            assert (
                any(item.source == "quiver" for item in selection.considered)
                == has_quiver_overlap
            )
            [selected] = [app for app in result.apps[variant] if app.id == effective_id]
            assert selected.url == original.url
            assert selected.data["additionalSettings"] == original.additional_settings


def test_quiver_credit_survives_catalog_rendering(
    current_configuration: CurrentConfiguration,
) -> None:
    readme = (ROOT / "README.md").read_bytes()
    credit = b"https://github.com/tgeorgiadis/quiver-community-app-catalog"
    assert credit in readme
    packs = {
        variant: render(current_configuration.result.apps[variant]).encode()
        for variant in Variant
    }
    catalog = generate_catalog(
        packs[Variant.SINGLE],
        packs[Variant.DUAL],
        parse_composition_policy(current_configuration.policy),
    )
    rebuilt = replace_catalog(readme, catalog)
    prefix, _, suffix = split_catalog(rebuilt)
    assert credit in prefix + suffix
    assert credit in rebuilt


def test_discovery_skip_does_not_replace_package_denial(tmp_path: Path) -> None:
    values = setup(tmp_path, rows=[{"repository": "o/renamed"}])
    package_id = "org.example.game"
    set_policy(
        tmp_path,
        skips=[{"url": "https://github.com/o/repo", "reason": "Review deferred."}],
    )
    renamed_api = "https://api.github.com/repos/o/renamed"
    values[renamed_api] = {"full_name": "o/renamed"}
    values[renamed_api + "/releases/latest"] = values[API + "/releases/latest"]
    http = ScenarioHttp(values)
    report = generate_quiver(tmp_path, http=http)
    assert report["status"] == "success"
    assert not report["skipped"]
    assert renamed_api in http.urls and API not in http.urls
    [candidate] = quiver.fetch(tmp_path, {"catalog": f"{OUTPUT}/catalog.json"})
    assert candidate.url == "https://github.com/o/renamed"
    assert candidate.id == package_id
    empty_policy = parse_composition_policy(
        {"schemaVersion": 1, "candidates": [], "pins": []}
    )
    unblocked = compose([candidate], [], [], policy=empty_policy)
    assert all(unblocked.apps[variant] for variant in Variant)
    blocked = compose(
        [candidate],
        [{"id": package_id, "reason": "Rejected after source review."}],
        [],
        policy=empty_policy,
    )
    assert all(not blocked.apps[variant] for variant in Variant)
