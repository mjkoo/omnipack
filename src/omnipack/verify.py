"""Standalone verification evidence and exact input snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omnipack.http import HttpConfig, redact_url
from omnipack.offline import Finding, OfflineInputs, validate_offline
from omnipack.settings_defaults import OBTAINIUM_VERSION

SCHEMA_VERSION = 1
VERIFIER_VERSION = "0.4.0"
VERIFY_PATH = Path(".build/verify.json")
INPUT_PATHS = {
    "single": Path("dist/single-screen.json"),
    "dual": Path("dist/dual-screen.json"),
    "deny": Path("config/deny.json"),
    "common_overlay": Path("config/overlay.json"),
    "dual_overlay": Path("config/overlay.dual.json"),
    "settings": Path("config/settings.json"),
    "composition": Path("config/composition.json"),
    "http": Path("config/http.json"),
}
_URL = re.compile(r"https?://[^\s\"'<>]+")


class VerificationReportError(RuntimeError):
    """Verification evidence could not be persisted."""


def verifier_identity() -> dict[str, str]:
    return {"version": VERIFIER_VERSION, "obtainium": OBTAINIUM_VERSION}


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


def run_verification(
    root: Path, *, live: bool = False, probe_assets: bool = False
) -> dict[str, Any]:
    """Verify one captured snapshot and atomically record its evidence."""
    if probe_assets and not live:
        raise ValueError("asset probes require live verification")
    started = _now()
    snapshots, fingerprints = capture_inputs(root)
    secrets = _secret_values(snapshots["http"])
    mode = "live-probe" if probe_assets else "live" if live else "offline"
    report = _base_report(mode, started, fingerprints)
    _write_atomic(root / VERIFY_PATH, report, secrets)
    offline_result = validate_offline(
        OfflineInputs(
            snapshots["single"],
            snapshots["dual"],
            snapshots["deny"],
            snapshots["common_overlay"],
            snapshots["dual_overlay"],
            snapshots["settings"],
            snapshots["composition"],
        )
    )
    report["errors"] = [_finding(item) for item in offline_result.findings]
    for name, fingerprint in fingerprints.items():
        if fingerprint["state"] == "unreadable":
            report["errors"].append(
                {
                    "stage": "input",
                    "code": "input_unreadable",
                    "message": f"{name} input is unreadable",
                }
            )
    if fingerprints["http"]["state"] != "present":
        report["errors"].append(
            {
                "stage": "input",
                "code": "input_missing"
                if fingerprints["http"]["state"] == "missing"
                else "input_unreadable",
                "message": "http input is unavailable",
            }
        )
    http_config = None
    if snapshots["http"] is not None:
        try:
            http_config = _http_config(snapshots["http"])
        except ValueError as error:
            report["errors"].append(
                {"stage": "input", "code": "http-config-invalid", "message": str(error)}
            )
    if live and not report["errors"] and http_config is not None:
        try:
            from omnipack.live import verify_live
            from omnipack.live_http import LiveHttpClient

            result = verify_live(
                offline_result.entries,
                LiveHttpClient(
                    http_config,
                    cache_dir=root / ".build/live-http-cache",
                ),
                probe_assets=probe_assets,
            )
            report["entries"] = [_plain(item) for item in result.entries]
            report["errors"].extend(
                _plain(item) for item in getattr(result, "errors", ())
            )
            report["warnings"].extend(
                _plain(item) for item in getattr(result, "warnings", ())
            )
        except Exception as error:  # noqa: BLE001 - record independent live failures
            report["errors"].append(
                {
                    "stage": "live",
                    "code": getattr(error, "code", "live_failed"),
                    "message": str(error),
                }
            )
    _, current = capture_inputs(root)
    if current != fingerprints:
        report["errors"].append(
            {
                "stage": "input",
                "code": "input_changed",
                "message": "verification inputs changed during the run",
            }
        )
    report.update(
        completedAt=_now(),
        complete=True,
        status="failed" if report["errors"] else "success",
    )
    _write_atomic(root / VERIFY_PATH, report, secrets)
    return _redact(report, secrets)


def _base_report(mode: str, started: str, inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "verifier": verifier_identity(),
        "mode": mode,
        "startedAt": started,
        "completedAt": None,
        "complete": False,
        "status": "running",
        "inputs": inputs,
        "errors": [],
        "warnings": [],
        "entries": [],
    }


def _http_config(value: bytes | None) -> HttpConfig:
    document = json.loads(value) if value is not None else None
    return HttpConfig.from_document(document)


def _secret_values(value: bytes | None) -> tuple[str, ...]:
    try:
        document = json.loads(value) if value is not None else {}
        return tuple(
            secret
            for variable in document.get("credentials", {}).values()
            if isinstance(variable, str) and (secret := os.environ.get(variable, ""))
        )
    except ValueError, AttributeError:
        return ()


def _finding(item: Finding) -> dict[str, Any]:
    return {key: value for key, value in asdict(item).items() if value is not None}


def _plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _redact(value: Any, secrets: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return {key: _redact(item, secrets) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_redact(item, secrets) for item in value]
    if isinstance(value, str):
        text = _URL.sub(lambda match: _safe_redact_url(match.group()), value)
        for secret in secrets:
            text = text.replace(secret, "REDACTED")
        return text
    return value


def _write_atomic(
    path: Path, document: dict[str, Any], secrets: tuple[str, ...]
) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(_redact(document, secrets), indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(path)
    except OSError as error:
        raise VerificationReportError(
            f"cannot write verification report: {error}"
        ) from error


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_redact_url(value: str) -> str:
    try:
        return redact_url(value)
    except ValueError:
        return "<invalid-url>"
