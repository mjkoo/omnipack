## Purpose

Allow curated Android applications hosted on public GitLab projects to be imported and verified through Obtainium's native GitLab source.

## ADDED Requirements

### Requirement: Public GitLab entries retain native source identity

The system SHALL accept explicit extras with source type `GitLab` and public HTTPS gitlab.com project URLs, preserve the full case-sensitive project path including subgroups, hydrate supported GitLab defaults, and render `overrideSource: GitLab`. Existing non-GitHub URL comparison semantics SHALL remain unchanged. Package ids for these explicit extras SHALL be supplied and backed by manifest evidence; adding GitLab SHALL NOT extend generated GitHub package discovery to arbitrary hosts.

#### Scenario: Aurora extra reaches both exports

- **WHEN** an explicit Aurora Store extra uses its canonical GitLab URL and both variants
- **THEN** both outputs and individual import links retain native GitLab identity and compatible settings

### Requirement: GitLab release resolution includes uploaded description APKs

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
