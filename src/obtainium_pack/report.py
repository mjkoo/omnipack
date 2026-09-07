"""Machine-readable build diagnostics."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from obtainium_pack.merge import (
    CompositionReport,
    CompositionResult,
    Displacement,
    Removal,
    StaleExclusion,
)
from obtainium_pack.model import Variant
from obtainium_pack.sources import IngestionReport


def write_report(
    root: Path,
    previous: dict[Variant, set[str]],
    composition: CompositionResult | None,
    ingestion: IngestionReport,
    *,
    composition_report: CompositionReport | None = None,
    stage: str | None = None,
    error: Exception | None = None,
) -> None:
    changes = None
    if composition is not None:
        changes = {}
        for variant in Variant:
            current = {app.id for app in composition.apps[variant]}
            before = previous.get(variant, set())
            changes[variant.value] = {
                "added": sorted(current - before),
                "removed": sorted(before - current),
            }
        composition_report = composition.report
    document: dict[str, Any] = {
        "status": "failed" if error else "success",
        "changes": changes,
        "skipped": ingestion.skipped,
        "unresolved": ingestion.unresolved,
        "generated": ingestion.generated,
        "retainedFailures": ingestion.retained_failures,
        "displacements": [],
        "denylistRemovals": [],
        "staleExclusions": [],
    }
    if composition_report is not None:
        document["displacements"] = [
            _record(item) for item in composition_report.displacements
        ]
        document["denylistRemovals"] = [
            _record(item) for item in composition_report.removals
        ]
        document["staleExclusions"] = [
            _record(item) for item in composition_report.stale_exclusions
        ]
    if error is not None:
        document["stage"] = stage
        document["error"] = str(error)
    path = root / ".build/report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _record(value: Displacement | Removal | StaleExclusion) -> dict[str, Any]:
    result = asdict(value)
    if "package_id" in result:
        result["id"] = result.pop("package_id")
    if isinstance(result.get("variant"), Variant):
        result["variant"] = result["variant"].value
    return result
