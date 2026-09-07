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

BUILD_SCHEMA_VERSION = 1


class ReportFormatError(ValueError):
    """Stored report evidence is missing, malformed, or unsupported."""


def write_report(
    root: Path,
    previous: dict[Variant, set[str]],
    composition: CompositionResult | None,
    ingestion: IngestionReport,
    *,
    composition_report: CompositionReport | None = None,
    stage: str | None = None,
    error: Exception | None = None,
    offline_verification: dict[str, Any] | None = None,
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
        "schemaVersion": BUILD_SCHEMA_VERSION,
        "status": "failed" if error else "success",
        "changes": changes,
        "skipped": ingestion.skipped,
        "unresolved": ingestion.unresolved,
        "generated": ingestion.generated,
        "retainedFailures": ingestion.retained_failures,
        "displacements": [],
        "denylistRemovals": [],
        "staleExclusions": [],
        "offlineVerification": offline_verification
        or {"status": "not-run", "findings": []},
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


def format_reports(root: Path) -> str:
    """Read and format available build and standalone verification evidence."""
    build_path = root / ".build/report.json"
    verify_path = root / ".build/verify.json"
    if not build_path.exists() and not verify_path.exists():
        raise ReportFormatError("no build or verification report exists")
    sections: list[str] = []
    if build_path.exists():
        build = _read_document(build_path, "build")
        schema = build.get("schemaVersion")
        if schema not in {None, BUILD_SCHEMA_VERSION}:
            raise ReportFormatError(f"unsupported build report schema {schema!r}")
        if build.get("status") not in {"success", "failed"}:
            raise ReportFormatError("malformed build report: status is required")
        lines = ["Build report", f"Status: {build['status']}"]
        if build.get("stage"):
            lines.append(f"Stage: {build['stage']}")
        if build.get("error"):
            lines.append(f"Error: {build['error']}")
        offline = build.get("offlineVerification")
        if isinstance(offline, dict):
            lines.append(f"Offline verification: {offline.get('status', 'unknown')}")
            lines.extend(_format_findings(offline.get("findings", [])))
        sections.append("\n".join(lines))
    else:
        sections.append("Build report\nNo build report recorded")

    if verify_path.exists():
        verify = _read_document(verify_path, "verification")
        _validate_verification_report(verify)
        from obtainium_pack.verify import capture_inputs, verifier_identity

        _, current = capture_inputs(root)
        freshness = (
            "current"
            if verify["inputs"] == current and verify["verifier"] == verifier_identity()
            else "stale"
        )
        observed = verify.get("completedAt") or verify["startedAt"]
        lines = [
            "Verification report",
            f"Status: {verify['status']}",
            f"Evidence: {freshness}",
            f"Mode: {verify['mode']}",
            f"Observed: {observed}",
            f"Complete: {'yes' if verify['complete'] else 'no'}",
        ]
        lines.extend(_format_findings(verify.get("errors", []), "Error"))
        lines.extend(_format_findings(verify.get("warnings", []), "Warning"))
        sections.append("\n".join(lines))
    else:
        sections.append("Verification report\nNo standalone verification recorded")
    return "\n\n".join(sections) + "\n"


def _read_document(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError) as error:
        raise ReportFormatError(f"cannot read {label} report: {error}") from error
    if not isinstance(value, dict):
        raise ReportFormatError(f"malformed {label} report: root must be an object")
    return value


def _format_findings(values: object, label: str = "Finding") -> list[str]:
    if not isinstance(values, list):
        return []
    lines: list[str] = []
    for value in values:
        if isinstance(value, dict):
            message = (
                value.get("message")
                or value.get("error")
                or json.dumps(value, sort_keys=True)
            )
        else:
            message = str(value)
        lines.append(f"{label}: {message}")
    return lines


def _validate_verification_report(value: dict[str, Any]) -> None:
    schema = value.get("schemaVersion")
    if schema != 1:
        raise ReportFormatError(f"unsupported verification report schema {schema!r}")
    verifier = value.get("verifier")
    inputs = value.get("inputs")
    if (
        value.get("status") not in {"running", "success", "failed"}
        or not isinstance(value.get("complete"), bool)
        or value.get("mode") not in {"offline", "live"}
        or not isinstance(value.get("startedAt"), str)
        or not isinstance(verifier, dict)
        or not all(
            isinstance(verifier.get(key), str) for key in ("version", "obtainium")
        )
        or not isinstance(inputs, dict)
        or set(inputs)
        != {
            "single",
            "dual",
            "deny",
            "common_overlay",
            "dual_overlay",
            "settings",
            "http",
        }
        or any(
            not isinstance(value.get(key), list)
            for key in ("errors", "warnings", "entries")
        )
    ):
        raise ReportFormatError("malformed verification report")


def _record(value: Displacement | Removal | StaleExclusion) -> dict[str, Any]:
    result = asdict(value)
    if "package_id" in result:
        result["id"] = result.pop("package_id")
    if isinstance(result.get("variant"), Variant):
        result["variant"] = result["variant"].value
    return result
