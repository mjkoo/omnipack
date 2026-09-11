"""GitHub Actions entrypoint for guarded nightly publication."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from scripts.nightly_release import GitHubApi
from scripts.nightly_reporting import PublicationReport, redact, report_publication

CANONICAL_REPOSITORY = "mjkoo/omnipack"
MAIN_REF = "refs/heads/main"
DIAGNOSTIC_DIRECTORY = "nightly-diagnostics"


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
    arguments = parser.parse_args(argv)
    environ = os.environ
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


if __name__ == "__main__":
    sys.exit(main())
