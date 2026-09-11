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
