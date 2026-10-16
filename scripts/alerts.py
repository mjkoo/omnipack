"""Standard-library alert reconciliation: findings files become GitHub issues.

Each producing job writes a findings file describing the problems it saw and
which keys it re-checked. A separate alert job holding only issue access runs
`reconcile` over those files, so one issue follows each finding. This module
runs on the runner's preinstalled `python3`, so it imports only the standard
library and the `scripts` package, and must not import anything from
`omnipack` or from a module that does.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from pathlib import Path

from scripts.workflow_support import (
    GhRunner,
    SubprocessGhRunner,
    append_summary,
    regular_file_problem,
    render_escaped_pre,
    require_env,
    run_url,
)

LABEL = "omnipack-alert"
LABEL_COLOR = "D93F0B"
LABEL_DESCRIPTION = "Raised by a scheduled omnipack workflow"
BODY_LIMIT = 65536
KEY_LIMIT = 1024
TITLE_LIMIT = 255
ELLIPSIS = "…"
DIGEST_LENGTH = 16

_SAFE_SUBJECT = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/:._~+-"
)
_KEY = re.compile(rf"[A-Za-z0-9/:._~%+-]{{1,{KEY_LIMIT}}}")
_MARKER_PREFIX = "<!-- omnipack-alert-key: "
_MARKER_SUFFIX = " -->"
_MARKER = re.compile(re.escape(_MARKER_PREFIX) + r"(\S+)" + re.escape(_MARKER_SUFFIX))
_RUN_LINE = "\nRun: "
_ALREADY_EXISTS = "already exists"
_COMPLETED_STATUSES = frozenset({"success", "failure"})
_MUTE_REASONS = frozenset({"not_planned", "duplicate"})
EARLY_FAILURE_SLUG = "run"


class Owner(StrEnum):
    """The producing jobs a findings file can come from."""

    NIGHTLY_PREPARE = "nightly-prepare"
    NIGHTLY_PUBLISH = "nightly-publish"
    CODM_CHECK = "codm-check"
    CODM_PUBLISH = "codm-publish"
    QUIVER_CHECK = "quiver-check"
    QUIVER_PUBLISH = "quiver-publish"
    LIVE_CHECK = "live-check"


# The key prefixes each owner may use. The first is the early-failure prefix.
OWNER_PREFIXES: Mapping[Owner, tuple[str, ...]] = {
    Owner.NIGHTLY_PREPARE: ("nightly/prepare/", "build/"),
    Owner.NIGHTLY_PUBLISH: ("nightly/publish/",),
    Owner.CODM_CHECK: ("codm/check/",),
    Owner.CODM_PUBLISH: ("codm/publish/",),
    Owner.QUIVER_CHECK: ("quiver/check/",),
    Owner.QUIVER_PUBLISH: ("quiver/publish/",),
    Owner.LIVE_CHECK: ("live-check/",),
}


@dataclass(frozen=True)
class Finding:
    """One problem: a stable key, a one-line title and raw detail lines."""

    key: str
    title: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class FindingsFile:
    """What a producing job reports.

    `scope` lists keys the run re-checked (an entry ending in `/` covers every
    key under it) and `unchecked` lists keys under those entries it did not.
    """

    owner: Owner
    scope: tuple[str, ...] = ()
    unchecked: tuple[str, ...] = ()
    findings: tuple[Finding, ...] = ()

    def to_json(self) -> str:
        return json.dumps(
            {
                "owner": self.owner.value,
                "scope": list(self.scope),
                "unchecked": list(self.unchecked),
                "findings": [
                    {"key": f.key, "title": f.title, "details": list(f.details)}
                    for f in self.findings
                ],
            },
            indent=2,
        )


@dataclass(frozen=True)
class Producer:
    """An expected producing job: its findings file and the job's result."""

    owner: Owner
    path: Path
    result: str


class ReconcileFailure(RuntimeError):
    """A `gh` operation failed; the message is fixed text with no `gh` output."""


def early_failure_key(owner: Owner) -> str:
    return OWNER_PREFIXES[owner][0] + EARLY_FAILURE_SLUG


def early_failure_finding(owner: Owner) -> Finding:
    """The finding for a producer that failed, was cancelled or reported nothing.

    Its title and details are fixed per owner and carry no per-run values.
    """
    return Finding(
        early_failure_key(owner),
        f"{owner.value} job failed without reporting findings",
        (
            (
                f"The {owner.value} job failed or was cancelled, or its findings"
                " did not reach the alert job intact."
            ),
            "See the workflow run linked below for the failing step.",
        ),
    )


def encode_subject(subject: str) -> str:
    """Percent-encode every UTF-8 byte outside letters, digits and `/:._~+-`."""
    return "".join(
        char
        if char in _SAFE_SUBJECT
        else "".join(f"%{byte:02X}" for byte in char.encode())
        for char in subject
    )


def subject_key(prefix: str, subject: str) -> str:
    """The key for `subject` under `prefix`, within the key length cap.

    A subject whose encoding would pass the cap is cut and suffixed with a
    digest of the whole encoding, so one subject still yields one valid key.
    """
    encoded = encode_subject(subject)
    if len(prefix) + len(encoded) <= KEY_LIMIT:
        return prefix + encoded
    digest = sha256(encoded.encode()).hexdigest()[:DIGEST_LENGTH]
    keep = KEY_LIMIT - len(prefix) - len(digest) - 1
    cut = encoded[:keep]
    # Do not leave a partial %XX escape at the cut.
    percent = cut.rfind("%")
    if percent >= keep - 2:
        cut = cut[:percent]
    return f"{prefix}{cut}~{digest}"


def truncate_title(title: str) -> str:
    """The title cut to GitHub's limit, ending in an ellipsis when it was cut."""
    if len(title) <= TITLE_LIMIT:
        return title
    return title[: TITLE_LIMIT - 1] + ELLIPSIS


def valid_key(owner: Owner, key: object) -> bool:
    return (
        isinstance(key, str)
        and _KEY.fullmatch(key) is not None
        and key.startswith(OWNER_PREFIXES[owner])
    )


def _valid_title(title: object) -> bool:
    return (
        isinstance(title, str)
        and 0 < len(title) <= TITLE_LIMIT
        and "\n" not in title
        and "\r" not in title
    )


def parse_findings(owner: Owner, text: str) -> FindingsFile | None:
    """The validated findings file, or None when it is malformed or not `owner`'s."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("owner") != owner.value:
        return None
    scope = data.get("scope")
    unchecked = data.get("unchecked")
    raw_findings = data.get("findings")
    if not (
        isinstance(scope, list)
        and isinstance(unchecked, list)
        and isinstance(raw_findings, list)
    ):
        return None
    if not all(valid_key(owner, entry) for entry in (*scope, *unchecked)):
        return None
    findings: dict[str, Finding] = {}
    for raw in raw_findings:
        if not isinstance(raw, dict):
            return None
        key, title, details = raw.get("key"), raw.get("title"), raw.get("details")
        if not valid_key(owner, key) or not _valid_title(title):
            return None
        if not isinstance(details, list) or not all(
            isinstance(line, str) for line in details
        ):
            return None
        findings.setdefault(key, Finding(key, title, tuple(details)))
    return FindingsFile(owner, tuple(scope), tuple(unchecked), tuple(findings.values()))


def marker_line(key: str) -> str:
    return f"{_MARKER_PREFIX}{key}{_MARKER_SUFFIX}"


def build_body(finding: Finding, url: str) -> str:
    """The issue body: key marker, escaped details in `<pre>`, then the run line."""
    run_line = f"{_RUN_LINE}{url}"
    core = render_escaped_pre(
        [marker_line(finding.key)],
        [],
        [(None, finding.details)],
        limit=BODY_LIMIT - len(run_line),
    )
    return core + run_line


def _without_run_line(body: str) -> str:
    body = body.replace("\r\n", "\n")
    index = body.rfind(_RUN_LINE)
    return body if index < 0 else body[: index + 1]


def body_key(body: str) -> str | None:
    """The key the body's first line identifies, or None when it identifies none."""
    first = body.split("\n", 1)[0].removesuffix("\r")
    match = _MARKER.fullmatch(first)
    if match is None or _KEY.fullmatch(match.group(1)) is None:
        return None
    return match.group(1)


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    body: str
    open: bool
    muted: bool


@dataclass
class ReconcileSummary:
    opened: int = 0
    updated: int = 0
    reopened: int = 0
    closed: int = 0
    cleared: int = 0
    raised: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return (
            f"alerts: {self.opened} opened, {self.updated} updated, "
            f"{self.reopened} reopened, {self.closed} closed, "
            f"{self.cleared} mute cleared"
        )


def _read_producer(producer: Producer) -> tuple[list[Finding], list[str], list[str]]:
    """The producer's findings, scope and unchecked keys by its result."""
    owner = producer.owner
    early = early_failure_key(owner)
    if producer.result == "cancelled":
        return [early_failure_finding(owner)], [early], []
    if producer.result not in _COMPLETED_STATUSES:
        return [], [], []
    parsed = None
    if regular_file_problem(producer.path) is None:
        try:
            parsed = parse_findings(owner, producer.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            parsed = None
    if parsed is None:
        return [early_failure_finding(owner)], [early], []
    return list(parsed.findings), [*parsed.scope, early], list(parsed.unchecked)


def _in_scope(key: str, scope: Sequence[str]) -> bool:
    return any(
        key == entry or (entry.endswith("/") and key.startswith(entry))
        for entry in scope
    )


def _parse_issues(text: str) -> list[Issue]:
    """Issues from one or more concatenated JSON arrays, as `--paginate` prints."""
    decoder = json.JSONDecoder()
    issues: list[Issue] = []
    index = 0
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return issues
        page, index = decoder.raw_decode(text, index)
        for raw in page:
            if "pull_request" in raw:
                continue
            issues.append(
                Issue(
                    number=raw["number"],
                    title=raw["title"],
                    body=raw.get("body") or "",
                    open=raw["state"] == "open",
                    muted=raw.get("state_reason") in _MUTE_REASONS,
                )
            )


def _list_issues(gh: GhRunner, repository: str) -> dict[str, Issue]:
    """The lowest-numbered labelled issue for each key found on a body's first line."""
    result = gh.run(
        [
            "api",
            "--paginate",
            "--method",
            "GET",
            f"repos/{repository}/issues",
            "-f",
            "state=all",
            "-f",
            f"labels={LABEL}",
            "-f",
            "per_page=100",
        ]
    )
    if result.returncode != 0:
        raise ReconcileFailure("reconcile failed: could not list issues")
    try:
        issues = _parse_issues(result.stdout)
    except (ValueError, KeyError, TypeError):
        raise ReconcileFailure(
            "reconcile failed: could not read the issue listing"
        ) from None
    by_key: dict[str, Issue] = {}
    for issue in sorted(issues, key=lambda item: item.number):
        key = body_key(issue.body)
        if key is not None:
            by_key.setdefault(key, issue)
    return by_key


class _Issues:
    """The `gh` issue operations, each failing with a fixed reason."""

    def __init__(self, gh: GhRunner, repository: str) -> None:
        self._gh = gh
        self._repository = repository

    def _run(self, reason: str, *args: str) -> None:
        result = self._gh.run([*args])
        if result.returncode != 0:
            raise ReconcileFailure(f"reconcile failed: could not {reason}")

    def _with_body(self, reason: str, body: str, *args: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "body.md"
            path.write_text(body, encoding="utf-8")
            self._run(reason, *args, "--body-file", str(path))

    def create(self, title: str, body: str) -> None:
        self._with_body(
            "create an issue",
            body,
            "issue", "create", "--repo", self._repository,
            "--title", title, "--label", LABEL,
        )  # fmt: skip

    def edit(self, number: int, title: str, body: str) -> None:
        self._with_body(
            "update an issue",
            body,
            "issue", "edit", str(number), "--repo", self._repository,
            "--title", title,
        )  # fmt: skip

    def reopen(self, number: int) -> None:
        self._run(
            "reopen an issue",
            "issue", "reopen", str(number), "--repo", self._repository,
        )  # fmt: skip

    def close(self, number: int, comment: str) -> None:
        self._run(
            "close an issue",
            "issue", "close", str(number), "--repo", self._repository,
            "--reason", "completed", "--comment", comment,
        )  # fmt: skip


def ensure_label(gh: GhRunner, repository: str) -> None:
    result = gh.run(
        [
            "label", "create", LABEL, "--repo", repository,
            "--color", LABEL_COLOR, "--description", LABEL_DESCRIPTION,
        ]
    )  # fmt: skip
    if result.returncode != 0 and _ALREADY_EXISTS not in result.stderr:
        raise ReconcileFailure("reconcile failed: could not create the label")


def reconcile(
    gh: GhRunner,
    producers: Sequence[Producer],
    *,
    repository: str,
    url: str,
) -> ReconcileSummary:
    """Make the labelled issues match what the producers raised and re-checked."""
    raised: dict[str, Finding] = {}
    scope: list[str] = []
    unchecked: set[str] = set()
    for producer in producers:
        findings, producer_scope, producer_unchecked = _read_producer(producer)
        for finding in findings:
            raised.setdefault(finding.key, finding)
        scope += producer_scope
        unchecked.update(producer_unchecked)

    summary = ReconcileSummary(raised=sorted(raised))
    ensure_label(gh, repository)
    existing = _list_issues(gh, repository)
    issues = _Issues(gh, repository)

    for key, finding in raised.items():
        title = finding.title
        body = build_body(finding, url)
        issue = existing.get(key)
        if issue is None:
            issues.create(title, body)
            summary.opened += 1
        elif not issue.open:
            if issue.muted:
                continue
            issues.reopen(issue.number)
            issues.edit(issue.number, title, body)
            summary.reopened += 1
        elif issue.title != title or _without_run_line(issue.body) != _without_run_line(
            body
        ):
            issues.edit(issue.number, title, body)
            summary.updated += 1

    for key, issue in existing.items():
        if key in raised or key in unchecked or not _in_scope(key, scope):
            continue
        if issue.open:
            issues.close(issue.number, f"Not seen in run {url}")
            summary.closed += 1
        elif issue.muted:
            issues.reopen(issue.number)
            issues.close(issue.number, f"Cleared in run {url}")
            summary.cleared += 1
    return summary


def _parse_producer(value: str, environ: Mapping[str, str]) -> Producer:
    name, separator, path = value.partition("=")
    try:
        owner = Owner(name)
    except ValueError:
        raise SystemExit(f"unknown producer owner: {name}") from None
    if not separator or not path:
        raise SystemExit(f"--producer needs OWNER=PATH, got {value}")
    result = require_env(environ, owner.value.upper().replace("-", "_") + "_RESULT")
    return Producer(owner, Path(path), result)


def _reconcile_command(
    arguments: argparse.Namespace, environ: Mapping[str, str]
) -> int:
    producers = [_parse_producer(value, environ) for value in arguments.producer]
    repository = require_env(environ, "GITHUB_REPOSITORY")
    url = run_url(environ)
    try:
        summary = reconcile(
            SubprocessGhRunner(), producers, repository=repository, url=url
        )
    except ReconcileFailure as failure:
        append_summary(environ, f"{failure}\n")
        print(failure, file=sys.stderr)
        return 1
    append_summary(environ, summary.text + "\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m scripts.alerts")
    subparsers = parser.add_subparsers(dest="command", required=True)
    reconcile_parser = subparsers.add_parser("reconcile")
    reconcile_parser.add_argument(
        "--producer",
        action="append",
        required=True,
        metavar="OWNER=PATH",
        help="an expected producer and its findings file; its job result is read "
        "from OWNER_RESULT in the environment (hyphens become underscores)",
    )
    arguments = parser.parse_args(argv)
    return _reconcile_command(arguments, os.environ)


if __name__ == "__main__":
    sys.exit(main())
