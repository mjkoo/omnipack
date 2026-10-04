from __future__ import annotations

import json
from pathlib import Path

from omnipack import build as build_module
from omnipack.composition_policy import parse_composition_policy
from omnipack.merge import (
    CompositionReport,
    CompositionResult,
    Removal,
    StaleExclusion,
)
from omnipack.model import Provenance, Variant
from omnipack.overlay import ComposedApp
from omnipack.report_model import BuildStage
from omnipack.sources import IngestionReport


def app(package_id: str) -> ComposedApp:
    return ComposedApp(
        f"example.test/{package_id}",
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
        {variant: [app(package_id) for package_id in ids] for variant in Variant},
        CompositionReport(
            removals=[
                Removal("example.test/denied", "curated", ("example.test/denied",))
            ],
            stale_exclusions=[StaleExclusion("example.test/stale", "gone")],
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
        ("sources.json", {}),
        ("extras.json", []),
    ):
        (root / "config" / name).write_text(json.dumps(value), encoding="utf-8")


def test_report_compares_with_previous_output_and_keeps_source_details(
    tmp_path: Path,
) -> None:
    old = {"id": "old.id", "url": "https://example.test/old.id"}
    kept = {"id": "kept.id", "url": "https://EXAMPLE.test/kept.id/"}
    write_previous(tmp_path, {"apps": [old, kept]}, {"apps": [kept]})
    write_config(tmp_path)
    admitted = {
        "source": "codm2000",
        "url": "https://github.com/owner/app",
        "kind": "apk",
        "id": "owner.app",
    }
    ingestion = IngestionReport(admitted=[admitted])
    build_module.publish_build(
        tmp_path,
        composition("kept.id", "new.id"),
        ingestion,
        build_module.BuildInputs.read(tmp_path),
    )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    added = [{"id": "new.id", "url": "example.test/new.id"}]
    assert report["changes"]["single"] == {
        "added": added,
        "removed": [{"id": "old.id", "url": "example.test/old.id"}],
    }
    assert report["changes"]["dual"] == {"added": added, "removed": []}
    assert report["sourceAdmissions"] == [admitted]
    assert report["denylistRemovals"] == [
        {
            "url": "example.test/denied",
            "reason": "curated",
            "families": ["example.test/denied"],
        }
    ]
    assert report["staleExclusions"] == [
        {"url": "example.test/stale", "reason": "gone"}
    ]
    for variant in ("single", "dual"):
        published = json.loads((tmp_path / f"dist/{variant}-screen.json").read_text())
        assert {app["allowIdChange"] for app in published["apps"]} == {True}


def test_previous_output_whose_apps_is_not_a_list_counts_as_empty(
    tmp_path: Path,
) -> None:
    write_previous(tmp_path, {"apps": {"id": "x"}}, {"apps": 7})
    assert build_module.previous_entries(tmp_path) == {
        Variant.SINGLE: set(),
        Variant.DUAL: set(),
    }


def test_family_switch_reports_package_diff_and_new_winner(tmp_path: Path) -> None:
    from omnipack.merge import compose
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
        Provenance("extras", current_url),
        eligibility=frozenset(Variant),
    )
    rules = [
        {
            "match": {
                "source": "extras",
                "origin": "extras",
                "id": "new.pkg",
                "url": current_url,
            },
            "family": "app:shared",
            "rationale": "curated replacement",
        }
    ]
    policy_data = {"schemaVersion": 1, "candidates": rules, "pins": []}
    policy_bytes = json.dumps(policy_data).encode()
    (tmp_path / "config/composition.json").write_bytes(policy_bytes)
    current = compose([candidate], [], [], policy=parse_composition_policy(policy_data))
    build_module.publish_build(
        tmp_path, current, IngestionReport(), build_module.BuildInputs.read(tmp_path)
    )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    for variant in Variant:
        assert report["changes"][variant.value] == {
            "added": [{"id": "new.pkg", "url": "example.test/new"}],
            "removed": [
                {"id": "old.pkg", "url": "example.test/old"},
                {"id": "retired.pkg", "url": "example.test/retired"},
            ],
        }
        [selection] = [
            item for item in report["selections"] if item["variant"] == variant.value
        ]
        assert selection["family"] == "app:shared"
        assert selection["id"] == "new.pkg"
        assert selection["url"] == current_url


BUILD_REPORT_FIELDS = {
    "schemaVersion",
    "status",
    "changes",
    "sourceAdmissions",
    "denylistRemovals",
    "staleExclusions",
    "selections",
    "repeatedIds",
    "singleOnlyFamilies",
    "sameRankTies",
    "uncategorizedFamilies",
    "staleCategoryAssignments",
    "offlineVerification",
}


def test_build_report_writes_exactly_its_schema_fields(tmp_path: Path) -> None:
    from omnipack.report import write_report

    write_config(tmp_path)
    build_module.publish_build(
        tmp_path,
        composition("one"),
        IngestionReport(),
        build_module.BuildInputs.read(tmp_path),
    )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["schemaVersion"] == 5
    assert set(report) == BUILD_REPORT_FIELDS
    write_report(
        tmp_path,
        {},
        None,
        IngestionReport(),
        stage=BuildStage.RENDERING,
        error=ValueError("bad"),
    )
    failed = json.loads((tmp_path / ".build/report.json").read_text())
    assert set(failed) == BUILD_REPORT_FIELDS | {"stage", "error"}
    assert (failed["status"], failed["stage"], failed["error"], failed["changes"]) == (
        "failed",
        "rendering",
        "bad",
        None,
    )
