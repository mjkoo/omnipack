"""Git publication, concurrency handling, and remote reconciliation."""

from __future__ import annotations

import base64
import os
import subprocess
from collections.abc import Callable, Mapping
from contextlib import ExitStack
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from scripts.nightly_publish import (
    CandidateError,
    CommandResult,
    LocalAttemptFactory,
    PublicationCandidate,
    RefreshResult,
    StageOutcome,
    _git,
    _git_bytes,
    _git_paths,
)


class RefreshBoundary(Protocol):
    def run(self, root: Path, base_sha: str) -> RefreshResult: ...


class RemoteBoundary(Protocol):
    def fetch_main(self) -> str: ...

    def push(self, root: Path, token: str) -> CommandResult: ...

    def main_contains(self, root: Path, sha: str) -> bool: ...


class ReleaseBoundary(Protocol):
    def synchronize(self, single: bytes, dual: bytes, source_commit: str) -> object: ...


class GitProcessBoundary(Protocol):
    def run(
        self,
        command: tuple[str, ...],
        cwd: Path,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult: ...


class GitSubprocessBoundary:
    def run(
        self,
        command: tuple[str, ...],
        cwd: Path,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        process_env = os.environ.copy()
        process_env.update(env or {})
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=process_env,
            capture_output=True,
            text=True,
            check=False,
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


class GitRemote:
    """Read and fast-forward the configured origin without persisting credentials."""

    def __init__(
        self, source: Path, *, runner: GitProcessBoundary | None = None
    ) -> None:
        self.source = source
        self.runner = runner or GitSubprocessBoundary()

    def fetch_main(self) -> str:
        result = self.runner.run(
            (
                "git",
                "fetch",
                "--quiet",
                "origin",
                "refs/heads/main:refs/remotes/origin/main",
            ),
            self.source,
        )
        if result.returncode != 0:
            raise OSError("unable to fetch remote main")
        resolved = self.runner.run(
            ("git", "rev-parse", "refs/remotes/origin/main"), self.source
        )
        if resolved.returncode != 0:
            raise OSError("unable to resolve remote main")
        return resolved.stdout.strip()

    def push(self, root: Path, token: str) -> CommandResult:
        authorization = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env = {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {authorization}",
        }
        return self.runner.run(
            ("git", "push", "origin", "HEAD:refs/heads/main"), root, env
        )

    def main_contains(self, root: Path, sha: str) -> bool:
        fetched = self.runner.run(
            (
                "git",
                "fetch",
                "--quiet",
                "origin",
                "refs/heads/main:refs/remotes/origin/main",
            ),
            root,
        )
        if fetched.returncode != 0:
            raise OSError("unable to fetch remote main")
        result = self.runner.run(
            (
                "git",
                "merge-base",
                "--is-ancestor",
                sha,
                "refs/remotes/origin/main",
            ),
            root,
        )
        if result.returncode not in (0, 1):
            raise OSError("unable to inspect remote main ancestry")
        return result.returncode == 0


@dataclass(frozen=True)
class AttemptRecord:
    number: int
    base_sha: str
    stages: tuple[StageOutcome, ...]
    build_report: bytes | None
    verify_report: bytes | None
    candidate_sha: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class PublicationResult:
    status: str
    attempts: tuple[AttemptRecord, ...]
    base_sha: str | None
    published_sha: str | None
    stage: str
    detail: str = ""
    cleanup_errors: tuple[str, ...] = ()
    release_status: str = "not-run"
    release_revision: int | None = None
    pending_revision: int | None = None
    pack_snapshots: Mapping[str, bytes] | None = None


class PublicationCoordinator:
    def __init__(
        self,
        attempts: LocalAttemptFactory,
        refresh: RefreshBoundary,
        remote: RemoteBoundary,
        release: ReleaseBoundary | None = None,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.attempts = attempts
        self.refresh = refresh
        self.remote = remote
        self.release = release
        self.now = now or (lambda: datetime.now(UTC))

    def run(self, run_url: str, token: str) -> PublicationResult:
        cleanup_start = len(self.attempts.cleanup_errors)
        result = self._run(run_url, token)
        result = replace(
            result, cleanup_errors=tuple(self.attempts.cleanup_errors[cleanup_start:])
        )
        if (
            self.release is None
            or result.status not in ("published", "no-op")
            or result.pack_snapshots is None
        ):
            if self.release is None and result.status in ("published", "no-op"):
                return replace(
                    result,
                    stage="release",
                    detail="release synchronization boundary is unavailable",
                    pack_snapshots=None,
                )
            return result
        source_commit = result.published_sha or result.base_sha
        if source_commit is None:
            return result
        try:
            synchronized = self.release.synchronize(
                result.pack_snapshots["dist/single-screen.json"],
                result.pack_snapshots["dist/dual-screen.json"],
                source_commit,
            )
        except Exception as error:  # noqa: BLE001 - release is an external boundary
            return replace(
                result,
                stage="release",
                detail=str(error),
                release_status="failed",
                pending_revision=getattr(error, "pending_revision", None),
                pack_snapshots=None,
            )
        return replace(
            result,
            release_status="success",
            release_revision=getattr(synchronized, "revision", None),
            pending_revision=getattr(synchronized, "pending_revision", None),
            pack_snapshots=None,
        )

    def _run(self, run_url: str, token: str) -> PublicationResult:
        records: list[AttemptRecord] = []
        try:
            base_sha = self.remote.fetch_main()
        except OSError:
            return PublicationResult(
                "failed", (), None, None, "fetch", "remote main unavailable"
            )

        for number in (1, 2):
            started_at = self.now()
            with ExitStack() as stack:
                try:
                    root = stack.enter_context(self.attempts.checkout(base_sha))
                except CandidateError, OSError:
                    records.append(
                        AttemptRecord(
                            number,
                            base_sha,
                            (
                                StageOutcome(
                                    "checkout", "failed", "attempt setup failed"
                                ),
                            ),
                            None,
                            None,
                            started_at=started_at,
                            finished_at=self.now(),
                        )
                    )
                    return PublicationResult(
                        "failed",
                        tuple(records),
                        base_sha,
                        None,
                        "checkout",
                        "attempt setup failed",
                    )
                refreshed = self.refresh.run(root, base_sha)
                record = AttemptRecord(
                    number,
                    base_sha,
                    refreshed.stages,
                    _read_optional(root / ".build/report.json"),
                    _read_optional(root / ".build/verify.json"),
                    started_at=started_at,
                    finished_at=self.now(),
                )
                records.append(record)
                if refreshed.status == "failed" or refreshed.candidate is None:
                    stage = (
                        refreshed.stages[-1].stage if refreshed.stages else "refresh"
                    )
                    return PublicationResult(
                        "failed",
                        tuple(records),
                        base_sha,
                        None,
                        stage,
                        "refresh failed",
                    )

                try:
                    current = self.remote.fetch_main()
                except OSError:
                    return PublicationResult(
                        "failed",
                        tuple(records),
                        base_sha,
                        None,
                        "fetch",
                        "remote main unavailable",
                    )
                if current != base_sha:
                    if number == 2:
                        return PublicationResult(
                            "failed",
                            tuple(records),
                            base_sha,
                            None,
                            "concurrency",
                            "remote main advanced twice",
                        )
                    base_sha = current
                    continue

                if refreshed.status == "no-op":
                    return PublicationResult(
                        "no-op",
                        tuple(records),
                        base_sha,
                        None,
                        "complete",
                        pack_snapshots=_pack_snapshots(refreshed.candidate),
                    )

                try:
                    commit_sha = _create_candidate_commit(
                        refreshed.candidate, self.now(), run_url, base_sha
                    )
                except CandidateError:
                    return PublicationResult(
                        "failed",
                        tuple(records),
                        base_sha,
                        None,
                        "commit",
                        "candidate commit failed",
                    )
                records[-1] = replace(records[-1], candidate_sha=commit_sha)
                try:
                    pushed = self.remote.push(root, token)
                except OSError:
                    pushed = CommandResult(1, "", "push outcome unavailable")
                if pushed.returncode == 0:
                    return PublicationResult(
                        "published",
                        tuple(records),
                        base_sha,
                        commit_sha,
                        "complete",
                        pack_snapshots=_pack_snapshots(refreshed.candidate),
                    )
                try:
                    if self.remote.main_contains(root, commit_sha):
                        return PublicationResult(
                            "published",
                            tuple(records),
                            base_sha,
                            commit_sha,
                            "complete",
                            pack_snapshots=_pack_snapshots(refreshed.candidate),
                        )
                    current = self.remote.fetch_main()
                except OSError:
                    return PublicationResult(
                        "uncertain",
                        tuple(records),
                        base_sha,
                        None,
                        "push",
                        "remote publication outcome is unreadable",
                    )
                if current != base_sha and number == 1:
                    base_sha = current
                    continue
                return PublicationResult(
                    "failed",
                    tuple(records),
                    base_sha,
                    None,
                    "push",
                    "push rejected and intended commit is absent from remote main",
                )
        raise AssertionError("attempt loop must return")


def _create_candidate_commit(
    candidate: PublicationCandidate, observed: datetime, run_url: str, base_sha: str
) -> str:
    candidate.stage_and_validate()
    date = observed.astimezone(UTC).date().isoformat()
    subject = f"chore(dist): nightly rebuild {date}"
    body = f"Workflow run: {run_url}\n\nBase SHA: {base_sha}"
    _git(
        candidate.root,
        "-c",
        "user.name=github-actions[bot]",
        "-c",
        "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "--quiet",
        "-m",
        subject,
        "-m",
        body,
    )
    sha = _git_bytes(candidate.root, "rev-parse", "HEAD").decode().strip()
    paths = _git_paths(
        candidate.root,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        "-z",
        sha,
    )
    if paths != set(candidate.changed_paths):
        raise CandidateError("commit path set does not match verified candidate")
    for relative in paths:
        if (
            _git_bytes(candidate.root, "show", f"{sha}:{relative}")
            != candidate.snapshots[relative]
        ):
            raise CandidateError(f"commit content does not match {relative}")
    return sha


def _pack_snapshots(candidate: PublicationCandidate) -> Mapping[str, bytes]:
    return {
        name: candidate.snapshots[name]
        for name in ("dist/single-screen.json", "dist/dual-screen.json")
    }


def _read_optional(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None
