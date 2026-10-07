from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from omnipack.report import format_reports, write_report
from omnipack.report_model import BuildStage
from omnipack.sources import IngestionReport
from omnipack.verify import (
    INPUT_PATHS,
    VERIFIER_VERSION,
    run_verification,
    verifier_identity,
)
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
    assert run_verification(tmp_path)["schemaVersion"] == 5
    output = format_reports(tmp_path)
    assert "No build report recorded" in output
    assert "Evidence: current" in output
    assert "Mode: offline (structural checks only)" in output
    (tmp_path / "config/overlay.json").write_text(
        '[{"url":"https://example.test/changed","patch":{"name":"Changed"}}]\n'
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
        {"schemaVersion": 4, "status": "success", "denylistRemovals": []},
    ],
    ids=["schemaless", "schema-4"],
)
def test_older_build_reports_require_regeneration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    document: dict[str, object],
) -> None:
    from omnipack.cli import main

    path = tmp_path / ".build/report.json"
    path.parent.mkdir()
    path.write_text(json.dumps(document))
    message = (
        f"unsupported build report schema {document.get('schemaVersion')!r}; "
        "regenerate with `pack build`"
    )
    with pytest.raises(ValueError, match=re.escape(message)):
        format_reports(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["report"]) == 1
    assert capsys.readouterr().err == f"report failed: {message}\n"


@pytest.mark.parametrize(
    "value", ["not json", "[]", '{"schemaVersion":99,"status":"success"}']
)
def test_corrupt_or_unsupported_report_fails(tmp_path: Path, value: str) -> None:
    path = tmp_path / ".build/report.json"
    path.parent.mkdir()
    path.write_text(value)
    with pytest.raises(ValueError):
        format_reports(tmp_path)


def test_missing_both_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from omnipack.cli import main

    with pytest.raises(ValueError, match="no build or verification"):
        format_reports(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["report"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "report failed: " in captured.err
    assert "no build or verification" in captured.err


@pytest.mark.parametrize(
    "mutation",
    [
        {"inputs": {name: {"state": "bogus"} for name in INPUT_PATHS}},
        {"inputs": {name: {"state": []} for name in INPUT_PATHS}},
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
        {"status": []},
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
    # Verification no longer limits source types, which changed its findings,
    # so evidence from an earlier verifier must read as stale.
    assert VERIFIER_VERSION == "4.0.0"
    assert report["schemaVersion"] == 5
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
    build_report(
        tmp_path,
        offlineVerification={
            "status": "success",
            "findings": [],
            "nonfatalFindings": [],
        },
    )
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
        (
            {
                "changes": {
                    "single": {"added": [], "removed": ["x"]},
                    "dual": {"added": [{"id": "x"}], "removed": []},
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
            {
                "offlineVerification": {
                    "status": [],
                    "findings": [],
                    "nonfatalFindings": [],
                }
            },
            "malformed build offline verification",
        ),
        (
            {
                "offlineVerification": {
                    "status": "success",
                    "findings": {},
                    "nonfatalFindings": [],
                }
            },
            "malformed build offline verification",
        ),
        (
            {
                "offlineVerification": {
                    "status": "failed",
                    "findings": [{}],
                    "nonfatalFindings": [],
                }
            },
            "malformed build offline verification",
        ),
        (
            {"offlineVerification": {"status": "success", "findings": []}},
            "malformed build offline verification",
        ),
        (
            {
                "offlineVerification": {
                    "status": "success",
                    "findings": [],
                    "nonfatalFindings": [{}],
                }
            },
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
        "repeatedIds",
        "singleOnlyFamilies",
        "sameRankTies",
        "uncategorizedFamilies",
        "staleCategoryAssignments",
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


def test_human_report_shows_winner_reason_and_considered_candidates(
    tmp_path: Path,
) -> None:
    from omnipack.merge import CompositionReport, ConsideredCandidate, FamilySelection
    from omnipack.model import Variant
    from omnipack.report import write_report
    from omnipack.report_model import SelectionReason
    from omnipack.sources import IngestionReport

    selection = FamilySelection(
        "app:shared",
        Variant.DUAL,
        "winner.pkg",
        "https://example.test/winner",
        "extras",
        "extras",
        SelectionReason.ORDINARY_FALLBACK,
        (
            ConsideredCandidate(
                "bboi",
                "bboi-standard-asset",
                "other.pkg",
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
        stage=BuildStage.COMPOSITION,
        error=ValueError("later family failed"),
    )
    output = format_reports(tmp_path)
    assert "Status: failed" in output
    assert (
        "Selection: dual app:shared -> id: winner.pkg; "
        "URL: https://example.test/winner; "
        "source: extras/extras; reason: ordinary-fallback"
    ) in output
    assert (
        "  Considered: id: other.pkg; URL: https://example.test/other; "
        "source: bboi/bboi-standard-asset"
    ) in output
    assert "lost:" not in output and "eligible:" not in output


WINNER = {
    "family": "app:x",
    "variant": "dual",
    "id": "winner",
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
            {key: value for key, value in WINNER.items() if key != "id"},
            "malformed build selection winner",
        ),
        (
            {
                **WINNER,
                "considered": [{"source": "rjny", "origin": "rjny-catalog", "id": "b"}],
            },
            "malformed build selection considered candidate",
        ),
    ],
    ids=["no-family", "considered-not-list", "no-id", "considered-no-url"],
)
def test_malformed_selection_records_are_rejected(
    tmp_path: Path, selection: dict[str, object], message: str
) -> None:
    build_report(tmp_path, selections=[selection])
    with pytest.raises(ValueError, match=message):
        format_reports(tmp_path)


def selector(i: int) -> dict[str, str]:
    return {
        "source": "rjny",
        "origin": "rjny-catalog",
        "id": f"tied.{i}",
        "url": f"example.test/tied/{i}",
    }


@pytest.mark.parametrize("failed", [False, True])
def test_recorded_build_diagnostics_are_displayed_in_full(
    tmp_path: Path, failed: bool
) -> None:
    # The writer's document shape, built literally so the lists can be long.
    document = {
        "schemaVersion": 5,
        "status": "failed" if failed else "success",
        "changes": {
            variant: {
                direction: [
                    {
                        "id": f"{variant}.{direction}.{i}",
                        "url": f"example.test/{direction}/{i}",
                    }
                    for i in range(40)
                ]
                for direction in ("added", "removed")
            }
            for variant in ("single", "dual")
        },
        "denylistRemovals": [
            {
                "url": f"example.test/denied/{i}",
                "reason": f"excluded {i}",
                "families": [f"app:a{i}", f"example.test/denied/{i}"],
            }
            for i in range(40)
        ],
        "staleExclusions": [
            {"url": f"example.test/stale/{i}", "reason": f"unmatched {i}"}
            for i in range(40)
        ],
        "sourceAdmissions": [
            {
                "source": "codm",
                "url": f"https://example.test/{i}",
                "id": f"committed.{i}",
            }
            for i in range(40)
        ],
        "selections": [WINNER],
        "repeatedIds": [
            {
                "variant": "single",
                "id": f"repeated.{i}",
                "entries": [
                    {"family": f"app:r{i}", "url": f"https://example.test/r{i}"},
                    {"family": "example.test/s", "url": "https://example.test/s"},
                ],
            }
            for i in range(40)
        ],
        "singleOnlyFamilies": [
            {"family": f"app:s{i}", "id": f"single.{i}", "url": f"https://x.test/{i}"}
            for i in range(40)
        ],
        "sameRankTies": [
            {
                "family": f"example.test/tie/{i}",
                "variant": "dual",
                "tied": [selector(i), selector(i + 100)],
                "winner": selector(i),
            }
            for i in range(40)
        ],
        "uncategorizedFamilies": [
            {"family": f"example.test/bare/{i}", "variants": ["single", "dual"]}
            for i in range(40)
        ],
        "staleCategoryAssignments": [f"app:gone-{i}" for i in range(40)],
        "offlineVerification": {
            "status": "not-run",
            "findings": [],
            "nonfatalFindings": [],
        },
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
                    f"{prefix}: {variant} {direction}: {variant}.{direction}.{i}; "
                    f"URL: example.test/{direction}/{i}\n"
                ) in output
    for i in range(40):
        assert (
            f"Exclusion: example.test/denied/{i}; families: app:a{i}, "
            f"example.test/denied/{i}; reason: excluded {i}\n"
        ) in output
        assert (
            f"Stale exclusion: example.test/stale/{i}; reason: unmatched {i}\n"
            in output
        )
        assert (
            f"Repeated package id: single repeated.{i}; entries: app:r{i} at "
            f"https://example.test/r{i}; example.test/s at https://example.test/s\n"
        ) in output
        assert (
            f"Single-only family: app:s{i}; id: single.{i}; URL: https://x.test/{i}\n"
            in output
        )
        assert (
            f"Same-rank tie: dual example.test/tie/{i}; tied: "
            f"rjny/rjny-catalog tied.{i} at example.test/tied/{i} | "
            f"rjny/rjny-catalog tied.{i + 100} at example.test/tied/{i + 100}; "
            f"winner: rjny/rjny-catalog tied.{i} at example.test/tied/{i}\n"
        ) in output
        assert (
            f"Admission: codm; URL: https://example.test/{i}; committed id: committed.{i}\n"
            in output
        )
        assert (
            f"Uncategorized: example.test/bare/{i}; variants: single, dual\n" in output
        )
        assert f"Stale category assignment: app:gone-{i}\n" in output
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


def only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    **fields: object,
) -> str:
    """Display, through `pack report`, a successful build report holding one
    kind of diagnostic.
    """
    from omnipack.cli import main

    changes = {variant: {"added": [], "removed": []} for variant in ("single", "dual")}
    document = build_report(tmp_path, changes=changes)
    (tmp_path / ".build/report.json").write_text(json.dumps({**document, **fields}))
    monkeypatch.chdir(tmp_path)
    assert main(["report"]) == 0
    return capsys.readouterr().out


def test_a_repeated_package_id_alone_is_displayed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = only(
        tmp_path,
        monkeypatch,
        capsys,
        repeatedIds=[
            {
                "variant": "dual",
                "id": "shared.pkg",
                "entries": [
                    {"family": "github.com/a/app", "url": "https://github.com/a/app"},
                    {"family": "app:b", "url": "https://github.com/b/app"},
                ],
            }
        ],
    )
    assert output.startswith(
        "Build report\nStatus: success\n"
        "Repeated package id: dual shared.pkg; entries: github.com/a/app at "
        "https://github.com/a/app; app:b at https://github.com/b/app\n"
        "Offline verification: not-run\n"
    )


def test_a_single_only_family_alone_is_displayed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = only(
        tmp_path,
        monkeypatch,
        capsys,
        singleOnlyFamilies=[
            {"family": "app:x", "id": "x.pkg", "url": "https://github.com/o/x"}
        ],
    )
    assert output.startswith(
        "Build report\nStatus: success\n"
        "Single-only family: app:x; id: x.pkg; URL: https://github.com/o/x\n"
        "Offline verification: not-run\n"
    )


def test_a_same_rank_tie_alone_is_displayed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = only(
        tmp_path,
        monkeypatch,
        capsys,
        sameRankTies=[
            {
                "family": "example.test/tie/1",
                "variant": "single",
                "tied": [selector(1), selector(2)],
                "winner": selector(2),
            }
        ],
    )
    assert output.startswith(
        "Build report\nStatus: success\n"
        "Same-rank tie: single example.test/tie/1; tied: rjny/rjny-catalog tied.1 "
        "at example.test/tied/1 | rjny/rjny-catalog tied.2 at example.test/tied/2; "
        "winner: rjny/rjny-catalog tied.2 at example.test/tied/2\n"
        "Offline verification: not-run\n"
    )


def test_a_change_of_url_alone_shows_both_urls(tmp_path: Path) -> None:
    from omnipack.merge import CompositionReport, CompositionResult
    from omnipack.model import Variant
    from omnipack.overlay import ComposedApp

    def entry(url: str) -> ComposedApp:
        return ComposedApp("app:x", {"id": "same.pkg", "url": url})

    moved = CompositionResult(
        {Variant.SINGLE: [entry("https://github.com/New/App")], Variant.DUAL: []},
        CompositionReport(),
    )
    write_report(
        tmp_path,
        {Variant.SINGLE: {("same.pkg", "github.com/old/app")}},
        moved,
        IngestionReport(),
    )
    recorded = json.loads((tmp_path / ".build/report.json").read_text())
    assert recorded["changes"]["single"] == {
        "added": [{"id": "same.pkg", "url": "github.com/new/app"}],
        "removed": [{"id": "same.pkg", "url": "github.com/old/app"}],
    }
    output = format_reports(tmp_path)
    assert "Change: single added: same.pkg; URL: github.com/new/app\n" in output
    assert "Change: single removed: same.pkg; URL: github.com/old/app\n" in output


def test_nonfatal_findings_are_displayed_from_both_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from omnipack.cli import main

    finding = {
        "stage": "composition",
        "code": "single_only_coverage",
        "message": "family label 'app:x' ('x' at 'github.com/o/x') has no dual",
        "variant": "single",
        "entry_id": "x",
    }
    repeated = {
        "stage": "composition",
        "code": "repeated_package_id",
        "message": "package id 'p' is carried by more than one entry",
        "variant": "dual",
        "entry_id": "p",
    }
    build_report(
        tmp_path,
        offlineVerification={
            "status": "success",
            "findings": [],
            "nonfatalFindings": [finding, repeated],
        },
    )
    write_verification_report(tmp_path, nonfatalFindings=[finding, repeated])
    output = format_reports(tmp_path)
    for value in (finding, repeated):
        line = (
            f"Nonfatal finding: [{value['variant']} / {value['entry_id']}] "
            f"{value['message']}\n"
        )
        assert output.count(line) == 2
    assert "Status: success" in output
    monkeypatch.chdir(tmp_path)
    assert main(["report"]) == 0
    assert capsys.readouterr().out == output


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


SELECTOR = {"source": "rjny", "origin": "rjny-catalog", "id": "x", "url": "x.test/a"}


@pytest.mark.parametrize(
    "field,record",
    [
        ("denylistRemovals", {"url": "x.test/a", "reason": "r"}),
        ("denylistRemovals", {"url": "x.test/a", "reason": "r", "families": []}),
        ("denylistRemovals", {"id": "denied", "reason": "r", "families": ["a"]}),
        ("staleExclusions", {"url": "x.test/a", "reason": 7}),
        ("staleExclusions", {"id": "stale", "reason": "r"}),
        ("repeatedIds", {"variant": "single", "id": "x", "entries": []}),
        ("repeatedIds", {"variant": "single", "id": "x", "entries": [{"url": "u"}]}),
        (
            "repeatedIds",
            {
                "variant": "bogus",
                "id": "x",
                "entries": [{"family": "app:x", "url": "x.test/a"}],
            },
        ),
        ("singleOnlyFamilies", {"family": "app:x", "id": "x"}),
        (
            "selections",
            {
                "family": "app:x",
                "variant": "single",
                **SELECTOR,
                "reason": "bogus",
                "considered": [],
            },
        ),
        (
            "sameRankTies",
            {
                "family": "app:x",
                "variant": "bogus",
                "tied": [SELECTOR],
                "winner": SELECTOR,
            },
        ),
        ("sameRankTies", {"family": "app:x", "variant": "single", "tied": []}),
        (
            "sameRankTies",
            {
                "family": "app:x",
                "variant": "single",
                "tied": [{"source": "rjny"}],
                "winner": {"source": "rjny"},
            },
        ),
        (
            "sourceAdmissions",
            {"source": "codm", "url": "https://example.test"},
        ),
        ("uncategorizedFamilies", {"family": "app:x"}),
        ("uncategorizedFamilies", {"family": "app:x", "variants": []}),
        ("uncategorizedFamilies", {"family": "app:x", "variants": [1]}),
        ("uncategorizedFamilies", {"family": 7, "variants": ["single"]}),
        ("uncategorizedFamilies", {"family": "app:x", "variants": ["bogus"]}),
        ("uncategorizedFamilies", "app:x"),
        ("staleCategoryAssignments", 7),
    ],
)
def test_malformed_diagnostic_elements_raise_report_format_error(
    tmp_path: Path, field: str, record: object
) -> None:
    from omnipack.report import ReportFormatError

    fields: dict[str, Any] = {field: [record]}
    build_report(tmp_path, **fields)
    with pytest.raises(ReportFormatError, match="malformed build"):
        format_reports(tmp_path)


def test_stale_category_assignments_must_be_a_list(tmp_path: Path) -> None:
    from omnipack.report import ReportFormatError

    build_report(tmp_path, staleCategoryAssignments="app:x")
    with pytest.raises(ReportFormatError, match="staleCategoryAssignments"):
        format_reports(tmp_path)


def test_category_lists_alone_are_displayed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from omnipack.cli import main

    build_report(
        tmp_path,
        changes={
            variant: {"added": [], "removed": []} for variant in ("single", "dual")
        },
        uncategorizedFamilies=[{"family": "example.test/bare", "variants": ["dual"]}],
        staleCategoryAssignments=["app:gone"],
    )
    monkeypatch.chdir(tmp_path)
    assert main(["report"]) == 0
    assert capsys.readouterr().out == (
        "Build report\nStatus: success\n"
        "Uncategorized: example.test/bare; variants: dual\n"
        "Stale category assignment: app:gone\n"
        "Offline verification: not-run\n\n"
        "Verification report\nNo standalone verification recorded\n"
    )


def test_removed_verification_state_is_rejected(tmp_path: Path) -> None:
    write_verification_report(tmp_path, complete=True)
    with pytest.raises(ValueError, match="malformed verification report"):
        format_reports(tmp_path)


def test_previous_verification_schema_requires_regeneration(tmp_path: Path) -> None:
    schema = 4
    report = write_verification_report(tmp_path, schemaVersion=schema)
    del report["nonfatalFindings"]
    (tmp_path / ".build/verify.json").write_text(json.dumps(report))
    with pytest.raises(
        ValueError,
        match=rf"unsupported verification report schema {schema}; "
        r"regenerate with `pack verify`",
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
