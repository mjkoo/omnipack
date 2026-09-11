## Why

Routine pack builds currently scrape a README and inspect release APKs to create
source entries. Moving that work into a separate, reviewed catalog update keeps
automatic onboarding while letting nightly use accepted JSON independently of
README and APK availability.

## What Changes

- Add deterministic README-to-Obtainium catalog generation with automatic
  package-ID resolution and reviewed per-project discovery settings. Keep
  stable releases as the default; explicitly support prerelease APKs for
  EmuLnk, Showdown-DS and Heimdall without hardcoded package-ID onboarding.
- Represent Kanto Gear as a clearly labeled, dual-screen track-only resource.
  Its Lua mod is installed through the already included Gen1Recomp host;
  Obtainium supplies release notifications, not mod installation or detection.
  Failed APK discovery never implicitly converts an app to track-only.
- Add a separate scheduled and manually dispatched workflow. Changed README
  bytes produce or update one source PR containing catalog, source hash and
  resolution state; identical accepted README and project-policy inputs skip
  generation. Manual forced refresh supports release changes without README
  or policy changes. Automation consumes reviewed policy and cannot modify it.
- Block incomplete new-project generation, retain accepted entries on refresh
  failures with diagnostics, and leave the accepted source hash unchanged until
  merge. Failed runs are retried by later invocations.
- **BREAKING**: Build codm2000 candidates from committed Obtainium JSON instead
  of scraping or resolving APKs during `pack build`. Preserve source provenance,
  dual-screen coverage, preference, composition rules and curated overrides.
- **BREAKING**: Remove package-ID cache writes from nightly's publication scope
  and move resolution diagnostics to the generation operation.
- Validate proposed catalogs and their composed pack effects before PR writes;
  preserve captured existing selections and bytes, and separately verify the
  intended Showdown-DS, Heimdall and Kanto tracker additions.

## Capabilities

### New Capabilities

- `readme-source-generation`: Automatic catalog generation, accepted source
  state, explicit APK/track-only treatment, discovery policy, failure handling
  and the separate catalog-update PR workflow.

### Modified Capabilities

- `source-ingestion`: Read committed codm2000 JSON and retain device-aware
  coverage; transfer README resolution and cache responsibilities to generation.
- `pack-cli`: Expose catalog generation and remove build-time resolution,
  cache persistence and resolution-attempt reporting obligations.
- `nightly-publishing`: Publish only verified pack outputs and the generated
  README section; treat the source catalog and resolver state as read-only inputs.

## Impact

Affects the codm adapter, ingestion orchestration, resolver integration, CLI,
build reports, reviewed project policy, source configuration, committed catalog/state, nightly path
guards, a new Actions workflow, tests and operator documentation. Automatic
resolution remains GitHub release APK inspection, with bounded prerelease
listing where explicitly configured; no new runtime dependency is required.

## Non-goals

Do not remove automatic APK resolution, add manual APK package-ID onboarding,
add automatic non-APK classification or a mod downloader/installer, redesign
composition or its historical registry, replace structural publication evidence,
or change release synchronization. Do not auto-merge catalog PRs, write directly
to main from generation, alter repository protections, or perform external PR,
release or issue writes while implementing or validating this change.
