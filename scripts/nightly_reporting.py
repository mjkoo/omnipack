"""Redacted diagnostics and concise Actions reporting for nightly publishing."""

from __future__ import annotations

import html
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

RESULT_NAME = "run-result.json"
BUILD_REPORT_NAME = "build-report.json"
VERIFY_REPORT_NAME = "verify-report.json"
SUMMARY_LIMIT = 16_000
_URL = re.compile(r"https?://[^\s<>()\[\]\"']+")
_CREDENTIAL = re.compile(
    r"(?i)\b(bearer|authorization|password|token|secret)(\s*[:=]\s*|\s+)([^\s,;]+)"
)
_SENSITIVE_KEY = re.compile(r"(?i)(authorization|credential|password|secret|token)")
_JSON_ERRORS = (UnicodeDecodeError, json.JSONDecodeError)


@dataclass(frozen=True)
class PublicationReport:
    workflow_status: str
    publication_status: str
    release_status: str
    summary: str
    artifacts: tuple[Path, ...]
    pending_revision: int | None = None


def log_main_confirmation(
    outcome: object,
    *,
    secrets: Sequence[str] = (),
    stream: TextIO | None = None,
) -> None:
    """Flush a JSON line confirming main before release synchronization starts."""
    status = str(_field(outcome, "status", "failed"))
    if status not in ("published", "no-op"):
        return
    sha = _field(outcome, "published_sha", None) or _field(outcome, "base_sha", None)
    document = redact({"main_publication": status, "sha": sha}, secrets)
    print(json.dumps(document, sort_keys=True), file=stream or sys.stdout, flush=True)


def write_diagnostics(
    output_dir: Path,
    outcome: object,
    run_url: str,
    *,
    secrets: Sequence[str] = (),
) -> tuple[Path, ...]:
    """Write only available, explicitly named, redacted diagnostic reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "status": _field(outcome, "status", "failed"),
        "stage": _field(outcome, "stage", "unknown"),
        "detail": _field(outcome, "detail", ""),
        "run_url": run_url,
        "base_sha": _field(outcome, "base_sha", None),
        "candidate_sha": _field(outcome, "candidate_sha", None),
        "published_sha": _field(outcome, "published_sha", None),
        "release_status": _field(outcome, "release_status", "not-run"),
        "release_revision": _field(outcome, "release_revision", None),
        "pending_revision": _field(outcome, "pending_revision", None),
        "started_at": _timestamp(_field(outcome, "started_at", None)),
        "finished_at": _timestamp(_field(outcome, "finished_at", None)),
        "stages": [_stage(stage) for stage in _field(outcome, "stages", ())],
        "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
    }
    paths = [_write_json(output_dir / RESULT_NAME, result, secrets)]
    for name, filename in (
        ("build", BUILD_REPORT_NAME),
        ("verify", VERIFY_REPORT_NAME),
    ):
        value = _field(outcome, f"{name}_report", None)
        if value is not None:
            paths.append(
                _write_json(
                    output_dir / filename, _report_document(name, value), secrets
                )
            )
    return tuple(paths)


def artifact_paths(output_dir: Path) -> tuple[Path, ...]:
    """Return available regular files from the fixed diagnostic allowlist."""
    return tuple(
        path
        for path in (
            output_dir / RESULT_NAME,
            output_dir / BUILD_REPORT_NAME,
            output_dir / VERIFY_REPORT_NAME,
        )
        if _regular_file(path)
    )


def report_publication(
    outcome: object,
    output_dir: Path,
    run_url: str,
    *,
    secrets: Sequence[str] = (),
) -> PublicationReport:
    artifacts = write_diagnostics(output_dir, outcome, run_url, secrets=secrets)
    publication_status = str(_field(outcome, "status", "failed"))
    release_status = str(_field(outcome, "release_status", "not-run"))
    workflow_status = (
        "success"
        if publication_status in ("published", "no-op") and release_status == "success"
        else "failed"
    )
    return PublicationReport(
        workflow_status,
        publication_status,
        release_status,
        publication_summary(outcome, run_url, secrets=secrets),
        artifacts,
        _field(outcome, "pending_revision", None),
    )


def publication_summary(
    outcome: object, run_url: str, *, secrets: Sequence[str] = ()
) -> str:
    values = {
        "Result": _field(outcome, "status", "failed"),
        "Stage": _field(outcome, "stage", "unknown"),
        "Run": run_url,
        "Base SHA": _field(outcome, "base_sha", None) or "unavailable",
        "Published SHA": _field(outcome, "published_sha", None) or "unavailable",
        "Release synchronization": _field(outcome, "release_status", "not-run"),
        "Release revision": _field(outcome, "release_revision", None) or "unavailable",
        "Pending release revision": _field(outcome, "pending_revision", None)
        or "unavailable",
        "Build report": "available"
        if _field(outcome, "build_report", None) is not None
        else "unavailable",
        "Candidate structural verification report": "available"
        if _field(outcome, "verify_report", None) is not None
        else "unavailable",
    }
    detail = _field(outcome, "detail", "")
    if detail:
        values["Detail"] = detail
    safe = redact(values, secrets)
    assert isinstance(safe, Mapping)
    lines = ["## Nightly publishing"]
    lines.extend(
        f"- {label}: {html.escape(str(value))}" for label, value in safe.items()
    )
    return "\n".join(lines)[:SUMMARY_LIMIT]


def redact(value: object, secrets: Sequence[str] = ()) -> object:
    """Recursively remove credential values from diagnostic and log data."""
    if is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    if isinstance(value, Mapping):
        return {
            str(key): (
                "REDACTED" if _SENSITIVE_KEY.search(str(key)) else redact(item, secrets)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        text = _URL.sub(lambda match: _redact_url(match.group(0)), value)
        text = _CREDENTIAL.sub(lambda match: f"{match.group(1)}=REDACTED", text)
        for secret in sorted((item for item in secrets if item), key=len, reverse=True):
            text = text.replace(secret, "REDACTED")
        return text
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact(str(value), secrets)


def _stage(stage: object) -> dict[str, object]:
    return {
        "stage": _field(stage, "stage", "unknown"),
        "status": _field(stage, "status", "unknown"),
        "detail": _field(stage, "detail", ""),
    }


def _report_document(name: str, value: object) -> object:
    if isinstance(value, bytes):
        try:
            return json.loads(value)
        except _JSON_ERRORS:
            return {
                "report": name,
                "parse_error": "report is not valid JSON",
                "text": value.decode("utf-8", errors="replace")[:8_000],
            }
    return value


def _write_json(path: Path, value: object, secrets: Sequence[str]) -> Path:
    document = json.dumps(redact(value, secrets), indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(document, encoding="utf-8")
    temporary.replace(path)
    return path


def _redact_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        query = urlencode(
            [
                (key, "REDACTED")
                for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
            ]
        )
        return urlunsplit((parsed.scheme, host, parsed.path, query, parsed.fragment))
    except ValueError:
        return _CREDENTIAL.sub(lambda match: f"{match.group(1)}=REDACTED", value)


def _regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def _timestamp(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else None


def _field(value: object, name: str, default: Any) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)
