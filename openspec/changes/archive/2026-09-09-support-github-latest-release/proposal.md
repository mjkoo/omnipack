## Why

Seven apps across thirteen entries in the committed packs enable `verifyLatestTag`,
which live verification currently rejects. Supporting this existing configuration
removes a known compatibility blocker before nightly publishing is introduced.

## What Changes

- Support GitHub latest-release prioritization under `verifyLatestTag`, following
  the repository's Obtainium v1.6.14 baseline while retaining existing filters,
  version processing, and fail-closed HTTP policy.
- Allow the separately fetched latest release to supplement the first 100
  release-list results, with truthful inspection counts.
- Specify latest-endpoint failures and the interaction with track-only tags
  fallback, including the baseline's `/tags/latest` request.
- Reuse latest metadata through the existing live HTTP client and retain
  independent selection and evidence per variant.
- Update compatibility documentation, regression coverage, and verifier identity.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-verification`: support latest-release prioritization, its bounded
  supplementary lookup, and its failure and fallback behavior.

## Impact

Changes are limited to the GitHub resolver, setting classification, verification
identity, verification tests and fixtures, and verification documentation.
No runtime dependency, CLI flag, report schema, or pack configuration change is
needed. Active `verifyLatestTag` entries can resolve instead of immediately
failing compatibility checks; upstream or selection failures remain errors.

## Non-goals

Nightly automation, publishing, overlay curation, other unsupported settings,
new source types, download policy changes, and a compatibility-baseline upgrade.
