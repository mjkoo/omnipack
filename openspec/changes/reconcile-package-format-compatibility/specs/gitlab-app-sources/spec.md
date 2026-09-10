## MODIFIED Requirements

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
