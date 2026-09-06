## Why

Three upstream Obtainium catalogs cover overlapping sets of emulation and
decomp/recomp apps, none of them is complete, and several entries carry
version-detection settings that make Obtainium report an update on every
check. Fixing those settings by hand does not survive the next upstream
refresh. This change builds the pipeline that turns those catalogs plus a
few hand-added apps into two import files, `single-screen.json` and
`dual-screen.json`, so that a committed overlay of per-app fixes is
reapplied on every rebuild.

This is the first of three changes. It covers fetching, composing and
rendering the packs. Verification (offline schema checks, live APK
resolution, the update-thrash lint) and the nightly rebuild workflow follow
in later changes.

## What Changes

- Fetch and normalize four sources into per-variant entries:
  - RJNY `src/applications.json` from `main` (76 entries, 72 unique ids),
    honouring its `meta` export flags.
  - BBoi34's latest Codeberg release assets, `Decomp-Recomp.V*.json` (25
    entries) and `Dual-Screen-Decomp-Recomp.V*.json` (7 entries).
  - codm2000's README, scraped for GitHub project links. 24 of its 28 links
    are GitHub repositories; those a higher-precedence source already
    contributes to the dual-screen variant are dropped and the rest become
    generated entries whose package id is read from the latest release APK.
    Non-GitHub rows have no APK feed and are skipped.
  - Hand-written entries from `config/extras.json`, contributing to both
    variants unless the entry names the variants it applies to.
- Resolve package ids for generated entries by parsing the Android manifest
  out of the release APK, cached in `config/package-ids.json` keyed by the
  project's normalized URL and recording the host-assigned identifier of the
  release each id was resolved from rather than its tag name, so nightly runs
  stay cheap. A project is resolved again when its latest release identifier
  differs from the cached one. Failure to read that identifier, a release with
  no eligible APK, disagreement between APK package ids, or any unreadable APK
  retains the cached id and reports the failure when an id is cached; otherwise
  the project is reported as unresolved and contributes no entry. Failed
  resolution preserves both the cached id and its release identifier so later
  builds retry the unresolved release.
  A generated entry is named for the repository in its project link and carries
  no category.
- Compose each variant independently, in a fixed stage order: union keyed by
  package id with precedence extras > RJNY > BBoi > generated, then a denylist
  naming a package id and optionally the one variant it applies to, whose
  entries matching nothing are reported as stale exclusions rather than failing
  the build, then overlay target validation, then a JSON Merge
  Patch (RFC 7386) overlay applied from `config/overlay.json` for both
  variants and `config/overlay.dual.json` for dual only, whose patch must be an
  object and may contain neither the package-id field nor the source-type field
  in any form, a merge-patch deletion included, then the dual-screen
  coverage check. The common overlay must name an id present in at least one
  composed variant and the dual-screen overlay one present in the composed
  dual-screen variant; an overlay naming an id present nowhere fails the
  build.
- Render both variants to `dist/` in Obtainium's import format:
  `additionalSettings` hydrated with the full default key set and encoded as
  a JSON string, deterministic entry order, and a settings block combining
  `config/settings.json` with the union of categories.
- Add `pack build` as the command that drives fetch, compose, render and
  write.

Resolving a package id per variant rather than once per id is a correction
to the original sketch. Verification against upstream showed a single id can
legitimately need different content per variant: RJNY's `info.cemu.cemu`
points at `SSimco/Cemu` for single-screen and `sapphirerhodonite/cemu` for
dual-screen, and four BBoi ids differ between its two files in category,
name or `apkFilterRegEx`. A model holding one entry per id with a set of
variant memberships cannot express that, so composition runs per variant.

## Capabilities

### New Capabilities

- `source-ingestion`: fetching each upstream catalog and normalizing it into
  per-variant entries, including package-id resolution and caching for
  generated entries.
- `pack-composition`: combining normalized entries into one entry set per
  variant, covering precedence, the denylist and overlay application.
- `pack-rendering`: serializing a composed variant into Obtainium's import
  format, covering settings hydration, ordering and the settings block.
- `pack-cli`: the `pack` command-line surface. This change adds `pack build`.

### Modified Capabilities

None. This is the project's first change.

## Impact

- Implements the stub modules under `src/obtainium_pack/`: `model.py`,
  `sources/`, `package_id.py`, `merge.py`, `overlay.py`, and the `build`
  path of `cli.py`. `verify.py` stays unimplemented until the next change.
- Adds no runtime dependency; fetching goes through a small internal HTTP
  helper built on the standard library, including the vendored resolver's
  release metadata, ranged APK reads and full asset downloads.
  `config/http.json` contains a `credentials` map from exact host to token
  environment-variable name, defaulting to `api.github.com` -> `GITHUB_TOKEN`.
  Unset or empty variables leave requests unauthenticated; tokens are sent only
  to their registered hosts and dropped across a cross-host redirect.
- Writes `dist/single-screen.json` and `dist/dual-screen.json`, updates the
  `config/package-ids.json` cache as a build side effect, and writes the build
  report as JSON to the uncommitted path `.build/report.json`.
- Vendors RJNY's APK manifest parser with attribution, under that project's
  licence.
- Depends on upstream shapes that can change without notice, so every fetch
  failure aborts the build rather than emitting a partial pack.
