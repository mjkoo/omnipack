## Why

Nightly refreshes duplicate development CI and maintain retry, checkout-cleanup,
issue-reconciliation and fallback-finalization machinery disproportionate to a
curated pack. Occasional failed runs and delayed update notifications are
acceptable, so these related responsibilities can be reduced in one change.

## What Changes

- Use one Actions checkout, locked runtime setup, build and fresh structural
  verification per run, retaining exact-byte and allowed-path publication guards.
- **BREAKING**: Stop when main advances instead of rebuilding automatically.
  Retain remote-history reconciliation after an ambiguous push, without another
  push or refresh attempt.
- Rely on development CI for formatting, lint, types, packaging and the full
  test suite; remove nightly's duplicate checks and pre-build pack verification.
- **BREAKING**: Replace automated failure issues and fallback-finalization
  commands with Actions step status, logs, a concise summary and available
  diagnostic artifacts. Remove issue-write permission and disposable checkouts.
- Keep the rolling release and Obtainium notifications, but check release seed
  readiness only after confirmed main publication or a verified no-op. Release
  failure fails the workflow without preventing or undoing main publication.
- Retain release ownership, explicit bootstrap, revision/digest state and asset
  repair on later runs, including main no-ops.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `nightly-publishing`: One attempt in the Actions workspace, candidate-only
  verification, CI-owned code checks and Actions-based failure reporting.
- `rolling-pack-release`: Release readiness gates release writes rather than
  main publication, with separately reported main and release outcomes.

## Impact

Affects `.github/workflows/nightly.yml`, nightly entrypoint, git orchestration,
candidate refresh, reporting, issue reconciliation, related tests and operator
documentation. Shared GitHub transport needed by release operations remains.
No new dependencies, export changes or curation-policy changes are intended.

## Non-goals

Do not redesign standalone structural evidence, release asset state, source
ingestion, APK discovery or composition. Do not create a CI-status polling gate,
change repository protections, automatically bootstrap a release, or perform
external publication or issue migration during implementation. Historical
validation and archived planning records remain intact.
