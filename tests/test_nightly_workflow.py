from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

import pytest

import scripts.nightly
from scripts.nightly import UrllibGitHubApi, is_eligible, run_publication
from scripts.nightly_git import PublicationResult
from scripts.nightly_publish import StageOutcome
from scripts.nightly_reporting import RESULT_NAME

WORKFLOW = Path(".github/workflows/nightly.yml")


class FakePublisher:
    def __init__(self, result: PublicationResult | BaseException) -> None:
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def run(self, run_url: str, token: str) -> PublicationResult:
        self.calls.append((run_url, token))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def _environment(tmp_path: Path) -> dict[str, str]:
    return {
        "GITHUB_REPOSITORY": "mjkoo/omnipack",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SERVER_URL": "https://github.example",
        "GITHUB_API_URL": "https://api.github.example",
        "GITHUB_RUN_ID": "42",
        "GITHUB_TOKEN": "workflow-secret",
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
    }


def _result(status: str, *, release_status: str = "not-run") -> PublicationResult:
    return PublicationResult(
        status=status,
        base_sha="base-sha",
        published_sha="published-sha" if status == "published" else None,
        stage="complete" if status in ("published", "no-op") else "build",
        stages=(StageOutcome("build", "success"),),
        build_report=b'{"build":"ok"}',
        verify_report=b'{"verify":"ok"}',
        candidate_sha="candidate-sha" if status == "published" else None,
        started_at=datetime(2026, 9, 8, 10, tzinfo=UTC),
        finished_at=datetime(2026, 9, 8, 11, tzinfo=UTC),
        release_status=release_status,
    )


def test_workflow_has_one_guarded_publisher_and_visible_diagnostic_upload() -> None:
    workflow = WORKFLOW.read_text()

    assert 'cron: "0 3 * * *"\n      timezone: "America/New_York"' in workflow
    assert "github.repository == 'mjkoo/omnipack'" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "timeout-minutes: 60" in workflow
    assert "ref: main" in workflow
    assert "persist-credentials: false" in workflow
    assert "contents: write" in workflow
    assert "issues: write" not in workflow
    assert "uv sync --locked" in workflow
    assert "uv run --no-sync python -m scripts.nightly publish" in workflow
    assert "if: always()" in workflow
    assert "continue-on-error" not in workflow
    assert "if-no-files-found: ignore" in workflow
    assert "retention-days: 14" in workflow
    for report in ("run-result.json", "build-report.json", "verify-report.json"):
        assert f"${{{{ runner.temp }}}}/nightly-diagnostics/{report}" in workflow
    assert "finalize-setup" not in workflow
    assert "record-upload" not in workflow
    assert "attempt-" not in workflow


def test_early_setup_or_sync_failure_skips_publish_but_still_runs_upload() -> None:
    workflow = WORKFLOW.read_text()

    assert "id: setup_uv" in workflow
    assert "id: sync" in workflow
    assert "id: publisher" in workflow
    assert (
        workflow.index("id: setup_uv")
        < workflow.index("id: sync")
        < workflow.index("id: publisher")
    )
    assert workflow.index("id: publisher") < workflow.index(
        "name: Upload available diagnostics"
    )
    assert (
        "if: always()"
        in workflow[workflow.index("name: Upload available diagnostics") :]
    )


def test_cli_guard_blocks_ineligible_repository_and_ref(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    environment["GITHUB_REPOSITORY"] = "fork/repo"
    publisher = FakePublisher(_result("published", release_status="success"))

    result = run_publication(environment, publisher=publisher)

    assert result is None
    assert not publisher.calls
    assert not (tmp_path / "nightly-diagnostics").exists()
    assert not is_eligible(environment)


def test_success_writes_summary_and_flat_diagnostics(tmp_path: Path) -> None:
    result = run_publication(
        _environment(tmp_path),
        publisher=FakePublisher(_result("published", release_status="success")),
    )

    assert result is not None and result.workflow_status == "success"
    document = json.loads((tmp_path / "nightly-diagnostics" / RESULT_NAME).read_text())
    assert document["status"] == "published"
    assert "attempts" not in document
    assert "diagnostic_upload_status" not in document
    assert "Result: published" in (tmp_path / "summary.md").read_text()


def test_summary_write_failure_is_visible_and_diagnostics_remain(
    tmp_path: Path,
) -> None:
    environment = _environment(tmp_path)
    environment["GITHUB_STEP_SUMMARY"] = str(tmp_path / "missing" / "summary.md")

    with pytest.raises(OSError):
        run_publication(
            environment,
            publisher=FakePublisher(_result("published", release_status="success")),
        )

    assert (tmp_path / "nightly-diagnostics" / RESULT_NAME).is_file()


def test_unexpected_helper_failure_is_redacted_json_without_reconstruction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(os, "environ", _environment(tmp_path))
    monkeypatch.setattr(
        scripts.nightly,
        "_publisher",
        lambda _root, _token: FakePublisher(
            RuntimeError("token=workflow-secret\n::error::hostile")
        ),
    )

    assert scripts.nightly.main(["publish"]) == 1

    error = capsys.readouterr().err
    assert len(error.splitlines()) == 1
    assert json.loads(error)["nightly_failure"] == "token=REDACTED\n::error::hostile"
    assert not (tmp_path / "nightly-diagnostics").exists()


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


def test_bootstrap_api_retains_auth_origin_and_redirect_guards() -> None:
    opened: list[tuple[Any, float]] = []

    def opener(request: Any, timeout: float) -> OpenedResponse:
        opened.append((request, timeout))
        return OpenedResponse()

    api = UrllibGitHubApi(
        "workflow-secret", "https://api.github.example", timeout=7.5, opener=opener
    )
    response = api.request("POST", "/repos/owner/repo/releases", {"body": "data"})

    assert response.status == 200
    request, timeout = opened[0]
    assert request.full_url == "https://api.github.example/repos/owner/repo/releases"
    assert request.get_header("Authorization") == "Bearer workflow-secret"
    assert timeout == 7.5
    with pytest.raises(ValueError, match="relative"):
        api.request("GET", "//attacker.example/releases")
    with pytest.raises(ValueError, match="HTTPS origin"):
        UrllibGitHubApi("secret", "http://api.github.example")


def test_ineligible_entrypoint_keeps_project_runtime_lazy(tmp_path: Path) -> None:
    blocker = tmp_path / "sitecustomize.py"
    blocker.write_text(
        "import builtins\noriginal = builtins.__import__\n"
        "def blocked(name, *args, **kwargs):\n"
        "    if name in ('scripts.nightly_git', 'scripts.nightly_publish'):\n"
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

    assert completed.returncode == 0
    assert "ineligible" in completed.stdout.lower()
