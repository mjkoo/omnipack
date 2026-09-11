from __future__ import annotations

import io
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.nightly_reporting import (
    BUILD_REPORT_NAME,
    RESULT_NAME,
    VERIFY_REPORT_NAME,
    log_main_confirmation,
    report_publication,
    write_diagnostics,
)


@dataclass(frozen=True)
class Stage:
    stage: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class Publication:
    status: str = "failed"
    base_sha: str | None = "base-secret"
    published_sha: str | None = None
    stage: str = "build"
    detail: str = "token=secret-value\n::error::hostile <script>"
    stages: tuple[Stage, ...] = (Stage("build", "failed", "secret-value"),)
    build_report: bytes | None = b'{"message":"Bearer secret-value"}'
    verify_report: bytes | None = None
    candidate_sha: str | None = None
    started_at: datetime | None = datetime(2026, 9, 8, 10, tzinfo=UTC)
    finished_at: datetime | None = datetime(2026, 9, 8, 11, tzinfo=UTC)
    release_status: str = "not-run"
    release_revision: int | None = None
    pending_revision: int | None = None


def test_diagnostics_are_flat_redacted_and_write_only_available_reports(
    tmp_path: Path,
) -> None:
    written = write_diagnostics(
        tmp_path,
        Publication(),
        "https://github.example/runs/42?token=secret-value",
        secrets=("secret-value",),
    )

    assert [path.name for path in written] == [RESULT_NAME, BUILD_REPORT_NAME]
    combined = "".join(path.read_text() for path in written)
    assert "secret-value" not in combined
    assert "REDACTED" in combined
    result = json.loads((tmp_path / RESULT_NAME).read_text())
    assert "attempts" not in result
    assert "diagnostic_upload_status" not in result
    assert result["started_at"] == "2026-09-08T10:00:00+00:00"
    assert not (tmp_path / VERIFY_REPORT_NAME).exists()


def test_summary_redacts_and_escapes_source_text_as_markdown_data(
    tmp_path: Path,
) -> None:
    result = report_publication(
        Publication(), tmp_path, "run", secrets=("secret-value",)
    )

    assert result.workflow_status == "failed"
    assert "secret-value" not in result.summary
    assert "&lt;script&gt;" in result.summary
    assert "::error::" in result.summary
    assert "Diagnostic upload" not in result.summary


def test_release_failure_keeps_confirmed_main_and_pending_revision(
    tmp_path: Path,
) -> None:
    outcome = replace(
        Publication(),
        status="published",
        published_sha="published-sha",
        stage="release",
        detail="asset upload failed",
        release_status="failed",
        pending_revision=5,
    )

    result = report_publication(outcome, tmp_path, "run")

    assert result.workflow_status == "failed"
    assert result.publication_status == "published"
    assert result.pending_revision == 5
    persisted = json.loads((tmp_path / RESULT_NAME).read_text())
    assert persisted["published_sha"] == "published-sha"
    assert persisted["release_status"] == "failed"


def test_main_confirmation_is_one_redacted_json_line_and_flushes() -> None:
    class RecordingStream(io.StringIO):
        flushed = False

        def flush(self) -> None:
            self.flushed = True
            super().flush()

    stream = RecordingStream()
    outcome = replace(
        Publication(), status="published", published_sha="sha-secret-value"
    )

    log_main_confirmation(outcome, secrets=("secret-value",), stream=stream)

    assert stream.flushed
    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "main_publication": "published",
        "sha": "sha-REDACTED",
    }


def test_invalid_report_text_is_redacted_and_json_encoded(tmp_path: Path) -> None:
    outcome = replace(Publication(), build_report=b"line one\n::warning::secret-value")

    write_diagnostics(tmp_path, outcome, "run", secrets=("secret-value",))

    document = json.loads((tmp_path / BUILD_REPORT_NAME).read_text())
    assert document["text"] == "line one\n::warning::REDACTED"


@pytest.mark.parametrize("status", ["failed", "uncertain"])
def test_push_summary_identifies_candidate_without_claiming_publication(
    tmp_path: Path, status: str
) -> None:
    outcome = replace(
        Publication(), status=status, stage="push", candidate_sha="candidate-sha"
    )

    result = report_publication(outcome, tmp_path, "run")

    assert "- Candidate SHA: candidate-sha" in result.summary
    assert "- Published SHA: unavailable" in result.summary
    assert f"- Result: {status}" in result.summary
    assert result.workflow_status == "failed"


def test_reused_diagnostic_directory_drops_prior_reports(tmp_path: Path) -> None:
    write_diagnostics(tmp_path, Publication(verify_report=b"{}"), "old-run")

    written = write_diagnostics(tmp_path, Publication(build_report=None), "current-run")

    assert [path.name for path in written] == [RESULT_NAME]
    assert not (tmp_path / BUILD_REPORT_NAME).exists()
    assert not (tmp_path / VERIFY_REPORT_NAME).exists()
    assert json.loads((tmp_path / RESULT_NAME).read_text())["run_url"] == "current-run"


def test_diagnostic_cleanup_attempts_all_reports_before_failing(tmp_path: Path) -> None:
    (tmp_path / BUILD_REPORT_NAME).mkdir()
    (tmp_path / VERIFY_REPORT_NAME).write_bytes(b'{"old": true}')
    (tmp_path / RESULT_NAME).write_bytes(b'{"old": true}')

    with pytest.raises(OSError):
        write_diagnostics(tmp_path, Publication(build_report=None), "current-run")

    assert not (tmp_path / VERIFY_REPORT_NAME).exists()
    assert not (tmp_path / RESULT_NAME).exists()
