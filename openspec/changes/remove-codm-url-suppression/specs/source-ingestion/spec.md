## ADDED Requirements

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
preference, precedence, pins and package denials in pack-composition decide
between a codm2000 build and another source's build of the same app.

Retained entries SHALL preserve codm2000 provenance, generated origin, original
package identity and source settings, so family rules and fork-specific overlays
that select a generated entry match it. How a policy selector is validated
against the admitted candidates, and what a missing rule target or pinned
candidate does, is defined by "Composition policy separates app families from
package identities" and "Explicit selections identify an eligible candidate" in
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

### Requirement: No source record carries composition policy fields

This requirement SHALL apply to every record a source normalizes,
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
corrected by editing it. The one other field name
ingestion reserves is `meta`, which the RJNY catalog uses for its export flags
and presentation overrides and which is not part of an Obtainium app object:
ingestion SHALL drop a top-level `meta` from a record of any source, so it never
reaches a pack. Every other field ingestion does not model SHALL be retained
unchanged for rendering, from every source.

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

#### Scenario: Unrelated unmodeled field passes through

- **WHEN** an otherwise valid entry from any source carries a top-level field
  that ingestion does not model and that is not `family`, `packageId`,
  `variant` or `meta`
- **THEN** ingestion retains the field unchanged for rendering rather than
  rejecting or removing it

#### Scenario: A record outside RJNY carries catalog metadata

- **WHEN** an otherwise valid extras or committed codm2000 record carries a
  top-level `meta`
- **THEN** ingestion accepts the record and the rendered entry carries no `meta`

## REMOVED Requirements

### Requirement: Committed codm2000 entries are dual-screen builds that keep their generated identity

**Reason**: It suppressed a codm2000 candidate whenever a higher-precedence
source listed the same project URL with dual eligibility, a rule no other
source has.

**Migration**: "Every committed codm2000 entry is a dual-screen candidate with
its generated identity" carries the rest of the requirement unchanged. Owner
configuration settles overlaps: package-ID corrections, family rules, pins and
denials.

### Requirement: Source records carry no composition policy fields

**Reason**: It named suppressed codm2000 records and had a scenario for them;
codm2000 records are no longer suppressed.

**Migration**: "No source record carries composition policy fields" states the
same rule without the suppression case.
