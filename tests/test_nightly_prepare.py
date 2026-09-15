"""Tests for the guarded nightly `prepare` step and its real hand-off bundle.

Git runs in an isolated environment (no global identity), so these tests
exercise the actual allowlist, README-boundary and commit behavior against a
temporary repository and bare remote.
"""

from __future__ import annotations

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
from scripts.workflow_support import BOT_EMAIL, BOT_NAME
from tests.publication_support import (
    OK,
    FakeGh,
    bare_remote,
    install_failing_hooks,
    isolated_git_identity,
    repository,
    shallow_checkout,
)
from tests.publication_support import (
    git as _git,
)

pytestmark = pytest.mark.usefixtures(isolated_git_identity.__name__)


README_BYTES = (
    b"guide\n<!-- omnipack:catalog:start -->\nbase catalog\n"
    b"<!-- omnipack:catalog:end -->\ncredits\n"
)


def _repo(tmp_path: Path, name: str = "repo") -> Path:
    files: dict[str, str | bytes] = {
        relative: README_BYTES if relative == "README.md" else f"base:{relative}\n"
        for relative in ALLOWED_PATHS
    }
    files.update({"tracked.txt": "base\n", ".gitignore": ".build/\n"})
    return repository(tmp_path, files, name=name)


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
    install_failing_hooks(root, "pre-commit", "commit-msg", "post-commit")
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
    bundle_path = runner_temp / "nightly-handoff" / "candidate.bundle"
    assert _git(root, "bundle", "list-heads", str(bundle_path)) == f"{sha} HEAD"
    assert base in _git(root, "bundle", "verify", str(bundle_path))
    assert _git(root, "show", "-s", "--format=%an <%ae>%n%cn <%ce>", sha) == (
        f"{BOT_NAME} <{BOT_EMAIL}>\n{BOT_NAME} <{BOT_EMAIL}>"
    )
    assert (
        _git(root, "show", "-s", "--format=%s", sha)
        == f"chore(dist): nightly rebuild {datetime.now(UTC):%Y-%m-%d}"
    )
    body = _git(root, "show", "-s", "--format=%b", sha)
    assert "https://github.example/mjkoo/omnipack/actions/runs/42" in body
    assert base in body
    assert (
        _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", sha)
        == ALLOWED_PATHS[0]
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
    assert _git(root, "rev-parse", "HEAD") == base
    assert process.calls == [BUILD_COMMAND, STRUCTURAL_VERIFY_COMMAND]


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
    bare = bare_remote(seed, tmp_path)
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

    write_side = shallow_checkout(tmp_path, bare, base)

    result = run_push(
        write_side,
        bundle_path,
        candidate_sha,
        base,
        gh=FakeGh({("auth", "setup-git"): OK}),
    )

    assert result.status == "published"
    assert result.summary == f"published {candidate_sha}"
    assert _git(bare, "rev-parse", "main") == candidate_sha
    assert _git(write_side, "rev-parse", "HEAD") == candidate_sha
