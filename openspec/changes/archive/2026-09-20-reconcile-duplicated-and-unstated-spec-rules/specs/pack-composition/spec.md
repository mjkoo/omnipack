## MODIFIED Requirements

### Requirement: Each build is a baseline build or a dual-screen build

Every candidate build SHALL be either a baseline build or a dual-screen build.
A build SHALL be a dual-screen build exactly when it is eligible for dual only,
and dual preference SHALL be derived from that alone, with no separate
preference setting. A build's kind and eligibility SHALL come only from its
source, as source ingestion defines for each source. No candidate rule or other
composition setting SHALL change a build's eligibility or dual preference.

The single-screen pack SHALL select among a family's baseline builds. A valid
pin comes first, as "Explicit selections identify an eligible candidate"
defines. Absent a pin, a family's available
dual-screen build SHALL replace its baseline build in the dual-screen pack, a
family with no available dual-screen build SHALL use its dual-eligible baseline
build, and source precedence SHALL decide among builds of one kind. A family
whose only builds are dual-screen builds SHALL appear only in the dual-screen
pack. Nothing other than a pin naming a specific candidate SHALL make the
dual-screen pack select a baseline build over an available dual-screen build.

A package denial removes builds, not families, as "Package denials exclude
candidates from both variants" defines, including where a family's baseline and
dual-screen builds share the denied package id.

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

### Requirement: Explicit selections identify an eligible candidate

Policy SHALL permit one candidate pin per family and variant. A pin SHALL name
an original candidate selector and a rationale, and SHALL select that candidate
ahead of dual preference or source ranking. A dual pin MAY therefore name a
dual-eligible baseline build even when the family has an available dual-screen
build, and SHALL keep that baseline build in the dual-screen pack in place of
the family's dual-screen build whether or not the two builds share a package id.
A missing, ambiguous, excluded,
wrong-family or target-ineligible pinned candidate SHALL fail the build. A pin
SHALL NOT implicitly override an exclusion or eligibility restriction. Multiple
pins for one family and target SHALL fail.

#### Scenario: A dual pin selects a baseline build over a dual-screen build

- **WHEN** a valid dual pin names a baseline build eligible for dual and the
  family has an available dual-screen build
- **THEN** the pinned build wins and the report identifies the explicit selection

#### Scenario: Pinned build disappears

- **WHEN** successful ingestion does not supply the pinned candidate
- **THEN** the build fails without selecting another build

#### Scenario: Pin conflicts with a denial

- **WHEN** a pin names a candidate whose effective package is denied
- **THEN** the build fails with the conflicting pin and denial identified

### Requirement: Composition policy separates app families from package identities

The system SHALL load a versioned committed composition policy. A candidate
SHALL retain original source, source origin, package id and normalized project
URL. These fields SHALL identify a candidate after identical duplicates
collapse; different records sharing that identity SHALL fail rather than be
chosen by order. Policy candidate selectors SHALL match this original identity
exactly once. Every policy selector, including the selector a pin matches with,
SHALL name one of the sources the pipeline ingests and an origin belonging to
that source, and SHALL fail with the selector and the offending value identified
otherwise. A selector's `url` SHALL be one the pipeline can normalize for
comparison: a host SHALL be readable from it, any port SHALL be numeric and in
the valid range, and it SHALL contain no whitespace. Failure SHALL identify that
field and the offending value. Corrections SHALL NOT recursively match other
rules. Unmatched or ambiguous selectors, duplicate selectors, invalid targets,
unknown fields and inconsistent rules SHALL fail with the affected selector
identified.

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

A candidate-rule field other than `match`, `rationale`, `packageId` and `family`
SHALL fail as an unknown candidate-rule field with the rule and field
identified. An identity correction SHALL be the maintainer's decision, made from
recorded primary APK manifest evidence as "Curation evidence states its limits"
in pack-curation requires of identity decisions; the pipeline SHALL NOT verify
it. Rules projecting to the same effective id and normalized URL SHALL agree on
family, so rendered-family interpretation is unambiguous, and a projection SHALL
carry the family only. Build SHALL reject any candidate sharing that rendered
key whose family contradicts the projection, including candidates without their
own rule. Projections SHALL impose no offline eligibility restriction, because
source-derived eligibility cannot be reconstructed from rendered entries.
Composition SHALL NOT serialize the family, original identity, eligibility or
selection reason it computes into Obtainium app records.

#### Scenario: Different package ids represent replacement builds

- **WHEN** explicit policy assigns a baseline build and a different-package
  dual-screen build to one family
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

#### Scenario: A selector's URL has no host

- **WHEN** a candidate rule or a pin selects with a `url` no host can be read
  from, one with a non-numeric or out-of-range port, or one containing
  whitespace
- **THEN** configuration fails with that field and the offending value
  identified, before any candidate is matched

### Requirement: One candidate is selected per family and variant under a fixed precedence

The system SHALL use effective package id as the default family key and explicit
family rules for declared replacements. It SHALL select at most one candidate
per family per variant, honoring a valid explicit pin first, as "Explicit
selections identify an eligible candidate" defines. Otherwise single
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

### Requirement: Family selections are reported

The system SHALL report every selected family and variant with the winning
candidate's original and effective package ids, project URL, source and origin,
the other candidates of that family it was chosen over, and one selection
reason: pin, dual preference, ordinary fallback or source precedence. The reason
SHALL be the pin whenever a pin selected the winner. Otherwise single SHALL
report source precedence, and dual SHALL report dual preference when the winner
is a dual-screen build and ordinary fallback when the family had no available
dual-screen build, including when source precedence chose among several
baseline builds. Exclusions and stale exclusions SHALL also be reported.

#### Scenario: Lower-source dual build wins

- **WHEN** a dual-preferred BBoi entry defeats an ordinary RJNY entry
- **THEN** the report names the winner, lists the RJNY candidate as considered
  and identifies dual preference as the reason

#### Scenario: Identity correction is visible in the selection

- **WHEN** an evidenced rule changes the winning candidate's effective package id
- **THEN** the selection records both its original and effective package ids

#### Scenario: Dual falls back among several baseline builds

- **WHEN** a family has no available dual-screen build and source precedence
  chooses among its dual-eligible baseline builds
- **THEN** the dual selection's reason is ordinary fallback and the single
  selection's reason is source precedence

### Requirement: Package denials exclude candidates from both variants

A denylist entry SHALL contain exactly a nonempty effective package `id` and a
nonempty `reason`. The system SHALL exclude every candidate carrying that
effective package id from both variants before selection and report the
exclusion. Package denials SHALL match effective package identities across
sources. A package denial SHALL NOT remove different-package alternatives merely
because they share a family, so a family SHALL be absent from a variant after
denials only when none of its remaining candidates is eligible there. Where a
family's baseline and dual-screen builds share a package id, a denial of that id
SHALL remove both builds from both packs, and a family whose only builds share
the denied package id is therefore absent from both packs. An entry matching no
candidate SHALL be reported as a stale exclusion and SHALL NOT fail the build.
An entry whose only matching candidates are eligible for neither variant SHALL
count as matched: it removes nothing, reports no exclusion and SHALL NOT be
reported stale. Any other field SHALL fail explicitly with the entry identified.

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

#### Scenario: A denial matches only candidates eligible for neither variant

- **WHEN** a denial names a package id carried only by candidates that are
  eligible for neither variant
- **THEN** nothing is removed, no exclusion is reported, and the denial is not
  reported stale

### Requirement: Every single-screen family has a dual-screen selection

Every family selected in single SHALL have a selected build in dual. Upstream
eligibility restrictions, unresolved generated links, denials of other packages
in the family and verification failures SHALL NOT waive family coverage. An app
therefore cannot be published in single only. An app is kept out of both packs
by denying every package id its family's builds carry, since a package denial
removes builds, not families, as "Package denials exclude candidates from both
variants" defines. Different-package replacements in one declared
family SHALL satisfy coverage. Dual-only additions SHALL NOT require a single
counterpart.

#### Scenario: Different-package dual replacement

- **WHEN** single and dual select different package ids in the same declared family
- **THEN** family coverage passes without requiring both packages in dual

#### Scenario: An app is missing from the dual-screen variant

- **WHEN** single selects a family with no dual-eligible candidate
- **THEN** the build fails with the family coverage gap rather than copying an ineligible build

#### Scenario: The only dual build is denied

- **WHEN** the only dual-eligible candidate of a single-selected family carries a denied package
- **THEN** the build fails with the family coverage gap

## RENAMED Requirements

- FROM: `### Requirement: Entries are unioned by package id under a fixed precedence`
- TO: `### Requirement: One candidate is selected per family and variant under a fixed precedence`
