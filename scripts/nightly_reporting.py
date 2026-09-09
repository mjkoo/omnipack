"""Runtime-independent diagnostics and finalization for nightly publishing."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from scripts.nightly_issues import MARKER, IssueResult

ISSUE_BODY_LIMIT = 4_000
SUMMARY_LIMIT = 16_000
RESULT_NAME = "orchestration-result.json"
_REPORT_NAMES = ("build", "verify")
_URL = re.compile(r"https?://[^\s<>()\[\]\"']+")
_CREDENTIAL = re.compile(
    r"(?i)\b(bearer|authorization|password|token|secret)"
    r"(\s*[:=]\s*|\s+)([^\s,;]+)"
)
_SENSITIVE_KEY = re.compile(r"(?i)(authorization|credential|password|secret|token)")
_JSON_ERRORS = (UnicodeDecodeError, json.JSONDecodeError)
_RESULT_READ_ERRORS = (OSError, UnicodeDecodeError, json.JSONDecodeError)


class IssueReporter(Protocol):
    def report_failure(self, body: str) -> IssueResult: ...

    def report_recovery(self, body: str) -> IssueResult: ...


@dataclass(frozen=True)
class FinalizationResult:
    workflow_status: str
    publication_status: str
    issue_status: str
    summary: str
    artifacts: tuple[Path, ...]


@dataclass(frozen=True)
class _SetupOutcome:
    status: str
    attempts: tuple[object, ...]
    base_sha: str | None
    published_sha: str | None
    stage: str
    detail: str


def write_diagnostics(
    output_dir: Path,
    outcome: object,
    run_url: str,
    *,
    secrets: Sequence[str] = (),
) -> tuple[Path, ...]:
    """Write only bounded, redacted JSON selected for workflow artifact upload."""
    output_dir.mkdir(parents=True, exist_ok=True)
    attempts = tuple(_field(outcome, "attempts", ()))
    result = {
        "status": _field(outcome, "status", "failed"),
        "stage": _field(outcome, "stage", "unknown"),
        "detail": _field(outcome, "detail", ""),
        "cleanup_errors": _field(outcome, "cleanup_errors", ()),
        "run_url": run_url,
        "base_sha": _field(outcome, "base_sha", None),
        "published_sha": _field(outcome, "published_sha", None),
        "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "attempts": [_attempt_summary(attempt) for attempt in attempts],
    }
    paths = [_write_json(output_dir / RESULT_NAME, result, secrets)]
    for attempt in attempts:
        number = _field(attempt, "number", 0)
        for report in _REPORT_NAMES:
            value = _field(attempt, f"{report}_report", None)
            paths.append(
                _write_json(
                    output_dir / f"attempt-{number}-{report}.json",
                    _report_document(report, value),
                    secrets,
                )
            )
    return tuple(paths)


def artifact_paths(output_dir: Path) -> tuple[Path, ...]:
    """Return regular files named by the orchestration report's explicit allowlist."""
    result = output_dir / RESULT_NAME
    if not _regular_file(result):
        return ()
    allowed = [result]
    try:
        document = json.loads(result.read_bytes())
    except _RESULT_READ_ERRORS:
        return tuple(allowed)
    attempts = document.get("attempts", []) if isinstance(document, dict) else []
    if not isinstance(attempts, list):
        return tuple(allowed)
    numbers = sorted(
        {
            attempt.get("number")
            for attempt in attempts
            if isinstance(attempt, dict)
            and isinstance(attempt.get("number"), int)
            and not isinstance(attempt.get("number"), bool)
            and attempt.get("number") in (1, 2)
        }
    )
    for number in numbers:
        for report in _REPORT_NAMES:
            candidate = output_dir / f"attempt-{number}-{report}.json"
            if _regular_file(candidate):
                allowed.append(candidate)
    return tuple(allowed)


def finalize_publication(
    outcome: object,
    issues: IssueReporter,
    output_dir: Path,
    run_url: str,
    *,
    secrets: Sequence[str] = (),
    diagnostic_url: str | None = None,
    prior_failure: bool = False,
) -> FinalizationResult:
    """Persist diagnostics and reconcile issues while preserving publication truth."""
    artifacts = write_diagnostics(output_dir, outcome, run_url, secrets=secrets)
    publication_status = str(_field(outcome, "status", "failed"))
    issue_body = _issue_body(outcome, run_url, diagnostic_url, secrets)
    cleanup_failed = bool(_field(outcome, "cleanup_errors", ()))
    if publication_status in ("published", "no-op"):
        issue = _safe_issue_call(issues.report_recovery, issue_body, secrets)
    else:
        issue = _safe_issue_call(issues.report_failure, issue_body, secrets)
    workflow_status = (
        "success"
        if publication_status in ("published", "no-op")
        and issue.status != "failed"
        and not cleanup_failed
        and not prior_failure
        else "failed"
    )
    summary_suffix = (
        f"\n- Workflow status: {workflow_status}\n- Diagnostic upload: pending"
    )
    summary = (
        _summary(outcome, run_url, issue, secrets)[
            : SUMMARY_LIMIT - len(summary_suffix)
        ]
        + summary_suffix
    )
    finalization = FinalizationResult(
        workflow_status,
        publication_status,
        issue.status,
        summary,
        artifacts,
    )
    _record_finalization(output_dir, finalization)
    return finalization


def record_upload_status(output_dir: Path, status: str) -> str:
    """Persist the artifact step outcome and return the resulting workflow status."""
    result = output_dir / RESULT_NAME
    try:
        document = json.loads(result.read_bytes())
    except _RESULT_READ_ERRORS as error:
        raise OSError("cannot read the orchestration result") from error
    if not isinstance(document, dict):
        raise OSError("orchestration result is not an object")
    document["diagnostic_upload_status"] = status
    if status != "success":
        document["workflow_status"] = "failed"
    _write_json(result, document, ())
    return str(document.get("workflow_status", "failed"))


def finalize_setup_failure(
    issues: IssueReporter,
    output_dir: Path,
    *,
    run_url: str,
    stage: str,
    detail: BaseException | str,
    base_sha: str | None = None,
    secrets: Sequence[str] = (),
    diagnostic_url: str | None = None,
) -> FinalizationResult:
    """Finalize setup failures using only Python 3.10 standard-library features."""
    outcome = _SetupOutcome("failed", (), base_sha, None, stage, str(detail))
    return finalize_publication(
        outcome,
        issues,
        output_dir,
        run_url,
        secrets=secrets,
        diagnostic_url=diagnostic_url,
    )


def redact(value: object, secrets: Sequence[str] = ()) -> object:
    """Recursively remove credential values from structured diagnostic data."""
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


def _attempt_summary(attempt: object) -> dict[str, object]:
    mode = _verification_mode(attempt)
    stages = []
    for stage in _field(attempt, "stages", ()):
        stages.append(
            {
                "stage": _field(stage, "stage", "unknown"),
                "status": _field(stage, "status", "unknown"),
                "detail": _field(stage, "detail", ""),
            }
        )
    return {
        "number": _field(attempt, "number", None),
        "base_sha": _field(attempt, "base_sha", None),
        "candidate_sha": _field(attempt, "candidate_sha", None),
        "started_at": _timestamp(_field(attempt, "started_at", None)),
        "finished_at": _timestamp(_field(attempt, "finished_at", None)),
        "build_report": "available"
        if _field(attempt, "build_report", None) is not None
        else "unavailable",
        "verify_report": "available"
        if _field(attempt, "verify_report", None) is not None
        else "unavailable",
        "verify_mode": mode,
        "live_verify_report": "available" if mode == "live" else "unavailable",
        "stages": stages,
    }


def _verification_mode(attempt: object) -> str:
    report = _report_document("verify", _field(attempt, "verify_report", None))
    if isinstance(report, dict) and report.get("mode") in ("offline", "live"):
        return str(report["mode"])
    return "unknown"


def _report_document(name: str, value: object) -> object:
    if value is None:
        return {
            "available": False,
            "report": "verification" if name == "verify" else name,
        }
    if isinstance(value, bytes):
        try:
            return json.loads(value)
        except _JSON_ERRORS:
            return {
                "available": True,
                "report": name,
                "parse_error": "report is not valid JSON",
                "text": value.decode("utf-8", errors="replace")[:8_000],
            }
    return value


def _issue_body(
    outcome: object,
    run_url: str,
    diagnostic_url: str | None,
    secrets: Sequence[str],
) -> str:
    status = str(_field(outcome, "status", "failed"))
    attempts = tuple(_field(outcome, "attempts", ()))
    last_attempt = attempts[-1] if attempts else None
    base_sha = _field(last_attempt, "base_sha", _field(outcome, "base_sha", None))
    detail = _field(outcome, "detail", "")
    stage_detail = ""
    if last_attempt is not None:
        stages = tuple(_field(last_attempt, "stages", ()))
        if stages:
            stage_detail = str(_field(stages[-1], "detail", ""))
    lines = [
        MARKER,
        "## Nightly publishing status",
        f"- Stage: {_field(outcome, 'stage', 'unknown')}",
        f"- Run: {run_url}",
        f"- Attempt: {_field(last_attempt, 'number', 'unavailable')}",
        f"- Base SHA: {base_sha or 'unavailable'}",
        f"- Publication: {status}",
        f"- Published SHA: {_field(outcome, 'published_sha', None) or 'unavailable'}",
        f"- Diagnostics: {diagnostic_url or 'available in the workflow run'}",
    ]
    for error in _field(outcome, "cleanup_errors", ()):
        lines.append(f"- Cleanup failure: {error}")
    if stage_detail and stage_detail != detail:
        lines.extend(("", "### Stage detail", stage_detail))
    if detail:
        lines.extend(("", "### Detail", str(detail)))
    body = str(redact("\n".join(lines), secrets))
    return _bounded_with_marker(body, ISSUE_BODY_LIMIT)


def _summary(
    outcome: object, run_url: str, issue: IssueResult, secrets: Sequence[str]
) -> str:
    attempts = tuple(_field(outcome, "attempts", ()))
    lines = [
        "## Nightly publishing",
        f"- Result: {_field(outcome, 'status', 'failed')}",
        f"- Stage: {_field(outcome, 'stage', 'unknown')}",
        f"- Run: {run_url}",
        f"- Base SHA: {_field(outcome, 'base_sha', None) or 'unavailable'}",
        f"- Published SHA: {_field(outcome, 'published_sha', None) or 'unavailable'}",
        f"- Issue maintenance: {issue.status}",
    ]
    cleanup_errors = _field(outcome, "cleanup_errors", ())
    lines.append(f"- Cleanup: {'failed' if cleanup_errors else 'success'}")
    for error in cleanup_errors:
        lines.append(f"- Cleanup detail: {error}")
    if issue.detail:
        lines.append(f"- Issue detail: {issue.detail}")
    for attempt in attempts:
        number = _field(attempt, "number", "unknown")
        build = "available" if _field(attempt, "build_report", None) else "unavailable"
        verify = (
            "available" if _field(attempt, "verify_report", None) else "unavailable"
        )
        mode = _verification_mode(attempt)
        label = f"{mode} verification" if mode != "unknown" else "verification"
        lines.append(
            f"- Attempt {number}: build report {build}; {label} report {verify}"
        )
        if mode != "live":
            lines.append(f"- Attempt {number}: live verification report unavailable")
    if not attempts:
        lines.append(
            "- Attempts: unavailable; failure occurred before an attempt completed"
        )
        lines.append("- Build report: unavailable")
        lines.append("- Verification report: unavailable")
    return str(redact("\n".join(lines), secrets))[:SUMMARY_LIMIT]


def _safe_issue_call(call: Any, body: str, secrets: Sequence[str]) -> IssueResult:
    try:
        result = call(body)
    except Exception as error:  # noqa: BLE001 - this is the workflow finalization boundary
        return IssueResult("failed", detail=str(redact(str(error), secrets)))
    if not isinstance(result, IssueResult):
        return IssueResult("failed", detail="issue reporter returned an invalid result")
    return IssueResult(
        result.status,
        result.issue_number,
        str(redact(result.detail, secrets)),
    )


def _write_json(path: Path, value: object, secrets: Sequence[str]) -> Path:
    document = json.dumps(redact(value, secrets), indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(document, encoding="utf-8")
    temporary.replace(path)
    return path


def _record_finalization(output_dir: Path, finalization: FinalizationResult) -> None:
    result = output_dir / RESULT_NAME
    try:
        document = json.loads(result.read_bytes())
    except _RESULT_READ_ERRORS as error:
        raise OSError("cannot update the orchestration result") from error
    if not isinstance(document, dict):
        raise OSError("orchestration result is not an object")
    document.update(
        {
            "publication_status": finalization.publication_status,
            "issue_status": finalization.issue_status,
            "workflow_status": finalization.workflow_status,
            "diagnostic_upload_status": "pending",
        }
    )
    _write_json(result, document, ())


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


def _bounded_with_marker(body: str, limit: int) -> str:
    if len(body) <= limit:
        return body
    suffix = f"\n\n{MARKER}"
    return body[: limit - len(suffix)].rstrip() + suffix


def _timestamp(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else None


def _field(value: object, name: str, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()
