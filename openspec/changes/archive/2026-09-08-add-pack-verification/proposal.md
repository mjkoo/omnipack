## Why

The pack pipeline produces importable files but cannot yet establish whether
their configured update sources still resolve. Verification is needed before
nightly automation can safely publish refreshed packs and before maintainers can
identify version-format problems from evidence.

## What Changes

- Implement `pack verify` for offline validation of both rendered files and
  their local configuration; run the same checks before a build replaces output.
- Implement `pack verify --live` for GitHub and HTML source resolution using
  the entries' configured release, link, APK and version settings. Installable
  entries must resolve a nonempty version and at least one eligible APK candidate;
  track-only entries require a version without requiring an APK. Download
  reachability is an explicit `--probe-assets` diagnostic, not the live default.
- Reuse release metadata across variants, pace necessary requests, require
  configured GitHub authentication, and conditionally revalidate cached metadata.
  Stop contacting rate-limited hosts for the remainder of a run.
- Cover the resolution settings exercised by the existing packs, including
  prereleases, older-release fallback, HTML intermediate pages, release titles,
  release dates and regex group substitution. Reject active unsupported
  resolution behavior instead of silently ignoring it.
- Lint effective GitHub versions after extraction. Report suspicious formats as
  non-blocking warnings; a regex or title setting alone is not an exemption.
- Add structured verification diagnostics separate from the build report and
  implement `pack report` to display both, including whether verification
  corresponds to the current output and configuration.
- Add fixture coverage, offline CI verification and documentation of the
  guarantee and its limits.

## Capabilities

### New Capabilities

- `pack-verification`: rendered-output validation, live metadata resolution,
  opt-in bounded download reachability, effective-version lint, and evidence.

### Modified Capabilities

- `pack-cli`: offline build gating, standalone verification and report commands.

## Impact

Implements `verify.py` and the remaining CLI stubs; adds focused resolver modules
and report formatting; extends `build.py`, `http.py`, tests, CI and documentation.
Adapt useful RJNY verifier helpers with recorded origin and attribution, checking
semantics against the repository's Obtainium v1.6.14 baseline. Keep the existing
standard-library runtime dependency policy.

Verification is read-only with respect to distribution files, overlays and the
package-id cache. Reports remain uncommitted under `.build/`. Existing generated
package-id discovery and its soft-failure policy remain unchanged.

## Non-goals

Nightly workflows, git or GitHub publishing, APK manifest verification for the
whole pack, installation tests, signature checks, per-device compatibility,
automatic overlay repairs and support for additional Obtainium source types.
