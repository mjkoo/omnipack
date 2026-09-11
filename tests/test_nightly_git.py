from __future__ import annotations

import base64
import inspect
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from scripts.nightly_git import (
    GitRemote,
    PublicationCoordinator,
    ReleaseBoundary,
    RemoteBoundary,
)
from scripts.nightly_publish import (
    ALLOWED_PATHS,
    CandidateError,
    CommandResult,
    LocalAttemptFactory,
    RefreshOrchestrator,
    RefreshResult,
    StageOutcome,
    validate_candidate,
)
from tests.test_nightly_publish import _evidence, _git, _repo


class RecordingRelease:
    def __init__(
        self,
        failure: BaseException | None = None,
        *,
        preflight_failure: BaseException | None = None,
    ) -> None:
        self.failure = failure
        self.preflight_failure = preflight_failure
        self.calls: list[tuple[bytes, bytes, str]] = []
        self.preflight_calls = 0

    def preflight(self) -> None:
        self.preflight_calls += 1
        if self.preflight_failure is not None:
            raise self.preflight_failure

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
        LocalAttemptFactory(source),
        refresh,
        remote,
        selected_release,
        now=lambda: datetime(2026, 9, 8, 12, tzinfo=UTC),
    )


@pytest.mark.parametrize("change", [ALLOWED_PATHS[0], None])
def test_missing_release_boundary_preserves_main_without_claiming_completion(
    tmp_path: Path, change: str | None
) -> None:
    from scripts.nightly_reporting import finalize_publication
    from tests.test_nightly_reporting import RecordingIssues

    source, bare, base = _remote(tmp_path)
    refresh = ChangingRefresh(change=change)
    result = _coordinator(source, GitRemote(source), refresh, None).run("run", "token")

    assert result.status == "failed"
    assert result.base_sha == base
    assert result.published_sha is None
    assert _git(bare, "rev-parse", "main") == base
    assert result.release_status == "not-run"
    assert result.stage == "release-preflight"
    assert result.pack_snapshots is None
    assert all(not root.exists() for root in refresh.roots)
    issues = RecordingIssues()
    finalized = finalize_publication(result, issues, tmp_path / "diagnostics", "run")
    assert finalized.workflow_status == "failed"
    assert issues.failure_bodies and not issues.recovery_bodies


def test_release_preflight_failure_blocks_main_and_release_writes(
    tmp_path: Path,
) -> None:
    source, bare, base = _remote(tmp_path)
    release = RecordingRelease(preflight_failure=RuntimeError("discovery unavailable"))

    result = _coordinator(source, GitRemote(source), ChangingRefresh(), release).run(
        "run", "token"
    )

    assert result.status == "failed"
    assert result.stage == "release-preflight"
    assert "bootstrap-release" in result.detail
    assert _git(bare, "rev-parse", "main") == base
    assert release.preflight_calls == 1
    assert release.calls == []


@pytest.mark.parametrize(
    ("status", "body", "diagnostic"),
    [
        (404, None, "release discovery failed with status 404"),
        (200, "unowned release", "release ownership marker is absent"),
    ],
)
def test_seed_discovery_blocks_publication_without_owned_release(
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

    assert result.status == "failed"
    assert result.stage == "release-preflight"
    assert diagnostic in result.detail
    assert "bootstrap-release" in result.detail
    assert result.release_status == "not-run"
    assert _git(bare, "rev-parse", "main") == base
    assert requests == [("GET", f"https://api.github.com{RELEASE_PATH}")]


def test_release_uses_verified_bytes_after_successful_checkout_is_removed(
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
    assert all(not root.exists() for root in refresh.roots)
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
        def preflight(self) -> None:
            from scripts.nightly_release import parse_owned_release

            parse_owned_release(remote.discover())

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


def test_release_uses_only_successful_retry_pair(tmp_path: Path) -> None:
    source, bare, base = _remote(tmp_path)
    newer: list[str] = []
    release = RecordingRelease()
    remote = AdvancingRemote(
        GitRemote(source), lambda: newer.append(_advance(source, bare, "newer"))
    )

    result = _coordinator(source, remote, ChangingRefresh(), release).run(
        "run", "token"
    )

    assert base != newer[0]
    assert len(release.calls) == 1
    single, dual, source_commit = release.calls[0]
    assert single == f"candidate:{newer[0]}\n".encode()
    assert dual == b"base:dist/dual-screen.json\n"
    assert source_commit == result.published_sha


def test_fresh_attempt_preserves_new_base_readme_around_generated_catalog(
    tmp_path: Path,
) -> None:
    from omnipack.catalog import replace_catalog, split_catalog

    source, bare, base = _remote(tmp_path)
    newer: list[str] = []

    def advance_readme() -> None:
        _git(source, "fetch", "-q", "origin", "main")
        _git(source, "checkout", "-q", "-B", "advance-readme", "origin/main")
        readme = source / "README.md"
        readme.write_bytes(readme.read_bytes().replace(b"guide", b"updated guide"))
        _git(source, "add", "README.md")
        _git(source, "commit", "-qm", "update guide")
        _git(source, "push", "-q", str(bare), "HEAD:main")
        newer.append(_git(source, "rev-parse", "HEAD"))

    class CatalogRefresh(ChangingRefresh):
        def __init__(self) -> None:
            super().__init__(change=None)

        def run(self, root: Path, base_sha: str) -> RefreshResult:
            readme = root / "README.md"
            readme.write_bytes(
                replace_catalog(readme.read_bytes(), f"catalog:{base_sha}\n".encode())
            )
            return super().run(root, base_sha)

    refresh = CatalogRefresh()
    remote = AdvancingRemote(GitRemote(source), advance_readme)

    result = _coordinator(source, remote, refresh).run("run", "token")

    assert result.status == "published"
    assert refresh.bases == [base, newer[0]]
    published = subprocess.run(
        ["git", "show", "main:README.md"],
        cwd=bare,
        check=True,
        capture_output=True,
    ).stdout
    prefix, interior, suffix = split_catalog(published)
    assert b"updated guide" in prefix
    assert interior == f"catalog:{newer[0]}\n".encode()
    assert suffix.endswith(b"credits\r\n")
    assert (
        _git(bare, "diff-tree", "--no-commit-id", "--name-only", "-r", "main")
        == "README.md"
    )


class FailingSecondAttempt(LocalAttemptFactory):
    def __init__(self, source: Path) -> None:
        super().__init__(source)
        self.count = 0

    @contextmanager
    def checkout(self, base_sha: str) -> Iterator[Path]:
        self.count += 1
        if self.count == 2:
            raise CandidateError("credential secret from clone")
        with super().checkout(base_sha) as root:
            yield root


def test_retry_setup_failure_preserves_first_attempt_diagnostics(
    tmp_path: Path,
) -> None:
    source, bare, _ = _remote(tmp_path)

    def advance() -> None:
        _advance(source, bare, "newer")

    remote = AdvancingRemote(GitRemote(source), advance)
    coordinator = PublicationCoordinator(
        FailingSecondAttempt(source),
        ChangingRefresh(),
        remote,
        RecordingRelease(),
        now=lambda: datetime(2026, 9, 8, tzinfo=UTC),
    )

    result = coordinator.run("run", "token")

    assert result.status == "failed"
    assert result.stage == "checkout"
    assert len(result.attempts) == 2
    assert result.attempts[0].build_report is not None
    assert result.attempts[1].build_report is None
    assert result.attempts[1].stages[0].detail == "attempt setup failed"
    assert result.attempts[1].started_at == datetime(2026, 9, 8, tzinfo=UTC)


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


def test_cleanup_failure_preserves_confirmed_publication_and_fails_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.nightly_publish as publishing
    from scripts.nightly import run_publication, run_setup_failure
    from tests.test_nightly_workflow import FakeApi, _environment, _response

    source, bare, _ = _remote(tmp_path)
    refresh = ChangingRefresh()
    remove = publishing.shutil.rmtree

    def fail_cleanup(path: Path) -> None:
        remove(path)
        raise OSError("cleanup denied")

    monkeypatch.setattr(publishing.shutil, "rmtree", fail_cleanup)
    environment = _environment(tmp_path)
    api = FakeApi([_response(200, [])])
    finalized = run_publication(
        environment,
        publisher=_coordinator(source, GitRemote(source), refresh, RecordingRelease()),
        api=api,
    )
    output = tmp_path / "nightly-diagnostics"

    assert finalized is not None

    assert finalized.workflow_status == "failed"
    assert finalized.publication_status == "published"
    assert finalized.release_status == "success"
    document = json.loads((output / "orchestration-result.json").read_text())
    assert document["published_sha"] == _git(bare, "rev-parse", "main")
    assert document["workflow_status"] == "failed"
    assert document["cleanup_errors"]
    assert "Cleanup: failed" in finalized.summary
    assert json.loads((output / "attempt-1-verify.json").read_text())["complete"]
    assert json.loads((output / "attempt-1-build.json").read_text())["base"]
    assert [request[0] for request in api.requests] == ["GET"]
    assert finalized.issue_status == "unchanged"
    fallback = run_setup_failure(
        environment, "helper", "publisher execution failed", api=FakeApi([])
    )
    assert fallback is not None
    assert fallback.publication_status == "published"
    assert fallback.workflow_status == "failed"


@pytest.mark.parametrize("defect", [None, "verifier", "inputs", "schema"])
def test_retry_validates_evidence_with_selected_revision_runtime(
    tmp_path: Path, defect: str | None
) -> None:
    from omnipack.verify import VERIFIER_VERSION

    next_version = "test-next-verifier"
    source, bare, _ = _remote(tmp_path)
    project = Path(__file__).resolve().parents[1]
    for directory in ("src", "scripts"):
        shutil.copytree(
            project / directory,
            source / directory,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    _git(source, "add", "src", "scripts")
    _git(source, "commit", "-qm", "add runtime")
    _git(source, "push", "-q", str(bare), "HEAD:main")
    base = _git(source, "rev-parse", "HEAD")
    newer: list[str] = []

    def advance() -> None:
        verify = source / "src/omnipack/verify.py"
        verify.write_text(
            verify.read_text()
            .replace(
                f'VERIFIER_VERSION = "{VERIFIER_VERSION}"',
                f'VERIFIER_VERSION = "{next_version}"',
            )
            .replace("SCHEMA_VERSION = 2", "SCHEMA_VERSION = 3")
            .replace('Path("config/settings.json")', 'Path("config/new-settings.json")')
        )
        (source / "config/new-settings.json").write_text("new verifier input\n")
        report = source / "src/omnipack/report.py"
        report.write_text(report.read_text().replace("schema != 2:", "schema != 3:"))
        _git(source, "add", "src", "config/new-settings.json")
        _git(source, "commit", "-qm", "update verification contract")
        _git(source, "push", "-q", str(bare), "HEAD:main")
        newer.append(_git(source, "rev-parse", "HEAD"))

    class SelectedRuntimeProcess:
        def __init__(self) -> None:
            self.commands: list[tuple[str, ...]] = []

        def run(self, command: Sequence[str], cwd: Path) -> CommandResult:
            self.commands.append(tuple(command))
            if tuple(command[-2:]) == ("pack", "build"):
                (cwd / ALLOWED_PATHS[0]).write_text("candidate\n")
            if tuple(command[-2:]) == ("pack", "verify"):
                code = (
                    "import json\nfrom pathlib import Path\n"
                    "from datetime import UTC, datetime\n"
                    + inspect.getsource(_evidence)
                    + "\n_evidence(Path.cwd())\n"
                )
                completed = self.selected(cwd, ("-c", code))
                if newer and defect is not None:
                    path = cwd / ".build/verify.json"
                    report = json.loads(path.read_text())
                    if defect == "verifier":
                        report["verifier"]["version"] = VERIFIER_VERSION
                    elif defect == "inputs":
                        report["inputs"]["settings"] = {"state": "missing"}
                    else:
                        report["schemaVersion"] = 1
                    path.write_text(json.dumps(report))
                return completed
            if "scripts.nightly_publish" in command:
                return self.selected(cwd, tuple(command[4:]))
            return CommandResult(0, "", "")

        def selected(self, root: Path, args: tuple[str, ...]) -> CommandResult:
            completed = subprocess.run(
                [sys.executable, *args],
                cwd=root,
                env={**os.environ, "PYTHONPATH": str(root / "src")},
                capture_output=True,
                text=True,
                check=False,
            )
            return CommandResult(
                completed.returncode, completed.stdout, completed.stderr
            )

    process = SelectedRuntimeProcess()
    coordinator = PublicationCoordinator(
        LocalAttemptFactory(source),
        RefreshOrchestrator(process),
        AdvancingRemote(GitRemote(source), advance),
        RecordingRelease(),
    )
    result = coordinator.run("run", "token")

    assert result.status == ("published" if defect is None else "failed"), result
    assert len(result.attempts) == 2
    assert [attempt.base_sha for attempt in result.attempts] == [base, newer[0]]
    reports = [
        json.loads(attempt.verify_report or b"{}") for attempt in result.attempts
    ]
    assert reports[0]["verifier"]["version"] == VERIFIER_VERSION
    if defect is None:
        assert reports[1]["verifier"]["version"] == next_version
        assert reports[1]["schemaVersion"] == 3
        assert reports[1]["inputs"]["settings"]["state"] == "present"
    else:
        assert result.published_sha is None
        assert _git(bare, "rev-parse", "main") == newer[0]


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
