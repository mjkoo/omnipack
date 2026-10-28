from __future__ import annotations

import subprocess
from compression import zstd
from pathlib import Path

import pytest

from omnipack.archive import source
from omnipack.archive.source import capture_source


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.test",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "tag.gpgsign=false",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "--quiet", "--initial-branch=main")
    (path / "a.txt").write_text("a")
    git(path, "add", "a.txt")
    git(path, "commit", "--quiet", "-m", "one")
    git(path, "tag", "v1")
    git(path, "checkout", "--quiet", "-b", "feature")
    (path / "b.txt").write_text("b")
    git(path, "add", "b.txt")
    git(path, "commit", "--quiet", "-m", "two")
    git(path, "checkout", "--quiet", "main")
    return path


def test_capture_yields_a_bundle_that_clones_with_every_ref(
    repo: Path, tmp_path: Path
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    destination = work / "repo.bundle.zst"
    assert capture_source(str(repo), destination, work) is None

    bundle = tmp_path / "repo.bundle"
    bundle.write_bytes(zstd.decompress(destination.read_bytes()))
    restored = tmp_path / "restored"
    subprocess.run(
        ["git", "clone", "--quiet", "--mirror", str(bundle), str(restored)], check=True
    )
    refs = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname)"],
        cwd=restored,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert {"refs/heads/main", "refs/heads/feature", "refs/tags/v1"} <= set(refs)


def test_work_directory_holds_only_the_output_afterwards(
    repo: Path, tmp_path: Path
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    capture_source(str(repo), work / "out.zst", work)
    assert [p.name for p in work.iterdir()] == ["out.zst"]


def test_missing_remote_returns_a_reason(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    reason = capture_source(str(tmp_path / "absent"), work / "out.zst", work)
    assert reason is not None and "clone" in reason
    assert not (work / "out.zst").exists()


def test_empty_repository_returns_a_reason(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    git(empty, "init", "--quiet", "--bare")
    work = tmp_path / "work"
    work.mkdir()
    reason = capture_source(str(empty), work / "out.zst", work)
    assert reason is not None and "bundle" in reason


def test_passed_deadline_returns_a_reason_without_running_git(
    repo: Path, tmp_path: Path
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    reason = capture_source(
        str(repo), work / "out.zst", work, deadline=0.0, clock=lambda: 1.0
    )
    assert reason is not None and "deadline" in reason


def test_clone_timeout_returns_a_reason(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def hang(command: list[str], **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(command, 1)

    monkeypatch.setattr(source.subprocess, "run", hang)
    work = tmp_path / "work"
    work.mkdir()
    reason = capture_source(str(repo), work / "out.zst", work)
    assert reason is not None and "timed out" in reason
