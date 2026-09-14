## ADDED Requirements

### Requirement: Hand-written extras are ingested as baseline or dual-screen builds

The system SHALL ingest each entry in the extras configuration as a candidate
entry, and SHALL fail the build with an error naming the entry when an extras
entry is missing a package id, a URL or a name. An extras entry has no upstream
record to take a display name from, and a name is not optional downstream:
rendering orders entries by name and the import format displays it. An extras
entry SHALL be a baseline build, a candidate for both variants, unless it
carries an optional boolean `dualScreen` set to true, which makes it a
dual-screen build: a candidate for the dual-screen variant only, preferred
there. `dualScreen` SHALL default to false, and a non-boolean value SHALL fail
the build with an error naming the entry. An extras entry carrying a `variants`
or `dualPreferred` field SHALL fail the build with an error naming the entry
and the field. Composition policy SHALL NOT change an extra's eligibility or
dual preference. `dualScreen` and the other composition-only fields SHALL NOT
reach Obtainium app records.

#### Scenario: Extras entry lacks a package id

- **WHEN** an extras entry has no package id
- **THEN** the build fails with an error naming that entry

#### Scenario: Extras entry lacks a name

- **WHEN** an extras entry carries a package id and a URL but no name
- **THEN** the build fails with an error naming that entry

#### Scenario: Extras entry is a baseline build

- **WHEN** an extras entry carries a package id, a URL and a name and no
  `dualScreen` field
- **THEN** it is a candidate for both the single-screen and the dual-screen
  variant and is not preferred in dual

#### Scenario: Extras entry is a dual-screen build

- **WHEN** an extras entry sets `dualScreen` to true, a dual-screen
  lower-source candidate shares its family and no pin applies
- **THEN** the extra is a candidate for the dual-screen variant only and wins
  dual selection over that candidate by source precedence

#### Scenario: Extras dual-screen flag is not a boolean

- **WHEN** an extras entry's `dualScreen` field holds a value other than true
  or false
- **THEN** the build fails with an error naming that entry

#### Scenario: Extras entry carries a retired field

- **WHEN** an extras entry carries a `variants` or `dualPreferred` field
- **THEN** the build fails with an error naming that entry and the field

#### Scenario: Ordinary extra competes with a dual fork

- **WHEN** a baseline extra and a dual-screen lower-source candidate share a
  family and no pin applies
- **THEN** the dual-screen candidate wins dual selection, and the extra does
  not win it solely through source precedence

## MODIFIED Requirements

### Requirement: HTTP credentials are optional and scoped to exact hosts

Source-discovery HTTP requests SHALL use the shared standard-library HTTP
helper, including the vendored package-id resolver's release metadata requests,
ranged APK reads and full asset downloads. GitHub default stable-release
metadata SHALL be requested from
`https://api.github.com/repos/OWNER/REPO/releases/latest`. Explicit prerelease
or release-title policy SHALL use
`https://api.github.com/repos/OWNER/REPO/releases` with bounded listing under
the source-generation contract. Track-only release checks SHALL use the same
host-scoped helper without APK requests. Routine build ingestion SHALL fetch
upstream catalogs with standard-library requests that carry no credentials,
and SHALL NOT read the HTTP credential configuration. Publication operations
are outside this helper: release and PR operations SHALL use the `gh` CLI and
branch pushes SHALL use `git`, under the publication credential rules of the
workflows that make them.

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

#### Scenario: Build ingestion carries no credentials

- **WHEN** `pack build` fetches upstream catalogs while `GITHUB_TOKEN` is nonempty
- **THEN** no catalog request carries an Authorization header, and the build
  succeeds without `config/http.json`

### Requirement: RJNY export flags select entries per variant

The RJNY catalog carries per-entry export metadata that determines whether an
entry is exported at all and which variants it belongs to. The system SHALL
drop any entry marked as excluded from export, SHALL omit an entry from the
single-screen variant when it is marked as not included in the standard pack,
and SHALL omit an entry from the dual-screen variant when it is marked as not
included in the dual-screen pack. An entry carrying no such flag SHALL be a
candidate for both variants. An entry in both exports SHALL be a baseline
build. An entry only in the dual-screen export SHALL be a dual-screen build,
preferred in dual. An entry only in the standard export SHALL be a baseline
build that upstream keeps out of dual. An entry marked out of both packs SHALL
contribute to neither. These flags SHALL alone decide an entry's kind and
eligibility: composition policy SHALL NOT change them, restore an entry to a
pack its flags leave it out of, or revive an entry excluded from export.

#### Scenario: Entry excluded from export

- **WHEN** an RJNY entry is marked as excluded from export
- **THEN** it contributes to neither variant, regardless of its other flags

#### Scenario: Entry opted out of one variant

- **WHEN** an RJNY entry is marked as not included in the standard pack
- **THEN** it is a candidate for the dual-screen variant only

#### Scenario: Entry carries no export metadata

- **WHEN** an RJNY entry carries no export metadata
- **THEN** it is a candidate for both variants

#### Scenario: Entry kept out of dual by upstream

- **WHEN** an RJNY entry is marked as not included in the dual-screen pack, as
  the captured catalog's Cemu 0.5 entry is
- **THEN** it is a baseline build for single only, and its family's dual
  selection comes from another build, such as the dual-only Cemu 0.5.2 entry

### Requirement: BBoi34 entries map to variants by source file

The system SHALL retain each standard-asset record as a baseline build eligible
for both targets, and each dual-asset record as a dual-screen build eligible
only for dual and therefore preferred there. It SHALL preserve asset origin and
retain both records when a package id appears in both assets. Selection SHALL
occur during composition, where, absent a pin, a dual-screen build replaces the
baseline build in dual ahead of source ranking. The asset a record comes from
SHALL alone decide its kind; composition policy SHALL NOT change its
eligibility or dual preference. A package denial SHALL remove a dual-asset
build together with any standard-asset build carrying the same package id. A
dual pin naming the standard-asset build keeps it in dual in place of the
dual-asset build without removing either.

#### Scenario: Id present in both BBoi34 assets

- **WHEN** both assets contain different builds of an id, and no pin applies
- **THEN** ingestion retains both and composition selects the standard build for single and the dual build for dual, absent a higher-precedence build of the same kind

#### Scenario: Standard alternative remains available

- **WHEN** a family's standard-asset build is eligible for both targets and the
  family has no available dual-screen build, because the dual asset lacks one
  or a denial removed one whose package the standard build does not carry
- **THEN** the retained standard build remains available for dual selection

### Requirement: Committed codm2000 entries retain device-aware source semantics

The system SHALL ingest accepted codm2000 entries from committed Obtainium JSON.
README parsing and package-ID resolution SHALL occur only in the separate
source-generation operation. The source catalog SHALL contain generated GitHub
project entries independently of other upstream coverage, including APKs and
explicit track-only resources. It SHALL retain discovery settings such as
prerelease enablement and filename filters, and SHALL NOT reinterpret a
track-only resource ID as an Android package ID.

During routine ingestion, codm2000 entries SHALL be dual-screen builds,
eligible for dual only and preferred there; composition policy SHALL NOT change
that. A normalized project URL already supplied by a higher-precedence
candidate that its source makes eligible for dual SHALL suppress the
corresponding codm2000 candidate before exclusions and selection. Single-only
coverage SHALL NOT suppress it. Suppression SHALL use source eligibility alone,
and ingestion SHALL NOT read or apply the composition policy. Merely appearing
in codm2000 SHALL NOT promote an ordinary higher-source build.

Retained entries SHALL preserve codm2000 provenance, generated origin, original
package identity and source settings so existing family rules and fork-specific
overlays continue matching. Active candidate selectors SHALL be validated
against the complete admitted candidate set. Missing rules or pinned candidates
SHALL fail explicitly.

#### Scenario: Dual coverage suppresses a local catalog candidate

- **WHEN** a higher-source candidate covers dual with a normalized URL equal to a committed codm2000 entry
- **THEN** the codm2000 candidate is suppressed without promoting the higher-source candidate

#### Scenario: Single-only coverage leaves a dual candidate

- **WHEN** the higher-precedence candidate for that URL is eligible for single only, as an RJNY entry left out of the dual-screen export is
- **THEN** the committed entry remains a dual-screen codm2000 candidate, preferred in dual

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

## REMOVED Requirements

### Requirement: Hand-written extras are ingested as complete entries

**Reason**: Replaced by "Hand-written extras are ingested as baseline or
dual-screen builds". The `variants` list could also express a single-only
extra, which no entry uses, and the composition-policy override of an extra's
eligibility and preference is gone. A boolean `dualScreen` states the one
distinction extras need: a baseline build for both packs, or a dual-screen
build for dual only.

**Migration**: Remove `"variants": ["single", "dual"]` from an extras entry.
Replace `"variants": ["dual"]` with `"dualScreen": true`; that entry becomes
preferred in dual. Delete any `dualPreferred` field. A single-only extra has no
replacement.
