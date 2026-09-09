## Why

The committed packs produce 23 version-format warnings across 12 package ids.
Release and APK inspection shows a mixture of removable labels, valid integer
versions rejected by the lint heuristic, and build identifiers that must remain
distinct even when APK version names do not distinguish them. The planned
Cinderbox addition is also still absent.

## What Changes

- Add Cinderbox to both variants with its verified package identity, numeric
  release versions, and prereleases excluded.
- Use numeric extraction for BanjoRecomp and SymphonyRecomp, and numeric tags
  instead of release titles for both Cemu variants.
- Explicitly use source-version tracking for eight apps whose release identities
  carry information that APK version names cannot safely represent. Preserve
  their complete selected version strings and keep update checks enabled.
- Accept single-component numeric versions in the existing lint heuristic,
  covering RPCSX without changing its release configuration.
- Record per-app rationale, observed APK metadata, upstream package-id
  mismatches, and re-import limitations in durable curation documentation.
- Regenerate both import files and validate the policies against captured
  release histories and fresh metadata verification.

## Capabilities

### New Capabilities

- `pack-curation`: maintained app additions and version policies expressed
  through extras and overlays, with evidence and documented limitations.

### Modified Capabilities

- `pack-verification`: accept one or more numeric components in the
  numeric-shape heuristic while retaining its other classifications and limits.

## Impact

Changes affect `config/extras.json`, the common overlay, distribution files,
version-lint classification and verifier identity, focused regression fixtures,
and curation/verification documentation. Existing source ingestion, precedence,
HTTP policy, report schema, and nightly orchestration remain sufficient.
No dependency or new CLI option is required.

## Non-goals

isle-portable, package-id migrations, changing APK selection, expanding the
catalog beyond Cinderbox, changing pack-wide settings, probing every download
nightly, or claiming zero spurious updates after every re-import. The four
observed package-id mismatches require a separate identity/migration decision.
