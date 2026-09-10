"""Testable orchestration for verified nightly publication candidates."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from omnipack.catalog import CatalogError, split_catalog
from omnipack.report import ReportFormatError, _validate_verification_report
from omnipack.verify import VERIFY_PATH, capture_inputs, verifier_identity

ALLOWED_PATHS = (
    "dist/single-screen.json",
    "dist/dual-screen.json",
    "README.md",
    "config/package-ids.json",
)


class CandidateError(RuntimeError):
    """A refresh result is not safe to publish."""


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class ProcessBoundary(Protocol):
    def run(self, command: Sequence[str], cwd: Path) -> CommandResult: ...


class SubprocessBoundary:
    """Run a command without shell interpolation."""

    def run(self, command: Sequence[str], cwd: Path) -> CommandResult:
        completed = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, check=False
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


@dataclass(frozen=True)
class StageOutcome:
    stage: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class RefreshResult:
    status: str
    base_sha: str
    stages: tuple[StageOutcome, ...]
    candidate: PublicationCandidate | None = None


@dataclass(frozen=True)
class PublicationCandidate:
    root: Path
    snapshots: Mapping[str, bytes]
    changed_paths: tuple[str, ...]

    @classmethod
    def capture(
        cls, root: Path, *, validate_evidence: Callable[[Path], None] | None = None
    ) -> PublicationCandidate:
        (validate_evidence or _validate_live_evidence)(root)
        snapshots = _snapshot_allowed(root)
        _reject_unexpected_tracked_changes(root)
        _validate_readme_change(root, snapshots["README.md"])
        changed = tuple(
            path
            for path in ALLOWED_PATHS
            if snapshots[path] != _git_bytes(root, "show", f"HEAD:{path}")
        )
        return cls(root, snapshots, changed)

    def stage_and_validate(self) -> None:
        if _snapshot_allowed(self.root) != self.snapshots:
            raise CandidateError("candidate bytes changed after verification")
        _reject_unexpected_tracked_changes(self.root)
        _git(self.root, "add", "--", *ALLOWED_PATHS)
        for relative in ALLOWED_PATHS:
            mode = _base_mode(self.root, relative)
            _git(
                self.root,
                "update-index",
                f"--chmod={'+x' if mode == b'100755' else '-x'}",
                "--",
                relative,
            )
        self.validate_staged()

    def validate_staged(self) -> None:
        _reject_unexpected_tracked_changes(self.root)
        if _snapshot_allowed(self.root) != self.snapshots:
            raise CandidateError("candidate bytes changed after verification")
        for relative in ALLOWED_PATHS:
            mode = _git_bytes(self.root, "ls-files", "--stage", "--", relative).split()[
                0
            ]
            if mode != _base_mode(self.root, relative):
                raise CandidateError(f"staged mode does not match base for {relative}")
        staged_readme = _git_bytes(self.root, "show", ":README.md")
        _validate_readme_change(self.root, staged_readme)
        staged = _git_paths(
            self.root, "diff", "--cached", "--name-only", "-z", "HEAD", "--"
        )
        if staged != set(self.changed_paths):
            raise CandidateError("staged path set does not match verified candidate")
        for relative in staged:
            value = _git_bytes(self.root, "show", f":{relative}")
            if value != self.snapshots[relative]:
                raise CandidateError(f"staged content does not match {relative}")


@dataclass(frozen=True)
class Check:
    stage: str
    command: tuple[str, ...]


CHECKS = (
    Check("sync", ("uv", "sync", "--locked")),
    Check("format-check", ("uv", "run", "--no-sync", "ruff", "format", "--check")),
    Check("lint-check", ("uv", "run", "--no-sync", "ruff", "check")),
    Check("typecheck", ("uv", "run", "--no-sync", "ty", "check")),
    Check(
        "python-build",
        ("uv", "build", "--no-sources", "--out-dir", "build/python-dist"),
    ),
    Check("tests", ("uv", "run", "--no-sync", "pytest", "--cov")),
    Check("offline-verify", ("uv", "run", "--no-sync", "pack", "verify")),
    Check("build", ("uv", "run", "--no-sync", "pack", "build")),
)
LIVE_VERIFY = Check(
    "live-verify", ("uv", "run", "--no-sync", "pack", "verify", "--live")
)


class RefreshOrchestrator:
    def __init__(self, process: ProcessBoundary) -> None:
        self.process = process

    def run(self, root: Path, base_sha: str) -> RefreshResult:
        outcomes: list[StageOutcome] = []
        for check in CHECKS:
            if failure := self._run(check, root):
                outcomes.append(failure)
                return RefreshResult("failed", base_sha, tuple(outcomes))
            outcomes.append(StageOutcome(check.stage, "success"))

        try:
            before_verify = _snapshot_allowed(root)
        except CandidateError as error:
            outcomes.append(StageOutcome("candidate", "failed", str(error)))
            return RefreshResult("failed", base_sha, tuple(outcomes))
        evidence = root / VERIFY_PATH
        try:
            evidence.unlink(missing_ok=True)
        except OSError as error:
            outcomes.append(StageOutcome("live-verify", "failed", str(error)))
            return RefreshResult("failed", base_sha, tuple(outcomes))
        invoked_at = datetime.now(UTC)
        if failure := self._run(LIVE_VERIFY, root):
            outcomes.append(failure)
            return RefreshResult("failed", base_sha, tuple(outcomes))
        outcomes.append(StageOutcome("live-verify", "success"))

        try:
            if _snapshot_allowed(root) != before_verify:
                raise CandidateError("publishable bytes changed during verification")
            candidate = PublicationCandidate.capture(
                root,
                validate_evidence=lambda path: self._validate_attempt_evidence(
                    path, invoked_at
                ),
            )
            if candidate.snapshots != before_verify:
                raise CandidateError("publishable bytes changed during verification")
            candidate.stage_and_validate()
        except CandidateError as error:
            outcomes.append(StageOutcome("candidate", "failed", str(error)))
            return RefreshResult("failed", base_sha, tuple(outcomes))
        outcomes.append(StageOutcome("candidate", "success"))
        status = "no-op" if not candidate.changed_paths else "publishable"
        return RefreshResult(status, base_sha, tuple(outcomes), candidate)

    def _validate_attempt_evidence(self, root: Path, invoked_at: datetime) -> None:
        check = Check(
            "candidate",
            (
                "uv",
                "run",
                "--no-sync",
                "python",
                "-m",
                "scripts.nightly_publish",
                "--validate-evidence",
                invoked_at.isoformat(),
            ),
        )
        if failure := self._run(check, root):
            raise CandidateError(failure.detail)

    def _run(self, check: Check, root: Path) -> StageOutcome | None:
        try:
            result = self.process.run(check.command, root)
        except OSError as error:
            return StageOutcome(check.stage, "failed", str(error))
        if result.returncode == 0:
            return None
        detail = result.stderr.strip() or result.stdout.strip()
        return StageOutcome(check.stage, "failed", detail)


class LocalAttemptFactory:
    """Create clean, disposable local checkouts for refresh attempts."""

    def __init__(self, source: Path) -> None:
        self.source = source
        self.cleanup_errors: list[str] = []
        try:
            self.remote_url = (
                _git_bytes(source, "remote", "get-url", "origin").decode().strip()
            )
        except CandidateError:
            self.remote_url = str(source)

    @contextmanager
    def checkout(self, base_sha: str) -> Iterator[Path]:
        root = Path(tempfile.mkdtemp(prefix="obtainium-nightly-"))
        try:
            _git(
                root.parent,
                "clone",
                "--quiet",
                "--no-checkout",
                str(self.source),
                str(root),
            )
            _git(root, "remote", "set-url", "origin", self.remote_url)
            _git(root, "checkout", "--quiet", "--detach", base_sha)
            yield root
        finally:
            try:
                shutil.rmtree(root)
            except OSError as error:
                self.cleanup_errors.append(f"attempt checkout cleanup failed: {error}")


def validate_candidate(root: Path) -> PublicationCandidate:
    candidate = PublicationCandidate.capture(root)
    candidate.stage_and_validate()
    return candidate


def _validate_live_evidence(root: Path, invoked_at: datetime | None = None) -> None:
    path = root / VERIFY_PATH
    try:
        report = json.loads(path.read_bytes())
        if not isinstance(report, dict):
            raise CandidateError("live verification evidence is malformed")
        _validate_verification_report(report)
    except FileNotFoundError as error:
        raise CandidateError("live verification evidence is absent") from error
    except (OSError, ValueError, ReportFormatError) as error:
        raise CandidateError(
            f"live verification evidence is malformed: {error}"
        ) from error
    _, current = capture_inputs(root)
    try:
        started = datetime.fromisoformat(report["startedAt"])
        completed = datetime.fromisoformat(report["completedAt"])
        if started.tzinfo is None or completed.tzinfo is None:
            raise ValueError("timestamps must include timezone offsets")
    except (KeyError, TypeError, ValueError) as error:
        raise CandidateError("live verification timestamps are invalid") from error
    if (
        report["mode"] != "live"
        or report["status"] != "success"
        or not report["complete"]
        or report["errors"]
        or report["verifier"] != verifier_identity()
        or report["inputs"] != current
        or (invoked_at is not None and started < invoked_at)
        or completed < started
    ):
        raise CandidateError("live verification evidence is stale or incomplete")


def _base_mode(root: Path, relative: str) -> bytes:
    entry = _git_bytes(root, "ls-tree", "HEAD", "--", relative).split()
    if not entry or entry[0] not in (b"100644", b"100755"):
        raise CandidateError(f"base publishable path is not a regular file: {relative}")
    return entry[0]


def _validate_readme_change(root: Path, candidate: bytes) -> None:
    base = _git_bytes(root, "show", "HEAD:README.md")
    try:
        base_prefix, _, base_suffix = split_catalog(base)
        candidate_prefix, _, candidate_suffix = split_catalog(candidate)
    except CatalogError as error:
        raise CandidateError(str(error)) from error
    if candidate_prefix != base_prefix or candidate_suffix != base_suffix:
        raise CandidateError("README changed outside catalog markers")


def _snapshot_allowed(root: Path) -> dict[str, bytes]:
    snapshots: dict[str, bytes] = {}
    for relative in ALLOWED_PATHS:
        path = root / relative
        current = root
        for part in Path(relative).parts[:-1]:
            current /= part
            if current.is_symlink():
                raise CandidateError(
                    f"publishable path uses a symlink directory: {relative}"
                )
        try:
            stat = path.lstat()
        except FileNotFoundError as error:
            raise CandidateError(f"missing publishable file: {relative}") from error
        if not path.is_file() or path.is_symlink() or not stat.st_mode:
            raise CandidateError(f"publishable path is not a regular file: {relative}")
        try:
            snapshots[relative] = path.read_bytes()
        except OSError as error:
            raise CandidateError(f"cannot read publishable file: {relative}") from error
    return snapshots


def _reject_unexpected_tracked_changes(root: Path) -> None:
    changed = _git_paths(root, "diff", "--name-only", "-z", "HEAD", "--")
    unexpected = changed - set(ALLOWED_PATHS)
    if unexpected:
        raise CandidateError(
            f"unexpected tracked changes: {', '.join(sorted(unexpected))}"
        )


def _git_paths(root: Path, *args: str) -> set[str]:
    return {item.decode() for item in _git_bytes(root, *args).split(b"\0") if item}


def _git_bytes(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, check=False
    )
    if completed.returncode != 0:
        raise CandidateError(completed.stderr.decode(errors="replace").strip())
    return completed.stdout


def _git(root: Path, *args: str) -> None:
    completed = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, check=False
    )
    if completed.returncode != 0:
        raise CandidateError(completed.stderr.decode(errors="replace").strip())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--validate-evidence", required=True, type=datetime.fromisoformat
    )
    arguments = parser.parse_args()
    try:
        _validate_live_evidence(Path.cwd(), arguments.validate_evidence)
    except CandidateError as error:
        raise SystemExit(str(error)) from error
