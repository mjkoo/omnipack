from __future__ import annotations

import json
from pathlib import Path

from omnipack import build as build_module
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
    (root / "config").mkdir(exist_ok=True)
    for name, value in (
        ("deny.json", []),
        ("overlay.json", {}),
        ("overlay.dual.json", {}),
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
        skipped=[{"source": "codm2000", "url": "https://covered"}],
        unresolved=[
            {"source": "codm2000", "url": "https://missing", "failure": "no APK"}
        ],
        generated=[
            {
                "source": "codm2000",
                "url": "https://kept",
                "id": "kept.id",
                "status": "reused",
            }
        ],
        retained_failures=[
            {
                "source": "codm2000",
                "url": "https://kept",
                "id": "kept.id",
                "failure": "HTTP 503",
            }
        ],
    )
    build_module.publish_build(
        tmp_path, composition("kept.id", "new.id"), {}, ingestion
    )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["changes"]["single"] == {"added": ["new.id"], "removed": ["old.id"]}
    assert report["changes"]["dual"] == {"added": ["new.id"], "removed": []}
    assert report["generated"] == ingestion.generated
    assert report["unresolved"] == ingestion.unresolved
    assert report["retainedFailures"] == ingestion.retained_failures
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
