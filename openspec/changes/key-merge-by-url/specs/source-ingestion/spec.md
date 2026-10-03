## ADDED Requirements

### Requirement: Source records carry no composition policy fields

This requirement SHALL apply to every record a source normalizes,
and SHALL NOT apply to an RJNY entry marked as excluded from export, which is
dropped before normalization. Every such record, from each upstream catalog, the
committed codm2000 catalog and the hand-written extras, SHALL be
an Obtainium app object as its source publishes it, and the extras
`dualScreen` field SHALL be the only field defined by this system that
ingestion reads from a source record. A source record carrying `family` or
`variant` at its top level SHALL fail ingestion regardless of
the field's value, including null, with an error naming the source, the entry
and the field, stating that the field cannot come from a source record, and
stating that composition policy in `config/composition.json` owns app
families and per-pack selection. The error SHALL NOT
direct or imply that the failure can be corrected by editing composition
policy. The failure SHALL persist while the configured source location serves
a record carrying the field, and the system SHALL provide no override for an
individual record or field; an extras entry or a committed codm2000 record is
corrected by editing it. The one other field name
ingestion reserves is `meta`, which the RJNY catalog uses for its export flags
and presentation overrides and which is not part of an Obtainium app object:
ingestion SHALL drop a top-level `meta` from a record of any source, so it never
reaches a pack. Every other field ingestion does not model SHALL be retained
unchanged for rendering, from every source.

#### Scenario: Upstream entry carries a variant field

- **WHEN** an otherwise valid upstream catalog entry carries a top-level
  `variant`
- **THEN** ingestion fails naming that source, the entry and `variant`,
  stating that the field cannot come from a source record and that
  composition policy in `config/composition.json` owns per-pack selection,
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

#### Scenario: Unrelated unmodeled field passes through

- **WHEN** an otherwise valid entry from any source carries a top-level field
  that ingestion does not model and that is not `family`, `variant` or `meta`,
  including `packageId`
- **THEN** ingestion retains the field unchanged for rendering rather than
  rejecting or removing it

#### Scenario: A record outside RJNY carries catalog metadata

- **WHEN** an otherwise valid extras or committed codm2000 record carries a
  top-level `meta`
- **THEN** ingestion accepts the record and the rendered entry carries no `meta`

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
eligibility. "Builds are baseline or dual-screen and each pack selects its kind" in
pack-composition states, once for every source, that no composition setting
changes either, which is also why none restores an entry to a pack its flags
leave it out of or revives an entry excluded from export.

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
  selection, if any, comes from another build in that family

### Requirement: BBoi34 entries map to variants by source file

The system SHALL retain each standard-asset record as a baseline build eligible
for both targets, and each dual-asset record as a dual-screen build eligible
only for dual and therefore preferred there. It SHALL preserve asset origin and
retain both records when one project appears in both assets. Selection SHALL
occur during composition: what a pin, a dual-screen build and a project denial
each do to a project present in both assets is defined by "Builds are baseline
or dual-screen and each pack selects its kind", "Pins select an eligible
candidate of their family" and "Project denials exclude candidates from both
variants" in pack-composition. The asset a record comes from SHALL alone decide
its kind.

#### Scenario: Id present in both BBoi34 assets

- **WHEN** both assets contain different builds of an id
- **THEN** ingestion retains both as separate candidates, a baseline build from
  the standard asset and a dual-screen build from the dual asset, and leaves
  the choice between them to composition

#### Scenario: Standard alternative remains available

- **WHEN** a family's standard-asset build is eligible for both targets and the
  family has no available dual-screen build, because the dual asset lacks one
  or a denial removed one at a project URL the standard build does not share
- **THEN** the retained standard build remains available for dual selection

### Requirement: Every committed codm2000 entry is a dual-screen candidate with its generated identity

The system SHALL ingest accepted codm2000 entries from committed Obtainium JSON.
README parsing and package-ID resolution SHALL occur only in the separate
source-generation operation. The source catalog SHALL contain generated GitHub
project entries independently of other upstream coverage, including APKs and
explicit track-only resources. It SHALL retain discovery settings such as
prerelease enablement and filename filters, and SHALL NOT reinterpret a
track-only resource ID as an Android package ID.

During routine ingestion, codm2000 entries SHALL be dual-screen builds, eligible
for dual only and preferred there. Every committed entry SHALL become a
candidate whether or not another source lists the same project, and ingestion
SHALL NOT read or apply the composition policy. Family formation, dual
preference, precedence, pins and project denials in pack-composition decide
between a codm2000 build and another source's build of the same app.

Retained entries SHALL preserve codm2000 provenance, generated origin, original
package identity and source settings, so family rules and fork-specific overlays
that select a generated entry match it. How a policy selector is validated
against the admitted candidates, and what a missing rule target or pinned
candidate does, is defined by "Composition policy assigns app families by
project URL" and "Pins select an eligible candidate of their family" in
pack-composition.

#### Scenario: Another source lists the same project

- **WHEN** a higher-precedence source supplies a candidate with a normalized URL equal to a committed codm2000 entry's
- **THEN** the committed entry still enters composition as a dual-screen codm2000 candidate, and pack-composition selects between the two builds

#### Scenario: Retained generated selectors keep matching

- **WHEN** a retained committed entry has a generated-origin rule or overlay selector
- **THEN** its source identity is preserved and the same family and override behavior applies

#### Scenario: A selected project is removed

- **WHEN** an accepted source update removes a candidate required by an active rule or pin
- **THEN** pack composition fails explicitly rather than silently ignoring the stale selector

#### Scenario: Committed prerelease entries retain their settings

- **WHEN** the committed catalog includes manifest-verified APK entries with explicit prerelease settings
- **THEN** they enter dual as installable APK entries, retaining those settings and their original identities without entering single

#### Scenario: A tracking resource keeps its identity

- **WHEN** the committed catalog includes an explicit track-only resource
- **THEN** dual retains its stable resource identity, track-only flag and manual-installation description
- **AND** neither pack's entry for the app the resource extends is replaced

### Requirement: Committed Quiver entries are baseline builds with generated provenance

Routine ingestion SHALL read Quiver entries from its configured committed
Obtainium catalog without requesting Quiver lists, release metadata or APKs.
A missing, unreadable or malformed catalog or repeated entry ID SHALL fail the
build while preserving previous outputs. Valid entries SHALL carry source
`quiver`, generated origin `quiver-generated`, their committed package identities,
explicit GitHub source type and reviewed discovery settings. They SHALL be
baseline candidates eligible for both packs, subject to ordinary normalization,
composition policy, denials and overlays. Every valid entry SHALL reach
composition, including entries sharing another source's project URL. Routine
ingestion SHALL NOT modify the catalog or generate missing entries. Source
records SHALL obey the existing prohibition on composition fields and preserve
generated provenance in reports without claiming a fresh APK check.

#### Scenario: Quiver hosting is unavailable during build

- **WHEN** the committed Quiver catalog and the other build inputs are valid
- **THEN** building succeeds without requesting Quiver hosting or APK data

#### Scenario: Broken committed Quiver catalog

- **WHEN** the configured catalog is missing, malformed or repeats an entry ID
- **THEN** the build fails naming Quiver and leaves published outputs unchanged

#### Scenario: Quiver record carries policy fields

- **WHEN** a committed Quiver record includes a top-level family or variant field
- **THEN** ingestion rejects it under the source-record policy-field prohibition

## REMOVED Requirements

### Requirement: No source record carries composition policy fields

**Reason**: `packageId` is no longer a composition policy field, so it is no longer reserved.

**Migration**: Replaced by "Source records carry no composition policy fields".
