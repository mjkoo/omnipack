"""Archive each target's current release, and the run loop around it.

A version counts as archived exactly when its manifest exists in the bucket.
A target is checked by resolving its version and asking for that manifest; a
version without one has every object stored under its own prefix and the
manifest written last, so an interrupted or failed attempt leaves nothing
that reads as archived and is simply attempted again.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import tempfile
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NotRequired, Protocol, TypedDict

from omnipack.archive import Outcome, ResolutionError, ResolvedRelease
from omnipack.archive.github import resolve_github
from omnipack.archive.gitlab import resolve_gitlab
from omnipack.archive.html import resolve_html
from omnipack.archive.source import CaptureOutcome, CaptureResult, capture_source
from omnipack.archive.store import StoreError
from omnipack.archive.targets import (
    ArchiveTarget,
    escape_segment,
    select_targets,
)
from omnipack.http import HttpClient, failure_reason
from omnipack.live_check import PackReadError, request_headers
from omnipack.model import SourceType
from omnipack.report_model import Status
from omnipack.urls import normalize_project_url

OUTPUT = Path(".build/archive")
REPORT = OUTPUT / "report.json"
SUMMARY = OUTPUT / "summary.md"

SLUG_LENGTH = 80
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")
HASH_CHUNK = 1024 * 1024


class Bucket(Protocol):
    """What the flow needs of the store."""

    def exists(self, key: str) -> bool: ...

    def put_json(self, key: str, document: Any) -> None: ...

    def upload_file(self, path: Path, key: str) -> None: ...


class BudgetSpent(Exception):
    """The run's deadline passed while a target was being archived."""


class ObjectRecord(TypedDict):
    """One stored object, keyed relative to its version's prefix."""

    key: str
    size: int
    sha256: str
    url: NotRequired[str]


class SourceHistory(TypedDict):
    """A forge version's source bundle, or why there is none."""

    key: NotRequired[str]
    size: NotRequired[int]
    sha256: NotRequired[str]
    reason: NotRequired[str]


class Manifest(TypedDict):
    """The record that marks a version archived."""

    entry: dict[str, Any]
    sourceType: SourceType
    version: str
    tag: str | None
    releaseDate: str | None
    archivedAt: str
    objects: list[ObjectRecord]
    sourceHistory: NotRequired[SourceHistory]
    fetchedUrls: NotRequired[list[str]]


class TargetReport(TypedDict):
    """One target's result. A dry run that resolved a target carries its
    version and no outcome, since nothing was archived or compared."""

    name: str
    url: str
    outcome: NotRequired[Outcome]
    version: NotRequired[str]
    error: NotRequired[str]
    reason: NotRequired[str]


class ArchiveReport(TypedDict):
    """The run's report. `status` is `failed` only for a run-level error
    (unreadable packs, an unusable bucket), described by `error`; any
    target-level outcome leaves a run `success`."""

    status: Status
    dryRun: bool
    targets: list[TargetReport]
    error: NotRequired[str]


def version_slug(version: str) -> str:
    """The version as a bucket path segment: sanitized, truncated and tagged
    with a digest of the raw version so distinct versions never share one."""
    digest = hashlib.sha256(version.encode()).hexdigest()[:8]
    return f"{_UNSAFE.sub('_', version)[:SLUG_LENGTH]}-{digest}"


def _describe(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(HASH_CHUNK):
            digest.update(chunk)
    return path.stat().st_size, digest.hexdigest()


class Archiver:
    """Archives targets one at a time into a bucket, or only resolves them
    when `bucket` is None (a dry run)."""

    def __init__(
        self,
        bucket: Bucket | None,
        http: HttpClient,
        *,
        github_token: str | None = None,
        deadline: float | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        capture: Callable[..., CaptureResult] = capture_source,
    ) -> None:
        self.bucket = bucket
        self.http = http
        self.github_token = github_token
        self.deadline = deadline
        self.now = now
        self.capture = capture

    def process(self, target: ArchiveTarget) -> TargetReport:
        """The target's report. Only a `StoreError` escapes; every other
        failure is that target's outcome."""
        report = TargetReport(name=target.entry["name"], url=target.entry["url"])
        if target.skip is not None:
            report["outcome"] = Outcome.SKIPPED
            report["reason"] = str(target.skip)
            return report
        try:
            release = self._resolve(target)
            report["version"] = release.version
            if self.bucket is not None:
                report["outcome"] = self._archive(target, release)
        except StoreError:
            raise
        except ResolutionError as error:
            report["outcome"] = error.outcome
            report["error"] = str(error)
        except Exception as error:  # noqa: BLE001 - every failure is the target
            report["outcome"] = Outcome.FAILED
            report["error"] = failure_reason(error)
        return report

    def _resolve(self, target: ArchiveTarget) -> ResolvedRelease:
        match target.source:
            case SourceType.GITHUB:
                return resolve_github(
                    target.entry,
                    self.http,
                    token=self.github_token,
                    deadline=self.deadline,
                )
            case SourceType.GITLAB:
                return resolve_gitlab(target.entry, self.http, deadline=self.deadline)
            case SourceType.HTML:
                return resolve_html(target.entry, self.http, deadline=self.deadline)
        raise ValueError(f"no resolver for source {target.source}")

    def _check_time(self) -> None:
        if self.deadline is not None and self.http.clock() >= self.deadline:
            raise BudgetSpent("the run's time budget passed")

    def _archive(self, target: ArchiveTarget, release: ResolvedRelease) -> Outcome:
        bucket = self.bucket
        assert bucket is not None
        if target.source is None:
            raise ValueError(f"target {target.key} has no source type")
        prefix = f"apps/{target.key}/releases/{version_slug(release.version)}"
        manifest_key = f"{prefix}/manifest.json"
        if bucket.exists(manifest_key):
            return Outcome.UNCHANGED

        objects: list[ObjectRecord] = []
        with tempfile.TemporaryDirectory(prefix="archive-") as scratch:
            work = Path(scratch)

            def store(path: Path, key: str, url: str | None = None) -> ObjectRecord:
                self._check_time()
                size, sha256 = _describe(path)
                bucket.upload_file(path, f"{prefix}/{key}")
                record = ObjectRecord(key=key, size=size, sha256=sha256)
                if url is not None:
                    record["url"] = url
                objects.append(record)
                path.unlink()
                return record

            self._store_assets(target, release, work, store)
            manifest = Manifest(
                entry=target.entry,
                sourceType=target.source,
                version=release.version,
                tag=release.tag,
                releaseDate=release.date.isoformat() if release.date else None,
                archivedAt=self.now().isoformat(),
                objects=objects,
            )
            if target.source is SourceType.HTML:
                manifest["fetchedUrls"] = list(release.raw_record["fetched_urls"])
            else:
                manifest["sourceHistory"] = self._store_forge_files(
                    target, release, work, store
                )
            self._check_time()
            bucket.put_json(manifest_key, manifest)
        return Outcome.ARCHIVED

    def _store_assets(
        self,
        target: ArchiveTarget,
        release: ResolvedRelease,
        work: Path,
        store: Callable[..., ObjectRecord],
    ) -> None:
        headers = (
            request_headers(target.entry.get("additionalSettings"))
            if target.source is SourceType.HTML
            else None
        )
        used: set[str] = set()
        for number, asset in enumerate(release.assets):
            name = escape_segment(asset.name)
            if name in used:
                name = f"{number}-{name}"
                while name in used:
                    name = f"{number}-{name}"
            used.add(name)
            path = work / "asset"
            self.http.download(asset.url, path, headers, deadline=self.deadline)
            store(path, f"assets/{name}", asset.url)

    def _store_forge_files(
        self,
        target: ArchiveTarget,
        release: ResolvedRelease,
        work: Path,
        store: Callable[..., ObjectRecord],
    ) -> SourceHistory:
        record = work / "release.json"
        record.write_text(json.dumps(release.raw_record, indent=2, sort_keys=True))
        store(record, "release.json")
        if release.notes:
            notes = work / "release.md"
            notes.write_text(release.notes)
            store(notes, "release.md")

        bundle = work / "repo.bundle.zst"
        result = self.capture(
            f"https://{normalize_project_url(target.entry['url'])}",
            bundle,
            work,
            deadline=self.deadline,
            clock=self.http.clock,
        )
        if result.outcome is CaptureOutcome.EXPIRED:
            # Not a missing history: the target is abandoned so the next run
            # archives it whole.
            raise BudgetSpent(result.reason or "the run's time budget passed")
        if result.outcome is CaptureOutcome.CAPTURED:
            stored = store(bundle, "source/repo.bundle.zst")
            return SourceHistory(
                key=stored["key"], size=stored["size"], sha256=stored["sha256"]
            )
        return SourceHistory(reason=result.reason or "source capture failed")


def run_archive(
    root: Path,
    bucket: Bucket | None,
    *,
    http: HttpClient | None = None,
    github_token: str | None = None,
    budget: float | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    capture: Callable[..., CaptureResult] = capture_source,
) -> ArchiveReport:
    """Archive every target of the packs under `root`, serially.

    `budget` is seconds on the client's clock from now: once spent no new
    target starts and the rest are not checked, and the target in flight is
    abandoned at the deadline. A `bucket` of None resolves without writing.
    A pack that cannot be read, or a bucket error, ends the run with a failed
    report.
    """
    client = http or HttpClient()
    report = ArchiveReport(status=Status.SUCCESS, dryRun=bucket is None, targets=[])
    try:
        targets = select_targets(root)
    except PackReadError as error:
        report["status"] = Status.FAILED
        report["error"] = str(error)
        return report
    deadline = None if budget is None else client.clock() + budget
    archiver = Archiver(
        bucket,
        client,
        github_token=github_token,
        deadline=deadline,
        now=now,
        capture=capture,
    )
    stopped: str | None = None
    for target in targets:
        entry = target.entry
        if stopped is not None:
            report["targets"].append(
                TargetReport(
                    name=entry["name"],
                    url=entry["url"],
                    outcome=Outcome.NOT_CHECKED,
                    reason=stopped,
                )
            )
            continue
        if deadline is not None and client.clock() >= deadline:
            stopped = "time budget spent"
            report["targets"].append(
                TargetReport(
                    name=entry["name"],
                    url=entry["url"],
                    outcome=Outcome.NOT_CHECKED,
                    reason=stopped,
                )
            )
            continue
        try:
            report["targets"].append(archiver.process(target))
        except StoreError as error:
            report["status"] = Status.FAILED
            report["error"] = str(error)
            stopped = "the run stopped on a bucket error"
            report["targets"].append(
                TargetReport(
                    name=entry["name"],
                    url=entry["url"],
                    outcome=Outcome.NOT_CHECKED,
                    reason=stopped,
                )
            )
    return report


def failed_report(error: str, *, dry_run: bool) -> ArchiveReport:
    """A report for a run that could not start."""
    return ArchiveReport(status=Status.FAILED, dryRun=dry_run, targets=[], error=error)


def render_summary(report: ArchiveReport) -> str:
    """Render the report for a run summary, escaped inside a `<pre>` block."""
    title = "Release archive dry run" if report["dryRun"] else "Release archive"
    lines = [f"## {title}", "", "<pre>"]
    if report["status"] == Status.FAILED:
        lines.append(f"Run failed: {html.escape(report.get('error', ''))}")
    counts = Counter(target.get("outcome") for target in report["targets"])
    for outcome in Outcome:
        if counts[outcome]:
            lines.append(f"{outcome}: {counts[outcome]}")
    if counts[None]:
        lines.append(f"resolved: {counts[None]}")
    lines.append("")
    for target in report["targets"]:
        outcome = target.get("outcome")
        if outcome in (Outcome.UNCHANGED, Outcome.NOT_CHECKED):
            continue
        detail = target.get("version") or target.get("error") or target.get("reason")
        label = outcome or "resolved"
        lines.append(
            html.escape(f"{label}: {target['url']} ({target['name']}): {detail}")
        )
    return "\n".join([*lines, "</pre>"]) + "\n"


def write_archive_report(root: Path, report: ArchiveReport) -> None:
    """Write the report and its summary, replacing any earlier pair."""
    (root / OUTPUT).mkdir(parents=True, exist_ok=True)
    (root / REPORT).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (root / SUMMARY).write_text(render_summary(report), encoding="utf-8")
