"""Publication boundaries shared by the checked-in Actions workflows."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from itertools import pairwise
from pathlib import Path

import pytest
import yaml

from omnipack.live_check import REPORT, SUMMARY
from omnipack.source_registry import GENERATED
from scripts.alerts import Owner

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github/workflows"


def command(step):
    return shlex.split(step.get("run", "").replace("\\\n", ""))


def action_steps(job, action):
    return [s for s in job["steps"] if s.get("uses", "").startswith(action + "@")]


def command_step(job, *words):
    return next(s for s in job["steps"] if command(s) == list(words))


GUARD = "github.repository == 'mjkoo/omnipack' && github.ref == 'refs/heads/main'"
FINDINGS_PATH = ".build/alerts/findings.json"


def is_findings_upload(step):
    return step.get("uses", "").startswith("actions/upload-artifact@") and step["with"][
        "name"
    ].startswith("alert-findings-")


def is_emit(step):
    return command(step)[:4] == ["python3", "-m", "scripts.alerts", "emit"]


def producing_jobs(workflow):
    return {n: j for n, j in workflow["jobs"].items() if n != "alert"}


def output(owner, field):
    return "${{ " + owner + ".outputs." + field + " }}"


@pytest.fixture(params=["nightly.yml", "source-maintenance.yml"])
def workflow(request):
    return yaml.safe_load((WORKFLOWS / request.param).read_text())


def check_job_name(workflow):
    return workflow["jobs"]["publish"]["needs"]


def triggers(workflow):
    # PyYAML's YAML 1.1 loader parses the unquoted `on` key as True.
    return workflow.get("on", workflow.get(True, {}))


def test_nightly_refreshes_daily_at_three_in_eastern_time():
    nightly = yaml.safe_load((WORKFLOWS / "nightly.yml").read_text())
    assert triggers(nightly) == {
        "schedule": [{"cron": "0 3 * * *", "timezone": "America/New_York"}],
        "workflow_dispatch": None,
    }
    assert nightly["concurrency"]["cancel-in-progress"] is False


def test_source_maintenance_runs_only_when_called_for_one_source():
    # The caller schedules each source and serializes its runs, so the
    # reusable workflow declares neither a schedule nor its own concurrency.
    workflow = yaml.safe_load((WORKFLOWS / "source-maintenance.yml").read_text())
    assert set(triggers(workflow)) == {"workflow_call"}
    inputs = triggers(workflow)["workflow_call"]["inputs"]
    assert set(inputs) == {"source"}
    assert inputs["source"]["required"] is True
    assert inputs["source"]["type"] == "string"
    assert "concurrency" not in workflow


def test_publication_permissions_and_runtime_boundaries(workflow):
    assert workflow["permissions"] == {}
    publish = workflow["jobs"]["publish"]
    check = workflow["jobs"][publish["needs"]]
    assert check["permissions"] == {"contents": "read"}
    source = publish["needs"] == "check"
    assert publish["permissions"] == (
        {"contents": "write", "pull-requests": "write"}
        if source
        else {"contents": "write"}
    )
    for job, depth in [(check, 0), (publish, 1)]:
        [checkout] = action_steps(job, "actions/checkout")
        assert checkout["with"]["ref"] == "${{ github.sha }}"
        assert checkout["with"]["persist-credentials"] is False
        assert checkout["with"]["fetch-depth"] == depth
    assert set(workflow["jobs"]) == {check_job_name(workflow), "publish", "alert"}
    for job_name, job in producing_jobs(workflow).items():
        assert job["if"] == GUARD
        if job_name != "publish":
            assert job.get("permissions", {}) in ({}, {"contents": "read"})
        for setup in action_steps(job, "astral-sh/setup-uv"):
            assert setup["with"]["enable-cache"] is False
        for step in job["steps"]:
            if "uses" in step:
                assert re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", step["uses"])
                assert not step["uses"].startswith("actions/cache")
            assert "needs." not in step.get("run", "")
            assert "steps." not in step.get("run", "")
            if any(
                fn in step.get("if", "")
                for fn in ("always()", "failure()", "cancelled()")
            ):
                if step.get("id") == "summary" or is_emit(step):
                    assert step["if"] == "always()"
                elif is_findings_upload(step):
                    assert step["if"] == "always()"
                    assert step["with"]["if-no-files-found"] == "ignore"
                else:
                    assert step in action_steps(check, "actions/upload-artifact")
                    assert step["with"]["if-no-files-found"] == "ignore"
    # Generation reads public upstream lists, so no check step holds a token.
    assert not [s for s in check["steps"] if "GITHUB_TOKEN" in s.get("env", {})]
    if source:
        [generation] = [s for s in check["steps"] if s.get("id") == "generation"]
        assert "env" not in generation
    assert "GH_TOKEN" not in str(check["steps"])
    assert "secrets." not in str(check["steps"])
    assert len(action_steps(check, "astral-sh/setup-uv")) == 1
    assert not action_steps(publish, "astral-sh/setup-uv")
    assert all("uv" not in command(step) for step in publish["steps"])
    assert command_step(check, "uv", "sync", "--locked")


def test_handoff_connects_checked_candidate_to_writer(workflow):
    publish = workflow["jobs"]["publish"]
    check_name = publish["needs"]
    check = workflow["jobs"][check_name]
    stage_id = "prepare" if check_name == "prepare" else "stage"
    stage = next(s for s in check["steps"] if s.get("id") == stage_id)
    module = "scripts.nightly" if stage_id == "prepare" else "scripts.source_proposal"
    expected_stage = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        module,
        stage_id,
    ]
    if stage_id == "stage":
        expected_stage += ["--source", "$SOURCE"]
    assert command(stage) == expected_stage
    assert "if" not in stage
    assert check["outputs"] == {
        k: output(f"steps.{stage_id}", k) for k in ("changed", "sha", "base")
    }
    [download] = action_steps(publish, "actions/download-artifact")
    uploads = [
        s
        for s in action_steps(check, "actions/upload-artifact")
        if not is_findings_upload(s)
    ]
    handoff = next(s for s in uploads if s["with"]["name"] == download["with"]["name"])
    assert handoff["if"] == f"steps.{stage_id}.outputs.changed == 'true'"
    assert download["if"] == f"needs.{check_name}.outputs.changed == 'true'"
    directory = "nightly-handoff" if stage_id == "prepare" else "source-handoff"
    assert download["with"]["path"] == "${{ runner.temp }}/" + directory
    files = (
        ["candidate.bundle"]
        if stage_id == "prepare"
        else ["candidate.bundle", "pr-body.md"]
    )
    assert handoff["with"]["path"].splitlines() == [
        "${{ runner.temp }}/" + directory + "/" + f for f in files
    ]
    for upload in uploads:
        assert upload["with"]["overwrite"] is True
        if upload is handoff:
            assert upload["with"]["if-no-files-found"] == "error"
        else:
            assert upload["if"] == "always()"
            assert upload["with"]["if-no-files-found"] == "ignore"
    reports = {
        p for s in uploads if s is not handoff for p in s["with"]["path"].splitlines()
    }
    assert reports == (
        {".build/report.json", ".build/verify.json"}
        if stage_id == "prepare"
        else {".build/source-generation/${{ inputs.source }}/report.json"}
    )
    assert check["steps"].index(stage) < check["steps"].index(handoff)
    writer = next(s for s in publish["steps"] if "CANDIDATE_SHA" in s.get("env", {}))
    assert writer["env"]["CANDIDATE_SHA"] == output(f"needs.{check_name}", "sha")
    assert writer["env"]["BASE_SHA"] == output(f"needs.{check_name}", "base")
    tokens = command(writer)
    expected = (
        ["python3", "-m", "scripts.nightly_write", "push"]
        if stage_id == "prepare"
        else ["python3", "-m", "scripts.source_proposal", "publish"]
    )
    if stage_id == "stage":
        expected += ["--source", "$SOURCE"]
    expected += ["--bundle", "$RUNNER_TEMP/" + directory + "/candidate.bundle"]
    if stage_id == "stage":
        expected += ["--body-file", "$RUNNER_TEMP/source-handoff/pr-body.md"]
    assert tokens == expected
    token_steps = [
        s
        for s in publish["steps"]
        if "GH_TOKEN" in s.get("env", {}) or "GITHUB_TOKEN" in s.get("env", {})
    ]
    if stage_id == "prepare":
        assert writer["if"] == f"needs.{check_name}.outputs.changed == 'true'"
        release = command_step(
            publish, "python3", "-m", "scripts.nightly_write", "release"
        )
        assert "if" not in release
        assert token_steps == [writer, release]
    else:
        assert "if" not in writer
        assert writer["env"]["CHANGED"] == output(f"needs.{check_name}", "changed")
        assert token_steps == [writer]
    assert all(s["env"]["GH_TOKEN"] == "${{ github.token }}" for s in token_steps)


def test_base_guard_rejects_stale_revision_before_consumption(workflow):
    publish = workflow["jobs"]["publish"]
    [guard] = [s for s in publish["steps"] if set(s.get("env", {})) == {"BASE_SHA"}]
    assert guard["env"]["BASE_SHA"] == output(f"needs.{publish['needs']}", "base")
    assert "if" not in guard
    guard_index = publish["steps"].index(guard)
    [checkout] = action_steps(publish, "actions/checkout")
    assert publish["steps"].index(checkout) < guard_index
    for step in publish["steps"]:
        if step in action_steps(publish, "actions/download-artifact") or any(
            k in step.get("env", {}) for k in ("GH_TOKEN", "GITHUB_TOKEN")
        ):
            assert guard_index < publish["steps"].index(step)
    for base, expected in [("a" * 40, 0), ("b" * 40, 1)]:
        result = subprocess.run(
            ["bash", "-e", "-c", guard["run"]],
            env={**os.environ, "BASE_SHA": base, "GITHUB_SHA": "a" * 40},
            capture_output=True,
            check=False,
        )
        assert (result.returncode == 0) is (expected == 0)


def test_source_candidate_validation_finishes_before_handoff():
    workflow = yaml.safe_load((WORKFLOWS / "source-maintenance.yml").read_text())
    check = workflow["jobs"]["check"]
    commands = [
        ("uv", "sync", "--locked"),
        ("uv", "run", "--no-sync", "pack", "generate-source", "$SOURCE"),
        (
            "uv",
            "run",
            "--no-sync",
            "python",
            "-m",
            "scripts.source_proposal",
            "stage",
            "--source",
            "$SOURCE",
        ),
        ("uv", "run", "--no-sync", "pytest"),
        ("uv", "run", "--no-sync", "pack", "build"),
        ("uv", "run", "--no-sync", "pack", "verify"),
        ("python3", "-m", "scripts.source_proposal", "guard", "--source", "$SOURCE"),
    ]
    stages = [command_step(check, *words) for words in commands]
    [handoff] = [
        s
        for s in action_steps(check, "actions/upload-artifact")
        if s["with"]["if-no-files-found"] == "error"
    ]
    indices = [check["steps"].index(s) for s in [*stages, handoff]]
    assert indices == sorted(indices)
    assert all("if" not in s for s in stages[:3])
    assert all(
        s["if"] == "steps.stage.outputs.changed == 'true'"
        for s in [*stages[3:], handoff]
    )
    assert stages[-1]["env"] == {
        "CANDIDATE_SHA": output("steps.stage", "sha"),
        "BASE_SHA": output("steps.stage", "base"),
    }


def test_sources_run_independent_complete_check_publish_chains():
    caller = yaml.safe_load((WORKFLOWS / "source-catalog.yml").read_text())
    assert triggers(caller) == {
        "schedule": [{"cron": "17 4 * * *"}],
        "workflow_dispatch": None,
    }
    assert caller["permissions"] == {}
    assert "concurrency" not in caller
    assert set(caller["jobs"]) == {*GENERATED, "live-check", "alert-live-check"}
    for source in GENERATED:
        job = caller["jobs"][source]
        assert job["uses"] == "./.github/workflows/source-maintenance.yml"
        assert job["with"] == {"source": source}
        assert job["concurrency"] == {
            "group": f"omnipack-reviewed-source-catalog-{source}",
            "cancel-in-progress": False,
        }
        assert "needs" not in job
        # Only the called alert job uses issues: write.
        assert job["permissions"] == {
            "contents": "write",
            "pull-requests": "write",
            "issues": "write",
        }
        assert job["if"] == GUARD


def test_live_check_job_reads_only_and_reports_its_findings():
    job = yaml.safe_load((WORKFLOWS / "source-catalog.yml").read_text())["jobs"][
        "live-check"
    ]
    assert (
        job["if"]
        == "github.repository == 'mjkoo/omnipack' && github.ref == 'refs/heads/main'"
    )
    assert job["permissions"] == {"contents": "read"}
    assert job["concurrency"] == {
        "group": "omnipack-live-check",
        "cancel-in-progress": False,
    }
    assert job["timeout-minutes"] == 30
    assert "needs" not in job
    assert "uses" not in job
    assert "continue-on-error" not in job

    (checkout,) = action_steps(job, "actions/checkout")
    assert checkout["with"]["persist-credentials"] is False
    (setup_uv,) = action_steps(job, "astral-sh/setup-uv")
    assert setup_uv["with"]["enable-cache"] is False
    command_step(job, "uv", "sync", "--locked")
    check = command_step(job, "uv", "run", "--no-sync", "pack", "check-live")
    assert "if" not in check
    assert "continue-on-error" not in check

    summary = next(s for s in job["steps"] if "GITHUB_STEP_SUMMARY" in s.get("run", ""))
    assert summary["if"] == "always()"
    assert str(SUMMARY) in summary["run"]

    (findings,) = [s for s in job["steps"] if is_findings_upload(s)]
    (upload,) = [
        s
        for s in action_steps(job, "actions/upload-artifact")
        if not is_findings_upload(s)
    ]
    assert upload["if"] == "always()"
    assert upload["with"]["path"] == str(REPORT)
    assert upload["with"]["if-no-files-found"] == "ignore"
    assert upload["with"]["retention-days"] == 14
    steps = job["steps"]
    assert steps.index(check) < steps.index(summary)
    assert steps.index(check) < steps.index(upload)

    emit = next(s for s in job["steps"] if is_emit(s))
    assert steps[-2:] == [emit, findings]
    assert command(emit) == ["python3", "-m", "scripts.alerts", "emit", "live-check"]
    assert emit["env"] == {
        "JOB_STATUS": "${{ job.status }}",
        "CHECK_RESULT": "${{ steps.check.outcome }}",
    }
    assert check["id"] == "check"

    # Nothing in the job can change a branch, a PR or a committed file.
    assert [s for s in job["steps"] if "env" in s] == [emit]
    runs = " ".join(step.get("run", "") for step in job["steps"])
    for word in ("git", "gh ", "GITHUB_TOKEN", "github.token"):
        assert word not in runs.replace("alerts", "")
    assert {step.get("uses", "").split("@")[0] for step in job["steps"]} == {
        "actions/checkout",
        "astral-sh/setup-uv",
        "actions/upload-artifact",
        "",
    }


def test_source_artifacts_and_actual_validation_outcomes_are_scoped():
    workflow = yaml.safe_load((WORKFLOWS / "source-maintenance.yml").read_text())
    assert workflow["env"]["SOURCE"] == "${{ inputs.source }}"
    check = workflow["jobs"]["check"]
    assert (
        check["timeout-minutes"] == workflow["jobs"]["publish"]["timeout-minutes"] == 60
    )
    for step in action_steps(check, "actions/upload-artifact"):
        assert "${{ inputs.source }}" in step["with"]["name"]
        assert step["with"]["retention-days"] == (14 if step["if"] == "always()" else 1)
    summary = next(s for s in check["steps"] if s.get("id") == "summary")
    assert summary["if"] == "always()"
    for stage, step_id in (
        ("GENERATION", "generation"),
        ("STAGING", "stage"),
        ("TESTS", "tests"),
        ("BUILD", "build"),
        ("VERIFY", "verify"),
        ("GUARD", "guard"),
    ):
        assert (
            summary["env"][stage + "_RESULT"] == "${{ steps." + step_id + ".outcome }}"
        )
    handoff = next(
        s
        for s in action_steps(check, "actions/upload-artifact")
        if s["with"]["if-no-files-found"] == "error"
    )
    assert check["steps"].index(summary) < check["steps"].index(handoff)


def findings_name(owner):
    return f"alert-findings-{owner}-${{{{ github.run_id }}}}"


def alert_cases():
    """Each alert job with its producers, as (file, job, {owner: producer job})."""
    return [
        (
            "nightly.yml",
            "alert",
            {"nightly-prepare": "prepare", "nightly-publish": "publish"},
        ),
        (
            "source-maintenance.yml",
            "alert",
            {"$SOURCE-check": "check", "$SOURCE-publish": "publish"},
        ),
        ("source-catalog.yml", "alert-live-check", {"live-check": "live-check"}),
    ]


def load(name):
    return yaml.safe_load((WORKFLOWS / name).read_text())


@pytest.mark.parametrize(("file", "alert_name", "producers"), alert_cases())
def test_alert_job_holds_only_issue_access_and_reconciles_producer_findings(
    file, alert_name, producers
):
    workflow = load(file)
    job = workflow["jobs"][alert_name]
    assert job["permissions"] == {"issues": "write"}
    assert job["if"] == "always() && " + GUARD
    assert set(
        job["needs"] if isinstance(job["needs"], list) else [job["needs"]]
    ) == set(producers.values())
    assert "uses" not in job
    # The caller's group serializes the source alert job; live-check has its own.
    if file == "source-catalog.yml":
        assert job["concurrency"] == {
            "group": "omnipack-live-check-alerts",
            "cancel-in-progress": False,
        }
    else:
        assert "concurrency" not in job

    (checkout,) = action_steps(job, "actions/checkout")
    assert checkout["with"]["sparse-checkout"] == "scripts"
    assert checkout["with"]["persist-credentials"] is False
    assert not action_steps(job, "astral-sh/setup-uv")
    assert all("uv" not in command(s) for s in job["steps"])
    for step in job["steps"]:
        assert "${{" not in step.get("run", "")
        if "uses" in step:
            assert re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", step["uses"])

    downloads = action_steps(job, "actions/download-artifact")
    assert len(downloads) == len(producers)
    assert all(d["continue-on-error"] is True for d in downloads)
    paths = [d["with"]["path"] for d in downloads]
    assert len(set(paths)) == len(paths)
    names = [d["with"]["name"] for d in downloads]
    assert len(set(names)) == len(names)

    reconcile = next(s for s in job["steps"] if "reconcile" in command(s))
    assert [s for s in job["steps"] if "GH_TOKEN" in s.get("env", {})] == [reconcile]
    assert "continue-on-error" not in reconcile
    expected_env = {"GH_TOKEN": "${{ github.token }}"}
    parsed = reconcile_producers(reconcile)
    assert len(parsed) == len(producers)
    # Each producer's owner is the one its job's emit step passes, and its
    # result is that job's own, so a misspelled or swapped owner fails here.
    assert {owner for owner, _, _ in parsed} == set(producers)
    for owner, variable, path in parsed:
        job_name = producers[owner]
        assert emitted_owner(workflow["jobs"][job_name]) == owner
        result = "needs." + job_name + ".result"
        # A dependent job that never started reads as skipped, whatever its
        # upstream's own result, so it raises no early failure of its own.
        upstream = workflow["jobs"][job_name].get("needs")
        if upstream is not None:
            result = f"needs.{upstream}.result == 'success' && {result} || 'skipped'"
        expected_env[variable] = "${{ " + result + " }}"
        for source in GENERATED if "$SOURCE" in owner else [""]:
            assert Owner(owner.replace("$SOURCE", source)) in Owner
    assert reconcile["env"] == expected_env
    assert len({variable for _, variable, _ in parsed}) == len(parsed)
    # Each download lands in the directory its own producer reads.
    for download, (owner, _, path) in zip(downloads, parsed, strict=True):
        directory = download["with"]["path"].replace(
            "${{ runner.temp }}", "$RUNNER_TEMP"
        )
        directory = directory.replace("${{ inputs.source }}", "$SOURCE")
        assert path == directory + "/findings.json"
        assert owner == directory.rsplit("/", 1)[1]


def reconcile_producers(reconcile):
    """Each `--producer OWNER=$VARIABLE:PATH` as (owner, variable, path)."""
    words = command(reconcile)
    values = [w for previous, w in pairwise(words) if previous == "--producer"]
    parsed = []
    for value in values:
        match = re.fullmatch(r"(?P<o>[^=]+)=\$(?P<v>\w+):(?P<p>.+)", value)
        assert match, value
        owner, variable, path = match["o"], match["v"], match["p"]
        parsed.append(
            (
                owner.replace("${SOURCE}", "$SOURCE"),
                variable,
                path.replace("${SOURCE}", "$SOURCE"),
            )
        )
    return parsed


def emitted_owner(job):
    return command(producing_env(job["steps"]))[4]


def producing_env(job_steps):
    emit = [s for s in job_steps if is_emit(s)]
    assert len(emit) == 1
    return emit[0]


EMIT_BINDINGS = {
    ("nightly.yml", "prepare"): (
        "nightly-prepare",
        {
            "PREPARE_STAGE": "${{ steps.prepare.outputs.stage }}",
            "PREPARE_STAGES": "${{ steps.prepare.outputs.stages }}",
        },
    ),
    ("nightly.yml", "publish"): (
        "nightly-publish",
        {
            "PUSH_OUTCOME": "${{ steps.push.outputs.outcome }}",
            "RELEASE_OUTCOME": "${{ steps.release.outputs.outcome }}",
        },
    ),
    ("source-maintenance.yml", "check"): (
        '"$SOURCE-check"',
        {
            "CHANGED": "${{ steps.stage.outputs.changed }}",
            "GENERATION_RESULT": "${{ steps.generation.outcome }}",
            "STAGING_RESULT": "${{ steps.stage.outcome }}",
            "TESTS_RESULT": "${{ steps.tests.outcome }}",
            "BUILD_RESULT": "${{ steps.build.outcome }}",
            "VERIFY_RESULT": "${{ steps.verify.outcome }}",
            "GUARD_RESULT": "${{ steps.guard.outcome }}",
        },
    ),
    ("source-maintenance.yml", "publish"): (
        '"$SOURCE-publish"',
        {"PUBLISH_OUTCOME": "${{ steps.publish.outputs.outcome }}"},
    ),
    ("source-catalog.yml", "live-check"): (
        "live-check",
        {"CHECK_RESULT": "${{ steps.check.outcome }}"},
    ),
}


@pytest.mark.parametrize(("file", "job_name"), list(EMIT_BINDINGS))
def test_producing_jobs_emit_findings_last_and_tolerate_emit_failure(file, job_name):
    workflow = load(file)
    job = workflow["jobs"][job_name]
    owner, bindings = EMIT_BINDINGS[(file, job_name)]
    steps = job["steps"]
    emit = producing_env(steps)
    assert emit["if"] == "always()"
    assert emit["continue-on-error"] is True
    assert emit["env"] == {"JOB_STATUS": "${{ job.status }}", **bindings}
    assert emit["run"] == f"python3 -m scripts.alerts emit {owner}"
    (upload,) = [s for s in steps if is_findings_upload(s)]
    assert steps[-2:] == [emit, upload]
    assert upload["if"] == "always()"
    assert upload["continue-on-error"] is True
    assert upload["with"]["path"] == FINDINGS_PATH
    assert upload["with"]["overwrite"] is True
    assert upload["with"]["if-no-files-found"] == "ignore"
    # Every bound step id exists, and the job gained no permission.
    ids = {s.get("id") for s in steps}
    for value in bindings.values():
        assert value.split(".")[1] in ids
    assert (
        job["permissions"]
        == {
            "nightly.yml": {
                "prepare": {"contents": "read"},
                "publish": {"contents": "write"},
            },
            "source-maintenance.yml": {
                "check": {"contents": "read"},
                "publish": {"contents": "write", "pull-requests": "write"},
            },
            "source-catalog.yml": {"live-check": {"contents": "read"}},
        }[file][job_name]
    )


def test_findings_uploads_are_unique_and_each_alert_downloads_its_producers():
    nightly = load("nightly.yml")
    names = {
        job: next(s for s in nightly["jobs"][job]["steps"] if is_findings_upload(s))[
            "with"
        ]["name"]
        for job in ("prepare", "publish")
    }
    assert names == {
        "prepare": findings_name("nightly-prepare"),
        "publish": findings_name("nightly-publish"),
    }
    downloads = action_steps(nightly["jobs"]["alert"], "actions/download-artifact")
    assert [d["with"]["name"] for d in downloads] == list(names.values())

    source = load("source-maintenance.yml")
    uploads = {
        job: next(s for s in source["jobs"][job]["steps"] if is_findings_upload(s))[
            "with"
        ]["name"]
        for job in ("check", "publish")
    }
    assert uploads == {
        "check": findings_name("${{ inputs.source }}-check"),
        "publish": findings_name("${{ inputs.source }}-publish"),
    }
    downloads = action_steps(source["jobs"]["alert"], "actions/download-artifact")
    assert [d["with"]["name"] for d in downloads] == list(uploads.values())

    catalog = load("source-catalog.yml")
    live = next(
        s for s in catalog["jobs"]["live-check"]["steps"] if is_findings_upload(s)
    )["with"]["name"]
    assert live == findings_name("live-check")
    (download,) = action_steps(
        catalog["jobs"]["alert-live-check"], "actions/download-artifact"
    )
    assert download["with"]["name"] == live

    # One run holds the codm, Quiver and live-check uploads: all distinct.
    run_names = [
        n.replace("${{ inputs.source }}", source_name)
        for source_name in GENERATED
        for n in uploads.values()
    ] + [live, *names.values()]
    assert len(set(run_names)) == len(run_names)
