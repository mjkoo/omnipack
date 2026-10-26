# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: BBoi34 entries map to variants by source file`
- TO: `### Requirement: BBoi34 entries take their kind from their source file`

## ADDED Requirements

### Requirement: RJNY export flags decide entry kind

The RJNY catalog carries per-entry export metadata that determines whether an
entry is exported at all and which of its packs it belongs to. The system SHALL
drop any entry marked as excluded from export, and any entry marked as not
included in the standard pack and as not included in the dual-screen pack. An
entry only in the dual-screen export SHALL be a dual-screen build; every other
entry it keeps, one in both exports, one only in the standard export or one
carrying no such flag, SHALL be a baseline build. These flags SHALL alone decide
an entry's kind, and SHALL NOT keep a kept entry out of either pack: as "Builds
are baseline or dual-screen and each pack selects its kind" in pack-composition
states, every candidate is selectable in both packs and only the owner's
denials remove one. No composition setting revives an entry this requirement
drops.

#### Scenario: Entry excluded from export

- **WHEN** an RJNY entry is marked as excluded from export
- **THEN** it contributes to neither variant, regardless of its other flags

#### Scenario: Entry opted out of one variant

- **WHEN** an RJNY entry is marked as not included in the standard pack only
- **THEN** it is a dual-screen build, preferred in dual and selected in single
  only when its family has no available baseline build

#### Scenario: Entry carries no export metadata

- **WHEN** an RJNY entry carries no export metadata
- **THEN** it is a baseline build

#### Scenario: Entry only in the standard export

- **WHEN** an RJNY entry is marked as not included in the dual-screen pack only
- **THEN** it is a baseline build, and dual selects it only when its family has
  no available dual-screen build

#### Scenario: Entry marked out of both packs

- **WHEN** an RJNY entry is marked as not included in the standard pack and as
  not included in the dual-screen pack
- **THEN** it is dropped and contributes to neither variant

## MODIFIED Requirements

### Requirement: One package id may resolve differently per variant

Upstreams deliberately point a single package id at different projects or
settings per variant, so that a dual-screen fork replaces its single-screen
counterpart in their own packs. The system SHALL resolve each variant's
candidates independently and SHALL NOT require that a package id map to the
same entry across variants. A shared package id does not join candidates at
different project URLs into one family, so such a replacement across URLs
holds in these packs only when a family rule joins the URLs into one explicit
family, as "App families form by project URL under the composition policy" in
pack-composition defines; without one, both families are selected in both packs
and the shared id is recorded as a package id repeated within each pack.

An upstream catalog contributing two entries that share a package id SHALL have
both retained for composition to resolve, because ingestion cannot know which
of them a family rule, a pin or a denial will select. The committed codm
catalog SHALL instead fail ingestion when it repeats an entry id, naming the id
and both project URLs, because it is reviewed before it is committed and a
repeated id there is an error in the catalog rather than a choice for
composition.

#### Scenario: Same id, different project per variant

- **WHEN** an upstream contains two entries at one project URL sharing a
  package id, one a dual-screen build and the other a baseline build
- **THEN** ingestion retains both, single selects the baseline build and dual
  selects the dual-screen build

#### Scenario: A cross-URL replacement needs a family rule

- **WHEN** the two entries sharing a package id, one a baseline build and one a
  dual-screen build, carry different project URLs
- **THEN** ingestion retains both, and the dual-screen build replaces the
  baseline build in dual, with neither repeated in a pack, only when a family
  rule joins their URLs

#### Scenario: Duplicate ids remain within a variant

- **WHEN** ingesting one upstream catalog leaves two candidate entries sharing
  a package id within the same variant
- **THEN** the duplicate is resolved during composition, not silently dropped
  during ingestion

#### Scenario: The committed catalog repeats an entry id

- **WHEN** the committed codm catalog contains two entries carrying the
  same id
- **THEN** ingestion fails naming that id and both entries' project URLs,
  rather than retaining both or keeping whichever appears first

### Requirement: BBoi34 entries take their kind from their source file

The system SHALL retain each standard-asset record as a baseline build and each
dual-asset record as a dual-screen build. It SHALL preserve asset origin and
retain both records when one project appears in both assets. Selection SHALL
occur during composition: what a pin, a dual-screen build and a project denial
each do to a project present in both assets is defined by "Builds are baseline
or dual-screen and each pack selects its kind", "Pins select a candidate of
their family" and "Project denials exclude candidates from the packs they name"
in pack-composition. The asset a record comes from SHALL alone decide
its kind.

#### Scenario: Id present in both BBoi34 assets

- **WHEN** both assets contain different builds of an id
- **THEN** ingestion retains both as separate candidates, a baseline build from
  the standard asset and a dual-screen build from the dual asset, and leaves
  the choice between them to composition

#### Scenario: Standard alternative remains available

- **WHEN** a family has a standard-asset build and no available dual-screen
  build, because the dual asset lacks one
  or a denial removed one at a project URL the standard build does not share
- **THEN** the retained standard build remains available for dual selection

#### Scenario: A dual asset with no standard counterpart

- **WHEN** a family's only build is a dual-asset record and no denial or pin
  applies
- **THEN** both packs select it

### Requirement: Hand-written extras are baseline or dual-screen builds

The system SHALL ingest each entry in the extras configuration as a candidate
entry, and SHALL fail the build with an error naming the entry when an extras
entry is missing a package id, a URL or a name. An extras entry has no upstream
record to take a display name from, and a name is not optional downstream:
rendering orders entries by name and the import format displays it. An extras
entry SHALL be a baseline build unless it carries an optional boolean
`dualScreen` set to true, which makes it a dual-screen build. Either kind is a
candidate for both variants. `dualScreen` SHALL default to false, and a non-boolean value SHALL fail
the build with an error naming the entry. Ingestion SHALL consume an extras
entry's `dualScreen` field so it does not reach that entry's Obtainium app
record.

#### Scenario: Extras entry lacks a package id

- **WHEN** an extras entry has no package id
- **THEN** the build fails with an error naming that entry

#### Scenario: Extras entry lacks a name

- **WHEN** an extras entry carries a package id and a URL but no name
- **THEN** the build fails with an error naming that entry

#### Scenario: Extras entry is a baseline build

- **WHEN** an extras entry carries a package id, a URL and a name and no
  `dualScreen` field
- **THEN** it is a baseline build, a candidate for both variants and not
  preferred in dual

#### Scenario: Extras entry is a dual-screen build

- **WHEN** an extras entry sets `dualScreen` to true, a dual-screen
  lower-source candidate shares its family and no pin applies
- **THEN** the extra is a dual-screen build and wins dual selection over that
  candidate by source precedence

#### Scenario: Extras dual-screen flag is not a boolean

- **WHEN** an extras entry's `dualScreen` field holds a value other than true
  or false
- **THEN** the build fails with an error naming that entry

#### Scenario: Ordinary extra competes with a dual fork

- **WHEN** a baseline extra and a dual-screen lower-source candidate share a
  family and no pin applies
- **THEN** ingestion offers the extra as a baseline build, not preferred in
  dual, so composition rather than source precedence alone decides dual
  selection

### Requirement: Committed codm entries are dual-screen candidates

The system SHALL ingest the committed codm catalog as Obtainium JSON,
without fetching the codm README; generation from the README is the separate
source-generation operation. Each entry SHALL keep codm provenance, the
generated origin, its committed id, URL, name and settings, so composition
rules and overlays that select it match it. During routine ingestion, codm
entries SHALL be dual-screen builds, candidates for both variants and preferred
in dual. Every committed entry SHALL become a candidate whether or not another
source lists the same project, and ingestion SHALL NOT read or apply the
composition policy: family formation, dual preference, precedence, pins and
project denials in pack-composition decide between a codm build and
another source's build of the same app, and whether a codm build appears in
single. A missing, unreadable or malformed
catalog, a repeated entry ID or two entries at one normalized project URL
SHALL fail the build while preserving previous outputs.

#### Scenario: Broken committed codm catalog

- **WHEN** the configured catalog is missing, malformed, repeats an entry ID or
  holds two entries at one normalized project URL
- **THEN** the build fails naming codm and leaves published outputs unchanged

#### Scenario: Another source lists the same project

- **WHEN** a higher-precedence source supplies a candidate with a normalized
  URL equal to a committed codm entry's
- **THEN** the committed entry still enters composition as a dual-screen
  codm candidate, and pack-composition selects between the two builds

#### Scenario: A selected project is removed

- **WHEN** an accepted source update removes a candidate required by an active
  rule or pin
- **THEN** pack composition fails explicitly rather than silently ignoring the
  stale selector

## REMOVED Requirements

### Requirement: RJNY export flags select entries per variant

**Reason**: Replaced by "RJNY export flags decide entry kind": the flags now set only whether an entry is a baseline or a dual-screen build, and no longer keep an entry out of a pack.

**Migration**: No configuration change. An RJNY entry only in the standard export now also reaches dual when its family has no dual-screen build; deny it there with a denial naming only the dual-screen pack if it must stay out.
