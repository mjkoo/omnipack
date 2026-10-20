"""Small, explicit fixtures shared by the isolated publication tests.

This test support module deliberately imports only the standard library,
pytest and the standard-library `scripts` modules, because the publication
suite also runs on the runner's stock Python.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from scripts.alerts import Finding, build_body
from scripts.nightly_write import ALLOWED_PATHS


class CommandResult(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


GhResponse = CommandResult | Callable[[tuple[str, ...]], CommandResult]


@pytest.fixture
def isolated_git_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep real-Git tests independent of user and system configuration."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for name in list(os.environ):
        if name.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_")):
            monkeypatch.delenv(name)


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def repository(
    tmp_path: Path,
    files: Mapping[str, str | bytes],
    *,
    name: str = "repo",
) -> Path:
    root = tmp_path / name
    root.mkdir()
    git(root, "init", "-q", "--initial-branch=main")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    return root


def bare_remote(
    seed: Path,
    tmp_path: Path,
    *,
    name: str = "remote.git",
    main_only: bool = False,
) -> Path:
    bare = tmp_path / name
    command = ["git", "clone", "-q", "--bare"]
    if main_only:
        command.extend(("--single-branch", "--branch", "main"))
    subprocess.run([*command, str(seed), str(bare)], check=True)
    return bare


def shallow_checkout(
    tmp_path: Path,
    bare: Path,
    base_sha: str,
    *,
    name: str = "write-side",
) -> Path:
    root = tmp_path / name
    root.mkdir()
    git(root, "init", "-q")
    git(root, "remote", "add", "origin", f"file://{bare}")
    git(root, "fetch", "-q", "--depth", "1", "origin", base_sha)
    git(root, "checkout", "-q", "--detach", "FETCH_HEAD")
    assert git(root, "rev-parse", "--is-shallow-repository") == "true"
    return root


def bundle(seed: Path, base_sha: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    git(seed, "bundle", "create", str(path), f"{base_sha}..HEAD")
    return path


def install_failing_hooks(root: Path, *names: str) -> None:
    hooks = root / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    for name in names:
        hook = hooks / name
        hook.write_text("#!/bin/sh\necho 'a repository hook ran' >&2\nexit 1\n")
        hook.chmod(0o755)


class FakeGh:
    """A prefix-routed fake whose configured command outcomes stay visible."""

    def __init__(self, responses: Mapping[tuple[str, ...], GhResponse]) -> None:
        self.responses = dict(responses)
        self.calls: list[tuple[str, ...]] = []
        self.file_inputs: dict[tuple[str, ...], dict[str, str]] = {}

    def run(self, args: Sequence[str]) -> Any:
        call = tuple(args)
        self.calls.append(call)
        self.file_inputs[call] = {
            option: Path(call[call.index(option) + 1]).read_text()
            for option in ("--body-file", "--notes-file")
            if option in call
        }
        matches = [prefix for prefix in self.responses if call[: len(prefix)] == prefix]
        if not matches:
            raise AssertionError(f"unexpected gh command {call}")
        prefix = max(matches, key=len)
        response = self.responses[prefix]
        return response if isinstance(response, CommandResult) else response(call)

    def texts_for(self, prefix: tuple[str, ...], option: str) -> list[str]:
        return [
            files[option]
            for call, files in self.file_inputs.items()
            if call[: len(prefix)] == prefix and option in files
        ]


OK = CommandResult(0, "", "")


def failure(stderr: str = "") -> CommandResult:
    return CommandResult(1, "", stderr)


# --- alert reconciliation ----------------------------------------------------

REPOSITORY = "mjkoo/omnipack"
RUN_1 = "https://github.com/mjkoo/omnipack/actions/runs/1"
RUN_2 = "https://github.com/mjkoo/omnipack/actions/runs/2"
ISSUE_LISTING = ("api", "--paginate")


def alert_issue(
    number: int,
    key: str,
    *,
    details: tuple[str, ...] = ("boom",),
    title: str | None = None,
    state: str = "open",
    reason: str | None = None,
    run: str = RUN_1,
    body: str | None = None,
) -> dict:
    """One labelled issue as the listing returns it, keyed `key`."""
    return {
        "number": number,
        "title": title or f"title of {key}",
        "body": body
        if body is not None
        else build_body(Finding(key, "t", details), run),
        "state": state,
        "state_reason": reason,
    }


def alert_gh(
    issues: list[dict] | list[list[dict]] | None = None,
    *,
    label: CommandResult = OK,
    listing: CommandResult | None = None,
    **operations: CommandResult,
) -> FakeGh:
    """A `gh` listing `issues` (one page, or a list of pages) where every write
    succeeds unless an `issue_<verb>` keyword says otherwise."""
    pages = issues or []
    if pages and isinstance(pages[0], dict):
        pages = [pages]
    text = "".join(json.dumps(page) for page in pages) or "[]"
    responses = {
        ("label", "create"): label,
        ISSUE_LISTING: listing or CommandResult(0, text, ""),
        ("issue", "create"): OK,
        ("issue", "edit"): OK,
        ("issue", "reopen"): OK,
        ("issue", "close"): OK,
    }
    responses.update(
        {tuple(name.split("_")): value for name, value in operations.items()}
    )
    return FakeGh(responses)


def issue_writes(gh: FakeGh) -> list[tuple[str, ...]]:
    """Each issue write as (verb, number-or-title)."""
    return [
        (call[1], call[call.index("--title") + 1] if call[1] == "create" else call[2])
        for call in gh.calls
        if call[0] == "issue"
    ]


# --- write-side repositories -------------------------------------------------

README_BYTES = (
    b"guide\n<!-- omnipack:catalog:start -->\nbase catalog\n"
    b"<!-- omnipack:catalog:end -->\ncredits\n"
)


def push_gh(*, auth_ok: bool = True) -> FakeGh:
    return FakeGh({("auth", "setup-git"): OK if auth_ok else failure()})


def seed_repository(tmp_path: Path, name: str = "seed") -> Path:
    """A repository holding a base version of each published file."""
    return repository(
        tmp_path,
        {relative: f"base:{relative}\n" for relative in ALLOWED_PATHS},
        name=name,
    )


def commit_as_bot(root: Path, changes: dict[str, str]) -> str:
    """Commit `changes` as the Actions bot's nightly rebuild; return the SHA."""
    for relative, content in changes.items():
        path = root / relative
        path.write_text(content)
        git(root, "add", "--", relative)
    git(
        root,
        "-c",
        "user.name=github-actions[bot]",
        "-c",
        "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit",
        "-qm",
        "chore(dist): nightly rebuild 2026-09-12",
    )
    return git(root, "rev-parse", "HEAD")


def advance_main(remote: Path, workdir: Path) -> str:
    """Push another commit to `remote`'s main, as a later run would; return it."""
    other = workdir / "other"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
    git(other, "config", "user.name", "Test")
    git(other, "config", "user.email", "test@example.invalid")
    (other / "tracked.txt").write_text("advance\n")
    git(other, "add", "tracked.txt")
    git(other, "commit", "-qm", "advance")
    git(other, "push", "-q", "origin", "HEAD:main")
    return git(other, "rev-parse", "HEAD")


def prepare_repository(tmp_path: Path, name: str = "repo") -> Path:
    """A repository the nightly prepare step can run in."""
    files: dict[str, str | bytes] = {
        relative: README_BYTES if relative == "README.md" else f"base:{relative}\n"
        for relative in ALLOWED_PATHS
    }
    files.update(
        {
            "tracked.txt": "base\n",
            "config/catalogs/codm.json": '{"apps": []}\n',
            ".gitignore": ".build/\n",
        }
    )
    return repository(tmp_path, files, name=name)


def prepare_environment(
    monkeypatch: pytest.MonkeyPatch, root: Path, tmp_path: Path
) -> Path:
    """The prepare step's Actions environment in `root`; returns RUNNER_TEMP.

    Step outputs go to `tmp_path/output.txt` and the summary to
    `tmp_path/summary.md`.
    """
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    monkeypatch.chdir(root)
    monkeypatch.setenv("GITHUB_SHA", git(root, "rev-parse", "HEAD"))
    monkeypatch.setenv("RUNNER_TEMP", str(runner_temp))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output.txt"))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.example")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    return runner_temp
