"""Standalone verification evidence and exact input snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omnipack.offline import (
    Finding,
    OfflineInputs,
    missing_input,
    validate_offline,
)

SCHEMA_VERSION = 4
VERIFIER_VERSION = "2.0.0"
VERIFY_PATH = Path(".build/verify.json")
INPUT_PATHS = {
    "single": Path("dist/single-screen.json"),
    "dual": Path("dist/dual-screen.json"),
    "deny": Path("config/deny.json"),
    "overlay": Path("config/overlay.json"),
    "composition": Path("config/composition.json"),
    "readme": Path("README.md"),
}


class VerificationReportError(RuntimeError):
    """Verification evidence could not be persisted."""


def verifier_identity() -> dict[str, str]:
    return {"version": VERIFIER_VERSION, "scope": "structural"}


def capture_inputs(
    root: Path,
) -> tuple[dict[str, bytes | None], dict[str, dict[str, str]]]:
    snapshots: dict[str, bytes | None] = {}
    fingerprints: dict[str, dict[str, str]] = {}
    for name, relative in INPUT_PATHS.items():
        try:
            value = (root / relative).read_bytes()
        except FileNotFoundError:
            snapshots[name] = None
            fingerprints[name] = {"state": "missing"}
        except OSError as error:
            snapshots[name] = None
            fingerprints[name] = {"state": "unreadable", "error": type(error).__name__}
        else:
            snapshots[name] = value
            fingerprints[name] = {
                "state": "present",
                "sha256": hashlib.sha256(value).hexdigest(),
            }
    return snapshots, fingerprints


def run_verification(root: Path) -> dict[str, Any]:
    """Check one captured snapshot of inputs and record its evidence on completion.

    Every input is read once. The checks below, and the fingerprints already
    captured, describe exactly those bytes, regardless of what a concurrent
    writer does to the files afterward. The report is written once, when
    verification completes; a run that is interrupted first leaves no new
    report, so an existing report on disk still describes only the inputs its
    own run checked.
    """
    started = _now()
    snapshots, fingerprints = capture_inputs(root)
    errors: list[dict[str, Any]] = []

    findings = validate_offline(
        OfflineInputs(
            snapshots["single"],
            snapshots["dual"],
            snapshots["deny"],
            snapshots["overlay"],
            snapshots["composition"],
        )
    )
    # Offline checks see an absent snapshot for both missing and unreadable files.
    # Capture knows which it was, so replace only those false missing findings.
    unreadable_missing = {
        missing_input(name)
        for name, fingerprint in fingerprints.items()
        if fingerprint["state"] == "unreadable"
    }
    errors.extend(_finding(item) for item in findings if item not in unreadable_missing)
    from omnipack.catalog import generate_catalog, split_catalog
    from omnipack.composition_policy import load_composition_policy

    try:
        readme = snapshots["readme"]
        if readme is None:
            if fingerprints["readme"]["state"] == "missing":
                raise ValueError("README input is missing")
        else:
            _, interior, _ = split_catalog(readme)
            single, dual, policy = (
                snapshots[name] for name in ("single", "dual", "composition")
            )
            if single is not None and dual is not None and policy is not None:
                expected = generate_catalog(
                    single, dual, load_composition_policy(policy)
                )
                if interior != expected:
                    raise ValueError(
                        "README catalog differs from the captured packs and policy"
                    )
    except ValueError as error:
        errors.append(
            {"stage": "catalog", "code": "catalog_invalid", "message": str(error)}
        )
    for name, fingerprint in fingerprints.items():
        if fingerprint["state"] == "unreadable":
            errors.append(
                {
                    "stage": "input",
                    "code": "input_unreadable",
                    "message": f"{name} input is unreadable",
                }
            )
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "verifier": verifier_identity(),
        "mode": "offline",
        "startedAt": started,
        "completedAt": _now(),
        "status": "failed" if errors else "success",
        "inputs": fingerprints,
        "errors": errors,
    }
    _write_atomic(root / VERIFY_PATH, report)
    return report


def _finding(item: Finding) -> dict[str, Any]:
    return {key: value for key, value in asdict(item).items() if value is not None}


def _write_atomic(path: Path, document: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    except OSError as error:
        raise VerificationReportError(
            f"cannot write verification report: {error}"
        ) from error


def _now() -> str:
    return datetime.now(UTC).isoformat()
