## Why

Source precedence currently lets an ordinary build displace a dual-specific
fork, and package-id-only coverage cannot describe replacements with different
Android identities. Both collections need predictable device-aware selection
while preserving curation across upstream refreshes.

## What Changes

- Select one build per logical app family and device target. Single selects an
  eligible standard build; dual prefers a dual-specific build and otherwise
  uses an eligible standard build. Explicit maintainer selections override
  preference, with source precedence used only within the selected tier.
- Preserve upstream candidates and device intent through ingestion. Group
  different package ids only through explicit family declarations, and apply
  evidenced identity corrections before selection.
- Distinguish package exclusions from whole-family exclusions, apply them before
  selection, and fail on unresolved selection ties or output package collisions.
- **BREAKING**: Replace package-id superset validation with app-family coverage,
  and migrate overlays to package-id-and-project selectors. Patches cannot
  redirect a selected build or change its identity.
- Explain winners, fallbacks, alternatives, exclusions and identity changes in
  reports; validate local family constraints and fingerprint the new policy.
- Keep publication fail-closed for selected-build verification failures, without
  automatically switching forks. Document device migration limits.

## Capabilities

### New Capabilities

None. These changes extend existing ingestion, composition and verification.

### Modified Capabilities

- `source-ingestion`: Preserve candidate eligibility and dual preference;
  retain BBoi alternatives and resolve generated coverage after policy overrides.
- `pack-composition`: Explicit families, identity corrections, candidate pins,
  suitability-first selection, exclusions, build-bound patches and family coverage.
- `pack-cli`: Explain device-aware selections and policy errors in build reports.
- `pack-verification`: Validate serialized family constraints and build-bound
  overlay targets, including the composition policy in evidence fingerprints.

## Impact

Changes affect the normalized model, source adapters, composition, overlay
configuration, offline validation, reports and their tests. A new committed
composition policy and migrated overlays accompany regenerated import files.
Obtainium's JSON shape, CLI commands, release resolvers, HTTP policy and nightly
publication allowlist remain unchanged. No new runtime dependency is planned.

Known identity conflicts must be assessed when establishing initial family rules;
the change does not claim an automatic package/signature or device-data migration.
Unrelated forks are not grouped merely because they share an upstream ancestor.

The optional Ludashi update is deferred: the observed
[v4.0 release](https://github.com/StevenMXZ/Winlator-Ludashi/releases/tag/v4.0)
states that it cannot install as an update over the previous build. Updating its
APK filter therefore requires a separate flavor, identity and device-migration
decision, rather than a small version-only task. Preserve its current release
selection and source-version policy during this change.
