"""Machine-readable build diagnostics."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime
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
        if "schemaVersion" in build and (
            type(schema) is not int or schema != BUILD_SCHEMA_VERSION
        ):
            raise ReportFormatError(f"unsupported build report schema {schema!r}")
        if build.get("status") not in ("success", "failed"):
            raise ReportFormatError("malformed build report: status is required")
        if any(
            key in build and build[key] is not None and not isinstance(build[key], str)
            for key in ("stage", "error")
        ):
            raise ReportFormatError("malformed build report diagnostics")
        if "offlineVerification" in build:
            offline = build["offlineVerification"]
            if (
                not isinstance(offline, dict)
                or offline.get("status") not in ("not-run", "success", "failed")
                or not isinstance(offline.get("findings"), list)
                or not all(_valid_finding(item) for item in offline["findings"])
            ):
                raise ReportFormatError("malformed build offline verification")
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
            _format_verification_mode(verify),
            f"Observed: {observed}",
            f"Complete: {'yes' if verify['complete'] else 'no'}",
        ]
        lines.extend(_format_findings(verify.get("errors", []), "Error"))
        lines.extend(_format_findings(verify.get("warnings", []), "Warning"))
        sections.append("\n".join(lines))
    else:
        sections.append("Verification report\nNo standalone verification recorded")
    return "\n\n".join(sections) + "\n"


def _format_verification_mode(value: dict[str, Any]) -> str:
    from obtainium_pack.verify import verifier_identity

    mode = value["mode"]
    if mode == "live-probe":
        return "Mode: live-probe (asset probing requested)"
    if mode == "live" and value.get("verifier") == verifier_identity():
        return "Mode: live (metadata only; assets not probed)"
    return f"Mode: {mode}"


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
        location = []
        if isinstance(value, dict):
            for key in ("variant", "entry_id", "id"):
                if value.get(key) is not None:
                    location.append(str(value[key]))
            if value.get("index") is not None:
                location.append(f"index {value['index']}")
            if value.get("field") is not None:
                location.append(str(value["field"]))
            if value.get("effective_version") is not None:
                location.append(f"version {value['effective_version']!r}")
        context = f" [{' / '.join(location)}]" if location else ""
        lines.append(f"{label}{context}: {message}")
    return lines


def _validate_verification_report(value: dict[str, Any]) -> None:
    schema = value.get("schemaVersion")
    if type(schema) is not int or schema != 1:
        raise ReportFormatError(f"unsupported verification report schema {schema!r}")
    verifier = value.get("verifier")
    inputs = value.get("inputs")
    if (
        value.get("status") not in ("running", "success", "failed")
        or not isinstance(value.get("complete"), bool)
        or value.get("mode") not in ("offline", "live", "live-probe")
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

    if (
        "completedAt" not in value
        or not _timestamp(value["startedAt"])
        or (value["complete"] and not _timestamp(value.get("completedAt")))
        or (not value["complete"] and value.get("completedAt") is not None)
        or (value["status"] == "running") == value["complete"]
        or (value["status"] == "success" and bool(value["errors"]))
        or (value["status"] == "failed" and not value["errors"])
        or not all(_fingerprint(item) for item in inputs.values())
        or not all(_valid_finding(item) for item in value["errors"] + value["warnings"])
        or not all(_valid_entry(item) for item in value["entries"])
    ):
        raise ReportFormatError("malformed verification report records")


def _timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def _fingerprint(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    state = value.get("state")
    if state == "present":
        digest = value.get("sha256")
        return (
            set(value) == {"state", "sha256"}
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
        )
    if state == "missing":
        return set(value) == {"state"}
    if state == "unreadable":
        return set(value) == {"state", "error"} and isinstance(value.get("error"), str)
    return False


def _valid_finding(value: object) -> bool:
    return (
        isinstance(value, dict)
        and all(isinstance(value.get(key), str) for key in ("stage", "code", "message"))
        and all(
            value.get(key) is None or isinstance(value[key], str)
            for key in ("variant", "entry_id", "field")
        )
        and (value.get("index") is None or type(value["index"]) is int)
    )


def _valid_entry(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    from obtainium_pack.live import VersionClass

    if (
        not all(
            isinstance(value.get(key), str) for key in ("variant", "entry_id", "source")
        )
        or type(value.get("index")) is not int
        or value.get("version_class")
        not in (None, *(item.value for item in VersionClass))
        or not all(
            isinstance(value.get(key), list) for key in ("errors", "warnings", "probes")
        )
        or not all(_valid_finding(item) for item in value["errors"] + value["warnings"])
        or not all(_valid_probe(item) for item in value["probes"])
        or not {"resolution", "version_class"} <= value.keys()
    ):
        return False
    resolution = value["resolution"]
    if resolution is None:
        return True
    return (
        isinstance(resolution, dict)
        and {"selected", "inspected_count", "window_limit"} <= resolution.keys()
        and all(
            isinstance(resolution.get(key), str)
            for key in ("raw_version", "effective_version", "version_origin")
        )
        and isinstance(resolution.get("candidates"), list)
        and all(_candidate(item) for item in resolution["candidates"])
        and (
            resolution.get("selected") is None
            or isinstance(resolution["selected"], dict)
        )
        and all(
            resolution.get(key) is None or type(resolution[key]) is int
            for key in ("inspected_count", "window_limit")
        )
    )


def _candidate(value: object) -> bool:
    return isinstance(value, dict) and all(
        isinstance(value.get(key), str) for key in ("name", "url")
    )


def _valid_probe(value: object) -> bool:
    return (
        _candidate(value)
        and isinstance(value, dict)
        and {"response_url", "status"} <= value.keys()
        and type(value.get("success")) is bool
        and type(value.get("bytes_read")) is int
        and (value.get("status") is None or type(value["status"]) is int)
        and all(
            value.get(key) is None or isinstance(value[key], str)
            for key in ("response_url", "failure_reason")
        )
    )


def _record(value: Displacement | Removal | StaleExclusion) -> dict[str, Any]:
    result = asdict(value)
    if "package_id" in result:
        result["id"] = result.pop("package_id")
    if isinstance(result.get("variant"), Variant):
        result["variant"] = result["variant"].value
    return result
