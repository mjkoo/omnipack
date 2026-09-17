# Version detection in Obtainium imports

Update detection depends on the installed version and the effective upstream
version after Obtainium's reconciliation. Matching numeric formats such as
`1.2.3` and `v1.2.3` can help, but numeric syntax alone does not prove agreement
with an APK's versionName. A re-import does not necessarily cause a spurious
update for every numeric version. Rolling tags and date versions need deliberate
configuration and device testing.

## Recipes

- **Numeric tag matching versionName** (`1.2.3`, `v1.2.3`): no override
  needed.
- **Descriptive tag with a numeric app version**: use `versionExtractionRegEx`
  with `matchGroupToUse` only when removed labels do not distinguish builds.
  Preserve suffix-only builds through explicit source-version tracking
  (`versionDetection: false`) when APK versions cannot represent them.
- **Version only in the release title**: `releaseTitleAsVersion: true`,
  usually paired with an extraction regex.
- **Rolling tag** (`continuous`, `nightly`, `latest`): `releaseDateAsVersion:
  true` (optionally `useLatestAssetDateAsReleaseDate`) so new builds are
  still detected as updates. This intentionally compares a source observation
  date rather than claiming a match with the installed APK's versionName.
- **Multiple APKs per release**: `apkFilterRegEx` (e.g. `app-release`) so a
  debug build is never selected.
- **Prerelease tags that aren't app builds** (e.g. a dependency-bump tag):
  keep `includePrereleases: false` so they're ignored entirely.

## Validation and maintenance

`pack verify` validates setting types and local structural consistency. It does
not resolve releases, evaluate extraction patterns, classify effective versions,
or lint numeric formats. Unsupported arguments fail before verification. A
verification report with any schema other than the current one requires
regeneration with `uv run pack verify`.

The recipes above describe intended Obtainium behavior. Check changed release
selection and extraction in Obtainium, retain dated observations, and maintain
explicit overlays so upstream refreshes cannot replace curated settings.
Fixture-driven composition and rendering tests assert the exported policies.

Use `uv run pack report` to inspect structural evidence and its local freshness.
A successful result does not prove upstream health, APK version agreement, or
notification behavior. See [verification](verification.md) for the checks and
[maintained curation](curation.md) for per-app evidence and source-tracking
re-import and unchanged-tag asset-replacement limitations.
