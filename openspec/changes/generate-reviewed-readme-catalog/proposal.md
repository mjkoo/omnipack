## Why

Routine pack builds currently scrape a README and inspect release APKs to create
source entries. Moving that work into a separate, reviewed catalog update keeps
automatic onboarding while letting nightly use accepted JSON independently of
README and APK availability.

## What Changes

- Add deterministic README-to-Obtainium catalog generation with automatic
  package-ID resolution, preserving the existing resolver and credential rules.
- Add a separate scheduled and manually dispatched workflow. Changed README
  bytes produce or update one source PR containing catalog, source hash and
  resolution state; identical accepted bytes skip generation. Manual forced
  refresh supports release changes without README changes.
- Block incomplete new-project generation, retain accepted entries on refresh
  failures with diagnostics, and leave the accepted source hash unchanged until
  merge. Failed runs are retried by later invocations.
- **BREAKING**: Build codm2000 candidates from committed Obtainium JSON instead
  of scraping or resolving APKs during `pack build`. Preserve source provenance,
  dual-screen coverage, preference, composition rules and curated overrides.
- **BREAKING**: Remove package-ID cache writes from nightly's publication scope
  and move resolution diagnostics to the generation operation.
- Validate proposed catalogs and their composed pack effects before PR writes;
  preserve captured export regressions during migration.

## Capabilities

### New Capabilities

- `readme-source-generation`: Automatic catalog generation, accepted source
  state, failure handling and the separate catalog-update PR workflow.

### Modified Capabilities

- `source-ingestion`: Read committed codm2000 JSON and retain device-aware
  coverage; transfer README resolution and cache responsibilities to generation.
- `pack-cli`: Expose catalog generation and remove build-time resolution,
  cache persistence and resolution-attempt reporting obligations.
- `nightly-publishing`: Publish only verified pack outputs and the generated
  README section; treat the source catalog and resolver state as read-only inputs.

## Impact

Affects the codm adapter, ingestion orchestration, resolver integration, CLI,
build reports, source configuration, committed catalog/state, nightly path
guards, a new Actions workflow, tests and operator documentation. Automatic
resolution remains GitHub latest-release APK inspection; no new runtime
dependency is required by this design.

## Non-goals

Do not remove automatic resolution, add manual package-ID onboarding, redesign
composition or its historical registry, replace structural publication evidence,
or change release synchronization. Do not auto-merge catalog PRs, write directly
to main from generation, alter repository protections, or perform external PR,
release or issue writes while implementing or validating this change.
