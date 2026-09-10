## MODIFIED Requirements

### Requirement: Live checks honor a declared compatibility boundary

The system SHALL provide live GitHub and HTML resolution against the repository's
Obtainium v1.6.14 compatibility baseline. It SHALL document supported settings
and explicit device-independent limitations. It SHALL support the release and
HTML behavior specified below and SHALL reject active unsupported resolution
features with the setting and entry identified, rather than ignoring them.

Unsupported features SHALL include archives other than GitHub ZIP asset selection, non-date/non-none GitHub
sorting, request proxies, embedded credentials, disabled TLS
verification, device-dependent HTML intermediate filtering, and HTML
pseudo-versioning without explicit version extraction. Inactive defaults SHALL
not activate unsupported features. Unknown additional settings SHALL produce a
live compatibility error unless explicitly classified as harmless presentation
or device controls. Final device architecture filtering and preferred APK
selection SHALL be outside the guarantee and SHALL be identified as such.

#### Scenario: Unsupported feature is enabled

- **WHEN** an HTML entry enables ZIP downloads
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
title and notes filters, older-release fallback, direct APK assets, enabled GitHub
ZIP outer assets, outer-asset filename regex filtering and inversion, title
versions and release/asset dates according to the pinned provider. With
older-release fallback disabled, only the first non-draft release permitted by
the prerelease setting in the final prioritized order SHALL be considered; a
title, notes or eligible outer-asset mismatch SHALL fail rather than advance to
another release.

An installable entry SHALL select a release with eligible outer-asset candidates
and a nonempty version. An eligible candidate SHALL be a direct APK, or a GitHub
ZIP when `includeZips` is true. Metadata selection SHALL treat the ZIP itself as
the candidate and SHALL NOT inspect or assert the presence of an archive member.
A track-only entry SHALL apply the same configured filtering without requiring an
outer asset, and SHALL use the pinned provider's tags fallback when no release
qualifies. A network failure SHALL NOT trigger tags fallback. Once metadata
selects a release, failed reachability SHALL NOT select an older one.

#### Scenario: Latest eligible release has no matching APK

- **WHEN** fallback is enabled and an older release has a matching direct APK or
  enabled GitHub ZIP
- **THEN** resolution selects the older release and records its identity

#### Scenario: Title filter fails with fallback disabled

- **WHEN** the first non-draft, permitted-prerelease release fails the title filter
- **THEN** resolution fails even if a later inspected release matches

#### Scenario: Track-only resource has no APK

- **WHEN** an eligible release supplies a valid effective version but no APK or ZIP
- **THEN** a track-only entry passes resolution without a download probe

#### Scenario: Selected release has dead downloads

- **WHEN** asset probing is explicitly enabled and every eligible outer-asset
  candidate in the selected release is unreachable
- **THEN** the entry fails even if an older release has a reachable APK or ZIP

### Requirement: Reachability checks are bounded and do not prove binary identity

Ordinary live verification SHALL require successful metadata resolution, a
nonempty effective version and eligible outer-asset candidates for installable
entries, without requesting those downloads or claiming reachability. An eligible
outer candidate SHALL be a direct APK, or a GitHub ZIP when `includeZips` is true.
Ordinary live verification of a ZIP SHALL NOT inspect archive members or claim
that `zippedApkFilterRegEx` matches a member. Only when asset probing is explicitly
enabled SHALL an installable entry additionally require at least one selected
eligible outer candidate to respond to a bounded GET with status 200 or 206 and a
nonempty response prefix. For a selected ZIP, the probe SHALL request the outer
ZIP itself and SHALL NOT decompress or inspect it. The system SHALL read at most
1024 response-body bytes per probe and close the response, including when the
server ignores Range. It SHALL NOT require HEAD support or download a whole APK
or ZIP. The system SHALL report attempted candidate failures as warnings when
another candidate succeeds, and as an entry failure when none succeeds.
Track-only entries SHALL not require download probes.

The diagnostic guarantee SHALL be described as source resolution and HTTP
reachability, without asserting APK identity, signatures, installability,
architecture coverage, archive-member presence or correctness of a server's
content. A probe SHALL use at most three attempts with bounded backoff and a
30-second per-request timeout, and follow at most ten redirects. Metadata
responses SHALL be limited to 10 MiB. Exhausted failures SHALL be errors and
SHALL NOT be replaced by a prior run's success.

#### Scenario: Server ignores Range

- **WHEN** an APK or ZIP endpoint responds with 200 and a body larger than the
  probe limit
- **THEN** the probe reads only its prefix, closes the response and can pass

#### Scenario: One candidate succeeds

- **WHEN** the first outer-asset candidate fails and a second candidate in the
  same selected release responds successfully with data
- **THEN** the entry passes with the first failure recorded as a warning

## ADDED Requirements

### Requirement: GitHub ZIP releases expose outer assets with explicit extraction limits

GitHub resolution SHALL admit .zip assets alongside .apk assets only when
includeZips is true, applying apkFilterRegEx and inversion to the outer filename.
It SHALL preserve existing release filtering, ordering and fallback behavior.
A configured zippedApkFilterRegEx SHALL be validated before HTTP and classified
as on-device extraction behavior. Live metadata success SHALL NOT assert that a
matching APK member exists or that its package/signature has been inspected.
HTML and GitLab active archive settings SHALL remain unsupported.

#### Scenario: Official Android release is packaged as a ZIP

- **WHEN** a GitHub release contains Android, desktop and iOS ZIPs and settings
  enable ZIPs with an Android-only outer filter
- **THEN** resolution selects only the Android ZIP and its normal source version
- **AND** the report identifies member extraction as outside metadata verification

#### Scenario: ZIP selection is disabled or its regex is invalid

- **WHEN** ZIPs are disabled
- **THEN** ZIP assets do not satisfy an installable release
- **WHEN** the configured inner member regex is invalid
- **THEN** resolution fails before HTTP rather than claiming extraction support
