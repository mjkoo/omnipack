## Why

The repository can build and verify both Obtainium packs, but consumers of the
raw files on main receive updates only after a manual rebuild. Scheduled,
verified publication completes the delivery loop while retaining the previous
published pair whenever a refresh fails.

## What Changes

- Add nightly and manually dispatched refreshes from main using the existing
  build command followed by fresh metadata-only live verification.
- Publish changed distribution files and the package-id cache together in a
  direct commit to main, with an explicit file allowlist and no empty commits.
- Serialize publishers and rebuild once against a newer main when publication
  encounters concurrent changes; never force-push or reuse stale verification.
- Maintain one automation-owned failure issue and close it after recovery,
  including a successful refresh that produces no changes.
- Preserve run diagnostics in workflow artifacts and summaries, with clear
  reporting when publication or issue maintenance fails.

## Capabilities

### New Capabilities

- `nightly-publishing`: Scheduled refresh, verification-gated publication,
  concurrent-update handling, diagnostics, and failure-issue recovery.

### Modified Capabilities

None. Existing build, verification, ingestion, and reporting semantics remain
the inputs to the publisher.

## Impact

Adds `.github/workflows/nightly.yml`, a testable repository automation helper,
focused orchestration tests, and publishing documentation. Uses the existing
Python/uv toolchain and GitHub-provided token; requires repository permissions
that permit the intended direct push and issue maintenance. Changes committed
by automation are limited to the two `dist/` JSON files and
`config/package-ids.json`. Initial curation, asset probing, releases, and pull
request publication are outside this change.
