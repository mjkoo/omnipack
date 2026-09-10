## ADDED Requirements

### Requirement: GitLab release resolution includes uploaded description APKs

Eligible named GitLab asset links SHALL have a name or URL path ending in
`.apk`, `.xapk`, `.apkm` or `.apks`, without regard to extension case. Release
description links SHALL use the supported relative Markdown upload form
`[label](/uploads/.../filename)` with one of those suffixes. The configured APK
regex SHALL apply to the link's name, including the filename of a description
upload. Generic `.zip` assets SHALL NOT qualify. Recognized package containers
SHALL NOT require `includeZips`, and their resolution or optional probing SHALL
NOT assert member presence, extraction, package identity or installability.

The verifier SHALL resolve the project through the GitLab API and inspect at most 100 releases in API order. It SHALL combine eligible named asset links with project-upload APK links embedded in release descriptions, resolve upload links using the numeric project id, apply the configured APK filter, and select a release with matching APKs according to the configured older-release fallback. It SHALL use the release tag as the source version, apply supported version extraction, and produce per-variant evidence and optional bounded asset probes under existing verification guarantees. Successful acquisition with no qualifying APK SHALL fail. Request failures, malformed metadata and rate limits SHALL remain failures rather than silently selecting another source.

The supported scope SHALL be explicit installable public GitLab entries with tag versioning, APK filtering, optional extraction and older-release fallback. Unknown or unsupported active source settings SHALL fail before network access. Inactive settings SHALL be classified explicitly. GitLab requests SHALL use shared HTTP timeouts, retry bounds, deduplication, concurrency limits and exact-host credential isolation. GitHub tokens SHALL NOT be forwarded to GitLab; public GitLab access SHALL work without a token. Evidence fingerprints SHALL include GitLab resolution inputs and verifier identity.

#### Scenario: Release has no asset links but description has APK uploads

- **WHEN** Aurora release metadata contains normal, hw and preload APK upload links in its description and an empty asset-links list
- **THEN** the ordinary APK filter selects only the normal APK and resolves its project upload URL

#### Scenario: Older release fallback is disabled

- **WHEN** the first inspected release has no qualifying APK and fallback is disabled
- **THEN** verification fails without accepting an older release

#### Scenario: GitLab request fails

- **WHEN** metadata acquisition is unsuccessful or malformed
- **THEN** the entry fails verification and receives no successful evidence or alternate-source fallback

#### Scenario: Unsupported option is active

- **WHEN** an entry enables a GitLab option outside the declared compatibility boundary
- **THEN** verification rejects it before issuing an HTTP request

#### Scenario: Named package link qualifies by its URL path

- **WHEN** a named GitLab asset link has no package suffix in its display name but its URL path ends in `.apkm` and its name matches the configured APK filter
- **THEN** it is an eligible package candidate without enabling generic ZIP selection

#### Scenario: Description upload provides a package container

- **WHEN** release Markdown includes a relative `/uploads/` link ending in `.xapk` or `.apks` that matches the filename filter
- **THEN** resolution selects its numeric-project upload URL without inspecting container members

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

GitLab resolution SHALL follow "GitLab release resolution includes uploaded
description APKs" and the shared live-request and evidence requirements. Adding
GitLab SHALL NOT relax the existing GitHub credential requirement or HTML
compatibility checks.

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
