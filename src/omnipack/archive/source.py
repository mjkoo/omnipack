"""Capture a repository's full history as a git bundle."""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class CaptureOutcome(StrEnum):
    CAPTURED = "captured"
    # Git failed: the target is archived without a bundle.
    FAILED = "failed"
    # The run deadline passed: the target is abandoned.
    EXPIRED = "expired"


@dataclass(frozen=True)
class CaptureResult:
    outcome: CaptureOutcome
    reason: str | None = None


def capture_source(
    url: str,
    destination: Path,
    work_dir: Path,
    *,
    deadline: float | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> CaptureResult:
    """Write a git bundle of every ref of `url` to `destination`.

    The mirror clone lives under `work_dir` and is removed before returning.
    `deadline` is a reading of `clock` that bounds the clone and the bundling;
    a capture that outlasts it is `EXPIRED`. It never raises for a failed
    capture.
    """
    scratch = Path(tempfile.mkdtemp(dir=work_dir, prefix="source-"))
    try:
        mirror = scratch / "mirror.git"
        steps = (
            ("clone", ["git", "clone", "--mirror", "--quiet", url, str(mirror)], None),
            (
                "bundle",
                ["git", "bundle", "create", "--quiet", str(destination), "--all"],
                mirror,
            ),
        )
        for step, command, cwd in steps:
            result = _run(step, command, cwd, deadline, clock)
            if result is not None:
                return result
        return CaptureResult(CaptureOutcome.CAPTURED)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _run(
    step: str,
    command: list[str],
    cwd: Path | None,
    deadline: float | None,
    clock: Callable[[], float],
) -> CaptureResult | None:
    timeout = None if deadline is None else deadline - clock()
    if timeout is not None and timeout <= 0:
        return CaptureResult(
            CaptureOutcome.EXPIRED, f"git {step} not started: the run deadline passed"
        )
    try:
        completed = _run_process(command, cwd, timeout)
    except subprocess.TimeoutExpired:
        return CaptureResult(
            CaptureOutcome.EXPIRED, f"git {step} timed out at the run deadline"
        )
    except OSError as error:
        return CaptureResult(
            CaptureOutcome.FAILED, f"git {step} could not run: {error}"
        )
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        reason = detail[-1] if detail else f"exit {completed.returncode}"
        return CaptureResult(CaptureOutcome.FAILED, f"git {step} failed: {reason}")
    return None


def _run_process(
    command: list[str], cwd: Path | None, timeout: float | None
) -> subprocess.CompletedProcess[str]:
    """Run a command in its own process group; on timeout kill the whole group
    so transport helpers git spawns (git-remote-https, ssh) do not outlive it.
    Raises `subprocess.TimeoutExpired` after the group is gone."""
    with subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        start_new_session=True,
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # The group can already be gone; macOS refuses a signal to a group
            # whose leader has exited.
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
