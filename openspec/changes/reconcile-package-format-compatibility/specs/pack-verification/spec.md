## MODIFIED Requirements

### Requirement: Live checks honor a declared compatibility boundary

The system SHALL retain live GitHub and HTML resolution against the repository's
Obtainium v1.6.14 compatibility baseline and add native public GitLab resolution
against the bounded Obtainium v1.6.15 GitLab adapter behavior. It SHALL document supported settings
and explicit device-independent limitations. It SHALL support the release and
HTML behavior specified below and the native public GitLab requirements and SHALL reject active unsupported resolution
features with the setting and entry identified, rather than ignoring them.

Unsupported features SHALL include active generic ZIP-selection or archive-member
extraction settings outside GitHub ZIP asset selection, non-date/non-none GitHub
sorting, request proxies, embedded credentials, disabled TLS
verification, device-dependent HTML intermediate filtering, and HTML
pseudo-versioning without explicit version extraction. Inactive defaults SHALL
not activate unsupported features. Unknown additional settings SHALL produce a
live compatibility error unless explicitly classified as harmless presentation
or device controls. Final device architecture filtering and preferred APK
selection SHALL be outside the guarantee and SHALL be identified as such.

GitLab support SHALL be limited to explicit installable public gitlab.com project
entries with release-tag versions, APK filtering, optional version extraction
and older-release fallback. GitLab resolution SHALL include named asset links
and project-upload APK links in release descriptions, and inspect at most 100
releases in API order. Active GitLab options outside this boundary SHALL fail
before HTTP; inactive defaults SHALL be classified explicitly. Public GitLab
requests SHALL work without a token under the shared exact-host credential,
request-bound, evidence and optional-probe guarantees. Adding GitLab SHALL NOT
relax the existing GitHub credential requirement or HTML compatibility checks.


Recognized Android package containers SHALL include `.apk`, `.xapk`, `.apkm`
and `.apks`, compared without regard to extension case, under each provider's
selection rules below. Their recognition SHALL NOT depend on `includeZips`.
Acceptance of an outer package container SHALL NOT assert member presence,
extraction, package identity, signatures or installability. Generated package-id
discovery SHALL retain its separate `.apk`-only manifest-resolution contract.

#### Scenario: Unsupported feature is enabled

- **WHEN** an HTML or GitLab entry enables ZIP downloads
- **THEN** live verification reports unsupported resolution behavior
- **AND** it does not pass the entry by checking only a direct APK

#### Scenario: Inactive HTML pseudo-version default

- **WHEN** an HTML entry successfully extracts an explicit version and retains
  its default pseudo-versioning setting
- **THEN** that unused default does not cause a compatibility error

#### Scenario: Supported native GitLab entry dispatches to GitLab resolution

- **WHEN** offline verification passes for an installable GitLab entry using supported settings
- **THEN** live verification uses native GitLab release resolution and retains separate per-variant evidence without requiring a public GitLab token

### Requirement: GitHub resolution respects configured release selection

The system SHALL inspect up to the first 100 release-list results and report
the inspected window. With `verifyLatestTag` enabled, a separately fetched latest
release absent from that list SHALL additionally be eligible, so at most 101
release records can be considered. The reported `window_limit` SHALL remain 100
for the list request; `inspected_count` SHALL count those list results plus one
when the latest release supplements them. Matching an existing result SHALL NOT
increment the count. Tags fallback SHALL retain this release inspection count.
The system SHALL support `date` and `none` ordering, draft/prerelease eligibility,
title and notes filters, older-release fallback, recognized Android package assets, enabled GitHub
ZIP outer assets, outer-asset filename regex filtering and inversion, title
versions and release/asset dates according to the pinned provider. With
older-release fallback disabled, only the first non-draft release permitted by
the prerelease setting in the final prioritized order SHALL be considered; a
title, notes or eligible outer-asset mismatch SHALL fail rather than advance to
another release.

An installable entry SHALL select a release with eligible outer-asset candidates
and a nonempty version. An eligible candidate SHALL have an asset name ending in `.apk`, `.xapk`,
`.apkm` or `.apks`, compared without regard to case, or `.zip` when `includeZips`
is true. Filename regex filtering and inversion SHALL apply to that asset name. Metadata selection SHALL treat the ZIP itself as
the candidate and SHALL NOT inspect or assert the presence of an archive member.
A track-only entry SHALL apply the same configured filtering without requiring an
outer asset, and SHALL use the pinned provider's tags fallback when no release
qualifies. A network failure SHALL NOT trigger tags fallback. Once metadata
selects a release, failed reachability SHALL NOT select an older one.

#### Scenario: Latest eligible release has no matching APK

- **WHEN** fallback is enabled and an older release has a matching recognized package or
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

#### Scenario: Package container is eligible without generic ZIP selection

- **WHEN** an eligible GitHub release has an XAPK, APKM or APKS asset matching the configured filename filter and `includeZips` is false
- **THEN** the container can satisfy installable release selection while a generic ZIP cannot
- **AND** metadata success does not claim that an inner APK was inspected

### Requirement: HTML resolution follows the configured path

At each HTML link-selection stage, absent a nonempty custom-link filter, the
system SHALL choose the link URL, or the link text when text filtering is
enabled, percent-decode that chosen value, parse it as a URL, and retain the
link when the parsed path ends in `.apk`, `.xapk`, `.apkm` or `.apks`, without
regard to extension case. A nonempty custom-link filter SHALL replace that
extension filter. The final APK regex and inversion SHALL still filter the
selected URLs. A custom filter admitting another URL SHALL NOT imply archive
extraction support or prove the response contains a package.

The system SHALL support anchor and link-text filtering, relative URLs resolved
against final response URLs, links outside anchor tags including JSON strings,
configured non-secret request headers, intermediate steps, alphanumeric and
last-segment sorting, skip/reverse sorting, custom link filters, APK filters and
inversion, and URL/whole-page version extraction. Intermediate entries with empty
custom-link filters SHALL be ignored, matching the pinned provider. Each remaining
step SHALL select the last link after its configured filtering and sorting. More than ten
nonempty intermediate steps SHALL fail explicitly. When final link selection is
required, the final selected link SHALL be the last remaining candidate and SHALL
be the sole HTML download candidate. An empty selection at an active intermediate
step SHALL fail with the page and stage identified. Installable entries SHALL
require a final download candidate and SHALL fail on an empty final selection.
Track-only entries using whole-page version extraction MAY succeed with a
nonempty effective version and no eligible final download links, but SHALL still
follow all configured active intermediate steps. URL-based version extraction
SHALL require a usable final selected URL, including for track-only entries.

#### Scenario: Two intermediate pages lead to the download

- **WHEN** configured steps select a release directory and then its Android page
- **THEN** the final APK and extracted version come from that traversal
- **AND** links elsewhere on the starting page do not bypass it

#### Scenario: Selected HTML download is unavailable

- **WHEN** asset probing is explicitly enabled and the final selected link fails
  the reachability check
- **THEN** the entry fails without probing an older link as a substitute

#### Scenario: Track-only HTML page has a version but no download links

- **WHEN** configured intermediate traversal reaches a final page with a valid
  whole-page version extraction but no eligible download links
- **THEN** a track-only entry succeeds without a download probe
- **AND** the same configuration on an installable entry fails final selection

#### Scenario: Track-only HTML still requires its extraction input

- **WHEN** a track-only entry has an empty active intermediate selection, or uses
  URL-based extraction without a usable final selected URL
- **THEN** resolution fails rather than bypassing traversal or inventing a URL

#### Scenario: Links are embedded in JSON

- **WHEN** outside-anchor extraction is enabled for a JSON response
- **THEN** string URLs are extracted, resolved and filtered using the entry settings

#### Scenario: HTML custom filter replaces the default package extension filter

- **WHEN** a final HTML page has a versioned download URL without a package extension and a custom-link filter admits it
- **THEN** it can be the selected candidate if final filtering and version extraction succeed
- **AND** with no custom-link filter that URL does not pass the default package-extension filter

#### Scenario: Link-text filtering parses the decoded text as a URL

- **WHEN** text filtering is enabled and decoded link text has a recognized package path followed by a query or fragment
- **THEN** default extension filtering accepts it based on the parsed path suffix

### Requirement: Reachability checks are bounded and do not prove binary identity

Ordinary live verification SHALL require successful metadata resolution, a
nonempty effective version and eligible outer-asset candidates for installable
entries, without requesting those downloads or claiming reachability. Eligible outer candidates SHALL follow the provider-specific selection rules:
recognized Android package containers or enabled generic ZIPs for GitHub,
recognized package links for GitLab, and configured final links for HTML.
Ordinary live verification of a ZIP SHALL NOT inspect archive members or claim
that `zippedApkFilterRegEx` matches a member. Only when asset probing is explicitly
enabled SHALL an installable entry additionally require at least one selected
eligible outer candidate to respond to a bounded GET with status 200 or 206 and a
nonempty response prefix. For a selected package container or ZIP, the probe SHALL request only the
outer response and SHALL NOT decompress or inspect its members. The system SHALL read at most
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

### Requirement: GitHub ZIP releases expose outer assets with explicit extraction limits

GitHub resolution SHALL admit generic `.zip` assets alongside recognized
`.apk`, `.xapk`, `.apkm` and `.apks` assets only when `includeZips` is true, applying apkFilterRegEx and inversion to the outer filename.
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
