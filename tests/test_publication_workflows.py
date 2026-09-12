"""Structured checks for the publication workflows' job shape and hand-off.

These parse the workflow YAML with PyYAML and assert properties of the
parsed structure, rather than matching substrings of the file text, so a
change that keeps the same words but breaks the actual job shape is caught.
The helpers below take the check and write job names as parameters so a
workflow with a differently named check job can reuse them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / ".github" / "workflows"
STATUS_FUNCTIONS = ("always()", "failure()", "cancelled()", "!cancelled()")


def load_workflow(name: str) -> dict[Any, Any]:
    document = yaml.safe_load((WORKFLOWS_DIR / name).read_text())
    assert isinstance(document, dict)
    return document


def triggers(document: dict[Any, Any]) -> dict[str, Any]:
    # PyYAML's default (YAML 1.1) resolver parses the bare `on` key as the
    # boolean True, not the string "on".
    return document[True]


def jobs(document: dict[Any, Any]) -> dict[str, Any]:
    return document["jobs"]


def steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return job["steps"]


def step_uses(step: dict[str, Any], action_prefix: str) -> bool:
    return str(step.get("uses", "")).startswith(action_prefix)


def checkout_steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    found = [step for step in steps(job) if step_uses(step, "actions/checkout@")]
    assert found, "job has no checkout step"
    return found


def step_env(step: dict[str, Any]) -> dict[str, Any]:
    return step.get("env") or {}


def step_run(step: dict[str, Any]) -> str:
    return step.get("run") or ""


def normalized_run(step: dict[str, Any]) -> str:
    """The step's `run:` command with insignificant whitespace collapsed."""
    return " ".join(step_run(step).split())


def download_artifact_step(job: dict[str, Any]) -> dict[str, Any]:
    return next(
        step for step in steps(job) if step_uses(step, "actions/download-artifact@")
    )


def find_step(job: dict[str, Any], name: str) -> dict[str, Any]:
    for step in steps(job):
        if step.get("name") == name:
            return step
    raise AssertionError(f"no step named {name!r}")


def step_index(job: dict[str, Any], predicate: Any) -> int:
    for index, step in enumerate(steps(job)):
        if predicate(step):
            return index
    raise AssertionError("no step matches the predicate")


def assert_checkout_pins_the_ref(step: dict[str, Any], *, fetch_depth: int) -> None:
    with_block = step.get("with") or {}
    assert with_block.get("ref") == "${{ github.sha }}"
    assert with_block.get("persist-credentials") is False
    assert with_block.get("fetch-depth") == fetch_depth


def assert_no_setup_uv_or_uv(job: dict[str, Any]) -> None:
    for step in steps(job):
        assert not step_uses(step, "astral-sh/setup-uv@")
        run_words = step_run(step).split()
        assert "uv" not in run_words


def token_bearing_steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        step
        for step in steps(job)
        if "GH_TOKEN" in step_env(step) or "GITHUB_TOKEN" in step_env(step)
    ]


def assert_no_token_or_secret_reference(job: dict[str, Any]) -> None:
    for step in steps(job):
        text = str(step)
        assert "GH_TOKEN" not in text
        assert "github.token" not in text
        assert "secrets." not in text


def assert_no_status_function_except(job: dict[str, Any], allowed: set[str]) -> None:
    assert not any(function in job.get("if", "") for function in STATUS_FUNCTIONS)
    for step in steps(job):
        condition = step.get("if", "")
        if any(function in condition for function in STATUS_FUNCTIONS):
            assert step.get("name") in allowed, (
                f"unexpected status function on step {step.get('name')!r}"
            )


def assert_no_needs_or_steps_expression_in_run(document: dict[Any, Any]) -> None:
    for job in jobs(document).values():
        for step in steps(job):
            run = step_run(step)
            assert "needs." not in run
            assert "steps." not in run


def assert_base_guard_precedes(job: dict[str, Any], *, guarded_names: set[str]) -> None:
    """Assert the base guard step runs before every named step and every GH_TOKEN step."""
    guard_index = step_index(
        job,
        lambda step: step_run(step).strip() == 'test "$BASE_SHA" = "$GITHUB_SHA"',
    )
    for index, step in enumerate(steps(job)):
        if step.get("name") in guarded_names or "GH_TOKEN" in step_env(step):
            assert index > guard_index, (
                f"step {step.get('name')!r} does not follow the base guard"
            )


# --- nightly workflow ----------------------------------------------------

NIGHTLY = load_workflow("nightly.yml")


def test_nightly_triggers_permissions_and_concurrency() -> None:
    on = triggers(NIGHTLY)
    assert on["schedule"] == [{"cron": "0 3 * * *", "timezone": "America/New_York"}]
    assert on["workflow_dispatch"] is None
    assert NIGHTLY["permissions"] == {}
    assert NIGHTLY["concurrency"] == {
        "group": "omnipack-nightly-publisher",
        "cancel-in-progress": False,
    }


def test_nightly_both_jobs_share_the_repository_and_ref_guard() -> None:
    for job in jobs(NIGHTLY).values():
        assert job["if"] == (
            "github.repository == 'mjkoo/omnipack' && github.ref == 'refs/heads/main'"
        )
        assert job["runs-on"] == "ubuntu-latest"
        assert job["timeout-minutes"] == 60


def test_nightly_prepare_job_is_read_only() -> None:
    prepare = jobs(NIGHTLY)["prepare"]
    assert prepare["permissions"] == {"contents": "read"}
    for step in checkout_steps(prepare):
        assert_checkout_pins_the_ref(step, fetch_depth=0)
    assert_no_token_or_secret_reference(prepare)


def test_nightly_prepare_job_declares_its_outputs() -> None:
    prepare = jobs(NIGHTLY)["prepare"]
    assert prepare["outputs"] == {
        "changed": "${{ steps.prepare.outputs.changed }}",
        "sha": "${{ steps.prepare.outputs.sha }}",
        "base": "${{ steps.prepare.outputs.base }}",
    }


def test_nightly_publish_job_needs_prepare_and_writes_contents() -> None:
    publish = jobs(NIGHTLY)["publish"]
    assert publish["needs"] == "prepare"
    assert publish["permissions"] == {"contents": "write"}
    for step in checkout_steps(publish):
        assert_checkout_pins_the_ref(step, fetch_depth=1)
    assert_no_setup_uv_or_uv(publish)


def test_nightly_gh_token_only_on_push_and_release_steps() -> None:
    publish = jobs(NIGHTLY)["publish"]
    names = {step["name"] for step in token_bearing_steps(publish)}
    assert names == {
        "Push the verified candidate to main",
        "Synchronize the rolling release",
    }


def test_nightly_push_step_condition_is_only_the_changed_output() -> None:
    publish = jobs(NIGHTLY)["publish"]
    push_step = find_step(publish, "Push the verified candidate to main")
    assert push_step["if"] == "needs.prepare.outputs.changed == 'true'"


def test_nightly_release_step_has_no_condition() -> None:
    publish = jobs(NIGHTLY)["publish"]
    release_step = find_step(publish, "Synchronize the rolling release")
    assert "if" not in release_step


def test_nightly_download_gated_on_changed_output() -> None:
    publish = jobs(NIGHTLY)["publish"]
    download_step = next(
        step for step in steps(publish) if step_uses(step, "actions/download-artifact@")
    )
    assert download_step["if"] == "needs.prepare.outputs.changed == 'true'"


def test_nightly_base_guard_precedes_download_and_token_steps() -> None:
    publish = jobs(NIGHTLY)["publish"]
    guard_step = find_step(publish, "Guard the base revision")
    assert guard_step["env"] == {"BASE_SHA": "${{ needs.prepare.outputs.base }}"}
    assert_base_guard_precedes(
        publish,
        guarded_names={
            "Download the candidate hand-off",
            "Push the verified candidate to main",
            "Synchronize the rolling release",
        },
    )


def test_nightly_no_needs_or_steps_expression_in_any_run() -> None:
    assert_no_needs_or_steps_expression_in_run(NIGHTLY)


def test_nightly_no_status_function_outside_the_diagnostics_upload() -> None:
    prepare = jobs(NIGHTLY)["prepare"]
    publish = jobs(NIGHTLY)["publish"]
    assert_no_status_function_except(prepare, {"Upload build and verification reports"})
    assert_no_status_function_except(publish, set())


def test_nightly_diagnostics_upload_always_ignores_missing_at_14_days() -> None:
    prepare = jobs(NIGHTLY)["prepare"]
    upload_step = find_step(prepare, "Upload build and verification reports")
    assert upload_step["if"] == "always()"
    with_block = upload_step["with"]
    assert with_block["if-no-files-found"] == "ignore"
    assert with_block["retention-days"] == 14
    assert with_block["path"] == ".build/report.json\n.build/verify.json\n"


def test_nightly_handoff_upload_is_one_day_and_names_an_exact_file() -> None:
    prepare = jobs(NIGHTLY)["prepare"]
    upload_step = find_step(prepare, "Upload the candidate hand-off")
    assert upload_step["if"] == "steps.prepare.outputs.changed == 'true'"
    with_block = upload_step["with"]
    assert with_block["retention-days"] == 1
    assert with_block["path"] == "${{ runner.temp }}/nightly-handoff/candidate.bundle"


def test_nightly_download_lands_in_runner_temp_not_the_workspace() -> None:
    publish = jobs(NIGHTLY)["publish"]
    download_step = next(
        step for step in steps(publish) if step_uses(step, "actions/download-artifact@")
    )
    assert download_step["with"]["path"] == "${{ runner.temp }}/nightly-handoff"


def test_nightly_push_step_env_maps_prepare_outputs() -> None:
    publish = jobs(NIGHTLY)["publish"]
    push_step = find_step(publish, "Push the verified candidate to main")
    env = step_env(push_step)
    assert env["CANDIDATE_SHA"] == "${{ needs.prepare.outputs.sha }}"
    assert env["BASE_SHA"] == "${{ needs.prepare.outputs.base }}"


def test_nightly_step_run_commands_match_the_documented_commands() -> None:
    prepare = jobs(NIGHTLY)["prepare"]
    publish = jobs(NIGHTLY)["publish"]
    sync_step = find_step(prepare, "Sync locked environment")
    prepare_step = find_step(prepare, "Build, verify and commit a candidate")
    push_step = find_step(publish, "Push the verified candidate to main")
    release_step = find_step(publish, "Synchronize the rolling release")
    assert normalized_run(sync_step) == "uv sync --locked"
    assert (
        normalized_run(prepare_step)
        == "uv run --no-sync python -m scripts.nightly prepare"
    )
    assert normalized_run(push_step) == (
        "python3 -m scripts.nightly_write push \\"
        ' --bundle "$RUNNER_TEMP/nightly-handoff/candidate.bundle"'
    )
    assert normalized_run(release_step) == "python3 -m scripts.nightly_write release"


def test_nightly_handoff_upload_and_download_names_match() -> None:
    prepare = jobs(NIGHTLY)["prepare"]
    publish = jobs(NIGHTLY)["publish"]
    upload_step = find_step(prepare, "Upload the candidate hand-off")
    download_step = download_artifact_step(publish)
    assert upload_step["with"]["name"] == download_step["with"]["name"]
