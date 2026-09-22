"""Standalone verification evidence and exact input snapshots."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omnipack.composition_policy import (
    CompositionPolicy,
    CompositionPolicyError,
    load_composition_policy,
)
from omnipack.offline import (
    OfflineInputs,
    missing_input,
    validate_offline,
)
from omnipack.report_model import (
    VERIFICATION_MODE,
    VERIFIER_SCOPE,
    FindingRecord,
    Fingerprint,
    InputState,
    Status,
    VerificationReport,
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
    return {"version": VERIFIER_VERSION, "scope": VERIFIER_SCOPE}


def capture_inputs(
    root: Path,
) -> tuple[dict[str, bytes | None], dict[str, Fingerprint]]:
    snapshots: dict[str, bytes | None] = {}
    fingerprints: dict[str, Fingerprint] = {}
    for name, relative in INPUT_PATHS.items():
        try:
            value = (root / relative).read_bytes()
        except FileNotFoundError:
            snapshots[name] = None
            fingerprints[name] = {"state": InputState.MISSING}
        except OSError as error:
            snapshots[name] = None
            fingerprints[name] = {
                "state": InputState.UNREADABLE,
                "error": type(error).__name__,
            }
        else:
            snapshots[name] = value
            fingerprints[name] = {
                "state": InputState.PRESENT,
                "sha256": hashlib.sha256(value).hexdigest(),
            }
    return snapshots, fingerprints


def run_verification(root: Path) -> VerificationReport:
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
    errors: list[FindingRecord] = []

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
        if fingerprint["state"] == InputState.UNREADABLE
    }
    errors.extend(
        item.to_record() for item in findings if item not in unreadable_missing
    )
    from omnipack.catalog import generate_catalog, split_catalog

    # An invalid policy is already a finding above; without one there is no
    # expected catalog to compare, and repeating the policy error as a catalog
    # error would point the repair at the README.
    policy = _usable_policy(snapshots["composition"])
    try:
        readme = snapshots["readme"]
        if readme is None:
            if fingerprints["readme"]["state"] == InputState.MISSING:
                raise ValueError("README input is missing")
        else:
            _, interior, _ = split_catalog(readme)
            single, dual = snapshots["single"], snapshots["dual"]
            if single is not None and dual is not None and policy is not None:
                expected = generate_catalog(single, dual, policy)
                if interior != expected:
                    raise ValueError(
                        "README catalog differs from the captured packs and policy"
                    )
    except ValueError as error:
        errors.append(
            {"stage": "catalog", "code": "catalog_invalid", "message": str(error)}
        )
    for name, fingerprint in fingerprints.items():
        if fingerprint["state"] == InputState.UNREADABLE:
            errors.append(
                {
                    "stage": "input",
                    "code": "input_unreadable",
                    "message": f"{name} input is unreadable",
                }
            )
    report: VerificationReport = {
        "schemaVersion": SCHEMA_VERSION,
        "verifier": verifier_identity(),
        "mode": VERIFICATION_MODE,
        "startedAt": started,
        "completedAt": _now(),
        "status": Status.FAILED if errors else Status.SUCCESS,
        "inputs": fingerprints,
        "errors": errors,
    }
    _write_atomic(root / VERIFY_PATH, report)
    return report


def _usable_policy(data: bytes | None) -> CompositionPolicy | None:
    if data is None:
        return None
    try:
        return load_composition_policy(data)
    except CompositionPolicyError:
        return None


def _write_atomic(path: Path, document: Mapping[str, Any]) -> None:
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
