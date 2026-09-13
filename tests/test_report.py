from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from omnipack.report import format_reports
from omnipack.verify import INPUT_PATHS, run_verification, verifier_identity
from tests.test_verify import historical_composition


def copy_inputs(root: Path) -> None:
    for relative in INPUT_PATHS.values():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative.name == "overlay.json":
            target.write_text("[]")
        elif relative.name == "composition.json" and relative.exists():
            target.write_text(historical_composition())
        elif relative.exists():
            shutil.copyfile(relative, target)
        elif relative.name == "composition.json":
            target.write_text('{"schemaVersion":1,"candidates":[],"pins":[]}')


def test_verification_only_report_is_current_then_stale(tmp_path: Path) -> None:
    copy_inputs(tmp_path)
    assert run_verification(tmp_path)["schemaVersion"] == 3
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
                "schemaVersion": 3,
                "verifier": verifier_identity(),
                "mode": "offline",
                "startedAt": "2026-09-01T00:00:00+00:00",
                "completedAt": None,
                "complete": False,
                "status": "running",
                "inputs": {name: {"state": "missing"} for name in INPUT_PATHS},
                "errors": [],
            }
        )
    )
    output = format_reports(tmp_path)
    assert "Status: running" in output
    assert "Complete: no" in output
    assert "Observed: 2026-09-01T00:00:00+00:00" in output


def test_structural_mode_is_explicit(tmp_path: Path) -> None:
    copy_inputs(tmp_path)
    report = run_verification(tmp_path)
    (tmp_path / ".build/verify.json").write_text(json.dumps(report))
    assert "Mode: offline (structural checks only)" in format_reports(tmp_path)


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
        {"warnings": []},
        {"entries": []},
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
    assert report["verifier"] == verifier_identity()
    assert report["schemaVersion"] == 3
    report["verifier"]["version"] = "different-test-verifier"
    (tmp_path / ".build/verify.json").write_text(json.dumps(report))
    assert "Evidence: stale" in format_reports(tmp_path)


def test_schema_2_verification_report_requires_regeneration(tmp_path: Path) -> None:
    copy_inputs(tmp_path)
    report = run_verification(tmp_path)
    inputs = dict(report["inputs"])
    inputs["common_overlay"] = inputs.pop("overlay")
    inputs["dual_overlay"] = inputs["settings"] = {"state": "missing"}
    report.update(schemaVersion=2, inputs=inputs)
    report["verifier"]["version"] = "1.0.0"
    (tmp_path / ".build/verify.json").write_text(json.dumps(report))
    with pytest.raises(
        ValueError,
        match=r"unsupported verification report schema 2; regenerate with `pack verify`",
    ):
        format_reports(tmp_path)


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
        {"schemaVersion": []},
        {"schemaVersion": {}},
        {"schemaVersion": True},
        {"schemaVersion": None},
        {"status": []},
        {"status": {}},
        {"offlineVerification": []},
        {"offlineVerification": None},
        {"offlineVerification": {"status": [], "findings": []}},
        {"offlineVerification": {"status": "success", "findings": {}}},
        {"offlineVerification": {"status": "failed", "findings": [{}]}},
        {"error": []},
        {"stage": {}},
    ],
)
def test_malformed_build_report_is_concise_cli_failure(
    tmp_path, monkeypatch, capsys, mutation
) -> None:
    from omnipack.cli import main

    path = tmp_path / ".build/report.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"status": "success", **mutation}))
    monkeypatch.chdir(tmp_path)
    assert main(["report"]) == 1
    assert "Traceback" not in capsys.readouterr().err
    assert json.loads(path.read_text()) == {"status": "success", **mutation}


def test_findings_display_location_field_and_effective_version(
    tmp_path, monkeypatch, capsys
) -> None:
    from omnipack.cli import main

    copy_inputs(tmp_path)
    report = run_verification(tmp_path)
    report["errors"] = [
        {
            "stage": "offline",
            "code": "invalid",
            "message": "bad field",
            "variant": "dual",
            "index": 4,
            "field": "url",
        }
    ]
    report["status"] = "failed"
    path = tmp_path / ".build/verify.json"
    path.write_text(json.dumps(report))
    before = path.read_bytes()

    def forbidden(*args, **kwargs):
        pytest.fail("report attempted network")

    monkeypatch.setattr("omnipack.http.HttpClient.get", forbidden)
    monkeypatch.chdir(tmp_path)
    assert main(["report"]) == 0
    output = capsys.readouterr().out
    assert "dual" in output and "index 4" in output and "url" in output
    assert path.read_bytes() == before


def test_human_report_shows_corrected_winner_reason_and_considered_candidates(
    tmp_path: Path,
) -> None:
    from omnipack.merge import CompositionReport, ConsideredCandidate, FamilySelection
    from omnipack.model import Variant
    from omnipack.report import write_report
    from omnipack.sources import IngestionReport

    selection = FamilySelection(
        "app:shared",
        Variant.DUAL,
        "manifest.wrong",
        "correct.pkg",
        "https://example.test/winner",
        "extras",
        "extras",
        "ordinary-fallback",
        (
            ConsideredCandidate(
                "bboi",
                "bboi-standard-asset",
                "old.manifest",
                "https://example.test/other",
            ),
        ),
    )
    write_report(
        tmp_path,
        {},
        None,
        IngestionReport(),
        composition_report=CompositionReport(selections=[selection]),
        stage="composition",
        error=ValueError("later family failed"),
    )
    output = format_reports(tmp_path)
    assert "Status: failed" in output
    assert (
        "Selection: dual app:shared -> original id: manifest.wrong; "
        "effective id: correct.pkg; URL: https://example.test/winner; "
        "source: extras/extras; reason: ordinary-fallback"
    ) in output
    assert (
        "  Considered: original id: old.manifest; URL: https://example.test/other; "
        "source: bboi/bboi-standard-asset"
    ) in output
    assert "lost:" not in output and "eligible:" not in output
