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
from typing import Literal, Protocol

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


def main(argv: Sequence[str] | None = None) -> int:
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


# Joins stage names in the `stages` step output; no stage name contains it.
STAGE_SEPARATOR = ","

PrepareStatus = Literal["no-op", "prepared", "failed"]
PrepareStage = Literal[
    "checkout",
    "build",
    "allowlist",
    "README boundary",
    "commit",
    "verify",
    "drift after verify",
    "bundle",
    "complete",
]


@dataclass(frozen=True)
class PrepareOutcome:
    """The outcome of one guarded `prepare` run.

    `stage` names the failing stage on failure, or `"complete"` otherwise.
    `started` lists every stage the run began, in order: a no-op lists neither
    `commit` nor `bundle`, and a failure ends with the failing stage.
    """

    status: PrepareStatus
    stage: PrepareStage
    base_sha: str | None
    sha: str | None
    started: tuple[PrepareStage, ...] = ()

    @property
    def changed(self) -> bool:
        return self.status == "prepared"

    @property
    def summary(self) -> str:
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
    started: list[PrepareStage] = []

    def begin(stage: PrepareStage) -> None:
        if stage not in started:
            started.append(stage)

    def fail(stage: PrepareStage, base_sha: str | None) -> PrepareOutcome:
        begin(stage)
        return PrepareOutcome("failed", stage, base_sha, None, tuple(started))

    # Reports left by an earlier run in a reused workspace must never reach
    # this run's diagnostics upload, whichever stage fails.
    for relative in (".build/report.json", ".build/verify.json"):
        try:
            (root / relative).unlink(missing_ok=True)
        except OSError:
            return fail("build", None)

    begin("checkout")
    try:
        head = git_text(root, "rev-parse", "HEAD")
    except OSError:
        return fail("checkout", None)
    try:
        dirty = _dirty_paths(root)
    except OSError:
        return fail("checkout", head)
    if head != github_sha or dirty:
        return fail("checkout", head)
    base_sha = head

    begin("build")
    build_result = selected_process.run(BUILD_COMMAND, root)
    if build_result.returncode != 0:
        return fail("build", base_sha)

    begin("allowlist")
    try:
        out_of_scope = _dirty_paths(root) - set(ALLOWED_PATHS)
    except OSError:
        return fail("allowlist", base_sha)
    if out_of_scope:
        return fail("allowlist", base_sha)
    for relative in ALLOWED_PATHS:
        if regular_file_problem(root / relative, executable_ok=False) is not None:
            return fail("allowlist", base_sha)

    begin("README boundary")
    try:
        base_readme = git_output(root, "show", f"{base_sha}:README.md")
        current_readme = (root / "README.md").read_bytes()
        base_prefix, _, base_suffix = split_catalog(base_readme)
        current_prefix, _, current_suffix = split_catalog(current_readme)
    except CatalogError, OSError:
        return fail("README boundary", base_sha)
    if current_prefix != base_prefix or current_suffix != base_suffix:
        return fail("README boundary", base_sha)

    try:
        changed_paths = tuple(
            relative
            for relative in ALLOWED_PATHS
            if git_output(root, "show", f"{base_sha}:{relative}")
            != (root / relative).read_bytes()
        )
    except OSError:
        return fail("allowlist", base_sha)

    sha = base_sha
    if changed_paths:
        begin("commit")
        try:
            sha = _commit_candidate(
                root, changed_paths, selected_now(), run_url, base_sha
            )
        except OSError:
            return fail("commit", base_sha)

    begin("verify")
    verify_result = selected_process.run(STRUCTURAL_VERIFY_COMMAND, root)
    if verify_result.returncode != 0:
        return fail("verify", base_sha)

    begin("drift after verify")
    try:
        drifted = _dirty_paths(root)
    except OSError:
        return fail("drift after verify", base_sha)
    if drifted:
        return fail("drift after verify", base_sha)

    if not changed_paths:
        return PrepareOutcome("no-op", "complete", base_sha, base_sha, tuple(started))

    begin("bundle")
    try:
        if git_text(root, "rev-parse", "HEAD") != sha:
            return fail("bundle", base_sha)
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        git_output(root, "bundle", "create", str(bundle_path), f"{base_sha}..HEAD")
    except OSError:
        return fail("bundle", base_sha)
    return PrepareOutcome("prepared", "complete", base_sha, sha, tuple(started))


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
    # `stage` and `stages` are written on failure as well, since alerting
    # reads them; the hand-off outputs exist only for a candidate that passed.
    values: dict[str, str] = {}
    if outcome.status != "failed":
        values |= {
            "changed": "true" if outcome.changed else "false",
            "sha": outcome.sha or "",
            "base": outcome.base_sha or "",
        }
    values["stage"] = outcome.stage
    values["stages"] = STAGE_SEPARATOR.join(outcome.started)
    write_github_output(environ, values)
    append_summary(environ, outcome.summary + "\n")
    return 0 if outcome.status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
