"""Check that each project in the committed packs still answers and is
still maintained.

One request per distinct pack URL: a final 2xx is reachable, 404 or 410 is
unreachable, and anything else is inconclusive, because a rate limit, a
server error or a timeout is not evidence that a project is gone. Each
request carries the request headers the pack entry declares, as Obtainium
sends them. A GitHub repository URL that is not unreachable also gets an
update-health lookup (`omnipack.forge_health`), reported stale, archived or
health-inconclusive independently of its reachability. Nothing here writes
committed files; the owner reads the report and denies by hand.
"""

from __future__ import annotations

import contextlib
import html
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import NotRequired, TypedDict

from omnipack import forge_health
from omnipack.build import OUTPUTS
from omnipack.forge_health import check_health, decode_settings, github_repository
from omnipack.http import HttpClient, HttpError, HttpStatusError, failure_reason
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
    status: NotRequired[int]


class Stale(TypedDict):
    url: str
    name: str
    tag: NotRequired[str]
    date: NotRequired[str]


class Archived(TypedDict):
    url: str
    name: str


class HealthInconclusive(TypedDict):
    url: str
    name: str
    reason: str


class LiveCheckReport(TypedDict):
    status: Status
    unreachable: list[Unreachable]
    inconclusive: list[Inconclusive]
    stale: list[Stale]
    archived: list[Archived]
    healthInconclusive: list[HealthInconclusive]
    error: NotRequired[str]


class _BudgetSpent(Exception):
    """Raised before a health request once the time budget is spent."""


@dataclass(frozen=True, slots=True)
class Target:
    """A distinct pack URL with the name and `additionalSettings` of its first
    entry, which supply its request headers and its health settings."""

    url: str
    name: str
    settings: object


def check_live(
    root: Path,
    *,
    http: HttpClient | None = None,
    clock: Callable[[], float] = time.monotonic,
    budget: float = BUDGET_SECONDS,
    now: datetime | None = None,
    github_token: str | None = None,
) -> LiveCheckReport:
    """Check every distinct pack URL in pack order, single-screen first.

    No request starts once `budget` seconds have passed on `clock`; the URLs
    left are inconclusive as not checked, and GitHub repository URLs whose
    health lookup had not finished are health-inconclusive as not checked.
    Release ages are measured at `now`, the current UTC time by default.
    `github_token`, when given, authenticates the GitHub API requests only.
    Packs that cannot be read give a failed report with the error.
    """
    report: LiveCheckReport = {
        "status": Status.FAILED,
        "unreachable": [],
        "inconclusive": [],
        "stale": [],
        "archived": [],
        "healthInconclusive": [],
    }
    try:
        targets = read_targets(root)
    except PackReadError as error:
        report["error"] = str(error)
        return report
    client = http or HttpClient()
    now = now or datetime.now(UTC)
    start = clock()

    def before_request() -> None:
        if clock() - start >= budget:
            raise _BudgetSpent

    for target in targets:
        repository = github_repository(target.url)
        try:
            before_request()
        except _BudgetSpent:
            report["inconclusive"].append({"url": target.url, "reason": NOT_CHECKED})
            if repository is not None:
                _add_health(report, target, forge_health.Inconclusive(NOT_CHECKED))
            continue
        if _check_reachability(report, client, target) and repository is not None:
            try:
                result = check_health(
                    repository,
                    target.settings,
                    client,
                    token=github_token,
                    now=now,
                    before_request=before_request,
                )
            except _BudgetSpent:
                result = forge_health.Inconclusive(NOT_CHECKED)
            _add_health(report, target, result)
    report["status"] = Status.SUCCESS
    return report


def _check_reachability(
    report: LiveCheckReport, client: HttpClient, target: Target
) -> bool:
    """Request one target and record its outcome; False when unreachable."""
    try:
        client.get(target.url, headers=request_headers(target.settings))
    except HttpStatusError as error:
        if error.status in UNREACHABLE_STATUSES:
            report["unreachable"].append({"url": target.url, "status": error.status})
            return False
        report["inconclusive"].append(
            {
                "url": target.url,
                "reason": f"HTTP {error.status}",
                "status": error.status,
            }
        )
    except (HttpError, ValueError) as error:
        report["inconclusive"].append(
            {"url": target.url, "reason": failure_reason(error)}
        )
    return True


def _add_health(
    report: LiveCheckReport,
    target: Target,
    result: forge_health.Health | forge_health.Inconclusive,
) -> None:
    if isinstance(result, forge_health.Inconclusive):
        report["healthInconclusive"].append(
            {"url": target.url, "name": target.name, "reason": result.reason}
        )
        return
    if result.stale:
        stale: Stale = {"url": target.url, "name": target.name}
        if result.newest is not None:
            stale["tag"] = result.newest.tag
            stale["date"] = result.newest.date.astimezone(UTC).date().isoformat()
        report["stale"].append(stale)
    if result.archived:
        report["archived"].append({"url": target.url, "name": target.name})


def read_targets(root: Path) -> list[Target]:
    """Distinct pack URLs in pack order, each with its first entry's name and
    settings."""
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
    return [
        Target(entry["url"], _entry_name(entry), entry.get("additionalSettings"))
        for entry in apps
    ]


def _entry_name(entry: dict[str, object]) -> str:
    name = entry.get("name")
    return name if isinstance(name, str) else ""


def request_headers(settings: object) -> dict[str, str]:
    """The headers an entry's `requestHeader` setting declares.

    `settings` is the entry's `additionalSettings`, a JSON-encoded object in
    the committed packs. Each line is split at its first colon. Raises
    `SettingsError` or `RequestHeaderError` naming the problem when the
    settings or a line are malformed.
    """
    lines = decode_settings(settings).get("requestHeader")
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
        lines += ["", "Stale:"]
        lines += [html.escape(stale_line(item)) for item in report["stale"]]
        lines += ["", "Archived:"]
        lines += [
            html.escape(f"{item['url']} ({item['name']})")
            for item in report["archived"]
        ]
        lines += ["", "Health inconclusive:"]
        lines += [
            html.escape(f"{item['url']} ({item['name']}): {item['reason']}")
            for item in report["healthInconclusive"]
        ]
    return "\n".join([*lines, "</pre>"]) + "\n"


def stale_line(item: Stale) -> str:
    """A stale URL with its entry and newest qualifying release, if any."""
    release = (
        f"{item['tag']} {item['date']}"
        if "tag" in item and "date" in item
        else "no qualifying release"
    )
    return f"{item['url']} ({item['name']}): {release}"


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
