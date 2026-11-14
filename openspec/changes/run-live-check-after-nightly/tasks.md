# Tasks

## 1. Live check workflow

- [x] 1.1 Carry over commit `f3f592f` from branch `ci/live-check-after-nightly` with `git cherry-pick`. It adds `.github/workflows/live-check.yml` (Nightly publishing `workflow_run` and `workflow_dispatch`, the inline `dangerous-triggers` ignore, the checkout pinned to `${{ github.sha }}`, the `live-check` and `alert-live-check` jobs unchanged), drops those jobs from `.github/workflows/source-catalog.yml`, points the tests at the new file and updates the docs. Verify `tests/test_publication_workflows.py` and `tests/test_alert_boundaries.py` pass, and that actionlint and `zizmor --persona pedantic .github/workflows` report nothing. `test_only_the_release_archive_job_references_the_bucket_secrets` globs every workflow, so its passing shows the live check job holds no `ARCHIVE_S3_*` secret
- [x] 1.2 Add a test that the live check job runs whatever the nightly's outcome: the workflow has no `conclusion` filter on either job's `if`. Verify it passes, and that it fails against a copy of the workflow with a conclusion filter added

## 2. Documentation

- [x] 2.1 Move the "Live project check" section from `docs/source-generation.md` to `docs/publishing.md`, after the release archive paragraph, describing it as starting when each nightly run completes or on manual dispatch. Repoint the links in `docs/development.md`, `docs/alerts.md` and `docs/publishing.md`. Verify `grep -rn "source-generation.md#live-project-check" docs README.md` returns nothing and every new anchor resolves to a heading
- [x] 2.2 Add a residual-risk bullet to `docs/alerts.md`: the live check and the release archive start together after each nightly and share the repository token's API quota, and a rate-limited health lookup reads as health inconclusive and raises no finding. State no counts. Verify the bullet is present and the no-fancy-dashes hook passes

## 3. Test tidy-up

- [ ] 3.1 In `tests/test_publication_workflows.py`, define one constant for the after-nightly `workflow_run` triggers and one helper that asserts the single inline `dangerous-triggers` ignore. Use both in the release archive and live check trigger tests. Verify both tests pass and that no duplicated trigger dict remains
- [ ] 3.2 Reflow the module docstring of `tests/test_alert_boundaries.py` so it names `nightly.yml`, `live-check.yml` and `release-archive.yml` within the line length. Verify `uv run ruff check` and `uv run ruff format --check` pass

## 4. Integration checks and review

- [ ] 4.1 Run `just test lint-check typecheck format-check` and confirm all pass
- [ ] 4.2 Run the implementation review the spec-implementation skill requires on the branch diff against main, and fix or record every finding. Verify the review record names no open blocking finding

## Workflow follow-up

- After merge, the first Live project check run follows the next nightly. Its checkout SHA should be that nightly's commit, and the source catalog's next scheduled run should show no live check job.
- Branch `ci/live-check-after-nightly` is unmerged once its commit is carried over. Deleting it needs the owner's approval.
