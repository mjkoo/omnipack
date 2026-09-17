## ADDED Requirements

### Requirement: Source records carry no composition policy fields

This requirement SHALL apply to every record a source normalizes, including a
committed codm2000 record later suppressed by higher-precedence dual coverage,
and SHALL NOT apply to an RJNY entry marked as excluded from export, which is
dropped before normalization. Every such record, from each upstream catalog, the
committed codm2000 catalog and the hand-written extras, SHALL be
an Obtainium app object as its source publishes it, and the extras
`dualScreen` field SHALL be the only field defined by this system that
ingestion reads from a source record. A source record carrying `family`,
`packageId` or `variant` at its top level SHALL fail ingestion regardless of
the field's value, including null, with an error naming the source, the entry
and the field, stating that the field cannot come from a source record, and
stating that composition policy in `config/composition.json` owns app
families, package identities and per-pack selection. The error SHALL NOT
direct or imply that the failure can be corrected by editing composition
policy. The failure SHALL persist while the configured source location serves
a record carrying the field, and the system SHALL provide no override for an
individual record or field; an extras entry or a committed codm2000 record is
corrected by editing it. Ingestion SHALL reserve no other field name: every
field it does not model SHALL be retained unchanged for rendering, from every
source.

#### Scenario: Upstream entry carries a package identity field

- **WHEN** an otherwise valid upstream catalog entry carries a top-level
  `packageId`
- **THEN** ingestion fails naming that source, the entry and `packageId`,
  stating that the field cannot come from a source record and that
  composition policy in `config/composition.json` owns package identities,
  without directing the correction to composition policy, and later builds
  from that source location fail the same way while the record carries the
  field

#### Scenario: Extras entry carries a null family

- **WHEN** an otherwise valid extras entry carries a top-level `family` whose
  value is null
- **THEN** ingestion fails naming extras, the entry and `family`

#### Scenario: Entry excluded from export is not checked

- **WHEN** an RJNY entry marked as excluded from export carries a top-level
  `family`
- **THEN** ingestion does not fail and the entry is dropped

#### Scenario: Suppressed codm2000 entry is checked

- **WHEN** a committed codm2000 entry whose normalized URL is covered by a
  higher-precedence dual candidate carries a top-level `variant`
- **THEN** ingestion fails naming codm2000, the entry and `variant`

#### Scenario: Unrelated unmodeled field passes through

- **WHEN** an otherwise valid entry from any source carries a top-level field
  that ingestion does not model and that is not `family`, `packageId` or
  `variant`
- **THEN** ingestion retains the field unchanged for rendering rather than
  rejecting or removing it

### Requirement: Hand-written extras are baseline or dual-screen builds

The system SHALL ingest each entry in the extras configuration as a candidate
entry, and SHALL fail the build with an error naming the entry when an extras
entry is missing a package id, a URL or a name. An extras entry has no upstream
record to take a display name from, and a name is not optional downstream:
rendering orders entries by name and the import format displays it. An extras
entry SHALL be a baseline build, a candidate for both variants, unless it
carries an optional boolean `dualScreen` set to true, which makes it a
dual-screen build: a candidate for the dual-screen variant only, preferred
there. `dualScreen` SHALL default to false, and a non-boolean value SHALL fail
the build with an error naming the entry. Composition policy SHALL NOT change
an extra's eligibility or dual preference. The extras adapter SHALL consume an
extras entry's `dualScreen` field so it does not reach that entry's Obtainium
app record.

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

#### Scenario: Ordinary extra competes with a dual fork

- **WHEN** a baseline extra and a dual-screen lower-source candidate share a
  family and no pin applies
- **THEN** the dual-screen candidate wins dual selection, and the extra does
  not win it solely through source precedence

## REMOVED Requirements

### Requirement: Hand-written extras are ingested as baseline or dual-screen builds

**Reason**: Replaced by "Hand-written extras are baseline or dual-screen builds", which keeps every extras build-kind rule but drops the rejection of the retired `variants` and `dualPreferred` fields and the stripping of other composition-only fields. "Source records carry no composition policy fields" now states the one field guard for every source.

**Migration**: No current extras entry carries a retired field. An extras entry carrying `variants`, `dualPreferred` or another formerly stripped name now passes it through unchanged as an ordinary unmodeled field, so remove it; set `dualScreen` to make a dual-screen build.
