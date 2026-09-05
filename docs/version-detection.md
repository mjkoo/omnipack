# Version detection in Obtainium imports

Obtainium shows an update when the recorded installed version differs from
the latest version after reconciliation. Reconciliation needs both strings
to share a standard numeric format (`1.2.3`, `1.2.3-beta1`, ...); a `v`
prefix reconciles. Tags like `continuous` or dates never reconcile.

On every import, Obtainium resets `installedVersion` to the OS-reported
versionName, so an app whose recorded and latest versions were already equal
before the import will show one spurious update right after it. There is no
export setting that avoids this; it comes from the reset itself.

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
  still detected as updates. This still shows one spurious update after
  every re-import, same as the numeric case; nothing avoids that.
- **Multiple APKs per release**: `apkFilterRegEx` (e.g. `app-release`) so a
  debug build is never selected.
- **Prerelease tags that aren't app builds** (e.g. a dependency-bump tag):
  keep `includePrereleases: false` so they're ignored entirely.

## Lint

The build's version-format lint flags any GitHub-sourced app whose latest
version does not match a standard numeric format, unless the entry already
opts out via `versionDetection: false`, `releaseDateAsVersion`,
`releaseTitleAsVersion`, or a `versionExtractionRegEx`. This list is the
backlog to declare per-app fixes against in the overlay.
