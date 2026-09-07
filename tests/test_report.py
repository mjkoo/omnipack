from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from obtainium_pack.report import format_reports
from obtainium_pack.verify import INPUT_PATHS, run_verification, verifier_identity


def copy_inputs(root: Path) -> None:
    for relative in INPUT_PATHS.values():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(relative, target)


def test_verification_only_report_is_current_then_stale(tmp_path: Path) -> None:
    copy_inputs(tmp_path)
    run_verification(tmp_path)
    output = format_reports(tmp_path)
    assert "No build report recorded" in output
    assert "Evidence: current" in output
    assert "Mode: offline" in output
    (tmp_path / "config/overlay.json").write_text(
        '{"changed.app":{"name":"Changed"}}\n'
    )
    assert "Evidence: stale" in format_reports(tmp_path)


def test_build_only_legacy_failure_is_displayable(tmp_path: Path) -> None:
    path = tmp_path / ".build/report.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps({"status": "failed", "stage": "rendering", "error": "bad"})
    )
    output = format_reports(tmp_path)
    assert "Build report\nStatus: failed" in output
    assert "No standalone verification recorded" in output


@pytest.mark.parametrize(
    "value", ["not json", "[]", '{"schemaVersion":99,"status":"success"}']
)
def test_corrupt_or_unsupported_report_fails(tmp_path: Path, value: str) -> None:
    path = tmp_path / ".build/report.json"
    path.parent.mkdir()
    path.write_text(value)
    with pytest.raises(ValueError):
        format_reports(tmp_path)


def test_missing_both_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no build or verification"):
        format_reports(tmp_path)


def test_incomplete_verification_is_shown(tmp_path: Path) -> None:
    path = tmp_path / ".build/verify.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "verifier": verifier_identity(),
                "mode": "live",
                "startedAt": "2026-09-01T00:00:00+00:00",
                "completedAt": None,
                "complete": False,
                "status": "running",
                "inputs": {name: {"state": "missing"} for name in INPUT_PATHS},
                "errors": [],
                "warnings": [],
                "entries": [],
            }
        )
    )
    output = format_reports(tmp_path)
    assert "Status: running" in output
    assert "Complete: no" in output
    assert "Observed: 2026-09-01T00:00:00+00:00" in output


@pytest.mark.parametrize(
    "mutation",
    [
        {"inputs": {name: {"state": "bogus"} for name in INPUT_PATHS}},
        {
            "inputs": {
                name: {"state": "present", "sha256": "bad"} for name in INPUT_PATHS
            }
        },
        {
            "inputs": {
                name: {"state": "missing", "sha256": "a" * 64} for name in INPUT_PATHS
            }
        },
        {"inputs": {name: {"state": "unreadable"} for name in INPUT_PATHS}},
        {"completedAt": "yesterday"},
        {"startedAt": "then"},
        {"complete": False},
        {"status": "running"},
        {"status": "failed"},
        {"errors": [{"stage": "probe", "code": "oops"}]},
        {"warnings": [False]},
        {"entries": [{}]},
        {"entries": ["bad"]},
        {"schemaVersion": True},
    ],
)
def test_malformed_verification_records_are_rejected(
    tmp_path: Path, mutation: dict
) -> None:
    copy_inputs(tmp_path)
    report = run_verification(tmp_path)
    report.update(mutation)
    (tmp_path / ".build/verify.json").write_text(json.dumps(report))
    with pytest.raises(ValueError):
        format_reports(tmp_path)


def test_changed_verifier_identity_is_stale(tmp_path: Path) -> None:
    copy_inputs(tmp_path)
    report = run_verification(tmp_path)
    report["verifier"]["version"] = "future"
    (tmp_path / ".build/verify.json").write_text(json.dumps(report))
    assert "Evidence: stale" in format_reports(tmp_path)


@pytest.mark.parametrize("value", ["not json", "[]", '{"schemaVersion":99}'])
def test_corrupt_or_unsupported_verification_report_fails(
    tmp_path: Path, value: str
) -> None:
    path = tmp_path / ".build/verify.json"
    path.parent.mkdir()
    path.write_text(value)
    with pytest.raises(ValueError):
        format_reports(tmp_path)


def test_current_schema_build_only_is_displayable(tmp_path: Path) -> None:
    path = tmp_path / ".build/report.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "status": "success",
                "offlineVerification": {"status": "success", "findings": []},
            }
        )
    )
    assert "Offline verification: success" in format_reports(tmp_path)


@pytest.mark.parametrize(
    "mutation",
    [
        {
            "probes": [
                {
                    "name": "app.apk",
                    "url": "https://example.test/app.apk",
                    "success": "yes",
                    "response_url": "https://example.test/app.apk",
                    "status": 200,
                    "bytes_read": 1,
                }
            ]
        },
        {
            "resolution": {
                "raw_version": 42,
                "effective_version": "v1.2",
                "version_origin": "tag",
                "candidates": [],
                "selected": None,
                "inspected_count": 1,
                "window_limit": 100,
            }
        },
        {
            "resolution": {
                "raw_version": "v1.2",
                "effective_version": "v1.2",
                "version_origin": "tag",
                "candidates": [False],
                "selected": None,
                "inspected_count": 1,
                "window_limit": 100,
            }
        },
        {"errors": [{"code": "bad"}]},
        {"index": True},
        {"version_class": []},
    ],
)
def test_malformed_nested_live_entry_is_rejected(
    tmp_path: Path, mutation: dict
) -> None:
    copy_inputs(tmp_path)
    report = run_verification(tmp_path)
    entry = {
        "variant": "single",
        "entry_id": "app.example",
        "source": "GitHub",
        "index": 0,
        "version_class": "numeric",
        "resolution": None,
        "probes": [],
        "errors": [],
        "warnings": [],
    }
    entry.update(mutation)
    report["entries"] = [entry]
    (tmp_path / ".build/verify.json").write_text(json.dumps(report))
    with pytest.raises(ValueError):
        format_reports(tmp_path)
