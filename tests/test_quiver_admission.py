"""Reviewed first-admission choices against the committed source snapshots."""

from __future__ import annotations

import json
from pathlib import Path

from omnipack.catalog import generate_catalog, replace_catalog, split_catalog
from omnipack.composition_policy import parse_composition_policy
from omnipack.merge import compose
from omnipack.model import Variant
from omnipack.quiver_source import parse_quiver_policy
from omnipack.render import render
from omnipack.source_catalog import _render_catalog
from omnipack.sources import quiver
from omnipack.urls import normalize_project_url
from tests.current_config_support import (
    CurrentConfiguration,
    current_configuration_fixture,  # noqa: F401
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


def test_existing_bboi_port_settings_win_over_same_project_quiver_entries(
    current_configuration: CurrentConfiguration,
) -> None:
    overlaps = (
        ("com.chrissotraidis.kartpad", "dev.kartpad.android"),
        ("com.slickamogus.silenthill", "com.silenthill.port"),
    )
    for original_id, effective_id in overlaps:
        [original] = [
            app
            for app in current_configuration.candidates
            if app.provenance.source == "bboi" and app.id == original_id
        ]
        for variant in Variant:
            [selection] = [
                item
                for item in current_configuration.result.report.selections
                if item.variant is variant and item.effective_id == effective_id
            ]
            assert selection.source == "bboi"
            assert selection.original_id == original_id
            assert any(item.source == "quiver" for item in selection.considered)
            [selected] = [
                app
                for app in current_configuration.result.apps[variant]
                if app.id == effective_id
            ]
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
    old = "https://github.com/owner/old-name"
    renamed = "https://github.com/owner/new-name"
    package_id = "org.example.rejected"
    policy = parse_quiver_policy(
        {
            "schemaVersion": 1,
            "projects": {},
            "skips": [{"url": old, "reason": "Review deferred."}],
        }
    )
    assert policy.skips[0].matches("owner/old-name", None, "github.com/owner/old-name")
    catalog = tmp_path / "quiver.json"
    catalog.write_bytes(
        _render_catalog(
            [
                {
                    "id": package_id,
                    "url": renamed,
                    "name": "Rejected port under a new repository name",
                    "overrideSource": "GitHub",
                }
            ]
        )
    )
    [candidate] = quiver.fetch(tmp_path, {"catalog": "quiver.json"})
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
