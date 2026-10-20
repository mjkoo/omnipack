"""Alert emitters fed by the real producers: step outputs, workflow bindings and
the reports the build and live check write.

Each test runs the producing script or writer, resolves the producing job's
emit-step environment from `nightly.yml` or `source-catalog.yml` the way
Actions would, then emits and reconciles, so a renamed output, binding or
report key fails here.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import get_args

import pytest

from omnipack.live_check import REPORT, check_live, write_live_report
from omnipack.merge import CompositionReport, StaleExclusion, UncategorizedFamily
from omnipack.model import Variant
from omnipack.report import write_report
from omnipack.report_model import Status
from omnipack.sources import IngestionReport
from scripts import alerts as alerts_module
from scripts import nightly as nightly_module
from scripts import nightly_write as write_module
from scripts.alerts import (
    LIVE_CHECK,
    NIGHTLY_PREPARE,
    NIGHTLY_PUBLISH,
    Owner,
    Producer,
    parse_findings,
    reconcile,
)
from scripts.workflow_support import SOURCE_NAMES, ReportStatus, StepOutcome
from tests.publication_support import (
    REPOSITORY,
    RUN_2,
    alert_gh,
    alert_issue,
    bare_remote,
    bundle,
    commit_as_bot,
    isolated_git_identity,
    issue_writes,
    prepare_environment,
    prepare_repository,
    push_gh,
    seed_repository,
    shallow_checkout,
)
from tests.publication_support import git as _git
from tests.test_live_check import Transport, client, entry, write_packs
from tests.test_nightly_prepare import ScriptedProcess
from tests.test_publication_workflows import (
    WORKFLOWS,
    emit_step,
    emitted_owner,
    is_emit,
    is_findings_upload,
    load,
)

pytestmark = pytest.mark.usefixtures(isolated_git_identity.__name__)

_EXPRESSION = re.compile(
    r"\$\{\{ (?:steps\.(?P<step>[\w-]+)\.(?:outputs\.(?P<output>\w+)|(?P<outcome>outcome))"
    r"|(?P<job>job\.status)) \}\}"
)


def _emit_step(workflow: str, job: str) -> dict:
    return emit_step(load(workflow)["jobs"][job]["steps"])


def _resolve(
    value: str,
    *,
    outputs: Mapping[str, Mapping[str, str]],
    outcomes: Mapping[str, str] | None = None,
    job_status: StepOutcome,
) -> str:
    """One binding as Actions evaluates it; an unset output reads as empty."""
    match = _EXPRESSION.fullmatch(value)
    assert match, value
    if match["job"]:
        return job_status
    if match["outcome"]:
        return (outcomes or {}).get(match["step"], "")
    return outputs.get(match["step"], {}).get(match["output"], "")


def _run_emit(
    monkeypatch: pytest.MonkeyPatch,
    step: dict,
    output: Path,
    *,
    outputs: Mapping[str, Mapping[str, str]],
    job_status: StepOutcome,
    outcomes: Mapping[str, str] | None = None,
    report: Path | None = None,
) -> None:
    """Run the step's emit command with its environment resolved."""
    for name, value in step["env"].items():
        resolved = _resolve(
            value, outputs=outputs, outcomes=outcomes, job_status=job_status
        )
        monkeypatch.setenv(name, resolved)
    words = shlex.split(step["run"])
    assert words[:4] == ["python3", "-m", "scripts.alerts", "emit"]
    extra = ["--report", str(report)] if report is not None else []
    assert alerts_module.main([*words[3:], "--output", str(output), *extra]) == 0


def _outputs(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines())


def _reconcile(owner: Owner, path: Path, result: StepOutcome, issues: list[dict]):
    gh = alert_gh(issues)
    reconcile(gh, [Producer(owner, path, result)], repository=REPOSITORY, url=RUN_2)
    return gh


def test_no_op_prepare_closes_a_stage_it_ran_and_leaves_one_it_did_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = prepare_repository(tmp_path)
    prepare_environment(monkeypatch, root, tmp_path)
    process = ScriptedProcess(root)
    monkeypatch.setattr(nightly_module, "PrepareSubprocess", lambda: process)
    assert nightly_module.main(["prepare"]) == 0
    findings = tmp_path / "findings.json"

    _run_emit(
        monkeypatch,
        _emit_step("nightly.yml", "prepare"),
        findings,
        outputs={"prepare": _outputs(tmp_path / "output.txt")},
        job_status="success",
    )
    gh = _reconcile(
        NIGHTLY_PREPARE,
        findings,
        "success",
        [
            alert_issue(1, "nightly/prepare/build"),
            alert_issue(2, "nightly/prepare/commit"),
        ],
    )

    assert issue_writes(gh) == [("close", "1")]


def test_push_refused_as_main_advanced_raises_nothing_and_leaves_its_issue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = seed_repository(tmp_path)
    base = _git(seed, "rev-parse", "HEAD")
    bare = bare_remote(seed, tmp_path)
    sha = commit_as_bot(seed, {"dist/single-screen.json": "changed\n"})
    bundle_path = bundle(seed, base, tmp_path / "candidate.bundle")
    _git(seed, "push", "-q", str(bare), "HEAD:main")
    write_side = shallow_checkout(tmp_path, bare, base)
    output = tmp_path / "push-output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("CANDIDATE_SHA", sha)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setattr(write_module, "SubprocessGhRunner", push_gh)
    monkeypatch.chdir(write_side)
    assert write_module.main(["push", "--bundle", str(bundle_path)]) == 1
    findings = tmp_path / "findings.json"

    # The release step does not run after a failed push.
    _run_emit(
        monkeypatch,
        _emit_step("nightly.yml", "publish"),
        findings,
        outputs={"push": _outputs(output)},
        job_status="failure",
    )
    parsed = parse_findings(NIGHTLY_PUBLISH, findings.read_text())
    gh = _reconcile(
        NIGHTLY_PUBLISH, findings, "failure", [alert_issue(1, "nightly/publish/push")]
    )

    assert parsed is not None
    assert parsed.findings == ()
    assert parsed.scope == ()
    assert issue_writes(gh) == []


def test_build_report_from_the_real_writer_raises_its_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_report(
        tmp_path,
        {},
        None,
        IngestionReport(),
        composition_report=CompositionReport(
            stale_exclusions=[StaleExclusion("example.test/stale", "gone")],
            uncategorized_families=[
                UncategorizedFamily("example.test/family", (Variant.SINGLE,))
            ],
            stale_category_assignments=["Some Key"],
        ),
    )
    findings = tmp_path / "findings.json"

    _run_emit(
        monkeypatch,
        _emit_step("nightly.yml", "prepare"),
        findings,
        report=tmp_path / ".build/report.json",
        outputs={"prepare": {"stage": "complete", "stages": "checkout,build"}},
        job_status="success",
    )
    parsed = parse_findings(NIGHTLY_PREPARE, findings.read_text())

    assert parsed is not None
    assert [finding.key for finding in parsed.findings] == [
        "build/uncategorized/example.test/family",
        "build/stale-denial/example.test/stale",
        "build/stale-category/Some%20Key",
    ]
    assert parsed.findings[0].details == (
        "Family: example.test/family",
        "Variants: single",
    )
    assert "build/" in parsed.scope


def test_live_check_report_from_the_real_writer_raises_gone_and_status_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gone, blocked = "https://github.com/a/gone", "https://github.com/a/blocked"
    write_packs(tmp_path, [entry(gone), entry(blocked)])
    report = check_live(tmp_path, http=client(Transport({gone: [404], blocked: [403]})))
    write_live_report(tmp_path, report)
    findings = tmp_path / "findings.json"

    _run_emit(
        monkeypatch,
        _emit_step("source-catalog.yml", "live-check"),
        findings,
        report=tmp_path / REPORT,
        outputs={},
        outcomes={"check": "failure"},
        job_status="failure",
    )
    parsed = parse_findings(LIVE_CHECK, findings.read_text())

    assert parsed is not None
    assert [(f.key, f.title) for f in parsed.findings] == [
        (f"live-check/gone/{gone}", f"Project URL is gone (HTTP 404): {gone}"),
        (f"live-check/status/{blocked}", f"Project URL answers HTTP 403: {blocked}"),
    ]


def test_alert_report_status_mirrors_the_report_status() -> None:
    assert set(get_args(ReportStatus)) == {status.value for status in Status}


def test_alert_docs_name_the_label_keys_jobs_and_artifacts_the_code_uses() -> None:
    docs = (Path(__file__).resolve().parents[1] / "docs/alerts.md").read_text()
    named = set(re.findall(r"`([^`]+)`", docs))

    assert alerts_module.LABEL in named
    for owner in alerts_module.OWNERS:
        assert owner.value in named
        prefixes = (
            owner.prefixes
            if owner.source is None
            else tuple(
                p.replace(f"{owner.source}/", "<source>/", 1) for p in owner.prefixes
            )
        )
        assert set(prefixes) <= named
    assert set(alerts_module.PREPARE_STAGE_SLUGS.values()) <= named
    assert {slug for slug, _ in alerts_module.CHECK_STEPS.values()} <= named
    slugs = {
        alerts_module.EARLY_FAILURE_SLUG,
        alerts_module.PROPOSAL_SLUG,
        *(step.slug for step in alerts_module.NIGHTLY_PUBLISH_STEPS),
        alerts_module.LIVE_READ.removeprefix(LIVE_CHECK.prefixes[0]),
    }
    assert slugs <= named
    # A kind with a subject is named with a placeholder, as in `gone/<url>`.
    kinds = [
        *(
            key.removeprefix(LIVE_CHECK.prefixes[0])
            for key in (alerts_module.LIVE_GONE, alerts_module.LIVE_STATUS)
        ),
        *(
            key.removeprefix(NIGHTLY_PREPARE.prefixes[1])
            for key in (
                alerts_module.BUILD_UNCATEGORIZED,
                alerts_module.BUILD_STALE_DENIAL,
                alerts_module.BUILD_STALE_CATEGORY,
            )
        ),
    ]
    for kind in kinds:
        assert any(re.fullmatch(re.escape(kind) + "<[a-z]+>", n) for n in named), kind
    assert {
        str(alerts_module.BUILD_REPORT),
        str(alerts_module.LIVE_CHECK_REPORT),
    } <= named

    # Each owner table row names its owners, then its job in parentheses.
    job_of = {
        owner: re.findall(r"`([^`]+)`", jobs)
        for owners, jobs in re.findall(
            r"^\| ([^(|]+)\(([^)]*)\) \|", docs, re.MULTILINE
        )
        for owner in re.findall(r"`([^`]+)`", owners)
    }

    (artifact_pattern,) = [name for name in named if name.startswith("alert-findings-")]
    for workflow in WORKFLOWS.glob("*.yml"):
        for name, job in load(workflow.name)["jobs"].items():
            steps = job.get("steps", [])
            if any("scripts.alerts reconcile" in step.get("run", "") for step in steps):
                assert name in named
            if any(is_emit(step) for step in steps):
                owner = emitted_owner(job)
                for source in SOURCE_NAMES if "$SOURCE" in owner else ("",):
                    assert name in job_of[owner.replace("$SOURCE", source)]
                (upload,) = [s for s in steps if is_findings_upload(s)]
                assert upload["with"]["name"] == artifact_pattern.replace(
                    "<owner>", owner.replace("$SOURCE", "${{ inputs.source }}")
                ).replace("<run id>", "${{ github.run_id }}")
