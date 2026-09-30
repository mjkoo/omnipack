"""Reviewed first-admission choices against the committed source snapshots."""

from __future__ import annotations

import json
from pathlib import Path

from omnipack.catalog import generate_catalog, replace_catalog, split_catalog
from omnipack.composition_policy import (
    apply_composition_policy,
    parse_composition_policy,
    rendered_key,
)
from omnipack.merge import compose
from omnipack.model import Variant
from omnipack.quiver_generation import generate_quiver
from omnipack.render import render
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
    candidates = current_configuration.candidates
    baseline_candidates = [
        app for app in candidates if app.provenance.source != "quiver"
    ]
    # An overlay record patching an app only Quiver supplies has no target
    # before admission.
    corrected = apply_composition_policy(
        parse_composition_policy(current_configuration.policy), candidates
    )
    quiver_only = {
        rendered_key(app.id, app.url)
        for app in corrected
        if app.provenance.source == "quiver"
    } - {
        rendered_key(app.id, app.url)
        for app in corrected
        if app.provenance.source != "quiver"
    }
    baseline = compose(
        baseline_candidates,
        json.loads((ROOT / "config/deny.json").read_text()),
        [
            record
            for record in json.loads((ROOT / "config/overlay.json").read_text())
            if rendered_key(record["id"], record["url"]) not in quiver_only
        ],
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


def test_committed_package_id_corrections_onto_quiver_ids_keep_the_packs(
    current_configuration: CurrentConfiguration,
) -> None:
    """Quiver never displaces a candidate corrected onto its package id."""
    current = current_configuration
    quiver_ids = {
        app.id for app in current.candidates if app.provenance.source == "quiver"
    }
    corrected = {
        (
            rule["match"]["source"],
            rule["match"]["origin"],
            rule["match"]["id"],
            normalize_project_url(rule["match"]["url"]),
        ): rule["packageId"]
        for rule in current.policy["candidates"]
        if rule.get("packageId") in quiver_ids and rule["match"]["source"] != "quiver"
    }
    for selection in current.result.report.selections:
        members = {
            (
                item.source,
                item.origin,
                item.original_id,
                normalize_project_url(item.url),
            )
            for item in (selection, *selection.considered)
        }
        if corrected.keys() & members:
            assert selection.source != "quiver"

    without_overlaps = compose(
        [
            app
            for app in current.candidates
            if not (app.provenance.source == "quiver" and app.id in corrected.values())
        ],
        json.loads((ROOT / "config/deny.json").read_text()),
        json.loads((ROOT / "config/overlay.json").read_text()),
        policy=parse_composition_policy(current.policy),
    )
    for variant in Variant:
        assert render(without_overlaps.apps[variant]) == render(
            current.result.apps[variant]
        )


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
