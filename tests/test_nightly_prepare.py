"""Tests for the guarded nightly `prepare` step and its real hand-off bundle.

Git runs in an isolated environment (no global identity), so these tests
exercise the actual allowlist, README-boundary and commit behavior against a
temporary repository and bare remote.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts import nightly as nightly_module
from scripts.nightly import (
    ALLOWED_PATHS,
    BUILD_COMMAND,
    STRUCTURAL_VERIFY_COMMAND,
    PrepareCommandResult,
    PrepareSubprocess,
    run_prepare,
)
from scripts.nightly_write import run_push
from scripts.workflow_support import BOT_EMAIL, BOT_NAME, CommandResult


class StubGh:
    """A `gh` stand-in that only ever needs to hand git the write credential."""

    def run(self, args):
        return CommandResult(0, "", "")


README_BYTES = (
    b"guide\n<!-- omnipack:catalog:start -->\nbase catalog\n"
    b"<!-- omnipack:catalog:end -->\ncredits\n"
)


@pytest.fixture(autouse=True)
def _isolated_git_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for name in list(os.environ):
        if name.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_")):
            monkeypatch.delenv(name)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo(tmp_path: Path, name: str = "repo") -> Path:
    root = tmp_path / name
    root.mkdir()
    _git(root, "init", "-q", "--initial-branch=main")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.invalid")
    for relative in ALLOWED_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == "README.md":
            path.write_bytes(README_BYTES)
        else:
            path.write_text(f"base:{relative}\n")
    (root / "tracked.txt").write_text("base\n")
    (root / ".gitignore").write_text(".build/\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root


def _install_failing_hooks(root: Path, *names: str) -> None:
    """Hooks that would fail any git command that ran them."""
    hooks = root / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    for name in names:
        hook = hooks / name
        hook.write_text("#!/bin/sh\necho 'a repository hook ran' >&2\nexit 1\n")
        hook.chmod(0o755)


class ScriptedProcess:
    """A build/verify boundary that runs test-controlled callbacks instead."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[tuple[str, ...]] = []
        self.on_build: list[Callable[[], object]] = []
        self.on_verify: list[Callable[[], object]] = []
        self.fail_build = False
        self.fail_verify = False

    def run(self, command, cwd: Path) -> PrepareCommandResult:
        assert cwd == self.root
        self.calls.append(tuple(command))
        if tuple(command) == BUILD_COMMAND:
            if self.fail_build:
                return PrepareCommandResult(1, "", "build failed")
            queue = self.on_build
        elif tuple(command) == STRUCTURAL_VERIFY_COMMAND:
            if self.fail_verify:
                return PrepareCommandResult(1, "", "verification failed")
            queue = self.on_verify
        else:
            raise AssertionError(f"unexpected command {command}")
        if queue:
            queue.pop(0)()
        return PrepareCommandResult(0, "", "")


def _fail_verify(process: ScriptedProcess) -> None:
    process.fail_verify = True


def _fail_build(process: ScriptedProcess) -> None:
    process.fail_build = True


def _now() -> datetime:
    return datetime(2026, 9, 12, 3, 0, tzinfo=UTC)


def test_dirty_checkout_fails_before_build(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "tracked.txt").write_text("dirty\n")
    process = ScriptedProcess(root)

    outcome = run_prepare(
        root,
        _git(root, "rev-parse", "HEAD"),
        "run",
        tmp_path / "candidate.bundle",
        process=process,
        now=_now,
    )

    assert outcome.status == "failed"
    assert outcome.stage == "checkout"
    assert outcome.summary_line == "checkout"
    assert process.calls == []


def test_head_other_than_github_sha_fails(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    process = ScriptedProcess(root)

    outcome = run_prepare(
        root,
        "0" * 40,
        "run",
        tmp_path / "candidate.bundle",
        process=process,
        now=_now,
    )

    assert outcome.status == "failed"
    assert outcome.stage == "checkout"
    assert process.calls == []


def test_noop_run_makes_no_commit_or_bundle(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)
    bundle_path = tmp_path / "candidate.bundle"

    outcome = run_prepare(root, base, "run", bundle_path, process=process, now=_now)

    assert outcome.status == "no-op"
    assert outcome.summary_line == f"no-op at {base}"
    assert outcome.base_sha == base
    assert outcome.sha == base
    assert not outcome.changed
    assert _git(root, "rev-parse", "HEAD") == base
    assert not bundle_path.exists()
    assert [call for call in process.calls] == [
        BUILD_COMMAND,
        STRUCTURAL_VERIFY_COMMAND,
    ]


def test_changed_run_commits_as_bot_and_summarizes_prepared(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)
    process.on_build.append(
        lambda: (root / ALLOWED_PATHS[0]).write_text("changed pack\n")
    )
    bundle_path = tmp_path / "candidate.bundle"

    outcome = run_prepare(
        root,
        base,
        "https://github.example/runs/1",
        bundle_path,
        process=process,
        now=_now,
    )

    assert outcome.status == "prepared"
    assert outcome.changed
    assert outcome.base_sha == base
    sha = outcome.sha
    assert sha is not None
    assert outcome.summary_line == f"prepared {sha}"
    assert _git(root, "rev-parse", "HEAD") == sha
    assert _git(root, "show", "-s", "--format=%an <%ae>%n%cn <%ce>", "HEAD") == (
        f"{BOT_NAME} <{BOT_EMAIL}>\n{BOT_NAME} <{BOT_EMAIL}>"
    )
    assert (
        _git(root, "show", "-s", "--format=%s", "HEAD")
        == "chore(dist): nightly rebuild 2026-09-12"
    )
    body = _git(root, "show", "-s", "--format=%b", "HEAD")
    assert "https://github.example/runs/1" in body
    assert base in body
    assert (
        _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD")
        == ALLOWED_PATHS[0]
    )


def test_changed_run_writes_bundle_holding_head_with_base_prerequisite(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)
    process.on_build.append(
        lambda: (root / ALLOWED_PATHS[0]).write_text("changed pack\n")
    )
    bundle_path = tmp_path / "candidate.bundle"

    outcome = run_prepare(root, base, "run", bundle_path, process=process, now=_now)

    assert outcome.status == "prepared"
    assert bundle_path.exists()
    heads = _git(root, "bundle", "list-heads", str(bundle_path))
    assert heads == f"{outcome.sha} HEAD"
    verification = _git(root, "bundle", "verify", str(bundle_path))
    assert base in verification


def test_readme_catalog_interior_change_is_committed(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)
    process.on_build.append(
        lambda: (root / "README.md").write_bytes(
            README_BYTES.replace(b"base catalog", b"rebuilt catalog")
        )
    )

    outcome = run_prepare(
        root, base, "run", tmp_path / "candidate.bundle", process=process, now=_now
    )

    assert outcome.status == "prepared"
    assert outcome.summary_line == f"prepared {outcome.sha}"
    assert (
        _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD")
        == "README.md"
    )


def test_repository_hooks_never_run_on_the_candidate_commit(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _install_failing_hooks(root, "pre-commit", "commit-msg", "post-commit")
    process = ScriptedProcess(root)
    process.on_build.append(
        lambda: (root / ALLOWED_PATHS[0]).write_text("changed pack\n")
    )

    outcome = run_prepare(
        root, base, "run", tmp_path / "candidate.bundle", process=process, now=_now
    )

    assert outcome.status == "prepared"


def _prepare_environment(
    monkeypatch: pytest.MonkeyPatch, root: Path, tmp_path: Path
) -> Path:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    monkeypatch.chdir(root)
    monkeypatch.setenv("GITHUB_SHA", _git(root, "rev-parse", "HEAD"))
    monkeypatch.setenv("RUNNER_TEMP", str(runner_temp))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output.txt"))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.example")
    monkeypatch.setenv("GITHUB_REPOSITORY", "mjkoo/omnipack")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    return runner_temp


def test_prepare_cli_writes_changed_sha_and_base_for_a_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    runner_temp = _prepare_environment(monkeypatch, root, tmp_path)
    process = ScriptedProcess(root)
    process.on_build.append(
        lambda: (root / ALLOWED_PATHS[0]).write_text("changed pack\n")
    )
    monkeypatch.setattr(nightly_module, "PrepareSubprocess", lambda: process)

    exit_code = nightly_module.main(["prepare"])

    sha = _git(root, "rev-parse", "HEAD")
    assert exit_code == 0
    assert sha != base
    assert (tmp_path / "output.txt").read_text() == (
        f"changed=true\nsha={sha}\nbase={base}\n"
    )
    assert (tmp_path / "summary.md").read_text() == f"prepared {sha}\n"
    assert (runner_temp / "nightly-handoff" / "candidate.bundle").exists()
    assert "https://github.example/mjkoo/omnipack/actions/runs/42" in _git(
        root, "show", "-s", "--format=%b", "HEAD"
    )


def test_prepare_cli_writes_changed_false_for_a_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    runner_temp = _prepare_environment(monkeypatch, root, tmp_path)
    process = ScriptedProcess(root)
    monkeypatch.setattr(nightly_module, "PrepareSubprocess", lambda: process)

    exit_code = nightly_module.main(["prepare"])

    assert exit_code == 0
    assert (tmp_path / "output.txt").read_text() == (
        f"changed=false\nsha={base}\nbase={base}\n"
    )
    assert (tmp_path / "summary.md").read_text() == f"no-op at {base}\n"
    assert not (runner_temp / "nightly-handoff").exists()


def test_out_of_scope_tracked_change_fails_allowlist(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)
    process.on_build.append(lambda: (root / "tracked.txt").write_text("mutated\n"))
    bundle_path = tmp_path / "candidate.bundle"

    outcome = run_prepare(root, base, "run", bundle_path, process=process, now=_now)

    assert outcome.status == "failed"
    assert outcome.stage == "allowlist"
    assert _git(root, "rev-parse", "HEAD") == base
    assert not bundle_path.exists()


def test_deleted_allowed_file_fails_allowlist(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)
    process.on_build.append(lambda: (root / ALLOWED_PATHS[0]).unlink())
    bundle_path = tmp_path / "candidate.bundle"

    outcome = run_prepare(root, base, "run", bundle_path, process=process, now=_now)

    assert outcome.status == "failed"
    assert outcome.stage == "allowlist"
    assert _git(root, "rev-parse", "HEAD") == base
    assert not bundle_path.exists()


def test_allowed_file_replaced_by_symlink_fails_allowlist(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)

    def replace_with_symlink() -> None:
        target = root / ALLOWED_PATHS[0]
        target.unlink()
        target.symlink_to(root / "tracked.txt")

    process.on_build.append(replace_with_symlink)
    bundle_path = tmp_path / "candidate.bundle"

    outcome = run_prepare(root, base, "run", bundle_path, process=process, now=_now)

    assert outcome.status == "failed"
    assert outcome.stage == "allowlist"
    assert _git(root, "rev-parse", "HEAD") == base
    assert not bundle_path.exists()


def test_allowed_file_executable_bit_fails_allowlist(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)
    process.on_build.append(lambda: (root / ALLOWED_PATHS[0]).chmod(0o755))
    bundle_path = tmp_path / "candidate.bundle"

    outcome = run_prepare(root, base, "run", bundle_path, process=process, now=_now)

    assert outcome.status == "failed"
    assert outcome.stage == "allowlist"
    assert _git(root, "rev-parse", "HEAD") == base
    assert not bundle_path.exists()


def test_new_allowed_file_missing_at_base_fails_allowlist(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / ALLOWED_PATHS[1]).unlink()
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "drop a pack file")
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)
    process.on_build.append(lambda: (root / ALLOWED_PATHS[1]).write_text("new pack\n"))
    bundle_path = tmp_path / "candidate.bundle"

    outcome = run_prepare(root, base, "run", bundle_path, process=process, now=_now)

    assert outcome.status == "failed"
    assert outcome.stage == "allowlist"
    assert _git(root, "rev-parse", "HEAD") == base
    assert not bundle_path.exists()


def test_readme_change_outside_markers_fails(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)
    process.on_build.append(
        lambda: (root / "README.md").write_bytes(
            b"changed guide\n<!-- omnipack:catalog:start -->\nbase catalog\n"
            b"<!-- omnipack:catalog:end -->\ncredits\n"
        )
    )
    bundle_path = tmp_path / "candidate.bundle"

    outcome = run_prepare(root, base, "run", bundle_path, process=process, now=_now)

    assert outcome.status == "failed"
    assert outcome.stage == "README boundary"
    assert _git(root, "rev-parse", "HEAD") == base
    assert not bundle_path.exists()


def test_verification_failure_fails_the_run(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)
    process.on_build.append(
        lambda: (root / ALLOWED_PATHS[0]).write_text("changed pack\n")
    )
    _fail_verify(process)
    bundle_path = tmp_path / "candidate.bundle"

    outcome = run_prepare(root, base, "run", bundle_path, process=process, now=_now)

    assert outcome.status == "failed"
    assert outcome.stage == "verify"
    assert not bundle_path.exists()


def test_build_failure_fails_before_any_git_change(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)
    _fail_build(process)
    bundle_path = tmp_path / "candidate.bundle"

    outcome = run_prepare(root, base, "run", bundle_path, process=process, now=_now)

    assert outcome.status == "failed"
    assert outcome.stage == "build"
    assert _git(root, "rev-parse", "HEAD") == base


def test_allowed_file_changed_during_verification_fails_drift(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)
    process.on_verify.append(lambda: (root / ALLOWED_PATHS[0]).write_text("drifted\n"))
    bundle_path = tmp_path / "candidate.bundle"

    outcome = run_prepare(root, base, "run", bundle_path, process=process, now=_now)

    assert outcome.status == "failed"
    assert outcome.stage == "drift after verify"
    assert not bundle_path.exists()


def test_stale_reports_are_removed_even_when_build_fails(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    (root / ".build").mkdir()
    (root / ".build/report.json").write_text('{"stale": true}')
    (root / ".build/verify.json").write_text('{"stale": true}')
    process = ScriptedProcess(root)
    _fail_build(process)
    bundle_path = tmp_path / "candidate.bundle"

    outcome = run_prepare(root, base, "run", bundle_path, process=process, now=_now)

    assert outcome.status == "failed"
    assert outcome.stage == "build"
    assert not (root / ".build/report.json").exists()
    assert not (root / ".build/verify.json").exists()


def test_stale_reports_are_removed_even_when_the_checkout_check_fails(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    (root / ".build").mkdir()
    (root / ".build/report.json").write_text('{"stale": true}')
    (root / ".build/verify.json").write_text('{"stale": true}')
    (root / "tracked.txt").write_text("dirty\n")
    process = ScriptedProcess(root)

    outcome = run_prepare(
        root, base, "run", tmp_path / "candidate.bundle", process=process, now=_now
    )

    assert outcome.stage == "checkout"
    assert not (root / ".build/report.json").exists()
    assert not (root / ".build/verify.json").exists()


def _corrupt_index(root: Path) -> None:
    (root / ".git/index").write_bytes(b"not an index")


def test_git_failure_reading_the_checkout_fails_the_checkout_stage(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _corrupt_index(root)
    process = ScriptedProcess(root)

    outcome = run_prepare(
        root, base, "run", tmp_path / "candidate.bundle", process=process, now=_now
    )

    assert outcome.status == "failed"
    assert outcome.summary_line == "checkout"
    assert process.calls == []


def test_git_failure_after_the_build_fails_the_allowlist_stage(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)
    process.on_build.append(lambda: _corrupt_index(root))

    outcome = run_prepare(
        root, base, "run", tmp_path / "candidate.bundle", process=process, now=_now
    )

    assert outcome.status == "failed"
    assert outcome.summary_line == "allowlist"


def test_git_failure_committing_the_candidate_fails_the_commit_stage(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    bundle = tmp_path / "candidate.bundle"
    process = ScriptedProcess(root)

    def change_pack_and_lock_the_index() -> None:
        (root / "dist/single-screen.json").write_text("new single\n")
        (root / ".git/index.lock").write_bytes(b"")

    process.on_build.append(change_pack_and_lock_the_index)

    outcome = run_prepare(root, base, "run", bundle, process=process, now=_now)

    assert outcome.status == "failed"
    assert outcome.summary_line == "commit"
    assert _git(root, "rev-parse", "HEAD") == base
    assert not bundle.exists()
    assert STRUCTURAL_VERIFY_COMMAND not in process.calls


def test_git_failure_after_verification_fails_the_drift_stage(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    process = ScriptedProcess(root)
    process.on_verify.append(lambda: _corrupt_index(root))

    outcome = run_prepare(
        root, base, "run", tmp_path / "candidate.bundle", process=process, now=_now
    )

    assert outcome.status == "failed"
    assert outcome.summary_line == "drift after verify"


def test_build_and_verify_output_passes_through_to_the_log(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    result = PrepareSubprocess().run(
        ("sh", "-c", "echo build-output; echo build-error >&2; exit 3"), tmp_path
    )

    assert result.returncode == 3
    captured = capfd.readouterr()
    assert "build-output" in captured.out
    assert "build-error" in captured.err


def test_prepare_cli_without_runner_temp_exits_with_a_clear_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.delenv("RUNNER_TEMP", raising=False)
    monkeypatch.setenv("GITHUB_SHA", _git(root, "rev-parse", "HEAD"))
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.example")
    monkeypatch.setenv("GITHUB_REPOSITORY", "mjkoo/omnipack")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")

    with pytest.raises(SystemExit, match="^RUNNER_TEMP is required$"):
        nightly_module.main(["prepare"])


def test_real_prepare_commit_hands_off_to_push(tmp_path: Path) -> None:
    """The bundle a real `prepare` run writes is exactly what `push` accepts."""
    seed = _repo(tmp_path, "seed")
    base = _git(seed, "rev-parse", "HEAD")
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(seed), str(bare)], check=True)
    _git(seed, "remote", "add", "origin", str(bare))

    process = ScriptedProcess(seed)
    process.on_build.append(
        lambda: (seed / ALLOWED_PATHS[0]).write_text("changed pack\n")
    )
    bundle_path = tmp_path / "handoff" / "candidate.bundle"

    outcome = run_prepare(
        seed,
        base,
        "https://github.example/runs/9",
        bundle_path,
        process=process,
        now=_now,
    )
    assert outcome.status == "prepared"
    candidate_sha = outcome.sha
    assert candidate_sha is not None

    write_side = tmp_path / "write-side"
    write_side.mkdir()
    _git(write_side, "init", "-q")
    _git(write_side, "remote", "add", "origin", f"file://{bare}")
    _git(write_side, "fetch", "-q", "--depth", "1", "origin", base)
    _git(write_side, "checkout", "-q", "--detach", "FETCH_HEAD")
    assert _git(write_side, "rev-parse", "--is-shallow-repository") == "true"

    result = run_push(write_side, bundle_path, candidate_sha, base, gh=StubGh())

    assert result.status == "published"
    assert result.summary == f"published {candidate_sha}"
    assert _git(bare, "rev-parse", "main") == candidate_sha
    assert _git(write_side, "rev-parse", "HEAD") == candidate_sha
