from __future__ import annotations

import json
from pathlib import Path

import pytest

from omnipack import build as build_module
from omnipack.composition_policy import parse_composition_policy
from omnipack.merge import (
    CompositionReport,
    CompositionResult,
    Displacement,
    Removal,
    StaleExclusion,
)
from omnipack.model import Provenance, Variant
from omnipack.overlay import ComposedApp
from omnipack.sources import IngestionReport


def app(package_id: str, variant: Variant) -> ComposedApp:
    return ComposedApp(
        variant,
        Provenance("extras", f"https://example.test/{package_id}"),
        {
            "id": package_id,
            "url": f"https://example.test/{package_id}",
            "name": package_id,
            "overrideSource": "HTML",
            "categories": [],
        },
    )


def composition(*ids: str) -> CompositionResult:
    return CompositionResult(
        {
            variant: [app(package_id, variant) for package_id in ids]
            for variant in Variant
        },
        CompositionReport(
            [Displacement("old.id", Variant.SINGLE, "extras", "rjny", ("url",))],
            [Removal("denied.id", Variant.DUAL, "curated")],
            [StaleExclusion("stale.id", None, "gone")],
        ),
    )


def write_previous(root: Path, single: object | None, dual: object | None) -> None:
    (root / "dist").mkdir()
    for name, value in (("single-screen.json", single), ("dual-screen.json", dual)):
        if value is not None:
            (root / "dist" / name).write_text(json.dumps(value), encoding="utf-8")


def write_config(root: Path) -> None:
    (root / "README.md").write_bytes(
        b"<!-- omnipack:catalog:start -->\n<!-- omnipack:catalog:end -->\n"
    )
    (root / "config").mkdir(exist_ok=True)
    for name, value in (
        ("composition.json", {"schemaVersion": 1, "candidates": [], "pins": []}),
        ("deny.json", []),
        ("overlay.json", []),
        ("overlay.dual.json", []),
        ("settings.json", {}),
    ):
        (root / "config" / name).write_text(json.dumps(value), encoding="utf-8")


def test_report_compares_with_previous_output_and_keeps_source_details(
    tmp_path: Path,
) -> None:
    write_previous(
        tmp_path,
        {"apps": [{"id": "old.id"}, {"id": "kept.id"}]},
        {"apps": [{"id": "kept.id"}]},
    )
    write_config(tmp_path)
    ingestion = IngestionReport(
        skipped=[{"source": "codm2000", "url": "https://covered"}]
    )
    build_module.publish_build(
        tmp_path, composition("kept.id", "new.id"), {}, ingestion
    )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["changes"]["single"] == {"added": ["new.id"], "removed": ["old.id"]}
    assert report["changes"]["dual"] == {"added": ["new.id"], "removed": []}
    assert not ({"generated", "unresolved", "retainedFailures"} & report.keys())
    assert report["sourceAdmissions"] == []
    assert report["displacements"][0]["id"] == "old.id"
    assert report["denylistRemovals"][0]["id"] == "denied.id"
    assert report["staleExclusions"][0]["id"] == "stale.id"


def test_first_build_reports_every_app_added(tmp_path: Path) -> None:
    write_config(tmp_path)
    build_module.publish_build(
        tmp_path, composition("one", "two"), {}, IngestionReport()
    )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["changes"]["single"]["added"] == ["one", "two"]
    assert report["changes"]["dual"]["added"] == ["one", "two"]


@pytest.mark.parametrize("mutation_stage", ["offline verification", "publication"])
def test_policy_byte_change_during_build_prevents_publication(
    tmp_path: Path, mutation_stage: str
) -> None:
    write_config(tmp_path)
    policy = tmp_path / "config/composition.json"
    consumed = policy.read_bytes()

    def mutate(stage: str) -> None:
        if stage == mutation_stage:
            policy.write_bytes(consumed + b"\n")

    try:
        build_module.publish_build(
            tmp_path,
            composition("one"),
            {},
            IngestionReport(),
            composition_bytes=consumed,
            on_stage=mutate,
        )
    except build_module.OfflineVerificationError as error:
        assert error.findings[0]["code"] == "input_changed"
    else:
        raise AssertionError("policy mutation was accepted")
    assert not (tmp_path / "dist/single-screen.json").exists()


def test_family_switch_reports_package_diff_and_new_winner(tmp_path: Path) -> None:
    from omnipack.merge import CompositionError, compose
    from omnipack.model import App, SourceType

    write_config(tmp_path)
    old = {"id": "old.pkg", "url": "https://example.test/old/"}
    removed = {"id": "retired.pkg", "url": "https://example.test/retired"}
    write_previous(tmp_path, {"apps": [old, removed]}, {"apps": [old, removed]})
    current_url = "https://example.test/new"
    candidate = App(
        "new.pkg",
        current_url,
        "Replacement",
        SourceType.HTML,
        (),
        Variant.SINGLE,
        Provenance("extras", current_url),
        eligibility=frozenset(Variant),
    )
    rules = [
        {
            "match": {
                "source": "extras",
                "origin": "extras",
                "id": package_id,
                "url": url,
            },
            "family": "app:shared",
            "rationale": "curated replacement",
        }
        for package_id, url in (
            ("old.pkg", "https://example.test/old"),
            ("new.pkg", current_url),
        )
    ]
    policy_data = {"schemaVersion": 1, "candidates": rules, "pins": []}
    with pytest.raises(CompositionError, match="old.pkg"):
        compose([candidate], [], [], [], policy=parse_composition_policy(policy_data))
    rules.pop(0)
    policy_bytes = json.dumps(policy_data).encode()
    (tmp_path / "config/composition.json").write_bytes(policy_bytes)
    current = compose(
        [candidate], [], [], [], policy=parse_composition_policy(policy_data)
    )
    build_module.publish_build(
        tmp_path, current, {}, IngestionReport(), composition_bytes=policy_bytes
    )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    for variant in Variant:
        assert report["changes"][variant.value] == {
            "added": ["new.pkg"],
            "removed": ["old.pkg", "retired.pkg"],
        }
        [selection] = [
            item for item in report["selections"] if item["variant"] == variant.value
        ]
        assert selection["family"] == "app:shared"
        assert selection["effective_id"] == "new.pkg"
        assert selection["url"] == current_url
