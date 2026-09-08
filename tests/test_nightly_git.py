from __future__ import annotations

import base64
import os
import subprocess
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from scripts.nightly_git import (
    GitRemote,
    PublicationCoordinator,
    RemoteBoundary,
)
from scripts.nightly_publish import (
    ALLOWED_PATHS,
    CommandResult,
    LocalAttemptFactory,
    RefreshResult,
    StageOutcome,
    validate_candidate,
)
from tests.test_nightly_publish import _evidence, _git, _repo


def _remote(tmp_path: Path) -> tuple[Path, Path, str]:
    seed = _repo(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "-q", "--bare", seed, bare], check=True)
    _git(seed, "remote", "add", "origin", str(bare))
    _git(seed, "fetch", "-q", "origin", "main")
    return seed, bare, base


class ChangingRefresh:
    def __init__(self, *, change: str | None = ALLOWED_PATHS[0]) -> None:
        self.change = change
        self.bases: list[str] = []
        self.roots: list[Path] = []

    def run(self, root: Path, base_sha: str) -> RefreshResult:
        self.bases.append(base_sha)
        self.roots.append(root)
        if self.change is not None:
            (root / self.change).write_text(f"candidate:{base_sha}\n")
        report = root / ".build/report.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(f'{{"base": "{base_sha}"}}')
        _evidence(root)
        candidate = validate_candidate(root)
        status = "no-op" if not candidate.changed_paths else "publishable"
        return RefreshResult(
            status,
            base_sha,
            (StageOutcome("candidate", "success"),),
            candidate,
        )


class RecordingGit:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], dict[str, str] | None]] = []

    def run(
        self,
        command: tuple[str, ...],
        cwd: Path,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        self.calls.append((command, dict(env) if env is not None else None))
        completed = subprocess.run(
            command,
            cwd=cwd,
            env={**os.environ, **(env or {})},
            capture_output=True,
            text=True,
            check=False,
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _coordinator(
    source: Path, remote: RemoteBoundary, refresh: ChangingRefresh
) -> PublicationCoordinator:
    return PublicationCoordinator(
        LocalAttemptFactory(source),
        refresh,
        remote,
        now=lambda: datetime(2026, 9, 8, 12, tzinfo=UTC),
    )


def test_publishes_one_allowlisted_commit_with_metadata(tmp_path: Path) -> None:
    source, bare, base = _remote(tmp_path)
    runner = RecordingGit()
    remote = GitRemote(source, runner=runner)

    result = _coordinator(source, remote, ChangingRefresh()).run(
        "https://github.example/runs/42", "secret-token"
    )

    assert result.status == "published"
    assert result.base_sha == base
    assert result.published_sha
    assert _git(bare, "show", "-s", "--format=%s%n%b", "main").splitlines() == [
        "chore(dist): nightly rebuild 2026-09-08",
        "Workflow run: https://github.example/runs/42",
        "",
        f"Base SHA: {base}",
    ]
    assert (
        _git(bare, "diff-tree", "--no-commit-id", "--name-only", "-r", "main")
        == ALLOWED_PATHS[0]
    )
    push_command, push_env = next(call for call in runner.calls if "push" in call[0])
    assert push_command[-1] == "HEAD:refs/heads/main"
    assert "--force" not in push_command and "-f" not in push_command
    assert "secret-token" not in " ".join(push_command)
    encoded = base64.b64encode(b"x-access-token:secret-token").decode()
    assert push_env is not None and push_env["GIT_CONFIG_VALUE_0"].endswith(encoded)
    assert "secret-token" not in _git(source, "config", "--list")


def test_cache_only_change_is_committed_and_noop_is_not(tmp_path: Path) -> None:
    source, bare, base = _remote(tmp_path)
    remote = GitRemote(source)
    cache_result = _coordinator(
        source, remote, ChangingRefresh(change="config/package-ids.json")
    ).run("run", "token")
    assert cache_result.status == "published"
    assert (
        _git(bare, "diff-tree", "--no-commit-id", "--name-only", "-r", "main")
        == "config/package-ids.json"
    )

    no_op = _coordinator(source, remote, ChangingRefresh(change=None)).run(
        "run", "token"
    )
    assert no_op.status == "no-op"
    assert no_op.published_sha is None
    assert _git(bare, "rev-list", "--count", f"{base}..main") == "1"


class AdvancingRemote:
    def __init__(
        self,
        delegate: GitRemote,
        advance: Callable[[], None],
        *,
        advance_on: tuple[int, ...] = (2,),
    ) -> None:
        self.delegate = delegate
        self.advance = advance
        self.advance_on = advance_on
        self.fetches = 0

    def fetch_main(self) -> str:
        self.fetches += 1
        if self.fetches in self.advance_on:
            self.advance()
        return self.delegate.fetch_main()

    def push(self, root: Path, token: str) -> CommandResult:
        return self.delegate.push(root, token)

    def main_contains(self, root: Path, sha: str) -> bool:
        return self.delegate.main_contains(root, sha)


def _advance(seed: Path, bare: Path, marker: str) -> str:
    _git(seed, "fetch", "-q", "origin", "main")
    _git(seed, "checkout", "-q", "-B", "advance", "origin/main")
    (seed / "tracked.txt").write_text(marker)
    _git(seed, "add", "tracked.txt")
    _git(
        seed,
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "--allow-empty",
        "-qm",
        marker,
    )
    _git(seed, "push", "-q", str(bare), "HEAD:main")
    return _git(seed, "rev-parse", "HEAD")


def test_main_advancement_discards_candidate_and_runs_fresh_attempt(
    tmp_path: Path,
) -> None:
    source, bare, base = _remote(tmp_path)
    newer: list[str] = []
    remote = AdvancingRemote(
        GitRemote(source), lambda: newer.append(_advance(source, bare, "newer"))
    )
    refresh = ChangingRefresh()

    result = _coordinator(source, remote, refresh).run("run", "token")

    assert result.status == "published", result
    assert refresh.bases == [base, newer[0]]
    assert len(result.attempts) == 2
    assert result.attempts[0].build_report is not None
    assert result.attempts[0].verify_report is not None
    assert all(not root.exists() for root in refresh.roots)


def test_noop_rechecks_advanced_main_with_a_fresh_attempt(tmp_path: Path) -> None:
    source, bare, base = _remote(tmp_path)
    newer: list[str] = []
    remote = AdvancingRemote(
        GitRemote(source), lambda: newer.append(_advance(source, bare, "newer"))
    )
    refresh = ChangingRefresh(change=None)

    result = _coordinator(source, remote, refresh).run("run", "token")

    assert result.status == "no-op"
    assert refresh.bases == [base, newer[0]]


def test_second_advancement_exhausts_attempt_budget(tmp_path: Path) -> None:
    source, bare, _ = _remote(tmp_path)
    count = 0

    def advance() -> None:
        nonlocal count
        count += 1
        _advance(source, bare, f"newer-{count}")

    result = _coordinator(
        source,
        AdvancingRemote(GitRemote(source), advance, advance_on=(2, 3)),
        ChangingRefresh(),
    ).run("run", "token")

    assert result.status == "failed"
    assert result.stage == "concurrency"
    assert len(result.attempts) == 2


class PushOutcomeRemote:
    def __init__(
        self,
        delegate: GitRemote,
        *,
        advance: Callable[[], None] | None = None,
        unreadable: bool = False,
    ) -> None:
        self.delegate = delegate
        self.advance = advance
        self.unreadable = unreadable

    def fetch_main(self) -> str:
        return self.delegate.fetch_main()

    def push(self, root: Path, token: str) -> CommandResult:
        if self.advance is not None:
            self.advance()
        return CommandResult(1, "", "rejected")

    def main_contains(self, root: Path, sha: str) -> bool:
        if self.unreadable:
            raise OSError("cannot read remote")
        return self.delegate.main_contains(root, sha)


def test_lost_push_ack_is_reconciled_by_remote_ancestry(tmp_path: Path) -> None:
    source, bare, _ = _remote(tmp_path)
    delegate = GitRemote(source)

    class LostAck(PushOutcomeRemote):
        def push(self, root: Path, token: str) -> CommandResult:
            assert self.delegate.push(root, token).returncode == 0
            _advance(source, bare, "maintainer advanced")
            raise OSError("connection lost")

    result = _coordinator(source, LostAck(delegate), ChangingRefresh()).run(
        "run", "token"
    )

    assert result.status == "published"


def test_unchanged_rejected_push_fails_without_retry(tmp_path: Path) -> None:
    source, _, _ = _remote(tmp_path)
    result = _coordinator(
        source, PushOutcomeRemote(GitRemote(source)), ChangingRefresh()
    ).run("run", "token")

    assert result.status == "failed"
    assert result.stage == "push"
    assert result.published_sha is None
    assert len(result.attempts) == 1


def test_advanced_rejected_push_uses_remaining_fresh_attempt(tmp_path: Path) -> None:
    source, bare, _ = _remote(tmp_path)
    delegate = GitRemote(source)
    calls = 0

    class RejectOnce(PushOutcomeRemote):
        def push(self, root: Path, token: str) -> CommandResult:
            nonlocal calls
            calls += 1
            if calls == 1:
                _advance(source, bare, "race")
                return CommandResult(1, "", "rejected")
            return self.delegate.push(root, token)

    refresh = ChangingRefresh()
    result = _coordinator(source, RejectOnce(delegate), refresh).run("run", "token")

    assert result.status == "published"
    assert len(refresh.bases) == 2


def test_unreadable_remote_after_rejected_push_is_uncertain(tmp_path: Path) -> None:
    source, _, _ = _remote(tmp_path)
    result = _coordinator(
        source,
        PushOutcomeRemote(GitRemote(source), unreadable=True),
        ChangingRefresh(),
    ).run("run", "secret-token")

    assert result.status == "uncertain"
    assert result.published_sha is None
    assert result.attempts[-1].candidate_sha is not None
    assert "secret-token" not in result.detail
