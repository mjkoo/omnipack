from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

import pytest

from scripts.nightly import (
    ApiResponse,
    UrllibGitHubApi,
    is_eligible,
    record_upload,
    run_publication,
    run_setup_failure,
)
from scripts.nightly_git import AttemptRecord, PublicationResult
from scripts.nightly_publish import StageOutcome
from scripts.nightly_reporting import RESULT_NAME, write_diagnostics

WORKFLOW = Path(".github/workflows/nightly.yml")


class FakeApi:
    def __init__(self, responses: list[ApiResponse]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, str, dict[str, object] | None]] = []

    def request(
        self, method: str, path: str, body: Mapping[str, object] | None = None
    ) -> ApiResponse:
        self.requests.append((method, path, dict(body) if body is not None else None))
        return self.responses.pop(0)


class FakePublisher:
    def __init__(self, result: PublicationResult) -> None:
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def run(self, run_url: str, token: str) -> PublicationResult:
        self.calls.append((run_url, token))
        return self.result


def _response(status: int, value: object) -> ApiResponse:
    return ApiResponse(status, {}, json.dumps(value).encode())


def _environment(tmp_path: Path) -> dict[str, str]:
    return {
        "GITHUB_REPOSITORY": "mjkoo/obtainium-emulation-pack",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SERVER_URL": "https://github.example",
        "GITHUB_API_URL": "https://api.github.example",
        "GITHUB_RUN_ID": "42",
        "GITHUB_SHA": "base-sha",
        "GITHUB_TOKEN": "workflow-secret",
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
    }


def _result(status: str) -> PublicationResult:
    attempt = AttemptRecord(
        1,
        "base-sha",
        (StageOutcome("complete", "success"),),
        b'{"build":"ok"}',
        b'{"verify":"ok"}',
        "candidate-sha" if status == "published" else None,
        datetime(2026, 9, 8, 10, tzinfo=UTC),
        datetime(2026, 9, 8, 11, tzinfo=UTC),
    )
    return PublicationResult(
        status,
        (attempt,),
        "base-sha",
        "published-sha" if status == "published" else None,
        "complete" if status in ("published", "no-op") else "push",
        "",
    )


def test_workflow_has_guarded_serialized_publisher_and_pinned_actions() -> None:
    workflow = WORKFLOW.read_text()

    assert 'cron: "23 6 * * *"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "github.repository == 'mjkoo/obtainium-emulation-pack'" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "group: obtainium-pack-nightly-publisher" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "timeout-minutes: 60" in workflow
    assert "contents: write" in workflow
    assert "issues: write" in workflow
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in workflow
    assert "astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d" in workflow
    assert (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow
    )
    assert "persist-credentials: false" in workflow
    assert "retention-days: 14" in workflow
    assert "--probe-assets" not in workflow


def test_workflow_uses_runtime_independent_fallback_and_explicit_artifacts() -> None:
    workflow = WORKFLOW.read_text()

    assert "python3 -m scripts.nightly finalize-setup" in workflow
    assert "uv run --no-sync python -m scripts.nightly publish" in workflow
    assert "uv sync --locked" in workflow
    assert "if: always()" in workflow
    assert "continue-on-error: true" in workflow
    assert "retention-days: 14" in workflow
    assert (
        "${{ runner.temp }}/nightly-diagnostics/orchestration-result.json" in workflow
    )
    for number in (1, 2):
        for report in ("build", "verify"):
            assert (
                f"${{{{ runner.temp }}}}/nightly-diagnostics/attempt-{number}-{report}.json"
                in workflow
            )
    assert "nightly-diagnostics/**" not in workflow


def test_cli_guard_blocks_ineligible_repository_and_ref(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    environment["GITHUB_REPOSITORY"] = "fork/repo"
    publisher = FakePublisher(_result("published"))

    result = run_publication(environment, publisher=publisher, api=FakeApi([]))

    assert result is None
    assert not publisher.calls
    assert not (tmp_path / "nightly-diagnostics").exists()
    assert not is_eligible(environment)


def test_setup_failure_reports_with_system_runtime_boundary(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    api = FakeApi(
        [
            _response(200, []),
            _response(
                201,
                {
                    "number": 3,
                    "state": "open",
                    "body": "<!-- obtainium-pack:nightly-publishing -->",
                    "user": {"login": "github-actions[bot]"},
                },
            ),
        ]
    )

    result = run_setup_failure(environment, "setup-uv", "Python setup failed", api=api)

    assert result is not None
    assert result.workflow_status == "failed"
    assert result.issue_status == "created"
    persisted = json.loads((tmp_path / "nightly-diagnostics" / RESULT_NAME).read_text())
    assert persisted["publication_status"] == "failed"
    assert persisted["issue_status"] == "created"
    assert persisted["workflow_status"] == "failed"


def test_confirmed_publication_is_preserved_when_issue_maintenance_fails(
    tmp_path: Path,
) -> None:
    environment = _environment(tmp_path)
    publisher = FakePublisher(_result("published"))
    api = FakeApi([_response(500, {"message": "unavailable"})])

    result = run_publication(environment, publisher=publisher, api=api)

    assert result is not None
    assert result.workflow_status == "failed"
    assert result.publication_status == "published"
    persisted = json.loads((tmp_path / "nightly-diagnostics" / RESULT_NAME).read_text())
    assert persisted["status"] == "published"
    assert persisted["published_sha"] == "published-sha"
    assert persisted["issue_status"] == "failed"
    summary = (tmp_path / "summary.md").read_text()
    assert "Issue maintenance: failed" in summary
    assert "Workflow status: failed" in summary


@pytest.mark.parametrize(
    ("status", "expected_workflow", "response_count"),
    [
        ("published", "success", 1),
        ("no-op", "success", 1),
        ("failed", "failed", 2),
        ("uncertain", "failed", 2),
    ],
)
def test_publication_outcomes_remain_distinct_in_persistent_result(
    tmp_path: Path, status: str, expected_workflow: str, response_count: int
) -> None:
    responses = [_response(200, [])]
    if response_count == 2:
        responses.append(
            _response(
                201,
                {
                    "number": 7,
                    "state": "open",
                    "body": "<!-- obtainium-pack:nightly-publishing -->",
                    "user": {"login": "github-actions[bot]"},
                },
            )
        )

    result = run_publication(
        _environment(tmp_path),
        publisher=FakePublisher(_result(status)),
        api=FakeApi(responses),
    )

    assert result is not None
    assert result.publication_status == status
    assert result.workflow_status == expected_workflow
    persisted = json.loads((tmp_path / "nightly-diagnostics" / RESULT_NAME).read_text())
    assert persisted["status"] == status
    assert persisted["publication_status"] == status
    assert persisted["workflow_status"] == expected_workflow


def test_helper_fallback_reloads_confirmed_outcome_instead_of_resetting_it(
    tmp_path: Path,
) -> None:
    environment = _environment(tmp_path)
    first = run_publication(
        environment,
        publisher=FakePublisher(_result("published")),
        api=FakeApi([_response(200, [])]),
    )
    assert first is not None
    (tmp_path / "nightly-diagnostics" / ".finalized").unlink()

    retried = run_setup_failure(
        environment,
        "helper",
        "helper exited unexpectedly",
        api=FakeApi([_response(200, [])]),
    )

    assert retried is not None
    assert retried.publication_status == "published"
    persisted = json.loads((tmp_path / "nightly-diagnostics" / RESULT_NAME).read_text())
    assert persisted["status"] == "published"
    assert persisted["published_sha"] == "published-sha"


def test_upload_outcome_updates_persistent_result_and_summary(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    run_publication(
        environment,
        publisher=FakePublisher(_result("published")),
        api=FakeApi([_response(200, [])]),
    )

    status = record_upload(environment, "failure")

    assert status == "failed"
    persisted = json.loads((tmp_path / "nightly-diagnostics" / RESULT_NAME).read_text())
    assert persisted["diagnostic_upload_status"] == "failure"
    assert persisted["workflow_status"] == "failed"
    summary = (tmp_path / "summary.md").read_text()
    assert "Diagnostic upload: failure" in summary
    assert "Final workflow status: failed" in summary


@dataclass
class OpenedResponse:
    code: int = 200
    headers: dict[str, str] = field(default_factory=dict)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def getcode(self) -> int:
        return self.code

    def read(self) -> bytes:
        return b"[]"


def test_urllib_api_uses_structured_json_timeout_and_api_host_credentials() -> None:
    opened: list[tuple[Any, float]] = []

    def opener(request: Any, timeout: float) -> OpenedResponse:
        opened.append((request, timeout))
        return OpenedResponse(headers={})

    api = UrllibGitHubApi(
        "workflow-secret",
        "https://api.github.example",
        timeout=7.5,
        opener=opener,
    )

    response = api.request("POST", "/repos/owner/repo/issues", {"body": "$(false)"})

    assert response.status == 200
    request, timeout = opened[0]
    assert request.full_url == "https://api.github.example/repos/owner/repo/issues"
    assert request.get_header("Authorization") == "Bearer workflow-secret"
    assert request.data == b'{"body": "$(false)"}'
    assert timeout == 7.5
    assert "workflow-secret" not in request.full_url
    with pytest.raises(ValueError, match="relative"):
        api.request("GET", "//attacker.example/issues")


def test_system_python_module_entrypoint_does_not_import_project_runtime(
    tmp_path: Path,
) -> None:
    blocker = tmp_path / "sitecustomize.py"
    blocker.write_text(
        "import builtins\n"
        "original = builtins.__import__\n"
        "def blocked(name, *args, **kwargs):\n"
        "    if name.startswith('obtainium_pack') or name in "
        "('scripts.nightly_git', 'scripts.nightly_publish'):\n"
        "        raise RuntimeError('project runtime import blocked')\n"
        "    return original(name, *args, **kwargs)\n"
        "builtins.__import__ = blocked\n"
    )
    environment = os.environ.copy()
    environment.update(_environment(tmp_path))
    environment["GITHUB_REPOSITORY"] = "fork/repo"
    environment["PYTHONPATH"] = str(tmp_path)

    completed = subprocess.run(
        ["python3", "-m", "scripts.nightly", "publish"],
        cwd=Path.cwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "ineligible" in completed.stdout.lower()


def test_interrupted_finalization_write_preserves_publication_for_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = _environment(tmp_path)
    original = Path.write_text

    def interrupted_write(path: Path, data: str, *args: Any, **kwargs: Any) -> int:
        if '"diagnostic_upload_status": "pending"' in data:
            original(path, data[:20], *args, **kwargs)
            raise OSError("interrupted write")
        return original(path, data, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "write_text", interrupted_write)
        with pytest.raises(OSError, match="interrupted write"):
            run_publication(
                environment,
                publisher=FakePublisher(_result("published")),
                api=FakeApi([_response(200, [])]),
            )

    retried = run_setup_failure(
        environment, "helper", "interrupted write", api=FakeApi([_response(200, [])])
    )

    assert retried is not None
    assert retried.publication_status == "published"
    diagnostics = tmp_path / "nightly-diagnostics"
    persisted = json.loads((diagnostics / RESULT_NAME).read_text())
    assert persisted["published_sha"] == "published-sha"
    assert len(persisted["attempts"]) == 1
    assert retried.workflow_status == "failed"
    assert persisted["workflow_status"] == "failed"
    assert record_upload(environment, "success") == "failed"
    assert "Final workflow status: failed" in (tmp_path / "summary.md").read_text()
    assert json.loads((diagnostics / "attempt-1-build.json").read_text()) == {
        "build": "ok"
    }
    assert json.loads((diagnostics / "attempt-1-verify.json").read_text()) == {
        "verify": "ok"
    }


def test_fallback_preserves_missing_report_markers(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    outcome = _result("failed")
    outcome = replace(
        outcome,
        attempts=(replace(outcome.attempts[0], build_report=None, verify_report=None),),
    )
    diagnostics = tmp_path / "nightly-diagnostics"
    write_diagnostics(diagnostics, outcome, "run")

    result = run_setup_failure(
        environment,
        "helper",
        "publisher execution failed",
        api=FakeApi([_response(500, {})]),
    )

    assert result is not None
    persisted = json.loads((diagnostics / RESULT_NAME).read_text())
    assert persisted["attempts"][0]["build_report"] == "unavailable"
    assert persisted["attempts"][0]["verify_report"] == "unavailable"
    assert "build report unavailable; verification report unavailable" in result.summary
    for name in ("build", "verify"):
        report = json.loads((diagnostics / f"attempt-1-{name}.json").read_text())
        assert report["available"] is False
