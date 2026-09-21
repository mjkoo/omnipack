"""Standard-library helpers shared by the publication workflows' scripts.

The write jobs run these helpers on the runner's preinstalled `python3`, with
no project environment installed, so this module imports only the standard
library. It must not import anything from `omnipack` or from a module that
does.
"""

from __future__ import annotations

import re
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NamedTuple, Protocol

FULL_SHA = re.compile(r"[0-9a-f]{40}")
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
_NO_HOOKS = ("-c", "core.hooksPath=/dev/null")


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class GitError(OSError):
    """A git command exited nonzero."""


class HandoffRejected(RuntimeError):
    """The handed-off bundle, or the commit it carries, failed a check."""


class DiffEntry(NamedTuple):
    path: str
    old_mode: str
    new_mode: str


class GhRunner(Protocol):
    def run(self, args: Sequence[str]) -> CommandResult: ...


class SubprocessGhRunner:
    """Run `gh` without shell interpolation, reading GH_TOKEN from the process."""

    def run(self, args: Sequence[str]) -> CommandResult:
        completed = subprocess.run(
            ["gh", *args], capture_output=True, text=True, check=False
        )
        if completed.returncode != 0:
            _log_failure(
                f"gh {' '.join(args[:2])}", completed.returncode, completed.stderr
            )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def git(root: Path, *args: str) -> CommandResult:
    """Run one git command in `root` with repository hooks disabled.

    A failing command's stderr goes to the job log.
    """
    completed = subprocess.run(
        ["git", *_NO_HOOKS, *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        _log_failure(_git_command(args), completed.returncode, completed.stderr)
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def git_output(root: Path, *args: str) -> bytes:
    """Run one git command with hooks disabled and return its exact stdout bytes.

    Raises `GitError` when git exits nonzero, after writing its stderr to the
    job log.
    """
    completed = subprocess.run(
        ["git", *_NO_HOOKS, *args], cwd=root, capture_output=True, check=False
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode(errors="replace")
        _log_failure(_git_command(args), completed.returncode, stderr)
        raise GitError(stderr.strip() or f"{_git_command(args)} failed")
    return completed.stdout


def git_text(root: Path, *args: str) -> str:
    return git_output(root, *args).decode().strip()


def bot_commit(root: Path, subject: str, body: str) -> str:
    """Commit the index as the Actions bot, with hooks disabled; return the SHA."""
    git_output(
        root,
        "-c",
        f"user.name={BOT_NAME}",
        "-c",
        f"user.email={BOT_EMAIL}",
        "commit",
        "--quiet",
        "-m",
        subject,
        "-m",
        body,
    )
    return git_text(root, "rev-parse", "HEAD")


def expect(result: CommandResult, failure: type[Exception], message: str) -> str:
    """Return the command's stdout, or raise `failure(message)` when it failed."""
    if result.returncode != 0:
        raise failure(message)
    return result.stdout


def ls_remote_sha(root: Path, ref: str) -> str | None:
    """The SHA `origin` reports for exactly `ref`: "" when absent, None on error.

    `git ls-remote` matches a pattern against the tail of each ref name, so it
    also lists refs such as `refs/heads/x/refs/heads/main`; only the line whose
    name is exactly `ref` counts.
    """
    result = git(root, "ls-remote", "origin", ref)
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        sha, _, name = line.partition("\t")
        if name == ref:
            return sha
    return ""


def diff_raw_entries(root: Path, base_sha: str, candidate_sha: str) -> list[DiffEntry]:
    """Every path `candidate_sha` changes relative to `base_sha`, with both modes.

    Runs the plumbing `git diff-tree`, which ignores user diff configuration,
    without rename detection, so a rename appears as a deletion plus an
    addition. Raises `HandoffRejected` when git fails or a line does not parse.
    """
    result = git(
        root, "diff-tree", "-r", "--raw", "--no-renames", base_sha, candidate_sha
    )
    if result.returncode != 0:
        raise HandoffRejected("could not diff the candidate against the base")
    entries: list[DiffEntry] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        meta, separator, path = line.partition("\t")
        parts = meta.split()
        if not separator or len(parts) < 4:
            raise HandoffRejected("could not parse the candidate's diff")
        entries.append(DiffEntry(path, parts[0].lstrip(":"), parts[1]))
    return entries


def verify_handoff(
    root: Path, bundle_path: Path, candidate_sha: str, base_sha: str
) -> list[DiffEntry]:
    """Fetch the handed-off commit and check it against the base checkout.

    Requires `HEAD` to be `base_sha` with a clean working tree, the bundle to
    verify, its fetched `HEAD` to be `candidate_sha`, and that commit's only
    parent to be `base_sha`. Returns the commit's raw diff entries, so each
    caller applies its own path rule. Raises `HandoffRejected` on any failure;
    none of these checks writes to a remote.
    """
    head = expect(
        git(root, "rev-parse", "HEAD"), HandoffRejected, "could not read HEAD"
    ).strip()
    if head != base_sha:
        raise HandoffRejected("HEAD is not the base revision")
    status = expect(
        git(root, "status", "--porcelain"),
        HandoffRejected,
        "could not read the working tree status",
    )
    if status.strip():
        raise HandoffRejected("the working tree is not clean")
    expect(
        git(root, "bundle", "verify", str(bundle_path)),
        HandoffRejected,
        "the bundle does not verify",
    )
    expect(
        git(root, "fetch", "--quiet", str(bundle_path), "HEAD"),
        HandoffRejected,
        "could not fetch the bundle",
    )
    fetched_sha = expect(
        git(root, "rev-parse", "FETCH_HEAD"),
        HandoffRejected,
        "could not read the fetched commit",
    ).strip()
    if fetched_sha != candidate_sha:
        raise HandoffRejected("the bundle's HEAD is not the candidate")
    parents = expect(
        git(root, "rev-list", "--parents", "-n", "1", fetched_sha),
        HandoffRejected,
        "could not read the candidate's parents",
    ).split()
    if len(parents) != 2 or parents[1] != base_sha:
        raise HandoffRejected("the candidate's only parent is not the base revision")
    return diff_raw_entries(root, base_sha, fetched_sha)


FileProblem = Literal["missing", "symlink", "irregular", "executable"]


def regular_file_problem(
    path: Path, *, executable_ok: bool = True
) -> FileProblem | None:
    """Why `path` is not a regular file (checked with `lstat`), or None."""
    try:
        info = path.lstat()
    except OSError:
        return "missing"
    if stat.S_ISLNK(info.st_mode):
        return "symlink"
    if not stat.S_ISREG(info.st_mode):
        return "irregular"
    if not executable_ok and info.st_mode & 0o111:
        return "executable"
    return None


def require_env(environ: Mapping[str, str], name: str) -> str:
    """The named variable's value; exit with a clear message when it is unset."""
    value = environ.get(name)
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def run_url(environ: Mapping[str, str]) -> str:
    server = require_env(environ, "GITHUB_SERVER_URL").rstrip("/")
    repository = require_env(environ, "GITHUB_REPOSITORY")
    run_id = require_env(environ, "GITHUB_RUN_ID")
    return f"{server}/{repository}/actions/runs/{run_id}"


def append_summary(environ: Mapping[str, str], value: str) -> None:
    summary = environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    with Path(summary).open("a", encoding="utf-8") as stream:
        stream.write(value)


def write_github_output(environ: Mapping[str, str], values: Mapping[str, str]) -> None:
    output = environ.get("GITHUB_OUTPUT")
    if not output:
        return
    with Path(output).open("a", encoding="utf-8") as stream:
        stream.writelines(f"{key}={value}\n" for key, value in values.items())


def log(message: str) -> None:
    """Write one diagnostic line to the job log, never the step summary."""
    print(message, file=sys.stderr)


def _log_failure(command: str, returncode: int, stderr: str) -> None:
    log(f"{command} exited {returncode}")
    if stderr.strip():
        log(stderr.rstrip("\n"))


def _git_command(args: Sequence[str]) -> str:
    """`git <subcommand>` for a log line, skipping leading `-c` options."""
    index = 0
    while index + 1 < len(args) and args[index] == "-c":
        index += 2
    return f"git {args[index]}" if index < len(args) else "git"
