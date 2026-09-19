## MODIFIED Requirements

### Requirement: Composition policy separates app families from package identities

The system SHALL load a versioned committed composition policy. A candidate
SHALL retain original source, source origin, package id and normalized project
URL. These fields SHALL identify a candidate after identical duplicates collapse;
different records sharing that identity SHALL fail rather than be chosen by order.
Policy candidate selectors SHALL match this original identity exactly once.
Every policy selector, including the selector a pin matches with, SHALL name one
of the sources the pipeline ingests and an origin belonging to that source, and
SHALL fail with the selector and the offending value identified otherwise.
Corrections SHALL NOT recursively match other rules. Unmatched or ambiguous selectors,
duplicate selectors, invalid targets, unknown fields and inconsistent rules SHALL
fail with the affected selector identified.

A candidate SHALL default to family `package:<effective-package-id>`. Explicit
family assignments SHALL use the separate `app:` namespace and SHALL NOT be
inferred from names, categories or repository ancestry. A candidate rule SHALL
contain a `match` selector and a `rationale`, SHALL permit an effective
package-id correction (`packageId`) and a family assignment (`family`) for
candidates that are not track-only, and SHALL preserve original provenance.
If the ingested candidate has `trackOnly: true` in its normalized settings,
a matching rule containing either `family` or `packageId` SHALL fail the build
with the affected selector identified, including a `packageId` equal to the
original id. This restriction SHALL apply before exclusions and selection,
regardless of whether the candidate would win or be denied. A track-only
candidate without either assignment SHALL retain its ingested id and default
`package:<id>` family; a selector-and-rationale-only rule SHALL remain valid.
Any candidate that is not track-only whose effective package id, whether its
ingested id or its rule's corrected id, equals the ingested id of a
track-only candidate SHALL also fail the build with that candidate's selector
identified. This restriction SHALL apply whether or not the candidate has a
rule, and SHALL likewise apply before exclusions and selection, regardless of
whether either candidate would win or be denied.

A rule SHALL NOT set eligibility or dual preference, which come only from the
build's source. A candidate-rule field other than `match`, `rationale`,
`packageId` and `family` SHALL fail as an unknown candidate-rule field with the
rule and field identified. Identity corrections SHALL have recorded primary APK
manifest evidence. Rules projecting to the same effective id and normalized URL
SHALL agree on family, so rendered-family interpretation is unambiguous, and a
projection SHALL carry the family only. Build SHALL reject any candidate
sharing that rendered key whose family contradicts the projection, including
candidates without their own rule. Projections SHALL impose no offline
eligibility restriction, because source-derived eligibility cannot be
reconstructed from rendered entries. Composition SHALL NOT serialize the
family, original identity, eligibility or selection reason it computes into
Obtainium app records.

#### Scenario: Different package ids represent replacement builds

- **WHEN** explicit policy assigns a standard build and a different-package dual
  build to one family
- **THEN** they compete within that family for dual selection
- **AND** each selected output retains its build's own effective package id

#### Scenario: Similar fork names have no family declaration

- **WHEN** two candidates have different ids and similar names or repository ancestry
- **THEN** they remain separate default families

#### Scenario: Corrected package participates in collisions

- **WHEN** an evidenced rule changes a candidate's effective package id
- **THEN** grouping, exclusions and final package uniqueness use the effective id
- **AND** reports retain both original and effective ids

#### Scenario: Rules disagree on a rendered identity

- **WHEN** two source-specific rules project to one effective id and URL but assign
  different families
- **THEN** configuration fails instead of making offline interpretation ambiguous

#### Scenario: A rule carries an unknown field

- **WHEN** a candidate rule carries a field other than `match`, `rationale`,
  `packageId` and `family`
- **THEN** configuration fails with the rule and the unknown field identified

#### Scenario: A selector pairs a source with another source's origin

- **WHEN** a candidate rule or a pin selects with a selector naming one source
  and an origin that belongs to a different source
- **THEN** configuration fails with the selector and the invalid origin
  identified, before any candidate is matched

#### Scenario: Track-only resource is assigned to an app family

- **WHEN** a rule assigns a family to an ingested track-only candidate
- **THEN** the build fails with that selector identified before a pin or source ranking can hide or select the candidate

#### Scenario: Track-only identity is corrected or restated

- **WHEN** a rule supplies `packageId` for an ingested track-only candidate, whether different from or equal to its original id
- **THEN** the build fails with that selector identified

#### Scenario: Track-only candidate would be excluded

- **WHEN** a track-only candidate has a prohibited rule assignment and a package denial would remove it
- **THEN** the build fails on the invalid rule rather than ignoring it because of the denial

#### Scenario: Track-only candidate has a descriptive rule

- **WHEN** a track-only candidate has a matching rule containing only its selector and rationale
- **THEN** its ingested identity and default family remain unchanged and the rule does not cause rejection

#### Scenario: Identity correction takes a track-only id

- **WHEN** a rule for a candidate that is not track-only sets `packageId` equal to the ingested id of a track-only candidate
- **THEN** the build fails with that candidate's selector identified before exclusions, a pin or source ranking can hide either candidate

#### Scenario: Ingested id already equals a track-only id

- **WHEN** a candidate that is not track-only has an ingested id equal to the ingested id of a track-only candidate, and it has no rule or a rule containing only its selector and rationale
- **THEN** the build fails with that candidate's selector identified before exclusions, a pin or source ranking can hide either candidate

### Requirement: Entries are unioned by package id under a fixed precedence

The system SHALL use effective package id as the default family key and explicit
family rules for declared replacements. It SHALL select at most one candidate
per family per variant, honoring a valid explicit pin first. Otherwise single
SHALL consider single-eligible candidates; dual SHALL consider dual-preferred
eligible candidates when any exist, or all dual-eligible candidates otherwise.
Within that tier, precedence SHALL be extras, RJNY, BBoi34, then generated.
The winning candidate SHALL be retained whole, not merged with losing entries.

A family having no dual-preferred candidate left after successful ingestion and
deliberate exclusions SHALL be an ordinary outcome: dual SHALL select among that
family's remaining dual-eligible candidates and the build SHALL NOT fail for the
absence, unless a pin names a candidate that is absent. A source that cannot be
fetched SHALL abort the build instead, as "A failed fetch aborts the build" in
source-ingestion defines, so a missing preferred candidate and a missing source
are never confused.

Identical duplicates SHALL collapse. Different candidates tied at the winning
rank SHALL fail with the family, variant and selectors identified, requiring an
explicit selection. Ties among nonwinning candidates SHALL NOT displace a unique
winner. Iteration order, names, URLs and release dates SHALL NOT break ties.
Different families selecting the same effective package id in one variant SHALL
fail rather than be silently collapsed. A package id SHALL occur at most once
in each output, including when family rules separate candidates sharing an id.

#### Scenario: Two sources contribute the same id

- **WHEN** ordinary RJNY and BBoi entries compete for one family and target
- **THEN** RJNY wins and retains its complete entry

#### Scenario: Dual suitability outranks source precedence

- **WHEN** ordinary RJNY and dual-preferred BBoi builds compete for the same dual family
- **THEN** BBoi wins dual selection while the eligible ordinary build remains available to single

#### Scenario: Standard extra does not suppress a dual fork

- **WHEN** an ordinary extra and a dual-preferred generated build compete without a pin
- **THEN** dual selects the preferred build and single selects the extra if eligible

#### Scenario: Preferred build is absent from a valid source snapshot

- **WHEN** all source acquisition succeeds, no preferred candidate exists, and no pin requires one
- **THEN** dual selection uses an eligible ordinary candidate if available

#### Scenario: One source contributes the same id with different content

- **WHEN** one source contributes two different candidates tied at the winning tier
- **THEN** composition fails with both selectors rather than choosing by input order

#### Scenario: One source contributes an identical entry twice

- **WHEN** a source contributes an identical candidate twice
- **THEN** it contributes one candidate and does not create a selection conflict

#### Scenario: Families select a colliding package

- **WHEN** two families select candidates carrying one effective package id in dual
- **THEN** the build fails with the package id and both families identified

#### Scenario: An extras entry collides with an upstream entry

- **WHEN** an extras entry shares a family with an upstream candidate at the same dual-preference tier and no pin applies
- **THEN** extras wins and its complete entry is selected

### Requirement: One overlay patches composed entries

The overlay file SHALL contain an array of records with effective package `id`,
project `url` and object `patch`. An overlay document that is not an array
SHALL fail with the overlay identified. A record SHALL carry no field other than
`id`, `url` and `patch`, and SHALL fail with the record and the unknown field
identified otherwise. A record's `id` SHALL be a nonempty string, and its `url`
SHALL be a nonempty string that identifies a project, each failing with the
record and the offending value identified. Each record SHALL apply to the matching
selected entry in every variant that selects it. Matching SHALL use both
effective id and normalized project URL. Duplicate selectors SHALL fail. A
non-object patch, including null, SHALL fail.

Patches SHALL use recursive JSON Merge Patch, where null deletes an allowed key.
The protected patch fields SHALL be exactly `id`, `url`, `overrideSource`,
`family`, `packageId` and `variant`: a patch SHALL NOT contain any of them with
any value, including null. Every other key SHALL be patchable, and all other
unpatched data SHALL remain unchanged. Shared settings for distinct project URLs
SHALL require explicit records for each project; a common package id SHALL NOT
make a patch transfer to another fork. Whole-app removal SHALL remain the
denylist's responsibility.

#### Scenario: Overlay changes a setting

- **WHEN** both variants select the same effective id and normalized URL
- **THEN** a matching patch applies to both

#### Scenario: Shared package id uses different repositories

- **WHEN** single and dual select one package id from different project URLs
- **THEN** a patch naming the single repository does not affect the dual repository

#### Scenario: Overlay deletes a key

- **WHEN** a patch maps an allowed key to null
- **THEN** the key is deleted before normal rendering hydration

#### Scenario: Protected field is assigned or deleted

- **WHEN** a patch contains `id`, `url`, `overrideSource`, `family`,
  `packageId` or `variant`, with any value including null
- **THEN** the build fails naming the selector and forbidden field

#### Scenario: Overlay record carries an unknown field

- **WHEN** an overlay record carries a field other than `id`, `url` and `patch`
- **THEN** the build fails with that record and the unknown field identified,
  rather than ignoring the field or treating the record as matching nothing

#### Scenario: Overlay document is not an array

- **WHEN** the overlay file holds a JSON object or another non-array value
- **THEN** the build fails with the overlay identified as not being an array
  of patch records

#### Scenario: Overlay maps a package id to something other than an object

- **WHEN** an overlay record has a null patch
- **THEN** the build fails rather than removing the app

#### Scenario: Overlay patch contains the source-type field

- **WHEN** an overlay record's patch contains overrideSource
- **THEN** the build fails with the selector and protected field identified

#### Scenario: Overlay patch contains the package-id field

- **WHEN** an overlay record's patch contains id
- **THEN** the build fails with the selector and protected field identified

#### Scenario: Overlay patch maps the source-type or package-id field to null

- **WHEN** a patch maps overrideSource or id to null
- **THEN** the build fails because protected fields cannot be deleted

## REMOVED Requirements

### Requirement: Selected build verification does not change composition

**Reason**: The requirement prohibits publication eligibility depending on a separate lookup of the selected project's release metadata after a successful build, and prohibits that lookup triggering reselection. Composition performs no such lookup and has no reselection step: it runs once over the candidate set ingestion supplied, and two of the requirement's three scenarios describe a replacement that cannot occur in that pipeline. What remains true of it is stated elsewhere. That a selected build failing structural verification prevents publication without changing composition is nightly-publishing's eligibility contract, which states it against the publication workflow that really makes the decision. That an entire source fetch failure aborts the build is "A failed fetch aborts the build" in source-ingestion. That configured release fallback within one selected project is separate is readme-source-generation's consumer fallback rule.

**Migration**: None. The one rule this requirement stated that no other requirement did, that dual falls back to an eligible ordinary candidate when successful ingestion and deliberate exclusions leave no preferred candidate and no pin requires one, is carried into "Entries are unioned by package id under a fixed precedence" together with its scenario "Preferred build is absent from a valid source snapshot".
