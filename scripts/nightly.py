"""GitHub Actions entrypoint for the guarded nightly `prepare` step."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from omnipack.catalog import CatalogError, split_catalog
from scripts.nightly_write import ALLOWED_PATHS
from scripts.workflow_support import (
    CommandResult,
    append_summary,
    bot_commit,
    git_output,
    git_text,
    regular_file_problem,
    require_env,
    run_url,
    write_github_output,
)

HANDOFF_DIRECTORY = "nightly-handoff"
BUNDLE_NAME = "candidate.bundle"

BUILD_COMMAND = ("uv", "run", "--no-sync", "pack", "build")
STRUCTURAL_VERIFY_COMMAND = ("uv", "run", "--no-sync", "pack", "verify")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare")
    parser.parse_args(argv)
    return _run_prepare_command(os.environ)


PrepareCommandResult = CommandResult


class PrepareProcess(Protocol):
    def run(self, command: Sequence[str], cwd: Path) -> PrepareCommandResult: ...


class PrepareSubprocess:
    """Run a check command without shell interpolation.

    Its output goes straight to the job log rather than being captured, so
    the result carries only the exit status.
    """

    def run(self, command: Sequence[str], cwd: Path) -> PrepareCommandResult:
        completed = subprocess.run(command, cwd=cwd, check=False)
        return CommandResult(completed.returncode, "", "")


@dataclass(frozen=True)
class PrepareOutcome:
    """The outcome of one guarded `prepare` run.

    `stage` names the failing stage on failure, or `"complete"` otherwise.
    """

    status: str  # "no-op", "prepared" or "failed"
    stage: str
    base_sha: str | None
    sha: str | None
    changed: bool

    @property
    def summary_line(self) -> str:
        if self.status == "no-op":
            return f"no-op at {self.sha}"
        if self.status == "prepared":
            return f"prepared {self.sha}"
        return self.stage


def run_prepare(
    root: Path,
    github_sha: str,
    run_url: str,
    bundle_path: Path,
    *,
    process: PrepareProcess | None = None,
    now: Callable[[], datetime] | None = None,
) -> PrepareOutcome:
    """Build, allowlist, README-bound, commit locally and verify one candidate.

    Runs entirely in the read-only job: it commits the candidate before
    verification and hands the exact commit to the write job as a bundle, so
    the write job can push only bytes this run actually verified.
    """
    selected_process = process or PrepareSubprocess()
    selected_now = now or (lambda: datetime.now(UTC))

    # Reports left by an earlier run in a reused workspace must never reach
    # this run's diagnostics upload, whichever stage fails.
    for relative in (".build/report.json", ".build/verify.json"):
        try:
            (root / relative).unlink(missing_ok=True)
        except OSError:
            return PrepareOutcome("failed", "build", None, None, False)

    try:
        head = git_text(root, "rev-parse", "HEAD")
    except OSError:
        return PrepareOutcome("failed", "checkout", None, None, False)
    try:
        dirty = _dirty_paths(root)
    except OSError:
        return PrepareOutcome("failed", "checkout", head, None, False)
    if head != github_sha or dirty:
        return PrepareOutcome("failed", "checkout", head, None, False)
    base_sha = head

    build_result = selected_process.run(BUILD_COMMAND, root)
    if build_result.returncode != 0:
        return PrepareOutcome("failed", "build", base_sha, None, False)

    try:
        out_of_scope = _dirty_paths(root) - set(ALLOWED_PATHS)
    except OSError:
        return PrepareOutcome("failed", "allowlist", base_sha, None, False)
    if out_of_scope:
        return PrepareOutcome("failed", "allowlist", base_sha, None, False)
    for relative in ALLOWED_PATHS:
        if regular_file_problem(root / relative, executable_ok=False) is not None:
            return PrepareOutcome("failed", "allowlist", base_sha, None, False)

    try:
        base_readme = git_output(root, "show", f"{base_sha}:README.md")
        current_readme = (root / "README.md").read_bytes()
        base_prefix, _, base_suffix = split_catalog(base_readme)
        current_prefix, _, current_suffix = split_catalog(current_readme)
    except CatalogError, OSError:
        return PrepareOutcome("failed", "README boundary", base_sha, None, False)
    if current_prefix != base_prefix or current_suffix != base_suffix:
        return PrepareOutcome("failed", "README boundary", base_sha, None, False)

    try:
        changed_paths = tuple(
            relative
            for relative in ALLOWED_PATHS
            if git_output(root, "show", f"{base_sha}:{relative}")
            != (root / relative).read_bytes()
        )
    except OSError:
        return PrepareOutcome("failed", "allowlist", base_sha, None, False)

    sha = base_sha
    if changed_paths:
        try:
            sha = _commit_candidate(
                root, changed_paths, selected_now(), run_url, base_sha
            )
        except OSError:
            return PrepareOutcome("failed", "commit", base_sha, None, False)

    verify_result = selected_process.run(STRUCTURAL_VERIFY_COMMAND, root)
    if verify_result.returncode != 0:
        return PrepareOutcome("failed", "verify", base_sha, None, False)

    try:
        drifted = _dirty_paths(root)
    except OSError:
        return PrepareOutcome("failed", "drift after verify", base_sha, None, False)
    if drifted:
        return PrepareOutcome("failed", "drift after verify", base_sha, None, False)

    if not changed_paths:
        return PrepareOutcome("no-op", "complete", base_sha, base_sha, False)

    try:
        if git_text(root, "rev-parse", "HEAD") != sha:
            return PrepareOutcome("failed", "bundle", base_sha, None, False)
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        git_output(root, "bundle", "create", str(bundle_path), f"{base_sha}..HEAD")
    except OSError:
        return PrepareOutcome("failed", "bundle", base_sha, None, False)
    return PrepareOutcome("prepared", "complete", base_sha, sha, True)


def _commit_candidate(
    root: Path,
    changed_paths: Sequence[str],
    observed: datetime,
    run_url: str,
    base_sha: str,
) -> str:
    git_output(root, "add", "--", *changed_paths)
    date = observed.astimezone(UTC).date().isoformat()
    subject = f"chore(dist): nightly rebuild {date}"
    body = f"Workflow run: {run_url}\n\nBase SHA: {base_sha}"
    return bot_commit(root, subject, body)


def _dirty_paths(root: Path) -> set[str]:
    tracked = _git_paths(root, "diff", "--name-only", "-z", "HEAD", "--")
    untracked = _git_paths(root, "ls-files", "--others", "--exclude-standard", "-z")
    return tracked | untracked


def _git_paths(root: Path, *args: str) -> set[str]:
    return {item.decode() for item in git_output(root, *args).split(b"\0") if item}


def _handoff_bundle_path(environ: Mapping[str, str]) -> Path:
    runner_temp = require_env(environ, "RUNNER_TEMP")
    return Path(runner_temp) / HANDOFF_DIRECTORY / BUNDLE_NAME


def _run_prepare_command(
    environ: Mapping[str, str], *, root: Path | None = None
) -> int:
    selected_root = root or Path.cwd()
    outcome = run_prepare(
        selected_root,
        environ.get("GITHUB_SHA", ""),
        run_url(environ),
        _handoff_bundle_path(environ),
    )
    if outcome.status != "failed":
        write_github_output(
            environ,
            {
                "changed": "true" if outcome.changed else "false",
                "sha": outcome.sha or "",
                "base": outcome.base_sha or "",
            },
        )
    append_summary(environ, outcome.summary_line + "\n")
    return 0 if outcome.status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
