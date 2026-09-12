"""Tests for the standard-library helpers the publication scripts share.

This file imports only the standard library, pytest and the module under
test, so it runs under the runner's preinstalled CPython 3.12 as well as the
project's own interpreter.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts.workflow_support import (
    GitError,
    SubprocessGhRunner,
    diff_raw_entries,
    git,
    git_output,
    ls_remote_sha,
    run_url,
)

RUN_ENVIRONMENT = {
    "GITHUB_SERVER_URL": "https://github.example/",
    "GITHUB_REPOSITORY": "mjkoo/omnipack",
    "GITHUB_RUN_ID": "42",
}


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
    (root / "README.md").write_text("guide\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root


def test_failed_git_command_writes_its_stderr_to_the_log(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)

    result = git(root, "show", "no-such-ref:README.md")

    assert result.returncode != 0
    assert result.stderr.strip()
    assert result.stderr.strip() in capsys.readouterr().err


def test_failed_raw_git_command_writes_its_stderr_to_the_log(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)

    with pytest.raises(GitError):
        git_output(root, "show", "no-such-ref:README.md")

    assert "no-such-ref" in capsys.readouterr().err


def test_successful_git_command_logs_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)

    assert git(root, "rev-parse", "HEAD").returncode == 0
    git_output(root, "rev-parse", "HEAD")

    assert capsys.readouterr().err == ""


def test_failed_gh_command_writes_its_stderr_to_the_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_gh = bin_dir / "gh"
    fake_gh.write_text(
        "#!/bin/sh\necho 'HTTP 403: denied by the fixture' >&2\nexit 1\n"
    )
    fake_gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    result = SubprocessGhRunner().run(["release", "view", "continuous"])

    assert result.returncode == 1
    assert "HTTP 403: denied by the fixture" in capsys.readouterr().err


def test_diff_reports_a_rename_as_a_deletion_and_an_addition(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    base = _git(root, "rev-parse", "HEAD")
    _git(root, "mv", "README.md", "README2.md")
    _git(root, "commit", "-qm", "rename")
    renamed = _git(root, "rev-parse", "HEAD")

    entries = diff_raw_entries(root, base, renamed)

    assert entries == [
        ("README.md", "100644", "000000"),
        ("README2.md", "000000", "100644"),
    ]


def test_ls_remote_reads_only_the_exact_ref(tmp_path: Path) -> None:
    seed = _repo(tmp_path, "seed")
    main_sha = _git(seed, "rev-parse", "HEAD")
    # A branch whose name ends in "refs/heads/main" also matches the
    # ls-remote pattern, and sorts before the real main.
    _git(seed, "checkout", "-q", "-b", "a/refs/heads/main")
    (seed / "README.md").write_text("decoy\n")
    _git(seed, "commit", "-qam", "decoy")
    decoy_sha = _git(seed, "rev-parse", "HEAD")
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(seed), str(bare)], check=True)
    client = tmp_path / "client"
    client.mkdir()
    _git(client, "init", "-q")
    _git(client, "remote", "add", "origin", f"file://{bare}")
    listed = _git(client, "ls-remote", "origin", "refs/heads/main").splitlines()
    assert listed[0].split()[0] == decoy_sha

    assert ls_remote_sha(client, "refs/heads/main") == main_sha
    assert ls_remote_sha(client, "refs/heads/absent") == ""


def test_ls_remote_failure_is_none(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    assert ls_remote_sha(root, "refs/heads/main") is None


def test_run_url_names_the_workflow_run() -> None:
    assert run_url(RUN_ENVIRONMENT) == (
        "https://github.example/mjkoo/omnipack/actions/runs/42"
    )


@pytest.mark.parametrize("missing", sorted(RUN_ENVIRONMENT))
def test_run_url_requires_every_variable(missing: str) -> None:
    environ = {key: value for key, value in RUN_ENVIRONMENT.items() if key != missing}

    with pytest.raises(SystemExit, match=f"^{missing} is required$"):
        run_url(environ)
