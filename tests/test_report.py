from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from omnipack.report import format_reports, write_report
from omnipack.sources import IngestionReport
from omnipack.verify import INPUT_PATHS, run_verification, verifier_identity
from tests.verification_support import (
    write_verification_inputs as copy_inputs,
)
from tests.verification_support import (
    write_verification_report,
)


def build_report(
    root: Path, *, drop: tuple[str, ...] = (), **fields: object
) -> dict[str, Any]:
    """Write a writer-shaped build report with fields replaced or dropped."""
    write_report(root, {}, None, IngestionReport())
    path = root / ".build/report.json"
    document = {
        key: value
        for key, value in json.loads(path.read_text()).items()
        if key not in drop
    }
    document.update(fields)
    path.write_text(json.dumps(document))
    return document


def test_verification_only_report_is_current_then_stale(tmp_path: Path) -> None:
    copy_inputs(tmp_path)
    assert run_verification(tmp_path)["schemaVersion"] == 4
    output = format_reports(tmp_path)
    assert "No build report recorded" in output
    assert "Evidence: current" in output
    assert "Mode: offline (structural checks only)" in output
    (tmp_path / "config/overlay.json").write_text(
        '{"changed.app":{"name":"Changed"}}\n'
    )
    assert "Evidence: stale" in format_reports(tmp_path)


def test_build_only_failure_is_displayable(tmp_path: Path) -> None:
    build_report(tmp_path, status="failed", stage="rendering", error="bad")
    output = format_reports(tmp_path)
    assert "Build report\nStatus: failed" in output
    assert "Stage: rendering" in output and "Error: bad" in output
    assert "No standalone verification recorded" in output


@pytest.mark.parametrize(
    "document",
    [
        {"status": "success"},
        {"schemaVersion": 1, "status": "success"},
        {"schemaVersion": 2, "status": "success", "displacements": []},
    ],
    ids=["schemaless", "schema-1", "schema-2"],
)
def test_older_build_reports_require_regeneration(
    tmp_path: Path,
    document: dict[str, object],
) -> None:
    path = tmp_path / ".build/report.json"
    path.parent.mkdir()
    path.write_text(json.dumps(document))
    with pytest.raises(
        ValueError,
        match=(
            rf"unsupported build report schema {document.get('schemaVersion')!r}; "
            r"regenerate with `pack build`"
        ),
    ):
        format_reports(tmp_path)


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
        {"completedAt": None},
        {"completedAt": "2026-09-01T00:00:01"},
        {"startedAt": "then"},
        {"complete": False},
        {"status": "running"},
        {"status": "failed"},
        {"errors": [{"stage": "probe", "code": "oops"}]},
        {"unexpected": []},
        {"schemaVersion": True},
    ],
)
def test_malformed_verification_records_are_rejected(
    tmp_path: Path, mutation: dict
) -> None:
    write_verification_report(tmp_path, **mutation)
    with pytest.raises(ValueError):
        format_reports(tmp_path)


def test_changed_verifier_identity_is_stale(tmp_path: Path) -> None:
    copy_inputs(tmp_path)
    report = run_verification(tmp_path)
    assert report["verifier"] == verifier_identity()
    assert report["schemaVersion"] == 4
    report["verifier"]["version"] = "different-test-verifier"
    (tmp_path / ".build/verify.json").write_text(json.dumps(report))
    assert "Evidence: stale" in format_reports(tmp_path)


def test_unsupported_verification_schema_requires_regeneration(tmp_path: Path) -> None:
    write_verification_report(tmp_path, schemaVersion=99)
    with pytest.raises(
        ValueError,
        match=r"unsupported verification report schema 99; regenerate with `pack verify`",
    ):
        format_reports(tmp_path)


@pytest.mark.parametrize("value", ["not json", "[]"])
def test_corrupt_verification_report_fails(tmp_path: Path, value: str) -> None:
    path = tmp_path / ".build/verify.json"
    path.parent.mkdir()
    path.write_text(value)
    with pytest.raises(ValueError):
        format_reports(tmp_path)


def test_current_schema_build_only_is_displayable(tmp_path: Path) -> None:
    build_report(tmp_path, offlineVerification={"status": "success", "findings": []})
    assert "Offline verification: success" in format_reports(tmp_path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"schemaVersion": True}, "unsupported build report schema True"),
        ({"status": []}, "malformed build report: status is required"),
        (
            {"status": "failed", "stage": "rendering", "error": []},
            "malformed build report diagnostics",
        ),
        (
            {"status": "failed", "stage": "rendering"},
            "malformed build report fields",
        ),
        (
            {"changes": {"single": {"added": []}}},
            "malformed build package changes",
        ),
        (
            {
                "changes": {
                    "single": {"added": [], "removed": [1]},
                    "dual": {"added": [], "removed": []},
                }
            },
            "malformed build package changes",
        ),
        ({"sourceAdmissions": None}, "malformed build report sourceAdmissions"),
        (
            {"sourceAdmissions": ["admitted"]},
            "malformed build report sourceAdmissions",
        ),
        ({"offlineVerification": []}, "malformed build offline verification"),
        (
            {"offlineVerification": {"status": [], "findings": []}},
            "malformed build offline verification",
        ),
        (
            {"offlineVerification": {"status": "success", "findings": {}}},
            "malformed build offline verification",
        ),
        (
            {"offlineVerification": {"status": "failed", "findings": [{}]}},
            "malformed build offline verification",
        ),
    ],
)
def test_malformed_build_report_records_are_rejected(
    tmp_path: Path, mutation: dict[str, Any], message: str
) -> None:
    build_report(tmp_path, **mutation)
    with pytest.raises(ValueError, match=message):
        format_reports(tmp_path)


def test_malformed_build_report_is_concise_cli_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from omnipack.cli import main

    document = build_report(tmp_path, sourceAdmissions=None)
    monkeypatch.chdir(tmp_path)
    assert main(["report"]) == 1
    assert "Traceback" not in capsys.readouterr().err
    assert json.loads((tmp_path / ".build/report.json").read_text()) == document


@pytest.mark.parametrize(
    "field",
    [
        "changes",
        "sourceAdmissions",
        "denylistRemovals",
        "staleExclusions",
        "selections",
        "offlineVerification",
    ],
)
def test_build_report_missing_a_field_is_rejected(tmp_path: Path, field: str) -> None:
    build_report(tmp_path, drop=(field,))
    with pytest.raises(ValueError, match="malformed build report fields"):
        format_reports(tmp_path)


def test_findings_display_location_and_field(tmp_path, monkeypatch, capsys) -> None:
    from omnipack.cli import main

    write_verification_report(
        tmp_path,
        status="failed",
        errors=[
            {
                "stage": "offline",
                "code": "invalid",
                "message": "bad field",
                "variant": "dual",
                "index": 4,
                "field": "url",
            }
        ],
    )
    path = tmp_path / ".build/verify.json"
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


WINNER = {
    "family": "app:x",
    "variant": "dual",
    "original_id": "winner",
    "effective_id": "winner",
    "url": "https://example.test/winner",
    "source": "extras",
    "origin": "extras",
    "reason": "source",
    "considered": [],
}


@pytest.mark.parametrize(
    ("selection", "message"),
    [
        ({**WINNER, "family": None}, "malformed build family selection"),
        ({**WINNER, "considered": {}}, "malformed build family selection"),
        (
            {key: value for key, value in WINNER.items() if key != "original_id"},
            "malformed build selection winner",
        ),
        (
            {
                **WINNER,
                "considered": [
                    {"source": "rjny", "origin": "rjny-catalog", "original_id": "b"}
                ],
            },
            "malformed build selection considered candidate",
        ),
    ],
    ids=["no-family", "considered-not-list", "no-original-id", "considered-no-url"],
)
def test_malformed_selection_records_are_rejected(
    tmp_path: Path, selection: dict[str, object], message: str
) -> None:
    build_report(tmp_path, selections=[selection])
    with pytest.raises(ValueError, match=message):
        format_reports(tmp_path)


@pytest.mark.parametrize("failed", [False, True])
def test_recorded_build_diagnostics_are_displayed_in_full(
    tmp_path: Path, failed: bool
) -> None:
    # The writer's document shape, built literally so the lists can be long.
    document = {
        "schemaVersion": 3,
        "status": "failed" if failed else "success",
        "changes": {
            variant: {
                direction: [f"{variant}.{direction}.{i}" for i in range(40)]
                for direction in ("added", "removed")
            }
            for variant in ("single", "dual")
        },
        "denylistRemovals": [
            {
                "id": f"denied.{i}",
                "variant": "dual",
                "family": f"family:{i}",
                "reason": f"excluded {i}",
            }
            for i in range(40)
        ],
        "staleExclusions": [
            {"id": f"stale.{i}", "reason": f"unmatched {i}"} for i in range(40)
        ],
        "sourceAdmissions": [
            {
                "source": "codm2000",
                "url": f"https://example.test/{i}",
                "kind": "apk",
                "id": f"committed.{i}",
            }
            for i in range(40)
        ],
        "selections": [WINNER],
        "offlineVerification": {"status": "not-run", "findings": []},
    }
    if failed:
        document.update(stage="rendering", error="render failed")
    path = tmp_path / ".build/report.json"
    path.parent.mkdir()
    path.write_text(json.dumps(document))
    before = path.read_bytes()
    output = format_reports(tmp_path)
    prefix = "Candidate (not published)" if failed else "Change"
    for variant in ("single", "dual"):
        for direction in ("added", "removed"):
            for i in range(40):
                assert (
                    f"{prefix}: {variant} {direction}: {variant}.{direction}.{i}\n"
                    in output
                )
    for i in range(40):
        assert (
            f"Exclusion: dual denied.{i}; family: family:{i}; reason: excluded {i}\n"
            in output
        )
        assert f"Stale exclusion: stale.{i}; reason: unmatched {i}\n" in output
        assert (
            f"Admission: codm2000; URL: https://example.test/{i}; kind: apk; committed id: committed.{i}\n"
            in output
        )
    assert (
        output.index("Selection:")
        < output.index(prefix + ":")
        < output.index("Offline verification:")
    )
    if failed:
        assert "Change:" not in output
        assert (
            output.index("Admission:") < output.index("Stage:") < output.index("Error:")
        )
    assert path.read_bytes() == before


@pytest.mark.parametrize("unavailable", [False, True])
def test_empty_and_unavailable_comparisons_are_distinct_cli_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    unavailable: bool,
) -> None:
    from omnipack.cli import main

    build_report(
        tmp_path,
        changes=None
        if unavailable
        else {variant: {"added": [], "removed": []} for variant in ("single", "dual")},
    )
    monkeypatch.chdir(tmp_path)
    assert main(["report"]) == 0
    output = capsys.readouterr().out
    expected = "Build report\nStatus: success\n"
    if unavailable:
        expected += "Candidate comparison: unavailable\n"
    expected += "Offline verification: not-run\n\nVerification report\nNo standalone verification recorded\n"
    assert output == expected


@pytest.mark.parametrize(
    "field,record",
    [
        ("denylistRemovals", {"id": "denied", "variant": "dual", "family": "family"}),
        ("staleExclusions", {"id": "stale", "reason": 7}),
        (
            "sourceAdmissions",
            {"source": "codm2000", "url": "https://example.test", "kind": "apk"},
        ),
    ],
)
def test_malformed_diagnostic_elements_raise_report_format_error(
    tmp_path: Path, field: str, record: dict[str, object]
) -> None:
    from omnipack.report import ReportFormatError

    fields: dict[str, Any] = {field: [record]}
    build_report(tmp_path, **fields)
    with pytest.raises(ReportFormatError, match="malformed build"):
        format_reports(tmp_path)


@pytest.mark.parametrize(
    "mutation",
    [{"complete": True}, {"complete": False, "status": "running", "completedAt": None}],
)
def test_removed_verification_state_is_rejected(tmp_path: Path, mutation: dict) -> None:
    write_verification_report(tmp_path, **mutation)
    with pytest.raises(ValueError, match="malformed verification report"):
        format_reports(tmp_path)


def test_previous_verification_schema_requires_regeneration(tmp_path: Path) -> None:
    write_verification_report(tmp_path, schemaVersion=3, complete=True)
    with pytest.raises(
        ValueError,
        match=r"unsupported verification report schema 3; regenerate with `pack verify`",
    ):
        format_reports(tmp_path)


def test_verification_display_has_no_completion_flag(tmp_path: Path) -> None:
    copy_inputs(tmp_path)
    run_verification(tmp_path)
    output = format_reports(tmp_path)
    assert "Evidence: current" in output
    assert "Complete:" not in output


def test_verification_report_requires_completion_timestamp(tmp_path: Path) -> None:
    report = write_verification_report(tmp_path)
    del report["completedAt"]
    (tmp_path / ".build/verify.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="malformed verification report"):
        format_reports(tmp_path)
