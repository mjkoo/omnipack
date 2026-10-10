"""Check that each project in the committed packs still answers.

One request per distinct pack URL, the same for every host: a final 2xx is
reachable, 404 or 410 is unreachable, and anything else is inconclusive,
because a rate limit, a server error or a timeout is not evidence that a
project is gone. Each request carries the request headers the pack entry
declares, as Obtainium sends them. Nothing here writes committed files; the
owner reads the report and denies by hand.
"""

from __future__ import annotations

import contextlib
import html
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import NotRequired, TypedDict

from omnipack.build import OUTPUTS
from omnipack.http import HttpClient, HttpError, HttpStatusError, TransientHttpError
from omnipack.model import Variant
from omnipack.report_model import Status
from omnipack.strict_json import reject_duplicate_keys

OUTPUT = Path(".build/live-check")
REPORT = OUTPUT / "report.json"
SUMMARY = OUTPUT / "summary.md"

UNREACHABLE_STATUSES = frozenset({404, 410})
BUDGET_SECONDS = 20 * 60
NOT_CHECKED = "not checked: time budget spent"


class PackReadError(ValueError):
    """A committed pack is missing or malformed, so no URL can be checked."""


class RequestHeaderError(ValueError):
    """An entry's settings do not declare well-formed request headers."""


class Unreachable(TypedDict):
    url: str
    status: int


class Inconclusive(TypedDict):
    url: str
    reason: str


class LiveCheckReport(TypedDict):
    status: Status
    unreachable: list[Unreachable]
    inconclusive: list[Inconclusive]
    error: NotRequired[str]


@dataclass(frozen=True, slots=True)
class Target:
    """A distinct pack URL and the `additionalSettings` of its first entry."""

    url: str
    settings: object


def check_live(
    root: Path,
    *,
    http: HttpClient | None = None,
    clock: Callable[[], float] = time.monotonic,
    budget: float = BUDGET_SECONDS,
) -> LiveCheckReport:
    """Check every distinct pack URL in pack order, single-screen first.

    No request starts once `budget` seconds have passed on `clock`; the URLs
    left are inconclusive as not checked. Packs that cannot be read give a
    failed report with the error.
    """
    report: LiveCheckReport = {
        "status": Status.FAILED,
        "unreachable": [],
        "inconclusive": [],
    }
    try:
        targets = read_targets(root)
    except PackReadError as error:
        report["error"] = str(error)
        return report
    client = http or HttpClient()
    start = clock()
    for target in targets:
        if clock() - start >= budget:
            report["inconclusive"].append({"url": target.url, "reason": NOT_CHECKED})
            continue
        try:
            client.get(target.url, headers=request_headers(target.settings))
        except HttpStatusError as error:
            if error.status in UNREACHABLE_STATUSES:
                report["unreachable"].append(
                    {"url": target.url, "status": error.status}
                )
            else:
                report["inconclusive"].append(
                    {"url": target.url, "reason": f"HTTP {error.status}"}
                )
        except (HttpError, ValueError) as error:
            report["inconclusive"].append(
                {"url": target.url, "reason": _failure_reason(error)}
            )
    report["status"] = Status.SUCCESS
    return report


def read_targets(root: Path) -> list[Target]:
    """Distinct pack URLs in pack order, each with its first entry's settings."""
    targets: dict[str, Target] = {}
    for variant in (Variant.SINGLE, Variant.DUAL):
        name = OUTPUTS[variant]
        for target in _pack_entries(root / "dist" / name, name):
            targets.setdefault(target.url, target)
    return list(targets.values())


def _pack_entries(path: Path, name: str) -> list[Target]:
    try:
        document = json.loads(
            path.read_bytes(), object_pairs_hook=reject_duplicate_keys
        )
    except (OSError, ValueError) as error:
        raise PackReadError(f"pack {name} is unreadable: {error}") from error
    apps = document.get("apps") if isinstance(document, dict) else None
    if not isinstance(apps, list) or not all(
        isinstance(entry, dict) and isinstance(entry.get("url"), str) for entry in apps
    ):
        raise PackReadError(
            f"pack {name} is malformed: apps must be objects with a string url"
        )
    return [Target(entry["url"], entry.get("additionalSettings")) for entry in apps]


def request_headers(settings: object) -> dict[str, str]:
    """The headers an entry's `requestHeader` setting declares.

    `settings` is the entry's `additionalSettings`, a JSON-encoded object in
    the committed packs. Each line is split at its first colon. Raises
    `RequestHeaderError` naming the problem when the settings or a line are
    malformed.
    """
    if not isinstance(settings, str):
        raise RequestHeaderError("additionalSettings is not a JSON string")
    try:
        decoded = json.loads(settings)
    except ValueError as error:
        raise RequestHeaderError(
            f"additionalSettings is not valid JSON: {error}"
        ) from error
    if not isinstance(decoded, dict):
        raise RequestHeaderError("additionalSettings is not a JSON object")
    lines = decoded.get("requestHeader")
    if lines is None:
        return {}
    if not isinstance(lines, list) or not all(
        isinstance(line, dict) and isinstance(line.get("requestHeader"), str)
        for line in lines
    ):
        raise RequestHeaderError(
            "requestHeader is not a list of objects with string requestHeader lines"
        )
    headers: dict[str, str] = {}
    for line in lines:
        name, colon, value = line["requestHeader"].partition(":")
        if not colon or not name.strip():
            raise RequestHeaderError(
                f"request header line {line['requestHeader']!r} has no header name "
                "and colon"
            )
        headers[name.strip()] = value.strip()
    return headers


def _failure_reason(error: Exception) -> str:
    """Name a failure's cause: the last attempt's HTTP status when it got one,
    otherwise the failure's own message."""
    if isinstance(error, TransientHttpError):
        return f"HTTP {error.status}" if error.status is not None else error.detail
    return str(error) or type(error).__name__


def render_summary(report: LiveCheckReport) -> str:
    """Render the report for a run summary, escaped inside a `<pre>` block."""
    lines = ["## Live project check", "", "<pre>"]
    if report["status"] == Status.FAILED:
        lines.append(f"Error: {html.escape(report.get('error', ''))}")
    else:
        lines.append("Unreachable:")
        lines += [
            html.escape(f"{item['url']} (HTTP {item['status']})")
            for item in report["unreachable"]
        ]
        lines += ["", "Inconclusive:"]
        lines += [
            html.escape(f"{item['url']}: {item['reason']}")
            for item in report["inconclusive"]
        ]
    return "\n".join([*lines, "</pre>"]) + "\n"


def write_live_report(root: Path, report: LiveCheckReport) -> None:
    """Write the report and its summary whole, replacing any earlier pair.

    On failure neither file is left, so no partial or stale summary can be
    shown for this run; the `OSError` or `ValueError` (such as a URL that
    cannot be encoded) propagates.
    """
    output = root / OUTPUT
    files = {
        root / REPORT: json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        root / SUMMARY: render_summary(report),
    }
    try:
        output.mkdir(parents=True, exist_ok=True)
        for path in files:
            path.unlink(missing_ok=True)
        for path, text in files.items():
            partial = path.with_name(path.name + ".partial")
            try:
                partial.write_text(text, encoding="utf-8")
                partial.replace(path)
            finally:
                partial.unlink(missing_ok=True)
    except OSError, ValueError:
        for path in files:
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)
        raise
