from __future__ import annotations

import ast
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.nightly_issues import MARKER, IssueResult
from scripts.nightly_reporting import (
    artifact_paths,
    finalize_publication,
    finalize_setup_failure,
    write_diagnostics,
)


@dataclass(frozen=True)
class Stage:
    stage: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class Attempt:
    number: int
    base_sha: str
    stages: tuple[Stage, ...]
    build_report: bytes | None
    verify_report: bytes | None
    candidate_sha: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class Publication:
    status: str
    attempts: tuple[Attempt, ...]
    base_sha: str | None
    published_sha: str | None
    stage: str
    detail: str = ""
    release_status: str = "not-run"
    release_revision: int | None = None
    pending_revision: int | None = None


class RecordingIssues:
    def __init__(self, result: IssueResult | None = None) -> None:
        self.result = result or IssueResult("updated", 4)
        self.failure_bodies: list[str] = []
        self.recovery_bodies: list[str] = []

    def report_failure(self, body: str) -> IssueResult:
        self.failure_bodies.append(body)
        return self.result

    def report_recovery(self, body: str) -> IssueResult:
        self.recovery_bodies.append(body)
        return self.result


def _publication(
    status: str = "failed", *, release_status: str = "not-run"
) -> Publication:
    attempt = Attempt(
        1,
        "base-secret",
        (Stage("build", "failed", "$(touch /tmp/nope) token=secret-value"),),
        json.dumps(
            {"message": "secret-value", "nested": ["Bearer secret-value"]}
        ).encode(),
        None,
        started_at=datetime(2026, 9, 8, 10, tzinfo=UTC),
        finished_at=datetime(2026, 9, 8, 11, tzinfo=UTC),
    )
    return Publication(
        status,
        (attempt,),
        "base-secret",
        "published-sha" if status == "published" else None,
        "build" if status == "failed" else "complete",
        "exception contained secret-value",
        release_status=release_status,
    )


def test_diagnostics_are_per_attempt_redacted_and_identify_missing_reports(
    tmp_path: Path,
) -> None:
    outcome = _publication()

    written = write_diagnostics(
        tmp_path,
        outcome,
        "https://github.example/runs/42?token=secret-value",
        secrets=("secret-value",),
    )

    assert {path.name for path in written} == {
        "orchestration-result.json",
        "attempt-1-build.json",
        "attempt-1-verify.json",
    }
    combined = "".join(path.read_text() for path in written)
    assert "secret-value" not in combined
    assert "REDACTED" in combined
    verify = json.loads((tmp_path / "attempt-1-verify.json").read_text())
    assert verify == {"available": False, "report": "verification"}
    result = json.loads((tmp_path / "orchestration-result.json").read_text())
    assert result["attempts"][0]["started_at"] == "2026-09-08T10:00:00+00:00"
    assert result["attempts"][0]["finished_at"] == "2026-09-08T11:00:00+00:00"


def test_artifact_selection_is_an_explicit_regular_file_allowlist(
    tmp_path: Path,
) -> None:
    write_diagnostics(tmp_path, _publication(), "run", secrets=("secret-value",))
    (tmp_path / "download.apk").write_bytes(b"apk")
    (tmp_path / "http-cache.json").write_text("cache")
    (tmp_path / "notes.txt").write_text("unrelated")
    (tmp_path / "attempt-9-build.json").symlink_to(tmp_path / "notes.txt")

    assert [path.name for path in artifact_paths(tmp_path)] == [
        "orchestration-result.json",
        "attempt-1-build.json",
        "attempt-1-verify.json",
    ]


def test_failure_body_and_summary_are_bounded_and_treat_source_text_as_data(
    tmp_path: Path,
) -> None:
    issues = RecordingIssues()
    hostile = replace(
        _publication(), detail="exception contained secret-value " + "x" * 5_000
    )

    result = finalize_publication(
        hostile,
        issues,
        tmp_path,
        "https://github.example/runs/42",
        secrets=("secret-value",),
        diagnostic_url="https://github.example/runs/42#artifacts",
    )

    assert result.workflow_status == "failed"
    assert result.publication_status == "failed"
    assert len(result.summary) <= 16_000
    assert len(issues.failure_bodies[0]) <= 4_000
    assert MARKER in issues.failure_bodies[0]
    assert "$(touch /tmp/nope)" in issues.failure_bodies[0]
    assert "secret-value" not in result.summary + issues.failure_bodies[0]
    assert not Path("/tmp/nope").exists()


def test_published_result_survives_issue_failure_and_later_success_retries_closure(
    tmp_path: Path,
) -> None:
    publication = _publication("published", release_status="success")
    failed_issues = RecordingIssues(IssueResult("failed", detail="API unavailable"))

    failed = finalize_publication(
        publication, failed_issues, tmp_path, "run", secrets=("secret-value",)
    )
    recovered_issues = RecordingIssues(IssueResult("closed", 4))
    recovered = finalize_publication(
        publication, recovered_issues, tmp_path, "run", secrets=("secret-value",)
    )

    assert failed.workflow_status == "failed"
    assert failed.publication_status == "published"
    assert "Issue maintenance: failed" in failed.summary
    assert recovered.workflow_status == "success"
    assert (
        len(failed_issues.recovery_bodies) == len(recovered_issues.recovery_bodies) == 1
    )


def test_no_op_closes_recovery_without_failure_creation(tmp_path: Path) -> None:
    issues = RecordingIssues(IssueResult("closed", 4))

    result = finalize_publication(
        _publication("no-op", release_status="success"),
        issues,
        tmp_path,
        "run",
        secrets=("secret-value",),
    )

    assert result.workflow_status == "success"
    assert issues.recovery_bodies
    assert not issues.failure_bodies


def test_release_failure_keeps_published_sha_and_owned_issue_open(
    tmp_path: Path,
) -> None:
    issues = RecordingIssues(IssueResult("updated", 4))
    outcome = replace(
        _publication("published"),
        stage="release",
        detail="asset upload failed",
        release_status="failed",
        release_revision=None,
        pending_revision=5,
    )

    result = finalize_publication(outcome, issues, tmp_path, "run")

    assert result.workflow_status == "failed"
    assert result.publication_status == "published"
    assert result.release_status == "failed"
    assert result.pending_revision == 5
    assert issues.failure_bodies and not issues.recovery_bodies
    assert "Published SHA: published-sha" in issues.failure_bodies[0]
    assert "Release synchronization: failed" in issues.failure_bodies[0]
    persisted = json.loads((tmp_path / "orchestration-result.json").read_text())
    assert persisted["published_sha"] == "published-sha"
    assert persisted["release_status"] == "failed"
    assert persisted["pending_revision"] == 5


def test_setup_failure_entrypoint_needs_no_project_runtime(tmp_path: Path) -> None:
    issues = RecordingIssues()

    result = finalize_setup_failure(
        issues,
        tmp_path,
        run_url="run",
        stage="setup-python",
        detail=RuntimeError("setup failed with setup-secret"),
        base_sha="base",
        secrets=("setup-secret",),
    )

    assert result.workflow_status == "failed"
    assert result.publication_status == "failed"
    assert "setup-secret" not in result.summary + issues.failure_bodies[0]
    for module in ("scripts/nightly_issues.py", "scripts/nightly_reporting.py"):
        ast.parse(Path(module).read_text(), feature_version=(3, 10))


def test_candidate_structural_report_is_labeled_without_live_claims(
    tmp_path: Path,
) -> None:
    outcome = _publication()
    offline = b'{"mode":"offline","status":"success","complete":true}'
    outcome = replace(
        outcome,
        attempts=(
            replace(
                outcome.attempts[0],
                stages=(Stage("candidate-verify", "success"),),
                verify_report=offline,
            ),
        ),
    )

    result = finalize_publication(outcome, RecordingIssues(), tmp_path, "run")

    document = json.loads((tmp_path / "orchestration-result.json").read_text())
    assert document["attempts"][0]["verify_mode"] == "offline"
    assert document["attempts"][0]["verify_phase"] == "candidate"
    assert document["attempts"][0]["candidate_structural_report"] == "available"
    assert (
        "candidate structural/offline verification report available" in result.summary
    )
    assert "live verification" not in result.summary
    assert json.loads((tmp_path / "attempt-1-verify.json").read_text()) == json.loads(
        offline
    )


def test_retained_prebuild_evidence_is_not_labeled_as_candidate_evidence(
    tmp_path: Path,
) -> None:
    offline = b'{"mode":"offline","status":"success","complete":true}'
    outcome = _publication()
    outcome = replace(
        outcome,
        attempts=(
            replace(
                outcome.attempts[0],
                stages=(Stage("offline-verify", "success"), Stage("build", "failed")),
                verify_report=offline,
            ),
        ),
    )

    result = finalize_publication(outcome, RecordingIssues(), tmp_path, "run")

    document = json.loads((tmp_path / "orchestration-result.json").read_text())
    assert document["attempts"][0]["verify_phase"] == "pre-build"
    assert document["attempts"][0]["candidate_structural_report"] == "unavailable"
    assert "pre-build offline verification report available" in result.summary


@pytest.mark.parametrize("status", ["published", "no-op"])
def test_missing_release_status_cannot_authorize_recovery(
    tmp_path: Path, status: str
) -> None:
    outcome = {
        "status": status,
        "published_sha": "published-sha" if status == "published" else None,
        "base_sha": "base-sha",
    }
    issues = RecordingIssues()

    result = finalize_publication(outcome, issues, tmp_path, "run")

    assert result.workflow_status == "failed"
    assert result.publication_status == status
    assert result.release_status == "failed"
    assert issues.failure_bodies and not issues.recovery_bodies
    assert "Release synchronization: failed" in result.summary
    assert "Release synchronization: failed" in issues.failure_bodies[0]
    persisted = json.loads((tmp_path / "orchestration-result.json").read_text())
    assert persisted["release_status"] == result.release_status
    assert persisted["published_sha"] == outcome["published_sha"]
