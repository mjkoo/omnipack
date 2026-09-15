"""Small, explicit fixtures shared by the isolated publication tests.

This test support module deliberately imports only the standard library and
pytest because the publication suite also runs on the runner's stock Python.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

import pytest


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
