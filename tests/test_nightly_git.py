from __future__ import annotations

import base64
import io
import json
import os
import subprocess
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

import scripts.nightly_reporting
from scripts.nightly_git import (
    GitRemote,
    PublicationCoordinator,
    ReleaseBoundary,
    RemoteBoundary,
)
from scripts.nightly_publish import (
    ALLOWED_PATHS,
    CommandResult,
    RefreshResult,
    StageOutcome,
    validate_candidate,
)
from tests.test_nightly_publish import _evidence, _git, _repo


class RecordingRelease:
    def __init__(self, failure: BaseException | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[bytes, bytes, str]] = []

    def synchronize(self, single: bytes, dual: bytes, source_commit: str):
        self.calls.append((single, dual, source_commit))
        if self.failure is not None:
            raise self.failure
        return type("Sync", (), {"revision": 7, "pending_revision": None})()


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


_DEFAULT_RELEASE = object()


def _coordinator(
    source: Path,
    remote: RemoteBoundary,
    refresh: ChangingRefresh,
    release: ReleaseBoundary | None | object = _DEFAULT_RELEASE,
) -> PublicationCoordinator:
    selected_release = (
        RecordingRelease()
        if release is _DEFAULT_RELEASE
        else cast(ReleaseBoundary | None, release)
    )
    return PublicationCoordinator(
        source,
        refresh,
        remote,
        selected_release,
        now=lambda: datetime(2026, 9, 8, 12, tzinfo=UTC),
    )


def test_uses_selected_workspace_head_without_another_checkout(tmp_path: Path) -> None:
    source, _, base = _remote(tmp_path)
    refresh = ChangingRefresh(change=None)

    result = _coordinator(source, GitRemote(source), refresh).run("run", "token")

    assert result.status == "no-op"
    assert result.base_sha == base
    assert refresh.roots == [source]
    assert _git(source, "rev-parse", "HEAD") == base


@pytest.mark.parametrize(
    ("relative", "state"),
    [
        (ALLOWED_PATHS[0], "unstaged"),
        ("tracked.txt", "staged"),
        ("tracked.txt", "mode"),
    ],
)
def test_rejects_initial_tracked_changes_before_refresh(
    tmp_path: Path, relative: str, state: str
) -> None:
    source, bare, base = _remote(tmp_path)
    if state == "mode":
        _git(source, "config", "core.fileMode", "true")
        (source / relative).chmod(0o755)
    else:
        (source / relative).write_text("local modification\n")
        if state == "staged":
            _git(source, "add", relative)
    refresh = ChangingRefresh()

    result = _coordinator(source, GitRemote(source), refresh).run("run", "token")

    assert result.status == "failed"
    assert result.stage == "workspace"
    assert result.base_sha == base
    assert refresh.roots == []
    assert _git(bare, "rev-parse", "main") == base


@pytest.mark.parametrize("change", [ALLOWED_PATHS[0], None])
def test_missing_release_boundary_preserves_main_without_claiming_completion(
    tmp_path: Path, change: str | None
) -> None:
    from scripts.nightly_reporting import report_publication

    source, bare, base = _remote(tmp_path)
    refresh = ChangingRefresh(change=change)
    result = _coordinator(source, GitRemote(source), refresh, None).run("run", "token")

    assert result.status == ("published" if change else "no-op")
    assert result.base_sha == base
    assert _git(bare, "rev-parse", "main") == (result.published_sha or base)
    assert result.release_status == "not-run"
    assert result.stage == "release"
    assert result.pack_snapshots is None
    assert refresh.roots == [source]
    reported = report_publication(result, tmp_path / "diagnostics", "run")
    assert reported.workflow_status == "failed"


def test_release_failure_does_not_block_main_publication(
    tmp_path: Path,
) -> None:
    source, bare, base = _remote(tmp_path)
    release = RecordingRelease(RuntimeError("discovery unavailable"))

    result = _coordinator(source, GitRemote(source), ChangingRefresh(), release).run(
        "run", "token"
    )

    assert result.status == "published"
    assert result.stage == "release"
    assert result.release_status == "failed"
    assert "discovery unavailable" in result.detail
    assert _git(bare, "rev-parse", "main") == result.published_sha
    assert _git(bare, "rev-parse", "main") != base
    assert len(release.calls) == 1


def test_confirmed_main_log_is_flushed_before_release_and_survives_reporting_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FlushRecordingStream(io.StringIO):
        flushed = False

        def flush(self) -> None:
            self.flushed = True
            super().flush()

    class ObservingRelease(RecordingRelease):
        def synchronize(self, single: bytes, dual: bytes, source_commit: str):
            assert stream.flushed
            confirmation = json.loads(stream.getvalue())
            assert confirmation == {
                "main_publication": "published",
                "sha": source_commit,
            }
            return super().synchronize(single, dual, source_commit)

    source, bare, base = _remote(tmp_path)
    stream = FlushRecordingStream()
    monkeypatch.setattr("sys.stdout", stream)
    result = _coordinator(
        source, GitRemote(source), ChangingRefresh(), ObservingRelease()
    ).run("run", "token")
    assert result.status == "published"
    assert _git(bare, "rev-parse", "main") != base

    def fail_diagnostics(*_args, **_kwargs):
        raise OSError("reporting failed")

    monkeypatch.setattr(
        scripts.nightly_reporting, "write_diagnostics", fail_diagnostics
    )
    with pytest.raises(OSError, match="reporting failed"):
        scripts.nightly_reporting.report_publication(
            result, tmp_path / "diagnostics", "run"
        )

    assert json.loads(stream.getvalue())["main_publication"] == "published"


@pytest.mark.parametrize(
    ("status", "body", "diagnostic"),
    [
        (404, None, "release discovery failed with status 404"),
        (200, "unowned release", "release ownership marker is absent"),
    ],
)
def test_seed_discovery_fails_release_after_main_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    body: str | None,
    diagnostic: str,
) -> None:
    from scripts.nightly import _publisher
    from scripts.nightly_release import RELEASE_PATH
    from scripts.nightly_release_transport import GitHubReleaseRemote
    from tests.test_nightly_release import Opened, release

    source, bare, base = _remote(tmp_path)
    requests = []

    def opener(request, *, timeout):
        requests.append((request.get_method(), request.full_url))
        return Opened(status, json.dumps(release(body=body)).encode())

    remote = GitHubReleaseRemote("token", trusted_opener=opener)
    monkeypatch.setattr(
        "scripts.nightly_release_transport.GitHubReleaseRemote", lambda token: remote
    )
    coordinator = cast(PublicationCoordinator, _publisher(source, "token"))
    coordinator.refresh = ChangingRefresh()
    result = coordinator.run("run", "token")

    assert result.status == "published"
    assert result.stage == "release"
    assert diagnostic in result.detail
    if status == 404:
        assert "bootstrap-release" in result.detail
    assert result.release_status == "failed"
    assert _git(bare, "rev-parse", "main") == result.published_sha
    assert _git(bare, "rev-parse", "main") != base
    assert requests == [
        ("GET", f"https://api.github.com{RELEASE_PATH}"),
        ("GET", f"https://api.github.com{RELEASE_PATH}"),
    ]


def test_release_uses_captured_verified_bytes_from_workspace(
    tmp_path: Path,
) -> None:
    source, _, _ = _remote(tmp_path)
    refresh = ChangingRefresh()
    release = RecordingRelease()

    result = _coordinator(source, GitRemote(source), refresh, release).run(
        "run", "token"
    )

    assert result.status == "published"
    assert result.release_status == "success"
    assert result.release_revision == 7
    assert refresh.roots == [source]
    single, dual, source_commit = release.calls[0]
    assert result.base_sha is not None
    assert single == b"candidate:" + result.base_sha.encode() + b"\n"
    assert dual == b"base:dist/dual-screen.json\n"
    assert source_commit == result.published_sha


def test_noop_still_synchronizes_exact_verified_pair(tmp_path: Path) -> None:
    source, _, base = _remote(tmp_path)
    release = RecordingRelease()

    result = _coordinator(
        source, GitRemote(source), ChangingRefresh(change=None), release
    ).run("run", "token")

    assert result.status == "no-op"
    assert release.calls == [
        (
            b"base:dist/single-screen.json\n",
            b"base:dist/dual-screen.json\n",
            base,
        )
    ]


def test_verified_noop_repairs_release_assets_through_real_synchronizer(
    tmp_path: Path,
) -> None:
    from scripts.nightly_release_sync import synchronize_release
    from tests.test_nightly_release import ControlledReleaseRemote, completed_release

    source, _, base = _remote(tmp_path)
    single = b"base:dist/single-screen.json\n"
    dual = b"base:dist/dual-screen.json\n"
    document = completed_release(single, dual)
    document["assets"] = []
    remote = ControlledReleaseRemote(document)

    class RealRelease:
        def synchronize(self, single: bytes, dual: bytes, source_commit: str):
            return synchronize_release(remote, single, dual, source_commit)

    result = _coordinator(
        source, GitRemote(source), ChangingRefresh(change=None), RealRelease()
    ).run("run", "token")

    assert result.status == "no-op"
    assert result.release_status == "success"
    assert result.release_revision == 3
    assert remote.blobs == {
        "single-screen.json": single,
        "dual-screen.json": dual,
    }
    assert [call[0] for call in remote.calls].count("upload") == 2
    assert result.base_sha == base


def test_failed_release_is_repaired_by_later_fresh_noop_without_extra_revision(
    tmp_path: Path,
) -> None:
    from scripts.nightly_release import ReleaseError
    from scripts.nightly_release_sync import synchronize_release
    from tests.test_nightly_release import ControlledReleaseRemote
    from tests.test_nightly_release import release as seed

    source, bare, base = _remote(tmp_path)
    remote = ControlledReleaseRemote(seed())
    remote.fail["upload"] = ReleaseError("upload denied")

    class RealRelease:
        def synchronize(self, single: bytes, dual: bytes, source_commit: str):
            return synchronize_release(remote, single, dual, source_commit)

    first = _coordinator(
        source, GitRemote(source), ChangingRefresh(), RealRelease()
    ).run("run-1", "token")

    assert first.status == "published"
    assert first.release_status == "failed"
    assert first.pending_revision == 1
    assert _git(bare, "rev-list", "--count", f"{base}..main") == "1"
    assert remote.update_count == 1

    remote.fail.clear()
    second = _coordinator(
        source, GitRemote(source), ChangingRefresh(change=None), RealRelease()
    ).run("run-2", "token")

    assert second.status == "no-op"
    assert second.release_status == "success"
    assert second.release_revision == 1
    assert second.base_sha == first.published_sha
    assert remote.document["name"] == "omnipack revision 1"
    assert remote.update_count == 2
    assert _git(bare, "rev-list", "--count", f"{base}..main") == "1"


def test_release_failure_preserves_confirmed_main_sha(tmp_path: Path) -> None:
    from scripts.nightly_release_sync import SyncFailure

    source, bare, _ = _remote(tmp_path)
    release = RecordingRelease(SyncFailure("upload failed", 8))

    result = _coordinator(source, GitRemote(source), ChangingRefresh(), release).run(
        "run", "token"
    )

    assert result.status == "published"
    assert result.published_sha == _git(bare, "rev-parse", "main")
    assert result.release_status == "failed"
    assert result.pending_revision == 8
    assert result.stage == "release"


def test_failed_refresh_never_calls_release(tmp_path: Path) -> None:
    source, _, _ = _remote(tmp_path)
    release = RecordingRelease()

    class FailedRefresh(ChangingRefresh):
        def run(self, root: Path, base_sha: str) -> RefreshResult:
            return RefreshResult(
                "failed",
                base_sha,
                (StageOutcome("verify", "failed", "verification failed"),),
            )

    result = _coordinator(source, GitRemote(source), FailedRefresh(), release).run(
        "run", "token"
    )

    assert result.status == "failed"
    assert release.calls == []


def test_uncertain_push_never_calls_release(tmp_path: Path) -> None:
    source, _, _ = _remote(tmp_path)
    release = RecordingRelease()

    result = _coordinator(
        source,
        PushOutcomeRemote(GitRemote(source), unreadable=True),
        ChangingRefresh(),
        release,
    ).run("run", "token")

    assert result.status == "uncertain"
    assert release.calls == []


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
        advance_on: tuple[int, ...] = (1,),
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


def test_main_advancement_fails_without_another_refresh_or_push(
    tmp_path: Path,
) -> None:
    source, bare, base = _remote(tmp_path)
    newer: list[str] = []
    remote = AdvancingRemote(
        GitRemote(source), lambda: newer.append(_advance(source, bare, "newer"))
    )
    refresh = ChangingRefresh()

    result = _coordinator(source, remote, refresh).run("run", "token")

    assert result.status == "failed"
    assert result.stage == "concurrency"
    assert refresh.bases == [base]
    assert result.started_at is not None
    assert _git(bare, "rev-parse", "main") == newer[0]


def test_main_advancement_performs_no_release_write(tmp_path: Path) -> None:
    source, bare, base = _remote(tmp_path)
    newer: list[str] = []
    release = RecordingRelease()
    remote = AdvancingRemote(
        GitRemote(source), lambda: newer.append(_advance(source, bare, "newer"))
    )

    result = _coordinator(source, remote, ChangingRefresh(), release).run(
        "run", "token"
    )

    assert result.status == "failed"
    assert base != newer[0]
    assert release.calls == []


def test_noop_rejects_advanced_main_without_another_refresh(tmp_path: Path) -> None:
    source, bare, base = _remote(tmp_path)
    newer: list[str] = []
    remote = AdvancingRemote(
        GitRemote(source), lambda: newer.append(_advance(source, bare, "newer"))
    )
    refresh = ChangingRefresh(change=None)

    result = _coordinator(source, remote, refresh).run("run", "token")

    assert result.status == "failed"
    assert result.stage == "concurrency"
    assert refresh.bases == [base]
    assert result.started_at is not None
    assert _git(bare, "rev-parse", "main") == newer[0]


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


def test_remote_ancestry_fetches_complete_history_from_shallow_checkout(
    tmp_path: Path,
) -> None:
    class ShallowGit:
        def __init__(self) -> None:
            self.calls: list[tuple[str, ...]] = []

        def run(self, command, cwd, env=None):
            self.calls.append(command)
            if command == ("git", "rev-parse", "--is-shallow-repository"):
                return CommandResult(0, "true\n", "")
            return CommandResult(0, "", "")

    runner = ShallowGit()
    remote = GitRemote(tmp_path, runner=runner)

    assert remote.main_contains(tmp_path, "a" * 40) is True
    assert runner.calls[1] == (
        "git",
        "fetch",
        "--quiet",
        "--unshallow",
        "origin",
        "refs/heads/main:refs/remotes/origin/main",
    )


def test_unreadable_shallow_state_does_not_infer_commit_absence(tmp_path: Path) -> None:
    class BrokenGit:
        def run(self, command, cwd, env=None):
            return CommandResult(1, "", "cannot inspect repository")

    with pytest.raises(OSError, match="repository history"):
        GitRemote(tmp_path, runner=BrokenGit()).main_contains(tmp_path, "a" * 40)


def test_unchanged_rejected_push_fails_without_retry(tmp_path: Path) -> None:
    source, _, _ = _remote(tmp_path)
    result = _coordinator(
        source, PushOutcomeRemote(GitRemote(source)), ChangingRefresh()
    ).run("run", "token")

    assert result.status == "failed"
    assert result.stage == "push"
    assert result.published_sha is None
    assert result.started_at is not None


def test_advanced_rejected_push_fails_without_retry(tmp_path: Path) -> None:
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

    assert result.status == "failed"
    assert result.stage == "push"
    assert len(refresh.bases) == 1
    assert calls == 1


def test_unreadable_remote_after_rejected_push_is_uncertain(tmp_path: Path) -> None:
    source, _, _ = _remote(tmp_path)
    result = _coordinator(
        source,
        PushOutcomeRemote(GitRemote(source), unreadable=True),
        ChangingRefresh(),
    ).run("run", "secret-token")

    assert result.status == "uncertain"
    assert result.published_sha is None
    assert result.candidate_sha is not None
    assert "secret-token" not in result.detail


@pytest.mark.parametrize("byte_change", [False, True])
def test_publication_uses_byte_changes_without_mode_drift(
    tmp_path: Path, byte_change: bool
) -> None:
    source, bare, base = _remote(tmp_path)

    class ModeChangingRefresh(ChangingRefresh):
        def run(self, root: Path, base_sha: str) -> RefreshResult:
            _git(root, "config", "core.fileMode", "true")
            (root / ALLOWED_PATHS[0]).chmod(0o755)
            return super().run(root, base_sha)

    result = _coordinator(
        source,
        GitRemote(source),
        ModeChangingRefresh(change=ALLOWED_PATHS[0] if byte_change else None),
    ).run("run", "token")

    assert result.status == ("published" if byte_change else "no-op")
    assert _git(bare, "ls-tree", "main", ALLOWED_PATHS[0]).startswith("100644 ")
    assert _git(bare, "rev-list", "--count", f"{base}..main") == (
        "1" if byte_change else "0"
    )
