## ADDED Requirements

### Requirement: Composition policy separates app families from package identities

The system SHALL load a versioned committed composition policy. A candidate
SHALL retain original source, source origin, package id and normalized project
URL. These fields SHALL identify a candidate after identical duplicates collapse;
different records sharing that identity SHALL fail rather than be chosen by order.
Policy candidate selectors SHALL match this original identity exactly once.
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

### Requirement: Package denials exclude candidates from both variants

A denylist entry SHALL contain exactly a nonempty effective package `id` and a
nonempty `reason`. The system SHALL exclude every candidate carrying that
effective package id from both variants before selection and report the
exclusion. Package denials SHALL match effective package identities across
sources. A package denial SHALL NOT remove different-package alternatives merely
because they share a family, so a family SHALL be absent from a variant after
denials only when none of its remaining candidates is eligible there. An entry
matching no candidate SHALL be reported as
a stale exclusion and SHALL NOT fail the build. Any other field SHALL fail
explicitly with the entry identified.

#### Scenario: Denied by package id

- **WHEN** several sources contribute a denied package
- **THEN** no candidate carrying that package is selected in either output

#### Scenario: Package exclusion permits an alternative

- **WHEN** a preferred dual package is denied and its family has another eligible package
- **THEN** dual can select that alternative unless a conflicting pin fails validation

#### Scenario: Denylist entry matches no candidate

- **WHEN** a denial names a package that no candidate carries
- **THEN** the exclusion is reported stale, changes nothing and does not fail the build

#### Scenario: Denylist entry carries an unknown field

- **WHEN** a denylist entry carries a field other than `id` and `reason`
- **THEN** the build fails with the entry and the unknown field identified

## MODIFIED Requirements

### Requirement: Each build is a baseline build or a dual-screen build

Every candidate build SHALL be either a baseline build or a dual-screen build.
A build SHALL be a dual-screen build exactly when it is eligible for dual only,
and dual preference SHALL be derived from that alone, with no separate
preference setting. A build's kind and eligibility SHALL come only from its
source, as source ingestion defines for each source. No candidate rule or other
composition setting SHALL change a build's eligibility or dual preference.

The single-screen pack SHALL select among a family's baseline builds. A valid
pin comes first: it selects the one candidate it names for its family and pack
ahead of dual-screen replacement and source precedence, as explicit selections
define, and it may name a dual-eligible baseline build for dual even when the
family has an available dual-screen build. Absent a pin, a family's available
dual-screen build SHALL replace its baseline build in the dual-screen pack, a
family with no available dual-screen build SHALL use its dual-eligible baseline
build, and source precedence SHALL decide among builds of one kind. A family
whose only builds are dual-screen builds SHALL appear only in the dual-screen
pack. Nothing other than a pin naming a specific candidate SHALL make the
dual-screen pack select a baseline build over an available dual-screen build.

A package denial removes builds, not families, as "Package denials exclude
candidates from both variants" defines. Where a family's baseline and
dual-screen builds share a package id, a denial of that id SHALL remove both
builds from both packs, and the family's builds carrying other package ids
SHALL stay selectable. A family whose only builds share the denied package id
is therefore absent from both packs. A dual pin naming a family's baseline
build SHALL keep it in the dual-screen pack in place of the family's
dual-screen build, whether or not the two builds share a package id.

#### Scenario: A dual-screen build replaces the baseline in dual

- **WHEN** a family has a baseline build eligible for both packs and a
  dual-screen build, and no pin applies
- **THEN** single selects the baseline build and dual selects the dual-screen
  build, even when the baseline build comes from a higher-precedence source

#### Scenario: A family has no dual-screen build

- **WHEN** a family's builds are all baseline builds eligible for both packs,
  and no pin applies
- **THEN** both packs select among those baseline builds by source precedence

#### Scenario: A family has only a dual-screen build

- **WHEN** a family's only build is a dual-screen build
- **THEN** it is selected in the dual-screen pack and the single-screen pack
  has no entry for that family

#### Scenario: A denied package shared by both builds leaves other packages selectable

- **WHEN** a denial names a package id carried by both a family's baseline
  build and its dual-screen build, and the family has another baseline build
  with a different package id that is eligible for both packs
- **THEN** neither denied build is selected in either pack, and the
  different-package baseline build is selected in both

#### Scenario: A dual pin keeps a baseline build that shares its package

- **WHEN** a family's baseline build eligible for both packs and its
  dual-screen build share a package id, and a valid dual pin names the
  baseline build
- **THEN** both packs select the baseline build, the dual-screen build is
  selected in neither, and the dual selection's reason is the pin

### Requirement: Composition runs in a fixed stage order

The system SHALL normalize candidates, apply identity and family rules, remove
excluded candidates, validate explicit selections, select by family and target,
validate overlay targets, apply overlays, and check unique packages and family
coverage. Exclusions SHALL observe corrected package identities before selection
and SHALL NOT be re-applied after overlays. Overlays SHALL NOT assign or delete
`id`, `url`, `overrideSource`, `family`, `packageId` or `variant`, including by
null deletion. Failures SHALL preserve the previous output pair and diagnostics
already collected.

#### Scenario: An overlay cannot move an entry onto a denylisted package id

- **WHEN** an overlay contains an id field naming a denied package
- **THEN** the build fails because identity fields are forbidden in overlays

#### Scenario: Denylist removes an entry an overlay names

- **WHEN** candidate exclusions leave no selected entry matching an overlay selector
- **THEN** the build fails with that stale selector identified

### Requirement: One overlay patches composed entries

The overlay file SHALL contain an array of records with effective package `id`,
project `url` and object `patch`. An overlay document that is not an array
SHALL fail with the overlay identified. Each record SHALL apply to the matching
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

### Requirement: Explicit policy separates app families from package identities

**Reason**: Replaced by "Composition policy separates app families from package identities", which keeps every policy rule and states candidate-rule unknown-field rejection generically instead of naming the retired `eligible` and `dualPreferred` fields.

**Migration**: None. Candidate rules carrying `eligible` or `dualPreferred` still fail as unknown fields.

### Requirement: Denied packages are excluded from both variants

**Reason**: Replaced by "Package denials exclude candidates from both variants", which keeps every denial rule and states unknown-field rejection generically instead of naming retired family or variant selectors.

**Migration**: None. A denylist entry carrying `family` or `variant` still fails as an unknown field.
