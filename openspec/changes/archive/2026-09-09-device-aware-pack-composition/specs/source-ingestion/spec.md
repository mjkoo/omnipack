## MODIFIED Requirements

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

### Requirement: codm2000 entries are generated from GitHub project links

The codm2000 catalog is a README of links rather than a machine-readable
catalog. The system SHALL extract its project links, SHALL keep only those
that address a GitHub repository, and SHALL skip the rest. Generated entries
SHALL be candidates for the dual-screen variant only, so the test for a project
another source already covers is scoped to that variant after explicit
eligibility rules have been applied to higher-source candidates: a link SHALL NOT
produce a generated entry when a higher-precedence source already contributes
that project as a candidate for the dual-screen variant, compared in the
pipeline's normalized URL form before exclusions and selection, and SHALL produce one otherwise. A project that
a higher-precedence source contributes to the single-screen variant alone
therefore still generates its dual-screen candidate, since nothing else would
supply that variant.

Generated builds SHALL be dual-preferred within their family unless explicit
policy overrides that preference. Merely listing a covered project in codm SHALL
NOT promote a higher-source ordinary build to dual-preferred. Generated rules
SHALL be applied after package resolution; all active candidate selectors SHALL then be
validated against the complete candidate set. Historical mappings SHALL be exempt from candidate-presence checks.
A missing rule or pinned candidate SHALL fail explicitly rather than be treated as an ordinary unresolved skip.

A README link supplies no display name and no grouping of its own, so a
generated entry SHALL carry as its name the repository name of its project URL,
and SHALL carry an empty category list. An entry with no category is already
governed: it sorts as though its primary category were the empty string and it
contributes nothing to the rendered settings block's category union.

#### Scenario: Generated entry takes its name from the repository

- **WHEN** a README row links to a GitHub repository that no other source
  contributes and whose package id resolves
- **THEN** the generated entry's name is that repository's name and its
  category list is empty

#### Scenario: Link is not a GitHub repository

- **WHEN** a README row links to a host with no APK release feed
- **THEN** no entry is generated for that row and the row is reported as
  skipped

#### Scenario: Link already covered as a dual-screen candidate

- **WHEN** a README row links to a repository that a higher-precedence source
  already contributes as a candidate for the dual-screen variant, spelled
  differently but equal once normalized
- **THEN** no entry is generated for that row

#### Scenario: Link covered in the single-screen variant only

- **WHEN** a README row links to a repository that a higher-precedence source
  contributes as a candidate for the single-screen variant only
- **THEN** a generated entry is produced for that row as a candidate for the
  dual-screen variant

#### Scenario: Policy removes higher-source dual eligibility

- **WHEN** a higher-source project would normally cover dual but policy restricts it to single
- **THEN** its codm link can generate a dual candidate

#### Scenario: Covered ordinary build is also listed by codm

- **WHEN** a higher-source ordinary candidate already covers that project's dual target
- **THEN** codm generates no duplicate and does not change that candidate's preference

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

