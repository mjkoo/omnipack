from pathlib import Path

WORKFLOW = Path(".github/workflows/source-catalog.yml")


def test_source_workflow_has_scoped_schedule_force_and_permissions() -> None:
    workflow = WORKFLOW.read_text()
    assert 'cron: "17 4 * * *"' in workflow
    assert "force:" in workflow
    assert "type: boolean" in workflow
    assert "github.repository == 'mjkoo/omnipack'" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "timeout-minutes: 60" in workflow
    assert "permissions: {}" in workflow
    assert "contents: write" in workflow
    assert "pull-requests: write" in workflow
    assert "issues: write" not in workflow
    assert "persist-credentials: false" in workflow
    assert "ref: main" in workflow
    assert "uv sync --locked" in workflow
    assert "pack generate-source codm" in workflow
    assert "pack generate-source codm --force" in workflow
    assert "source_publication check" in workflow
    assert "source_publication observe" in workflow
    assert "source_publication publish" in workflow
    assert workflow.index("source_publication observe") < workflow.index(
        "pack generate-source codm"
    )
    assert workflow.index("source_publication check") < workflow.index("GITHUB_TOKEN:")
    assert "retention-days: 14" in workflow
    assert "if: always()" in workflow
    assert "if-no-files-found: ignore" in workflow
    assert "steps.setup_uv.outcome" in workflow
    assert "steps.sync.outcome" in workflow
    assert ".build/source-generation/codm/report.json" in workflow
    assert "pull_request" not in workflow.split("permissions:", 1)[0]


def test_final_workflow_step_records_each_failure_and_uncertainty(tmp_path) -> None:
    import json
    import os
    import subprocess
    import sys
    import textwrap

    workflow = WORKFLOW.read_text()
    block = workflow.split("- name: Record final current-run outcomes", 1)[1].split(
        "- name: Upload", 1
    )[0]
    assert "if: always()" in block
    code = textwrap.dedent(
        block.split("python3 - <<'PYTHON'\n", 1)[1].split("          PYTHON", 1)[0]
    )
    stages = [
        "CHECKOUT",
        "SETUP_UV",
        "SYNC",
        "OBSERVE",
        "SCHEDULED",
        "FORCED",
        "CHECK",
        "PUBLISH",
    ]
    for failure in [*stages, "UNCERTAIN"]:
        root = tmp_path / failure
        root.mkdir()
        diagnostics = root / "diagnostics"
        diagnostics.mkdir()
        initial = (
            {"status": "uncertain", "stage": "push"}
            if failure == "UNCERTAIN"
            else {"status": "started", "stage": "setup"}
        )
        (diagnostics / "run-result.json").write_text(json.dumps(initial))
        env = {
            **os.environ,
            "DIAGNOSTIC_ROOT": str(diagnostics),
            "GITHUB_SHA": "selected-main",
            "GITHUB_STEP_SUMMARY": str(root / "summary.md"),
        }
        for stage in stages:
            env[f"{stage}_OUTCOME"] = (
                "failure"
                if stage == failure or (failure == "UNCERTAIN" and stage == "PUBLISH")
                else "success"
            )
        subprocess.run([sys.executable, "-c", code], cwd=root, env=env, check=True)
        result = json.loads((diagnostics / "run-result.json").read_text())
        assert result["status"] == ("uncertain" if failure == "UNCERTAIN" else "failed")
        assert result["baseSha"] == "selected-main"
        assert set(result["outcomes"]) == {stage.lower() for stage in stages}
        assert "published" not in (root / "summary.md").read_text()
    assert workflow.index("Record final current-run") > workflow.index(
        "source_publication publish"
    )
    artifacts = workflow.split("          path: |", 1)[1].split(
        "          if-no-files-found", 1
    )[0]
    assert len(artifacts.strip().splitlines()) == 3
    assert all(
        name in artifacts
        for name in ("run-result.json", "report.json", "pack-diff.json")
    )
