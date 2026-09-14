## MODIFIED Requirements

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

- **WHEN** an RJNY entry is marked as not included in the dual-screen pack
- **THEN** it is a baseline build for single only, and its family's dual
  selection comes from another build in that family

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
"Public GitLab entries keep native source identity". Explicit per-app settings
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

- **WHEN** an extras entry declares `overrideSource: GitLab` with a public gitlab.com project URL
- **THEN** ingestion retains GitLab, and rendering uses GitLab defaults and preserves explicit settings in both variants instead of selecting HTML

#### Scenario: Native GitLab URL is outside the supported boundary

- **WHEN** an entry declares GitLab with a non-HTTPS URL, a host other than gitlab.com or no namespace/project path
- **THEN** the build fails with the entry and invalid URL identified

## ADDED Requirements

### Requirement: Committed codm2000 entries keep device-aware source semantics

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

#### Scenario: Newly resolved prerelease apps are admitted

- **WHEN** the committed catalog includes manifest-verified APK entries with explicit prerelease settings and no higher-source coverage
- **THEN** they enter dual as installable APK entries, retaining those settings and their original identities without entering single

#### Scenario: A tracking resource keeps its identity

- **WHEN** the committed catalog includes an explicit track-only resource
- **THEN** dual retains its stable resource identity, track-only flag and manual-installation description
- **AND** neither pack's entry for the app the resource extends is replaced

### Requirement: Public GitLab entries keep native source identity

The system SHALL accept explicit extras with source type `GitLab` and public HTTPS gitlab.com project URLs, preserve the full case-sensitive project path including subgroups (at most 21 path components in total), hydrate supported GitLab defaults, and render `overrideSource: GitLab`. Existing non-GitHub URL comparison semantics SHALL remain unchanged. Package ids for these explicit extras SHALL be supplied and backed by manifest evidence; adding GitLab SHALL NOT extend generated GitHub package discovery to arbitrary hosts.

#### Scenario: A GitLab extra reaches both exports

- **WHEN** an explicit GitLab extra uses its canonical gitlab.com project URL and is eligible for both variants
- **THEN** both outputs and individual import links retain native GitLab identity and compatible settings

## REMOVED Requirements

### Requirement: Committed codm2000 entries retain device-aware source semantics

**Reason**: Replaced by "Committed codm2000 entries keep device-aware source
semantics", which states the same rules. The EmuLnk scenario is dropped
because "Dual coverage suppresses a local catalog candidate" states the same
outcome. The Showdown-DS, Heimdall and Kanto Gear scenarios are restated without
naming projects; those projects' values remain in the reviewed project policy
and the committed catalog.

**Migration**: None. Ingestion behavior is unchanged.

### Requirement: Public GitLab entries retain native source identity

**Reason**: Replaced by "Public GitLab entries keep native source identity",
which is identical except that its scenario no longer names a specific app.

**Migration**: None. GitLab ingestion and rendering are unchanged.
