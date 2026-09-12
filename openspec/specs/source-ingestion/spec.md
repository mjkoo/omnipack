# source-ingestion Specification

## Purpose

Turns each upstream catalog and the hand-written extras into a normalized set
of candidate app entries per pack variant, so that the rest of the pipeline
never has to know how any individual upstream encodes its data.

## Requirements

### Requirement: Upstream catalogs are read from their canonical locations

The system SHALL read each upstream from the location recorded in the source
configuration: the RJNY catalog from the configured path on the configured
branch, the BBoi34 catalog from the single-screen and dual-screen JSON assets
of the latest release of the configured repository, and the codm2000 catalog
from its configured committed Obtainium JSON file. Routine ingestion SHALL NOT
fetch the source README, inspect APKs or resolve package IDs.

#### Scenario: BBoi34 assets come from the newest release

- **WHEN** ingestion runs and the newest BBoi34 release publishes assets named
  for a version later than any seen before
- **THEN** the entries are read from that release's assets rather than from a
  pinned or previously cached version

#### Scenario: Configured location is empty

- **WHEN** ingestion runs and a source's configured location is empty
- **THEN** the build fails with an error naming that source

#### Scenario: README or APK hosting is unavailable

- **WHEN** committed codm2000 JSON is valid and other catalog sources are available
- **THEN** ingestion succeeds without requesting README or APK data

### Requirement: HTTP credentials are optional and scoped to exact hosts

All ingestion and source-discovery HTTP requests SHALL use the shared
standard-library HTTP helper, including catalog fetches and the vendored
package-id resolver's release metadata requests, ranged APK reads and full asset
downloads. GitHub default stable-release metadata SHALL be requested from
`https://api.github.com/repos/OWNER/REPO/releases/latest`. Explicit prerelease
or release-title policy SHALL use
`https://api.github.com/repos/OWNER/REPO/releases` with bounded listing under
the source-generation contract. Track-only release checks SHALL use the same
host-scoped helper without APK requests. Publication operations are outside
this helper: release and PR operations SHALL use the `gh` CLI and branch pushes
SHALL use `git`, under the publication credential rules of the workflows that
make them.

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

#### Scenario: Fresh GitHub resolution uses the API credential

- **WHEN** generation resolves a GitHub project, as every generation run does
  for every eligible project, the default HTTP configuration is loaded and
  `GITHUB_TOKEN` is nonempty
- **THEN** its policy-selected release metadata request to `api.github.com` carries the
  bearer token through the shared helper, and its ranged APK reads and full
  asset download fallback use that same helper
- **AND** requests to unregistered `github.com`, `raw.githubusercontent.com`,
  `codeberg.org` and release asset hosts carry no Authorization header

#### Scenario: Optional token is absent

- **WHEN** a registered variable is unset or empty
- **THEN** requests to its host proceed without Authorization, including
  fresh package-id resolution against public GitHub releases

#### Scenario: Host registration does not cover related names

- **WHEN** only `github.com` is registered and its token variable is nonempty
- **THEN** requests to `api.github.com` and `www.github.com` carry no
  Authorization header because neither exact host is registered

#### Scenario: Authenticated request redirects to an unregistered host

- **WHEN** a request bearing the token for `api.github.com` redirects to an
  unregistered host
- **THEN** the redirected request carries no Authorization header

### Requirement: URLs are compared in a normalized form

The same project is spelled differently by different hands across the upstream
catalogs, the source README, the reviewed project policy and the committed
source catalog, so two spellings of one project must not be treated as two
projects. The system SHALL compare URLs in a normalized form
obtained by discarding the scheme, lowercasing the host, dropping a leading
`www.` from the host, dropping a trailing slash and a trailing `.git` from the
path, and reducing a GitHub project link to its owner and repository compared
without regard to case. The scheme SHALL NOT participate in the comparison, so
that `http` and `https` spellings of one project compare equal. Case SHALL be
folded only in the host and in a GitHub link's owner and repository; the case
of any other path SHALL be preserved, so that two URLs on another host
differing only in path case remain different projects. The pipeline SHALL use
this form wherever it compares URLs: deciding whether another source already
contributes a link, and matching a generated project to its reviewed rule and
to its entry in the committed source catalog.

#### Scenario: Two spellings of one project

- **WHEN** one source gives a project's URL as `https://github.com/Owner/Repo`
  and another gives it as `https://www.github.com/owner/repo.git/`
- **THEN** both normalize to the same URL and the two are treated as the same
  project, because a GitHub link's owner and repository are compared without
  regard to case

#### Scenario: Two spellings differ only in scheme

- **WHEN** one source gives a project's URL as `http://github.com/owner/repo`
  and another gives it as `https://github.com/owner/repo`
- **THEN** both normalize to the same URL and the two are treated as the same
  project

#### Scenario: A non-GitHub path differs only in case

- **WHEN** two URLs address the same non-GitHub host and differ only in the
  case of their path
- **THEN** they are treated as different projects, because case is folded only
  in the host and in a GitHub link's owner and repository

### Requirement: A failed fetch aborts the build

A pack that is silently missing a whole upstream is worse than no rebuild at
all, because it would drop every app that upstream contributes. The system
SHALL abort the build when any source cannot be fetched or parsed, and SHALL
NOT write either import file in that case. The build report SHALL still record the failure. The committed codm2000
catalog is a required local source: missing, malformed or unreadable content
SHALL fail the build without falling back to README generation. Builds SHALL
NOT modify that catalog.

#### Scenario: One upstream is unreachable

- **WHEN** one upstream cannot be fetched
- **THEN** the build fails, and the previously written import files are left
  unmodified

#### Scenario: An upstream returns unparseable content

- **WHEN** an upstream is reachable but its content cannot be parsed as the
  expected catalog shape
- **THEN** the build fails with an error naming that source

#### Scenario: Committed source catalog is missing

- **WHEN** the configured codm2000 JSON file is missing or malformed
- **THEN** the build fails naming codm2000 and preserves previous outputs

### Requirement: RJNY export flags select entries per variant

The RJNY catalog carries per-entry export metadata that determines whether an
entry is exported at all and which variants it belongs to. The system SHALL
drop any entry marked as excluded from export, SHALL omit an entry from the
single-screen variant when it is marked as not included in the standard pack,
and SHALL omit an entry from the dual-screen variant when it is marked as not
included in the dual-screen pack. An entry carrying no such flag SHALL be a
candidate for both variants. Entries eligible for single SHALL be ordinary
candidates; entries eligible only for dual SHALL be dual-preferred. Explicit
composition policy SHALL be able to override eligibility and preference after
source normalization, but SHALL NOT revive an entry excluded from export.

#### Scenario: Entry excluded from export

- **WHEN** an RJNY entry is marked as excluded from export
- **THEN** it contributes to neither variant, regardless of its other flags

#### Scenario: Entry opted out of one variant

- **WHEN** an RJNY entry is marked as not included in the standard pack
- **THEN** it is a candidate for the dual-screen variant only

#### Scenario: Entry carries no export metadata

- **WHEN** an RJNY entry carries no export metadata
- **THEN** it is a candidate for both variants

### Requirement: RJNY presentation metadata does not reach the pack

The RJNY catalog carries name and URL overrides that its own rendered exports
do not apply; they exist to build its documentation table. Applying them would
change the app name and source URL that Obtainium sees. The system SHALL
ignore those overrides and SHALL carry through the entry's own name and URL.

#### Scenario: Entry carries a name override

- **WHEN** an RJNY entry carries a name override that differs from its name
- **THEN** the ingested entry keeps the entry's own name

### Requirement: One package id may resolve differently per variant

Upstreams deliberately point a single package id at different projects or
settings per variant, so that a dual-screen fork replaces its single-screen
counterpart. The system SHALL resolve each variant's candidates independently
and SHALL NOT require that a package id map to the same entry across variants.

#### Scenario: Same id, different project per variant

- **WHEN** an upstream contains two entries sharing a package id, one opted
  out of the single-screen variant and the other opted out of the dual-screen
  variant
- **THEN** the single-screen variant ingests one of them and the dual-screen
  variant ingests the other

#### Scenario: Duplicate ids remain within a variant

- **WHEN** ingesting one source leaves two candidate entries sharing a package
  id within the same variant
- **THEN** the duplicate is resolved during composition, not silently dropped
  during ingestion

### Requirement: BBoi34 entries map to variants by source file

The system SHALL retain each standard-asset record as an ordinary candidate
eligible for both targets, and each dual-asset record as a dual-preferred
candidate eligible only for dual. It SHALL preserve asset origin and retain both
records when a package id appears in both assets. Selection SHALL occur during
composition, where device preference precedes source ranking. Explicit policy
SHALL be able to override normalized eligibility and preference.

#### Scenario: Id present in both BBoi34 assets

- **WHEN** both assets contain different builds of an id and no override changes their suitability
- **THEN** ingestion retains both and composition selects the standard build for single and the dual build for dual, absent a higher-ranked eligible choice

#### Scenario: Standard alternative remains available

- **WHEN** explicit policy makes the dual candidate ineligible for dual
- **THEN** the retained standard candidate remains available for dual selection

### Requirement: Hand-written extras are ingested as complete entries

The system SHALL ingest each entry in the extras configuration as a candidate
entry, and SHALL fail the build with an error naming the entry when an extras
entry is missing a package id, a URL or a name. An extras entry has no upstream
record to take a display name from, and a name is not optional downstream:
rendering orders entries by name and the import format displays it. An extras
entry SHALL be a candidate for both variants, unless it
carries a variants field naming the variants it applies to, in which case it
SHALL be a candidate for exactly the named variants. The system SHALL fail the
build when that field names anything other than the known variants, or names
an empty list. An optional boolean `dualPreferred` SHALL default to false and
SHALL be valid only with dual eligibility. Explicit composition policy SHALL be
able to override normalized eligibility and preference. Composition-only fields
SHALL NOT reach Obtainium app records.

#### Scenario: Extras entry lacks a package id

- **WHEN** an extras entry has no package id
- **THEN** the build fails with an error naming that entry

#### Scenario: Extras entry lacks a name

- **WHEN** an extras entry carries a package id and a URL but no name
- **THEN** the build fails with an error naming that entry

#### Scenario: Extras entry names no variants

- **WHEN** an extras entry carries a package id and a URL and no variants
  field
- **THEN** it is a candidate for both the single-screen and the dual-screen
  variant

#### Scenario: Extras entry names an unknown variant

- **WHEN** an extras entry's variants field names a variant the pack does not
  have
- **THEN** the build fails with an error naming that entry and the rejected
  value

#### Scenario: Ordinary extra competes with a dual fork

- **WHEN** an extra omits dualPreferred and a dual-preferred lower-source candidate shares its family
- **THEN** the extra is ordinary and does not win dual selection solely through source precedence

### Requirement: Every entry carries a supported source type

Obtainium reads a per-app source type that decides which settings keys an app
has, so every entry must carry one before it can be rendered. An entry ingested
from an upstream catalog SHALL take the source type that upstream's record
declares for it. An extras entry with an explicit `overrideSource` SHALL use
that declared source type before URL-based inference. Only when an extras entry
omits `overrideSource`, or for a generated entry, SHALL the system derive the
source type from the URL: a github.com repository takes GitHub and any other
URL takes HTML. The pack SHALL support GitHub, HTML and GitLab, and SHALL fail
the build with an error naming the entry and offending value for any other
source type, including a malformed explicit declaration rather than silently
falling back to URL inference.

Native GitLab entries SHALL follow the URL, identity and discovery boundary in
"Public GitLab entries retain native source identity". Explicit per-app settings
SHALL override hydrated defaults. Native GitLab selection SHALL NOT route through
HTML defaults.

#### Scenario: Upstream record declares a source type

- **WHEN** an upstream entry's record declares the HTML source type
- **THEN** the ingested entry carries the HTML source type

#### Scenario: An entry with no upstream record derives its source type

- **WHEN** a generated entry or an extras entry without `overrideSource` addresses a github.com
  repository
- **THEN** it carries the GitHub source type, while an entry addressing any
  other URL carries the HTML source type

#### Scenario: Unsupported source type

- **WHEN** an upstream or extras entry declares a source type other than GitHub, HTML or GitLab
- **THEN** the build fails with an error naming that entry and that source type

#### Scenario: Explicit GitLab declaration takes precedence over URL inference

- **WHEN** an Aurora extra declares `overrideSource: GitLab` and `https://gitlab.com/AuroraOSS/AuroraStore`
- **THEN** ingestion retains GitLab, and rendering uses GitLab defaults and preserves explicit settings in both variants instead of selecting HTML

#### Scenario: Native GitLab URL is outside the supported boundary

- **WHEN** an entry declares GitLab with a non-HTTPS URL, a host other than gitlab.com or no namespace/project path
- **THEN** the build fails with the entry and invalid URL identified

### Requirement: Per-app settings are normalized to a common form

Upstreams encode an entry's per-app settings inconsistently: some as a nested
object and some as a JSON-encoded string. The system SHALL normalize every
ingested entry's per-app settings to a single form so that later composition
compares and patches them uniformly.

#### Scenario: Upstream encodes settings as a string

- **WHEN** an upstream entry's per-app settings are a JSON-encoded string
- **THEN** the ingested entry exposes the same settings as structured data

#### Scenario: Settings string is malformed

- **WHEN** an upstream entry's per-app settings string cannot be decoded
- **THEN** the build fails with an error naming that entry

### Requirement: Public GitLab entries retain native source identity

The system SHALL accept explicit extras with source type `GitLab` and public HTTPS gitlab.com project URLs, preserve the full case-sensitive project path including subgroups (at most 21 path components in total), hydrate supported GitLab defaults, and render `overrideSource: GitLab`. Existing non-GitHub URL comparison semantics SHALL remain unchanged. Package ids for these explicit extras SHALL be supplied and backed by manifest evidence; adding GitLab SHALL NOT extend generated GitHub package discovery to arbitrary hosts.

#### Scenario: Aurora extra reaches both exports

- **WHEN** an explicit Aurora Store extra uses its canonical GitLab URL and both variants
- **THEN** both outputs and individual import links retain native GitLab identity and compatible settings

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
