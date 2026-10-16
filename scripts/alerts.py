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
_MUTE_REASONS = frozenset({"not_planned", "duplicate"})
EARLY_FAILURE_SLUG = "run"


EMIT_HELP = """Write the findings file for one producing job.

Every input comes from the environment or a file path; nothing is interpolated
into a command. Every owner requires JOB_STATUS, the job's `job.status`:
`cancelled` writes only the owner's early-failure finding with empty scope and
unchecked lists, whatever else is present, and `failure` that no stage, step or
main-advanced outcome accounts for adds the same finding. A step result is its
`outcome` (success, failure, skipped or cancelled); an unset or unrecognized
value counts for nothing.

nightly-prepare: PREPARE_STAGE and PREPARE_STAGES, the prepare step's `stage`
and `stages` outputs (stages comma-separated), and the build report at --report
(default .build/report.json).
nightly-publish: PUSH_OUTCOME and RELEASE_OUTCOME, the push and release steps'
`outcome` outputs (ok, main-advanced or failed; empty when a step did not run).
codm-check, quiver-check: GENERATION_RESULT, STAGING_RESULT, TESTS_RESULT,
BUILD_RESULT, VERIFY_RESULT and GUARD_RESULT, each step's `outcome`, and
CHANGED, the stage step's `changed` output.
codm-publish, quiver-publish: PUBLISH_OUTCOME, the publish step's `outcome`
output.
live-check: CHECK_RESULT, the `pack check-live` step's `outcome`, and its
report at --report (default .build/live-check/report.json).
"""


class JobResult(StrEnum):
    """How a job or step ended, as GitHub reports `result` and `outcome`."""

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"

    @classmethod
    def parse(cls, value: str | None) -> JobResult | None:
        """The result `value` names, or None for an absent or unknown value."""
        try:
            return cls(value)
        except ValueError:
            return None


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
    result: JobResult | None


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
        and title == title.strip()
    )


def parse_findings(owner: Owner, text: str) -> FindingsFile | None:
    """The validated findings file, or None when it is malformed or not `owner`'s."""
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
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
    if producer.result is JobResult.CANCELLED:
        return [early_failure_finding(owner)], [early], []
    if producer.result not in (JobResult.SUCCESS, JobResult.FAILURE):
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


# --- emitters -------------------------------------------------------------

DEFAULT_OUTPUT = Path(".build/alerts/findings.json")
BUILD_REPORT = Path(".build/report.json")
LIVE_CHECK_REPORT = Path(".build/live-check/report.json")
STAGE_SEPARATOR = ","
_OK = "ok"
_FAILED = "failed"
_MAIN_ADVANCED = "main-advanced"
# The prepare stage names `scripts.nightly` reports, mapped to the slug each
# one has in a key. A test outside the 3.12 run keeps these keys equal to that
# script's stage names other than `complete`.
PREPARE_STAGE_SLUGS: Mapping[str, str] = {
    "checkout": "checkout",
    "build": "build",
    "allowlist": "allowlist",
    "README boundary": "readme-boundary",
    "commit": "commit",
    "verify": "verify",
    "drift after verify": "drift-after-verify",
    "bundle": "bundle",
}
_BUILD_PREFIX = "build/"
_UNCATEGORIZED = _BUILD_PREFIX + "uncategorized/"
_STALE_DENIAL = _BUILD_PREFIX + "stale-denial/"
_STALE_CATEGORY = _BUILD_PREFIX + "stale-category/"
_LIVE_PREFIX = OWNER_PREFIXES[Owner.LIVE_CHECK][0]
_LIVE_READ = _LIVE_PREFIX + "read"
_GONE = _LIVE_PREFIX + "gone/"
_STATUS = _LIVE_PREFIX + "status/"
# Each check step's key slug, the variable holding its `outcome`, and a name.
_CHECK_STEPS = (
    ("generation", "GENERATION_RESULT", "generation"),
    ("stage", "STAGING_RESULT", "staging"),
    ("tests", "TESTS_RESULT", "test suite"),
    ("build", "BUILD_RESULT", "pack build"),
    ("verify", "VERIFY_RESULT", "pack verification"),
    ("guard", "GUARD_RESULT", "catalog guard"),
)
# The steps skipped, rather than run, when the candidate equals main's catalog.
_SKIPPED_WHEN_UNCHANGED = ("tests", "build", "verify", "guard")
_SOURCES = {
    Owner.CODM_CHECK: "codm",
    Owner.CODM_PUBLISH: "codm",
    Owner.QUIVER_CHECK: "quiver",
    Owner.QUIVER_PUBLISH: "quiver",
}
_SEE_RUN = "See the workflow run linked below for the failing step."


def _one_line(text: str) -> str:
    """`text` as one trimmed line, the shape GitHub keeps a title in."""
    return " ".join(text.split())


def _finding(key: str, title: str, details: Sequence[str]) -> Finding:
    return Finding(key, truncate_title(_one_line(title)), tuple(details))


def _finish(
    owner: Owner,
    environ: Mapping[str, str],
    findings: Sequence[Finding],
    scope: Sequence[str],
    unchecked: Sequence[str] = (),
    *,
    accounted: bool,
) -> FindingsFile:
    """The owner's file, adding its early-failure finding for a failed job that
    nothing else accounts for, and keeping only that finding for a cancelled one."""
    status = JobResult.parse(require_env(environ, "JOB_STATUS"))
    if status is JobResult.CANCELLED:
        return FindingsFile(owner, findings=(early_failure_finding(owner),))
    raised = {finding.key: finding for finding in findings}
    if status is JobResult.FAILURE and not accounted:
        early = early_failure_finding(owner)
        raised.setdefault(early.key, early)
    return FindingsFile(
        owner,
        tuple(dict.fromkeys(scope)),
        tuple(dict.fromkeys(unchecked)),
        tuple(raised.values()),
    )


def _read_object(path: Path) -> dict[str, object] | None:
    """The JSON object in the regular file at `path`, or None."""
    if regular_file_problem(path) is not None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return None
    return data if isinstance(data, dict) else None


def _objects(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _result(environ: Mapping[str, str], name: str) -> JobResult | None:
    return JobResult.parse(environ.get(name))


def emit_nightly_prepare(
    environ: Mapping[str, str], report_path: Path = BUILD_REPORT
) -> FindingsFile:
    """Stage findings from the prepare step's outputs, build warnings from its report."""
    owner = Owner.NIGHTLY_PREPARE
    prefix = OWNER_PREFIXES[owner][0]
    findings: list[Finding] = []
    scope = [
        prefix + PREPARE_STAGE_SLUGS[name]
        for name in environ.get("PREPARE_STAGES", "").split(STAGE_SEPARATOR)
        if name in PREPARE_STAGE_SLUGS
    ]
    failed_stage = environ.get("PREPARE_STAGE", "")
    if failed_stage in PREPARE_STAGE_SLUGS:
        findings.append(
            _finding(
                prefix + PREPARE_STAGE_SLUGS[failed_stage],
                f"Nightly preparation failed at the {failed_stage} stage",
                [
                    f"The nightly prepare job failed at its {failed_stage} stage.",
                    _SEE_RUN,
                ],
            )
        )
    report = _read_object(report_path)
    if report is not None:
        findings += _build_warnings(report)
        if report.get("status") == "success":
            scope.append(_BUILD_PREFIX)
    return _finish(
        owner,
        environ,
        findings,
        scope,
        accounted=failed_stage in PREPARE_STAGE_SLUGS,
    )


def _build_warnings(report: Mapping[str, object]) -> list[Finding]:
    findings: list[Finding] = []
    for item in _objects(report.get("uncategorizedFamilies")):
        family = item.get("family")
        if isinstance(family, str):
            variants = ", ".join(_strings(item.get("variants")))
            findings.append(
                _finding(
                    subject_key(_UNCATEGORIZED, family),
                    f"Family has no category: {family}",
                    [f"Family: {family}", f"Variants: {variants}"],
                )
            )
    for item in _objects(report.get("staleExclusions")):
        url, reason = item.get("url"), item.get("reason")
        if isinstance(url, str):
            details = [f"URL: {url}"]
            if isinstance(reason, str):
                details.append(f"Reason: {reason}")
            findings.append(
                _finding(
                    subject_key(_STALE_DENIAL, url),
                    f"Denial matches nothing: {url}",
                    details,
                )
            )
    for key in _strings(report.get("staleCategoryAssignments")):
        findings.append(
            _finding(
                subject_key(_STALE_CATEGORY, key),
                f"Category assignment matches nothing: {key}",
                [f"Category key: {key}"],
            )
        )
    return findings


def _publish_steps(
    owner: Owner,
    environ: Mapping[str, str],
    steps: Sequence[tuple[str, str, str]],
) -> FindingsFile:
    """Findings for write steps, given as (key slug, outcome variable, name).

    A step is re-checked when its `outcome` output is `ok` or `failed`; a
    `main-advanced` outcome raises nothing and re-checks nothing but still
    accounts for a failed job, and an empty one means the step did not run.
    """
    prefix = OWNER_PREFIXES[owner][0]
    findings: list[Finding] = []
    scope: list[str] = []
    accounted = False
    for slug, variable, name in steps:
        outcome = environ.get(variable, "")
        if outcome in (_OK, _FAILED):
            scope.append(prefix + slug)
        if outcome == _FAILED:
            findings.append(
                _finding(prefix + slug, f"{name} failed", [f"{name} failed.", _SEE_RUN])
            )
        accounted = accounted or outcome in (_FAILED, _MAIN_ADVANCED)
    return _finish(owner, environ, findings, scope, accounted=accounted)


def emit_nightly_publish(environ: Mapping[str, str]) -> FindingsFile:
    return _publish_steps(
        Owner.NIGHTLY_PUBLISH,
        environ,
        (
            ("push", "PUSH_OUTCOME", "Nightly push to main"),
            ("release", "RELEASE_OUTCOME", "Rolling release synchronization"),
        ),
    )


def emit_source_publish(environ: Mapping[str, str], owner: Owner) -> FindingsFile:
    source = _SOURCES[owner]
    return _publish_steps(
        owner,
        environ,
        (("proposal", "PUBLISH_OUTCOME", f"Publishing the {source} source proposal"),),
    )


def emit_source_check(environ: Mapping[str, str], owner: Owner) -> FindingsFile:
    """Step findings from the check job's step outcomes and `CHANGED` flag."""
    prefix = OWNER_PREFIXES[owner][0]
    source = _SOURCES[owner]
    results = {slug: _result(environ, variable) for slug, variable, _ in _CHECK_STEPS}
    unchanged = (
        results["generation"] is JobResult.SUCCESS
        and results["stage"] is JobResult.SUCCESS
        and environ.get("CHANGED") == "false"
    )
    findings: list[Finding] = []
    scope: list[str] = []
    for slug, _, name in _CHECK_STEPS:
        result = results[slug]
        if result in (JobResult.SUCCESS, JobResult.FAILURE) or (
            unchanged and slug in _SKIPPED_WHEN_UNCHANGED
        ):
            scope.append(prefix + slug)
        if result is JobResult.FAILURE:
            findings.append(
                _finding(
                    prefix + slug,
                    f"{source} {name} failed",
                    [f"The {name} step of the {source} source check failed.", _SEE_RUN],
                )
            )
    return _finish(owner, environ, findings, scope, accounted=bool(findings))


def _http_status(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def emit_live_check(
    environ: Mapping[str, str], report_path: Path = LIVE_CHECK_REPORT
) -> FindingsFile:
    """Findings from the live check's report, read only when the check step ran."""
    ran = _result(environ, "CHECK_RESULT") in (JobResult.SUCCESS, JobResult.FAILURE)
    report = _read_object(report_path) if ran else None
    if report is not None and report.get("status") not in ("success", "failed"):
        report = None
    findings: list[Finding] = []
    scope: list[str] = []
    unchecked: list[str] = []
    if report is not None:
        scope.append(_LIVE_READ)
        if report["status"] == "failed":
            findings.append(
                _finding(
                    _LIVE_READ,
                    "Live check could not read the committed packs",
                    [
                        "The committed packs could not be read; no URL was checked.",
                        _SEE_RUN,
                    ],
                )
            )
        else:
            scope += [_GONE, _STATUS]
            for item in _objects(report.get("unreachable")):
                url, status = item.get("url"), item.get("status")
                if not isinstance(url, str):
                    continue
                # A status that is not an HTTP code is left out of the text.
                known = _http_status(status)
                findings.append(
                    _finding(
                        subject_key(_GONE, url),
                        f"Project URL is gone{f' (HTTP {status})' if known else ''}: {url}",
                        [f"URL: {url}", *([f"Status: HTTP {status}"] if known else [])],
                    )
                )
            for item in _objects(report.get("inconclusive")):
                url, status = item.get("url"), item.get("status")
                if not isinstance(url, str):
                    continue
                if _http_status(status):
                    findings.append(
                        _finding(
                            subject_key(_STATUS, url),
                            f"Project URL answers HTTP {status}: {url}",
                            [f"URL: {url}", f"Status: HTTP {status}"],
                        )
                    )
                else:
                    unchecked += [subject_key(_GONE, url), subject_key(_STATUS, url)]
    return _finish(
        Owner.LIVE_CHECK,
        environ,
        findings,
        scope,
        unchecked,
        # The check step fails the job for unreadable packs or a gone URL, never
        # for an inconclusive status, so only those findings account for it.
        accounted=any(
            finding.key == _LIVE_READ or finding.key.startswith(_GONE)
            for finding in findings
        ),
    )


def emit(
    owner: Owner, environ: Mapping[str, str], report_path: Path | None = None
) -> FindingsFile:
    """The findings file for `owner` from the environment `EMIT_HELP` documents."""
    if owner is Owner.NIGHTLY_PREPARE:
        return emit_nightly_prepare(environ, report_path or BUILD_REPORT)
    if owner is Owner.NIGHTLY_PUBLISH:
        return emit_nightly_publish(environ)
    if owner is Owner.LIVE_CHECK:
        return emit_live_check(environ, report_path or LIVE_CHECK_REPORT)
    if owner in (Owner.CODM_CHECK, Owner.QUIVER_CHECK):
        return emit_source_check(environ, owner)
    return emit_source_publish(environ, owner)


def write_findings(file: FindingsFile, output: Path) -> None:
    """Write `file` whole, replacing any earlier one."""
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".partial")
    try:
        partial.write_text(file.to_json() + "\n", encoding="utf-8")
        partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)


def _emit_command(arguments: argparse.Namespace, environ: Mapping[str, str]) -> int:
    findings = emit(arguments.owner, environ, arguments.report)
    try:
        write_findings(findings, arguments.output)
    except OSError:
        print("emit failed: could not write the findings file", file=sys.stderr)
        return 1
    return 0


def _parse_producer(value: str) -> Producer:
    name, separator, rest = value.partition("=")
    try:
        owner = Owner(name)
    except ValueError:
        raise SystemExit(f"unknown producer owner: {name}") from None
    result, colon, path = rest.partition(":")
    if not separator or not colon or not path:
        raise SystemExit(f"--producer needs OWNER=RESULT:PATH, got {value}")
    return Producer(owner, Path(path), JobResult.parse(result))


def _reconcile_command(
    arguments: argparse.Namespace, environ: Mapping[str, str]
) -> int:
    producers = [_parse_producer(value) for value in arguments.producer]
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
        metavar="OWNER=RESULT:PATH",
        help="an expected producer, its job result and its findings file; an "
        "empty or unknown RESULT makes the producer contribute nothing",
    )
    emit_parser = subparsers.add_parser(
        "emit",
        help="write one producing job's findings file",
        description=EMIT_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    emit_parser.add_argument("owner", type=Owner, choices=list(Owner))
    emit_parser.add_argument("--report", type=Path, default=None)
    emit_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args(argv)
    if arguments.command == "emit":
        return _emit_command(arguments, os.environ)
    return _reconcile_command(arguments, os.environ)


if __name__ == "__main__":
    sys.exit(main())
