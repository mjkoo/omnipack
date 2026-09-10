"""GitHub Actions entrypoint for guarded nightly publication and finalization."""

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

from scripts.nightly_issues import GitHubApi, IssueReconciler
from scripts.nightly_reporting import (
    RESULT_NAME,
    FinalizationResult,
    finalize_publication,
    finalize_setup_failure,
    record_upload_status,
)

CANONICAL_REPOSITORY = "mjkoo/omnipack"
MAIN_REF = "refs/heads/main"
DIAGNOSTIC_DIRECTORY = "nightly-diagnostics"
COMPLETION_MARKER = ".finalized"
_JSON_ERRORS = (OSError, UnicodeDecodeError, json.JSONDecodeError)


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
        url = f"{self.origin}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "omnipack-nightly-publisher",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, data=data, headers=headers, method=method)
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
    """Bootstrap may run from any local ref but can target only the canonical repo."""
    return environ.get("GITHUB_REPOSITORY") == CANONICAL_REPOSITORY


def run_publication(
    environ: Mapping[str, str],
    *,
    publisher: Publisher | None = None,
    api: GitHubApi | None = None,
) -> FinalizationResult | None:
    if not is_eligible(environ):
        return None
    output_dir = _output_dir(environ)
    selected_api = api or _api(environ)
    run_url = _run_url(environ)
    token = environ.get("GITHUB_TOKEN", "")
    selected_publisher = publisher or _publisher(Path.cwd(), token)
    try:
        outcome = selected_publisher.run(run_url, token)
    except Exception as error:  # noqa: BLE001 - preserve diagnostics at the CLI boundary
        return run_setup_failure(
            environ, "helper", error, api=selected_api, ignore_completion=True
        )
    finalization = finalize_publication(
        outcome,
        IssueReconciler(selected_api, CANONICAL_REPOSITORY),
        output_dir,
        run_url,
        secrets=(token,),
        diagnostic_url=run_url,
    )
    _finish(environ, output_dir, finalization)
    return finalization


def run_setup_failure(
    environ: Mapping[str, str],
    stage: str,
    detail: BaseException | str,
    *,
    api: GitHubApi | None = None,
    ignore_completion: bool = False,
) -> FinalizationResult | None:
    if not is_eligible(environ):
        return None
    output_dir = _output_dir(environ)
    if not ignore_completion and (output_dir / COMPLETION_MARKER).is_file():
        return _existing_finalization(output_dir)
    selected_api = api or _api(environ)
    run_url = _run_url(environ)
    token = environ.get("GITHUB_TOKEN", "")
    existing = _load_outcome(output_dir, stage, detail)
    if existing is None:
        finalization = finalize_setup_failure(
            IssueReconciler(selected_api, CANONICAL_REPOSITORY),
            output_dir,
            run_url=run_url,
            stage=stage,
            detail=detail,
            base_sha=environ.get("GITHUB_SHA"),
            secrets=(token,),
            diagnostic_url=run_url,
        )
    else:
        finalization = finalize_publication(
            existing,
            IssueReconciler(selected_api, CANONICAL_REPOSITORY),
            output_dir,
            run_url,
            secrets=(token,),
            diagnostic_url=run_url,
            prior_failure=True,
        )
    _finish(environ, output_dir, finalization)
    return finalization


def record_upload(environ: Mapping[str, str], status: str) -> str:
    if not is_eligible(environ):
        return "skipped"
    output_dir = _output_dir(environ)
    workflow_status = record_upload_status(output_dir, status)
    _append_summary(
        environ,
        f"- Diagnostic upload: {status}\n- Final workflow status: {workflow_status}\n",
    )
    return workflow_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("publish")
    commands.add_parser("bootstrap-release")
    setup = commands.add_parser("finalize-setup")
    setup.add_argument("--stage", required=True)
    setup.add_argument("--detail", required=True)
    upload = commands.add_parser("record-upload")
    upload.add_argument("--status", choices=("success", "failure"))
    arguments = parser.parse_args(argv)
    environ = os.environ
    if arguments.command == "bootstrap-release":
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
    if not is_eligible(environ):
        print("Nightly publishing is ineligible for this repository or ref.")
        return 0
    if arguments.command == "publish":
        result = run_publication(environ)
        return 0 if result is not None and result.workflow_status == "success" else 1
    if arguments.command == "finalize-setup":
        output_dir = _output_dir(environ)
        if (output_dir / COMPLETION_MARKER).is_file():
            print("Nightly publishing was already finalized.")
            return 0
        result = run_setup_failure(environ, arguments.stage, arguments.detail)
        return 0 if result is None else 1
    status = arguments.status or environ.get("NIGHTLY_UPLOAD_STATUS", "failure")
    return 0 if record_upload(environ, status) == "success" else 1


def _publisher(source: Path, token: str) -> Publisher:
    # The project runtime is imported only after setup succeeds and publish starts.
    from scripts.nightly_git import GitRemote, PublicationCoordinator
    from scripts.nightly_publish import (
        LocalAttemptFactory,
        RefreshOrchestrator,
        SubprocessBoundary,
    )
    from scripts.nightly_release_sync import synchronize_release
    from scripts.nightly_release_transport import GitHubReleaseRemote

    class ReleaseSynchronizer:
        def __init__(self, remote: GitHubReleaseRemote) -> None:
            self.remote = remote

        def synchronize(self, single: bytes, dual: bytes, source_commit: str) -> object:
            return synchronize_release(self.remote, single, dual, source_commit)

    return PublicationCoordinator(
        LocalAttemptFactory(source),
        RefreshOrchestrator(SubprocessBoundary()),
        GitRemote(source),
        ReleaseSynchronizer(GitHubReleaseRemote(token)),
    )


def _api(environ: Mapping[str, str]) -> UrllibGitHubApi:
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


def _finish(
    environ: Mapping[str, str], output_dir: Path, finalization: FinalizationResult
) -> None:
    _append_summary(environ, finalization.summary + "\n")
    (output_dir / COMPLETION_MARKER).write_text("complete\n", encoding="utf-8")


def _append_summary(environ: Mapping[str, str], value: str) -> None:
    summary = environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    with Path(summary).open("a", encoding="utf-8") as stream:
        stream.write(value)


def _load_outcome(
    output_dir: Path, stage: str, detail: BaseException | str
) -> dict[str, object] | None:
    path = output_dir / RESULT_NAME
    try:
        document = json.loads(path.read_bytes())
    except _JSON_ERRORS:
        return None
    if not isinstance(document, dict):
        return None
    attempts: list[dict[str, object]] = []
    values = document.get("attempts", [])
    if isinstance(values, list):
        for value in values:
            if not isinstance(value, dict) or value.get("number") not in (1, 2):
                continue
            number = int(value["number"])
            attempt = dict(value)
            for report in ("build", "verify"):
                if value.get(f"{report}_report") == "unavailable":
                    attempt[f"{report}_report"] = None
                    continue
                report_path = output_dir / f"attempt-{number}-{report}.json"
                try:
                    attempt[f"{report}_report"] = report_path.read_bytes()
                except OSError:
                    attempt[f"{report}_report"] = None
            attempts.append(attempt)
    document["attempts"] = attempts
    document["stage"] = stage
    document["detail"] = str(detail)
    return document


def _existing_finalization(output_dir: Path) -> FinalizationResult:
    document = json.loads((output_dir / RESULT_NAME).read_bytes())
    if not isinstance(document, dict):
        raise OSError("orchestration result is not an object")
    return FinalizationResult(
        str(document.get("workflow_status", "failed")),
        str(document.get("publication_status", document.get("status", "failed"))),
        str(document.get("issue_status", "failed")),
        "",
        (output_dir / RESULT_NAME,),
        str(document.get("release_status", "failed")),
        document.get("pending_revision")
        if isinstance(document.get("pending_revision"), int)
        and not isinstance(document.get("pending_revision"), bool)
        else None,
    )


if __name__ == "__main__":
    sys.exit(main())
