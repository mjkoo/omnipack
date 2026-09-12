"""GitHub Actions entrypoint for guarded nightly publication."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from omnipack.catalog import CatalogError, split_catalog
from scripts.nightly_release import GitHubApi
from scripts.nightly_reporting import PublicationReport, redact, report_publication

CANONICAL_REPOSITORY = "mjkoo/omnipack"
MAIN_REF = "refs/heads/main"
DIAGNOSTIC_DIRECTORY = "nightly-diagnostics"
HANDOFF_DIRECTORY = "nightly-handoff"
BUNDLE_NAME = "candidate.bundle"

# Kept independent of scripts.nightly_publish, which a later change retires.
ALLOWED_PATHS = (
    "dist/single-screen.json",
    "dist/dual-screen.json",
    "README.md",
)
BUILD_COMMAND = ("uv", "run", "--no-sync", "pack", "build")
STRUCTURAL_VERIFY_COMMAND = ("uv", "run", "--no-sync", "pack", "verify")
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"


@dataclass(frozen=True)
class ApiResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class Publisher(Protocol):
    def run(self, run_url: str, token: str) -> object: ...


class OpenedResponse(Protocol):
    @property
    def headers(self) -> Mapping[str, str]: ...

    def __enter__(self) -> OpenedResponse: ...  # noqa: PYI034
    def __exit__(self, *args: object) -> None: ...
    def getcode(self) -> int: ...
    def read(self) -> bytes: ...


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


def _open_without_redirects(request: Request, *, timeout: float) -> OpenedResponse:
    return build_opener(_RejectRedirects()).open(request, timeout=timeout)


class UrllibGitHubApi:
    """Send structured JSON requests only to the configured GitHub API origin."""

    def __init__(
        self,
        token: str,
        api_url: str = "https://api.github.com",
        *,
        timeout: float = 30.0,
        opener: Callable[..., OpenedResponse] = _open_without_redirects,
    ) -> None:
        parsed = urlsplit(api_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.path.rstrip("/"):
            raise ValueError("GitHub API URL must be an HTTPS origin")
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("GitHub API URL must not contain credentials or metadata")
        self.origin = api_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.opener = opener

    def request(
        self, method: str, path: str, body: Mapping[str, object] | None = None
    ) -> ApiResponse:
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError(
                "GitHub API path must be relative to the configured origin"
            )
        data = json.dumps(body).encode() if body is not None else None
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "omnipack-nightly-publisher",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(
            f"{self.origin}{path}", data=data, headers=headers, method=method
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                return ApiResponse(
                    response.getcode(), dict(response.headers), response.read()
                )
        except HTTPError as error:
            return ApiResponse(error.code, dict(error.headers or {}), error.read())
        except URLError as error:
            raise OSError("GitHub API request failed") from error


def is_eligible(environ: Mapping[str, str]) -> bool:
    return (
        environ.get("GITHUB_REPOSITORY") == CANONICAL_REPOSITORY
        and environ.get("GITHUB_REF") == MAIN_REF
    )


def is_bootstrap_eligible(environ: Mapping[str, str]) -> bool:
    return environ.get("GITHUB_REPOSITORY") == CANONICAL_REPOSITORY


def run_publication(
    environ: Mapping[str, str], *, publisher: Publisher | None = None
) -> PublicationReport | None:
    if not is_eligible(environ):
        return None
    run_url = _run_url(environ)
    token = environ.get("GITHUB_TOKEN", "")
    selected_publisher = publisher or _publisher(Path.cwd(), token)
    outcome = selected_publisher.run(run_url, token)
    result = report_publication(
        outcome, _output_dir(environ), run_url, secrets=(token,)
    )
    _append_summary(environ, result.summary + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("publish")
    commands.add_parser("bootstrap-release")
    commands.add_parser("prepare")
    arguments = parser.parse_args(argv)
    environ = os.environ
    if arguments.command == "prepare":
        return _run_prepare_command(environ)
    if arguments.command == "bootstrap-release":
        return _bootstrap(environ)
    if not is_eligible(environ):
        print("Nightly publishing is ineligible for this repository or ref.")
        return 0
    try:
        result = run_publication(environ)
    except Exception as error:  # noqa: BLE001 - final CLI failure boundary
        token = environ.get("GITHUB_TOKEN", "")
        failure = redact({"nightly_failure": str(error)}, (token,))
        print(json.dumps(failure, sort_keys=True), file=sys.stderr, flush=True)
        return 1
    return 0 if result is not None and result.workflow_status == "success" else 1


def _bootstrap(environ: Mapping[str, str]) -> int:
    if not is_bootstrap_eligible(environ):
        print("Release bootstrap is restricted to the canonical repository.")
        return 1
    token = environ.get("GITHUB_TOKEN", "")
    if not token:
        print("Release bootstrap requires GITHUB_TOKEN.", file=sys.stderr)
        return 1
    from scripts.nightly_release import ReleaseError, bootstrap_release

    try:
        result = bootstrap_release(_api(environ))
    except ReleaseError as error:
        print(f"Release bootstrap failed: {error}", file=sys.stderr)
        return 1
    action = "created" if result.created else "already exists"
    print(f"Owned rolling release {action} (id {result.release.release_id}).")
    return 0


def _publisher(source: Path, token: str) -> Publisher:
    from scripts.nightly_git import GitRemote, PublicationCoordinator
    from scripts.nightly_publish import RefreshOrchestrator, SubprocessBoundary
    from scripts.nightly_release_sync import SyncResult, synchronize_release
    from scripts.nightly_release_transport import GitHubReleaseRemote

    class ReleaseSynchronizer:
        def __init__(self, remote: GitHubReleaseRemote) -> None:
            self.remote = remote

        def synchronize(
            self, single: bytes, dual: bytes, source_commit: str
        ) -> SyncResult:
            return synchronize_release(self.remote, single, dual, source_commit)

    return PublicationCoordinator(
        source,
        RefreshOrchestrator(SubprocessBoundary()),
        GitRemote(source),
        ReleaseSynchronizer(GitHubReleaseRemote(token)),
    )


def _api(environ: Mapping[str, str]) -> GitHubApi:
    return UrllibGitHubApi(
        environ.get("GITHUB_TOKEN", ""),
        environ.get("GITHUB_API_URL", "https://api.github.com"),
    )


def _output_dir(environ: Mapping[str, str]) -> Path:
    runner_temp = environ.get("RUNNER_TEMP")
    if not runner_temp:
        raise OSError("RUNNER_TEMP is required")
    return Path(runner_temp) / DIAGNOSTIC_DIRECTORY


def _run_url(environ: Mapping[str, str]) -> str:
    server = environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repository = environ.get("GITHUB_REPOSITORY", CANONICAL_REPOSITORY)
    run_id = environ.get("GITHUB_RUN_ID", "unknown")
    return f"{server}/{repository}/actions/runs/{run_id}"


def _append_summary(environ: Mapping[str, str], value: str) -> None:
    summary = environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    with Path(summary).open("a", encoding="utf-8") as stream:
        stream.write(value)


@dataclass(frozen=True)
class PrepareCommandResult:
    returncode: int
    stdout: str
    stderr: str


class PrepareProcess(Protocol):
    def run(self, command: Sequence[str], cwd: Path) -> PrepareCommandResult: ...


class PrepareSubprocess:
    """Run a check command without shell interpolation."""

    def run(self, command: Sequence[str], cwd: Path) -> PrepareCommandResult:
        completed = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, check=False
        )
        return PrepareCommandResult(
            completed.returncode, completed.stdout, completed.stderr
        )


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

    try:
        head = _git_text(root, "rev-parse", "HEAD")
    except OSError:
        return PrepareOutcome("failed", "checkout", None, None, False)
    if head != github_sha or _dirty_paths(root):
        return PrepareOutcome("failed", "checkout", head, None, False)
    base_sha = head

    for relative in (".build/report.json", ".build/verify.json"):
        try:
            (root / relative).unlink(missing_ok=True)
        except OSError:
            return PrepareOutcome("failed", "build", base_sha, None, False)

    build_result = selected_process.run(BUILD_COMMAND, root)
    if build_result.returncode != 0:
        return PrepareOutcome("failed", "build", base_sha, None, False)

    if _dirty_paths(root) - set(ALLOWED_PATHS):
        return PrepareOutcome("failed", "allowlist", base_sha, None, False)
    for relative in ALLOWED_PATHS:
        if _allowed_file_problem(root / relative) is not None:
            return PrepareOutcome("failed", "allowlist", base_sha, None, False)

    try:
        base_readme = _git_bytes(root, "show", f"{base_sha}:README.md")
        current_readme = (root / "README.md").read_bytes()
        base_prefix, _, base_suffix = split_catalog(base_readme)
        current_prefix, _, current_suffix = split_catalog(current_readme)
    except CatalogError, OSError:
        return PrepareOutcome("failed", "README boundary", base_sha, None, False)
    if current_prefix != base_prefix or current_suffix != base_suffix:
        return PrepareOutcome("failed", "README boundary", base_sha, None, False)

    changed_paths = tuple(
        relative
        for relative in ALLOWED_PATHS
        if _git_bytes(root, "show", f"{base_sha}:{relative}")
        != (root / relative).read_bytes()
    )

    sha = base_sha
    if changed_paths:
        try:
            sha = _commit_candidate(
                root, changed_paths, selected_now(), run_url, base_sha
            )
        except OSError:
            return PrepareOutcome("failed", "bundle", base_sha, None, False)

    verify_result = selected_process.run(STRUCTURAL_VERIFY_COMMAND, root)
    if verify_result.returncode != 0:
        return PrepareOutcome("failed", "verify", base_sha, None, False)

    if _dirty_paths(root):
        return PrepareOutcome("failed", "drift after verify", base_sha, None, False)

    if not changed_paths:
        return PrepareOutcome("no-op", "complete", base_sha, base_sha, False)

    try:
        if _git_text(root, "rev-parse", "HEAD") != sha:
            return PrepareOutcome("failed", "bundle", base_sha, None, False)
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        _git(root, "bundle", "create", str(bundle_path), f"{base_sha}..HEAD")
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
    _git(root, "add", "--", *changed_paths)
    date = observed.astimezone(UTC).date().isoformat()
    subject = f"chore(dist): nightly rebuild {date}"
    body = f"Workflow run: {run_url}\n\nBase SHA: {base_sha}"
    _git(
        root,
        "-c",
        f"user.name={BOT_NAME}",
        "-c",
        f"user.email={BOT_EMAIL}",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "--quiet",
        "-m",
        subject,
        "-m",
        body,
    )
    return _git_text(root, "rev-parse", "HEAD")


def _allowed_file_problem(path: Path) -> str | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return "missing"
    if stat.S_ISLNK(info.st_mode):
        return "symlink"
    if not stat.S_ISREG(info.st_mode):
        return "irregular"
    if info.st_mode & 0o111:
        return "executable"
    return None


def _dirty_paths(root: Path) -> set[str]:
    tracked = _git_paths(root, "diff", "--name-only", "-z", "HEAD", "--")
    untracked = _git_paths(root, "ls-files", "--others", "--exclude-standard", "-z")
    return tracked | untracked


def _git_paths(root: Path, *args: str) -> set[str]:
    return {item.decode() for item in _git_bytes(root, *args).split(b"\0") if item}


def _git_bytes(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, check=False
    )
    if completed.returncode != 0:
        raise OSError(
            completed.stderr.decode(errors="replace").strip()
            or f"git {' '.join(args)} failed"
        )
    return completed.stdout


def _git_text(root: Path, *args: str) -> str:
    return _git_bytes(root, *args).decode().strip()


def _git(root: Path, *args: str) -> None:
    _git_bytes(root, *args)


def _handoff_bundle_path(environ: Mapping[str, str]) -> Path:
    runner_temp = environ.get("RUNNER_TEMP")
    if not runner_temp:
        raise OSError("RUNNER_TEMP is required")
    return Path(runner_temp) / HANDOFF_DIRECTORY / BUNDLE_NAME


def _write_github_output(environ: Mapping[str, str], values: Mapping[str, str]) -> None:
    output = environ.get("GITHUB_OUTPUT")
    if not output:
        return
    with Path(output).open("a", encoding="utf-8") as stream:
        stream.writelines(f"{key}={value}\n" for key, value in values.items())


def _run_prepare_command(
    environ: Mapping[str, str], *, root: Path | None = None
) -> int:
    selected_root = root or Path.cwd()
    outcome = run_prepare(
        selected_root,
        environ.get("GITHUB_SHA", ""),
        _run_url(environ),
        _handoff_bundle_path(environ),
    )
    if outcome.status != "failed":
        _write_github_output(
            environ,
            {
                "changed": "true" if outcome.changed else "false",
                "sha": outcome.sha or "",
                "base": outcome.base_sha or "",
            },
        )
    _append_summary(environ, outcome.summary_line + "\n")
    return 0 if outcome.status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
