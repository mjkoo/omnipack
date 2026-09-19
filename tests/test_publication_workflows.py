"""Publication boundaries shared by the checked-in Actions workflows."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github/workflows"


def command(step):
    return shlex.split(step.get("run", "").replace("\\\n", ""))


def action_steps(job, action):
    return [s for s in job["steps"] if s.get("uses", "").startswith(action + "@")]


def command_step(job, *words):
    return next(s for s in job["steps"] if command(s) == list(words))


def output(owner, field):
    return "${{ " + owner + ".outputs." + field + " }}"


@pytest.fixture(params=["nightly.yml", "source-catalog.yml"])
def workflow(request):
    return yaml.safe_load((WORKFLOWS / request.param).read_text())


def test_nightly_refreshes_daily_at_three_in_eastern_time():
    # Only nightly keeps this schedule, so the shared fixture cannot assert it.
    nightly = yaml.safe_load((WORKFLOWS / "nightly.yml").read_text())
    triggers = nightly.get("on", nightly.get(True, {}))
    assert triggers["schedule"] == [
        {"cron": "0 3 * * *", "timezone": "America/New_York"}
    ]


def test_publication_permissions_and_runtime_boundaries(workflow):
    # PyYAML's YAML 1.1 loader parses the unquoted `on` key as True.
    triggers = workflow.get("on", workflow.get(True, {}))
    assert triggers["schedule"]
    assert "workflow_dispatch" in triggers
    assert workflow["permissions"] == {}
    assert workflow["concurrency"]["cancel-in-progress"] is False
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
    for job_name, job in workflow["jobs"].items():
        assert job["if"] == (
            "github.repository == 'mjkoo/omnipack' && github.ref == 'refs/heads/main'"
        )
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
                assert step in action_steps(check, "actions/upload-artifact")
                assert step["with"]["if-no-files-found"] == "ignore"
    assert not any(
        word in str(check["steps"])
        for word in ("GH_TOKEN", "GITHUB_TOKEN", "github.token", "secrets.")
    )
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
    assert command(stage) == [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        module,
        stage_id,
    ]
    assert "if" not in stage
    assert check["outputs"] == {
        k: output(f"steps.{stage_id}", k) for k in ("changed", "sha", "base")
    }
    [download] = action_steps(publish, "actions/download-artifact")
    uploads = action_steps(check, "actions/upload-artifact")
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
        else {".build/source-generation/codm/report.json"}
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
    workflow = yaml.safe_load((WORKFLOWS / "source-catalog.yml").read_text())
    check = workflow["jobs"]["check"]
    commands = [
        ("uv", "sync", "--locked"),
        ("uv", "run", "--no-sync", "pack", "generate-source", "codm"),
        ("uv", "run", "--no-sync", "python", "-m", "scripts.source_proposal", "stage"),
        ("uv", "run", "--no-sync", "pytest"),
        ("uv", "run", "--no-sync", "pack", "build"),
        ("uv", "run", "--no-sync", "pack", "verify"),
        ("git", "diff", "--quiet", "$SHA", "--", "config/catalogs/codm.json"),
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
    assert stages[-1]["env"] == {"SHA": output("steps.stage", "sha")}
