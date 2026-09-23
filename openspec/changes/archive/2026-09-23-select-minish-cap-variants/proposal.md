## Why

The packs currently select samyost1's Minish Cap Android fork for both variants.
Project Picori now supplies Android builds with a newer engine, while Sam's
fork retains useful second-screen behavior, so one source need not serve both.

## What Changes

- Target `999sian/tmc` for single-screen after reputation, APK and migration
  checks; retain `samyost1/tmc-android` for dual-screen.
- Express the split in existing extras/composition configuration and outcome
  tests, independently of Quiver integration.
- Record release identities and signing/version compatibility. Ship
  new-installation guidance and state that the save-preservation route from
  an existing Sam install is unresolved, without claiming a supported
  migration. Keep that unresolved compatibility in `docs/curation.md` under
  "Unresolved identity and selection findings", and raw observations in this
  change's `validation.md`.
- No single-screen preference setting exists to retire: Sam wins single today
  only as the family's sole baseline build. Both BBoi identity rules
  correcting `com.samyost1.tmcandroid` to `dev.picori.tmc` remain; if an
  explicit family rule is needed, it is placed on the extra and on both Sam
  rules. Existing per-pack uniqueness rules are unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-curation`: document the compatibility and consumer actions of a curated
  source transition without treating matching package IDs as upgrade proof.

## Impact

Expected changes are extras/composition/overlay configuration as needed,
curation outcome fixtures, consumer guidance, generated packs and README.
Validation observations belong in this change directory. No new resolver,
source adapter or device access is required; no dependency on Quiver is needed.

Estimate: 1 modified requirement, 2 added scenarios, 0-30 production-code
lines, 30-100 configuration lines and 60-120 test lines. Per-app decisions stay
in configuration and tests, not normative requirements.

A visible failure plus rerun cannot settle signing compatibility or restore a
user's save after an incompatible fork switch. Dated primary APK observations
and explicit migration guidance are therefore necessary evidence; no new retry,
race or diagnostic-format requirement is introduced.
