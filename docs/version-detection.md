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
- **Numeric tag, different shape from versionName** (e.g. `v1.2.3-r5` vs.
  APK versionName `1.2.3`): `versionExtractionRegEx` with `matchGroupToUse`
  to cut the tag down to the versionName's shape.
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

## Lint

`pack verify --live` lints the effective GitHub version after successful
extraction. Its anchored heuristic accepts an optional `v` or `V`, at least
two dot-separated numeric components, and optional `-` prerelease and `+`
build suffixes made of ASCII letters, digits, dots, or hyphens. Examples include
`1.2`, `v1.2.3-beta1`, and `1.2.3+build.4`.

Track-only entries, disabled version detection, and intentional date versions
have distinct classifications without numeric-shape warnings. A title or regex
setting alone is not an exemption: an extracted `continuous` still warns.
Warnings do not fail verification; extraction failures do. Offline builds
perform structural validation and do not run this live lint.

Review findings with `uv run pack report`. Treat the warning list as evidence
for deliberate configuration changes, not automatic overlay repairs. See
[verification](verification.md) for the compatibility boundary and report freshness.
