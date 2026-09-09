## MODIFIED Requirements

### Requirement: Live checks honor a declared compatibility boundary

The system SHALL provide live GitHub and HTML resolution against the repository's
Obtainium v1.6.14 compatibility baseline. It SHALL document supported settings
and explicit device-independent limitations. It SHALL support the release and
HTML behavior specified below and SHALL reject active unsupported resolution
features with the setting and entry identified, rather than ignoring them.

Unsupported features SHALL include archive downloads, non-date/non-none GitHub
sorting, request proxies, embedded credentials, disabled TLS
verification, device-dependent HTML intermediate filtering, and HTML
pseudo-versioning without explicit version extraction. Inactive defaults SHALL
not activate unsupported features. Unknown additional settings SHALL produce a
live compatibility error unless explicitly classified as harmless presentation
or device controls. Final device architecture filtering and preferred APK
selection SHALL be outside the guarantee and SHALL be identified as such.

#### Scenario: Unsupported feature is enabled

- **WHEN** an entry enables ZIP downloads
- **THEN** live verification reports unsupported resolution behavior
- **AND** it does not pass the entry by checking only a direct APK

#### Scenario: Inactive HTML pseudo-version default

- **WHEN** an HTML entry successfully extracts an explicit version and retains
  its default pseudo-versioning setting
- **THEN** that unused default does not cause a compatibility error

### Requirement: GitHub resolution respects configured release selection

The system SHALL inspect up to the first 100 release-list results and report
the inspected window. With `verifyLatestTag` enabled, a separately fetched latest
release absent from that list SHALL additionally be eligible, so at most 101
release records can be considered. The reported `window_limit` SHALL remain 100
for the list request; `inspected_count` SHALL count those list results plus one
when the latest release supplements them. Matching an existing result SHALL NOT
increment the count. Tags fallback SHALL retain this release inspection count.
The system SHALL support `date` and `none` ordering, draft/prerelease eligibility,
title and notes filters, older-release fallback, direct APK assets, APK filename
regex filtering and inversion, title versions and release/asset dates according
to the pinned provider. With older-release fallback disabled, only the first
non-draft release permitted by the prerelease setting in the final prioritized
order SHALL be considered; a title, notes or APK mismatch SHALL fail rather than
advance to another release.

An installable entry SHALL select a release with eligible APK candidates and a
nonempty version. A track-only entry SHALL apply the same configured filtering
without requiring an APK, and SHALL use the pinned provider's tags fallback when
no release qualifies. A network failure SHALL NOT trigger tags fallback. Once
metadata selects a release, failed reachability SHALL NOT select an older one.

#### Scenario: Latest eligible release has no matching APK

- **WHEN** fallback is enabled and an older release has a matching APK
- **THEN** resolution selects the older release and records its identity

#### Scenario: Title filter fails with fallback disabled

- **WHEN** the first non-draft, permitted-prerelease release fails the title filter
- **THEN** resolution fails even if a later inspected release matches

#### Scenario: Track-only resource has no APK

- **WHEN** an eligible release supplies a valid effective version but no APK
- **THEN** a track-only entry passes resolution without a download probe

#### Scenario: Selected release has dead downloads

- **WHEN** asset probing is explicitly enabled and every eligible APK candidate
  in the selected release is unreachable
- **THEN** the entry fails even if an older release has a reachable APK

## ADDED Requirements

### Requirement: GitHub latest metadata prioritizes release selection

When `verifyLatestTag` is true, the system SHALL fetch the repository's
`/releases/latest` metadata before its release list. A latest response SHALL be
an object with a nonempty string identity from `tag_name`, or from `name` when
`tag_name` is absent or null. Other shapes or invalid identities SHALL fail as
invalid metadata. Identity comparison SHALL be exact, without trimming, case
folding, version extraction, or numeric reconciliation.

The system SHALL use the release-list record when that identity is already in
the bounded list; otherwise it SHALL supplement the list with the latest record.
After configured ordering, the matching record SHALL be moved to the first
selection position while preserving the relative order of the other records.
Draft/prerelease eligibility, title/notes/APK filters, older-release fallback,
and version processing SHALL still apply to the resulting order. A false or
absent `verifyLatestTag` SHALL cause no latest-endpoint request or prioritization.

Any latest-endpoint HTTP failure, including 404, transport failure, or invalid
metadata SHALL fail that entry without proceeding to its list request or using
ordinary ordering or stale evidence as a substitute. These requests SHALL use
the existing authentication, pacing, retry, response-bound, and cache policy;
identical latest responses and failures SHALL be reused across variants without
sharing selection decisions between different settings.

For track-only entries, no qualifying release after successful acquisition SHALL
still permit tags fallback. With `verifyLatestTag` enabled, that fallback SHALL
first request `/tags/latest`, then `/tags?per_page=100`, applying the same identity,
supplementation, prioritization, failure, and configured selection rules to tags.
This endpoint behavior follows the compatibility baseline; a failed
`/tags/latest` SHALL fail the entry without fetching the tag list. With the setting
disabled, the existing tags fallback SHALL remain unchanged. Failure to extract
a version or requested date after selecting a record SHALL NOT initiate fallback.

#### Scenario: GitHub latest differs from date ordering

- **WHEN** GitHub identifies an older listed release as latest and a newer release
  would otherwise sort first
- **THEN** the listed record matching latest is evaluated first, with its list
  metadata retained even if the separate latest response has different assets
- **AND** the remaining release order is unchanged

#### Scenario: Latest release lies outside the list window

- **WHEN** the first 100 release results omit the latest response's identity
- **THEN** that response supplies the first candidate without another list page
- **AND** successful evidence reports an inspected count of 101 and window limit 100

#### Scenario: Latest release fails configured filters

- **WHEN** the prioritized eligible release fails a title, notes, or APK filter
- **THEN** enabled older-release fallback permits later candidates in their
  configured order, and disabled fallback fails release selection

#### Scenario: Latest response uses a name identity

- **WHEN** the latest object has no tag name and has a nonempty string name
- **THEN** identity matching uses that name, comparing list identities by the
  same tag-name-or-name rule

#### Scenario: Latest acquisition fails

- **WHEN** the latest endpoint returns 404, invalid JSON, a non-object, an invalid
  identity, or a transport failure
- **THEN** that entry fails with an endpoint-specific diagnostic
- **AND** it does not request the release list or attempt tags fallback

#### Scenario: Track-only tags fallback retains latest checking

- **WHEN** latest and release-list acquisition succeed but no release qualifies
  for a track-only entry with latest checking enabled
- **THEN** tags fallback requests `/tags/latest` before the tag list
- **AND** a failure at that endpoint fails the entry without a tag-list request

#### Scenario: Latest checking is disabled in one variant

- **WHEN** two variants share a repository and only one enables latest checking
- **THEN** each uses its own resulting release order and evidence
- **AND** the release-list response is shared, while only the enabled variant
  requires latest metadata
