"""Capture a repository's full history as a zstd-compressed git bundle."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from compression import zstd
from pathlib import Path

ZSTD_LEVEL = 10


def capture_source(
    url: str,
    destination: Path,
    work_dir: Path,
    *,
    deadline: float | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> str | None:
    """Write a compressed bundle of every ref of `url` to `destination`.

    The mirror clone and the intermediate bundle live under `work_dir` and are
    removed before returning. `deadline` is a reading of `clock` that bounds
    the clone and the bundling. Returns None on success, otherwise the reason
    the source could not be captured; it never raises for a failed capture.
    """
    scratch = Path(tempfile.mkdtemp(dir=work_dir, prefix="source-"))
    try:
        mirror = scratch / "mirror.git"
        bundle = scratch / "repo.bundle"
        steps = (
            ("clone", ["git", "clone", "--mirror", "--quiet", url, str(mirror)], None),
            (
                "bundle",
                ["git", "bundle", "create", "--quiet", str(bundle), "--all"],
                mirror,
            ),
        )
        for step, command, cwd in steps:
            reason = _run(step, command, cwd, deadline, clock)
            if reason is not None:
                return reason
        try:
            with (
                bundle.open("rb") as source,
                zstd.open(destination, "wb", level=ZSTD_LEVEL) as out,
            ):
                shutil.copyfileobj(source, out)
        except OSError as error:
            destination.unlink(missing_ok=True)
            return f"compressing the bundle failed: {error}"
        return None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _run(
    step: str,
    command: list[str],
    cwd: Path | None,
    deadline: float | None,
    clock: Callable[[], float],
) -> str | None:
    timeout = None if deadline is None else deadline - clock()
    if timeout is not None and timeout <= 0:
        return f"git {step} not started: the run deadline passed"
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except subprocess.TimeoutExpired:
        return f"git {step} timed out at the run deadline"
    except OSError as error:
        return f"git {step} could not run: {error}"
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        return f"git {step} failed: {detail[-1] if detail else f'exit {completed.returncode}'}"
    return None
