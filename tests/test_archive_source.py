from __future__ import annotations

import os
import subprocess
import time
from compression import zstd
from pathlib import Path
from typing import Any

import pytest

from omnipack.archive import source
from omnipack.archive.source import CaptureOutcome, capture_source


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
    result = capture_source(str(repo), destination, work)
    assert result.outcome is CaptureOutcome.CAPTURED and result.reason is None

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
    result = capture_source(str(tmp_path / "absent"), work / "out.zst", work)
    assert result.outcome is CaptureOutcome.FAILED
    assert result.reason is not None and "clone" in result.reason
    assert not (work / "out.zst").exists()


def test_empty_repository_returns_a_reason(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    git(empty, "init", "--quiet", "--bare")
    work = tmp_path / "work"
    work.mkdir()
    result = capture_source(str(empty), work / "out.zst", work)
    assert result.outcome is CaptureOutcome.FAILED
    assert result.reason is not None and "bundle" in result.reason


def test_passed_deadline_returns_a_reason_without_running_git(
    repo: Path, tmp_path: Path
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    result = capture_source(
        str(repo), work / "out.zst", work, deadline=0.0, clock=lambda: 1.0
    )
    assert result.outcome is CaptureOutcome.EXPIRED
    assert result.reason is not None and "deadline" in result.reason


def test_clone_timeout_expires_the_capture(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def hang(command: list[str], cwd: object, timeout: object) -> None:
        raise subprocess.TimeoutExpired(command, 1)

    monkeypatch.setattr(source, "_run_process", hang)
    work = tmp_path / "work"
    work.mkdir()
    result = capture_source(str(repo), work / "out.zst", work)
    assert result.outcome is CaptureOutcome.EXPIRED
    assert result.reason is not None and "timed out" in result.reason


def test_deadline_passing_during_compression_deletes_the_output(
    repo: Path, tmp_path: Path
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    destination = work / "out.zst"
    # Time is within the deadline for both git steps, then past it afterwards.
    readings = iter([0.0, 0.0, 10.0])
    result = capture_source(
        str(repo), destination, work, deadline=5.0, clock=lambda: next(readings)
    )
    assert result.outcome is CaptureOutcome.EXPIRED
    assert not destination.exists()


def test_timeout_kills_the_whole_process_group(tmp_path: Path) -> None:
    pid_file = tmp_path / "grandchild.pid"
    script = f"sleep 30 & echo $! > {pid_file}; wait"
    with pytest.raises(subprocess.TimeoutExpired):
        source._run_process(["sh", "-c", script], None, 1)
    pid = int(pid_file.read_text())
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    pytest.fail("the grandchild outlived the timeout")


def test_a_process_group_already_gone_still_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(pid: int, signal: int) -> None:
        raise PermissionError("group leader has exited")

    monkeypatch.setattr(source.os, "killpg", refuse)
    with pytest.raises(subprocess.TimeoutExpired):
        source._run_process(["sh", "-c", "sleep 0.5"], None, 0.1)


def test_the_mirror_is_gone_before_compression(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    mirrors: list[list[Path]] = []
    open_zstd = zstd.open

    def recording_open(*args: Any, **kwargs: Any) -> Any:
        mirrors.append(list(work.glob("*/mirror.git")))
        return open_zstd(*args, **kwargs)

    monkeypatch.setattr(source.zstd, "open", recording_open)
    result = capture_source(str(repo), work / "out.zst", work)

    assert result.outcome is CaptureOutcome.CAPTURED
    assert mirrors == [[]]
