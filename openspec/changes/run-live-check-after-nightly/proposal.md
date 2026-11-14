# Proposal

## Why

The live project check reads `main`'s committed packs at 04:17 UTC, about four
hours before nightly publishing rebuilds them. It therefore always checks the
previous day's packs. A merged fix clears its alert a day late: a gone project
repointed one afternoon kept its 404 issue open until the second check after
the merge. And a dead URL that a nightly brings in from an upstream catalog goes
unflagged for most of a day while users already have it.

## What Changes

- Move the live check job and its alert job out of the daily **Reviewed source
  catalog** workflow into a workflow of their own that starts when each
  **Nightly publishing** run completes, whatever its outcome, and on manual
  dispatch. The job checks out the `main` commit current at that point, which
  after a successful nightly is the commit it just published. Release archive
  already starts the same way.
- The reviewed source catalog workflow keeps its daily schedule and now runs
  only the per-source generation, proposal and alert jobs.
- The check's own behavior is unchanged: permissions, concurrency groups,
  timeout, report, run summary, findings, alert keys and issue reconciliation
  all stay as they are.
- Move the live check's documentation next to nightly publishing, since it no
  longer shares a workflow with source generation.

Retires the requirement that the daily source catalog workflow runs the live
check, and the rule that the live check does not wait on a source's runs, which
no longer applies once the jobs are in separate workflows. Estimated size: three
modified requirements, one of them renamed, two added scenarios; about 120
workflow lines moved rather than written, and about 40 test lines changed.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `source-generation`: the live-check requirement is renamed and now ties the
  check to each nightly publishing run's completion and manual dispatch,
  instead of the daily source catalog workflow.
- `maintenance-alerts`: the workflows that raise findings now include the live
  project check workflow.
- `release-archive`: the bucket-credentials requirement now states generally
  that no job other than the archive job receives the bucket secrets, instead
  of listing jobs, which also covers the live check job.

## Impact

- `.github/workflows/source-catalog.yml` loses the `live-check` and
  `alert-live-check` jobs, and a new `.github/workflows/live-check.yml` carries
  them with a `workflow_run` trigger on Nightly publishing.
- The live check and Release archive now start together after each nightly and
  share the repository's `GITHUB_TOKEN` API quota. A rate-limited health lookup
  reads as health inconclusive, which raises no finding.
- Tests in `tests/test_publication_workflows.py` and
  `tests/test_alert_boundaries.py` point at the new workflow file.
- Docs: `docs/source-generation.md`, `docs/publishing.md`, `docs/alerts.md`,
  `docs/development.md`.
