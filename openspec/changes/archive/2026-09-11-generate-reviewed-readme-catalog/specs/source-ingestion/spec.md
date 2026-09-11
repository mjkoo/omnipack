## MODIFIED Requirements

### Requirement: HTTP credentials are optional and scoped to exact hosts

All pipeline HTTP requests SHALL use the shared standard-library HTTP helper,
including catalog fetches and the vendored package-id resolver's release
metadata requests, ranged APK reads and full asset downloads. GitHub default
stable-release metadata SHALL be requested from
`https://api.github.com/repos/OWNER/REPO/releases/latest`. Explicit prerelease
or release-title policy SHALL use
`https://api.github.com/repos/OWNER/REPO/releases` with bounded listing under
the source-generation contract. Track-only release checks SHALL use the same
host-scoped helper without APK requests.

The system SHALL read host-to-environment-variable registrations from the
`credentials` object in dedicated `config/http.json`, whose committed default
content SHALL be `{"credentials": {"api.github.com": "GITHUB_TOKEN"}}`.
Registrations SHALL name exact hosts, compared case-insensitively against the
request hostname, without wildcard matching, subdomain inference or the
project-URL normalization rules. The configuration SHALL store variable names,
not token values.

The helper SHALL attach `Authorization: Bearer <token>` only when the request
host has a registered variable with a nonempty value. An unset or empty
variable SHALL leave the request unauthenticated. Unregistered hosts SHALL
receive no Authorization header even when tokens for other hosts are set.
Across a cross-host redirect, the helper SHALL strip the outgoing host's
credential; any destination credential SHALL be selected independently from
that destination's exact registration.

#### Scenario: Cold-cache GitHub resolution uses the API credential

- **WHEN** a generated GitHub project has no cached package id, the default
  HTTP configuration is loaded and `GITHUB_TOKEN` is nonempty
- **THEN** its policy-selected release metadata request to `api.github.com` carries the
  bearer token through the shared helper, and its ranged APK reads and full
  asset download fallback use that same helper
- **AND** requests to unregistered `github.com`, `raw.githubusercontent.com`,
  `codeberg.org` and release asset hosts carry no Authorization header

#### Scenario: Optional token is absent

- **WHEN** a registered variable is unset or empty
- **THEN** requests to its host proceed without Authorization, including
  cold-cache package-id resolution against public GitHub releases

#### Scenario: Host registration does not cover related names

- **WHEN** only `github.com` is registered and its token variable is nonempty
- **THEN** requests to `api.github.com` and `www.github.com` carry no
  Authorization header because neither exact host is registered

#### Scenario: Authenticated request redirects to an unregistered host

- **WHEN** a request bearing the token for `api.github.com` redirects to an
  unregistered host
- **THEN** the redirected request carries no Authorization header

#

## Requirement: Upstream catalogs are read from their canonical locations

The system SHALL read each upstream from the location recorded in the source
configuration: the RJNY catalog from the configured path on the configured
branch, the BBoi34 catalog from the single-screen and dual-screen JSON assets
of the latest release of the configured repository, and the codm2000 catalog
from its configured committed Obtainium JSON file. Routine ingestion SHALL NOT
fetch the source README, inspect APKs or read or mutate resolution state.

##

## Scenario: BBoi34 assets come from the newest release

- **WHEN** ingestion runs and the newest BBoi34 release publishes assets named
  for a version later than any seen before
- **THEN** the entries are read from that release's assets rather than from a
  pinned or previously cached version

##

## Scenario: Configured location is empty

- **WHEN** ingestion runs and a source's configured location is empty
- **THEN** the build fails with an error naming that source

##

## Scenario: README or APK hosting is unavailable

- **WHEN** committed codm2000 JSON is valid and other catalog sources are available
- **THEN** ingestion succeeds without requesting README or APK data

#

## Requirement: A failed fetch aborts the build

A pack that is silently missing a whole upstream is worse than no rebuild at
all, because it would drop every app that upstream contributes. The system
SHALL abort the build when any source cannot be fetched or parsed, and SHALL
NOT write either import file in that case. The build report SHALL still record the failure. The committed codm2000
catalog is a required local source: missing, malformed or unreadable content
SHALL fail the build without falling back to README generation. Builds SHALL
NOT modify that catalog or package-ID resolution state.

##

## Scenario: One upstream is unreachable

- **WHEN** one upstream cannot be fetched
- **THEN** the build fails, and the previously written import files are left
  unmodified

##

## Scenario: An upstream returns unparseable content

- **WHEN** an upstream is reachable but its content cannot be parsed as the
  expected catalog shape
- **THEN** the build fails with an error naming that source

##

## Scenario: Committed source catalog is missing

- **WHEN** the configured codm2000 JSON file is missing or malformed
- **THEN** the build fails naming codm2000 and preserves previous outputs

## REMOVED Requirements

#

### Requirement: codm2000 entries are generated from GitHub project links

**Reason**: README parsing and resolution move to source generation; routine ingestion reads accepted JSON.
**Migration**: Use "Committed codm2000 entries retain device-aware source semantics" and the separate readme-source-generation contract. Retained output safety and composition behavior are included in the replacement.


## Requirement: A generated entry carries a real package id

**Reason**: Automatic APK resolution belongs to source generation, not routine ingestion.
**Migration**: Preserve automatic manifest-backed APK IDs and agreement across the reviewed eligible asset set under readme-source-generation, with explicit prerelease discovery. Declared trackers have separate resource identities; unresolved new APK projects still block the complete proposal.

#

## Requirement: Resolved package ids are cached across builds

**Reason**: Builds consume committed IDs and no longer resolve or persist them.
**Migration**: Use generation-owned accepted resolution state and reuse it across generation invocations.

## ADDED Requirements

### Requirement: Committed codm2000 entries retain device-aware source semantics

The system SHALL ingest accepted codm2000 entries from committed Obtainium JSON.
README parsing and package-ID resolution SHALL occur only in the separate
source-generation operation. The source catalog SHALL contain generated GitHub
project entries independently of other upstream coverage, including APKs and
explicit track-only resources. It SHALL retain discovery settings such as
prerelease enablement and filename filters, and SHALL NOT reinterpret a
track-only resource ID as an Android package ID.

During routine ingestion, codm2000 entries SHALL be dual-only and dual-preferred
unless explicit policy overrides those properties. A normalized project URL
already supplied by a higher-precedence candidate eligible for dual after
explicit eligibility policy SHALL suppress the corresponding codm2000 candidate
before exclusions and selection. Single-only coverage SHALL NOT suppress it.
Merely appearing in codm2000 SHALL NOT promote an ordinary higher-source build.

Retained entries SHALL preserve codm2000 provenance, generated origin, original
package identity and source settings so existing family rules and fork-specific
overlays continue matching. Active candidate selectors SHALL be validated
against the complete admitted candidate set; historical mappings SHALL remain
exempt. Missing rules or pinned candidates SHALL fail explicitly.

#### Scenario: Dual coverage suppresses a local catalog candidate

- **WHEN** a higher-source candidate covers dual with a normalized URL equal to a committed codm2000 entry
- **THEN** the codm2000 candidate is suppressed without promoting the higher-source candidate

#### Scenario: Single-only coverage leaves a dual candidate

- **WHEN** the higher source covers only single, including after explicit eligibility policy
- **THEN** the committed entry remains a dual-preferred codm2000 candidate

#### Scenario: Existing generated family selector remains valid

- **WHEN** a retained committed entry has an existing generated-origin rule or overlay selector
- **THEN** its source identity is preserved and the same family and override behavior applies

#### Scenario: A selected project is removed

- **WHEN** an accepted source update removes a candidate required by an active rule or pin
- **THEN** pack composition fails explicitly rather than silently ignoring the stale selector

#### Scenario: EmuLnk already has correct higher-source settings

- **WHEN** RJNY supplies EmuLnk as dual-eligible with prereleases enabled
- **THEN** its entry remains the winner with unchanged settings and suppresses the independently generated codm entry

#### Scenario: Newly resolved prerelease apps are admitted

- **WHEN** the committed catalog includes manifest-verified Showdown-DS and Heimdall with explicit prerelease settings and no higher-source coverage
- **THEN** they enter dual as installable APK entries, retaining those settings and their original identities without entering single

#### Scenario: Kanto is a tracking resource

- **WHEN** the committed catalog includes the explicit Kanto Gear tracker
- **THEN** dual retains its stable resource identity, track-only flag and manual-installation description, and neither pack's Gen1Recomp host is replaced
