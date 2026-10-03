## ADDED Requirements

### Requirement: Builds are baseline or dual-screen and each pack selects its kind

Every candidate build SHALL be either a baseline build or a dual-screen build.
A build SHALL be a dual-screen build exactly when it is eligible for dual only,
and dual preference SHALL be derived from that alone, with no separate
preference setting. A build's kind and eligibility SHALL come only from its
source, as source ingestion defines for each source. No candidate rule or other
composition setting SHALL change a build's eligibility or dual preference.

The single-screen pack SHALL select among a family's baseline builds. A valid
pin comes first, as "Pins select an eligible candidate of their family"
defines. Absent a pin, a family's available
dual-screen build SHALL replace its baseline build in the dual-screen pack, a
family with no available dual-screen build SHALL use its dual-eligible baseline
build, and source precedence SHALL decide among builds of one kind. A family
whose only builds are dual-screen builds SHALL appear only in the dual-screen
pack. Nothing other than a pin naming a specific candidate SHALL make the
dual-screen pack select a baseline build over an available dual-screen build.

A project denial removes builds, not families, as "Project denials exclude
candidates from both variants" defines, including where a family's baseline and
dual-screen builds share the denied project URL.

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

#### Scenario: A denied URL shared by both builds leaves other projects selectable

- **WHEN** a denial names a project URL carrying both a family's baseline
  build and its dual-screen build, and an explicit family also holds a
  baseline build at another URL that is eligible for both packs
- **THEN** neither denied build is selected in either pack, and the
  other-URL baseline build is selected in both

#### Scenario: A dual pin keeps a baseline build that shares its project

- **WHEN** a family's baseline build eligible for both packs and its
  dual-screen build share a project URL, and a valid dual pin names the
  baseline build
- **THEN** both packs select the baseline build, the dual-screen build is
  selected in neither, and the dual selection's reason is the pin


### Requirement: Pins select an eligible candidate of their family

Policy SHALL permit one candidate pin per family and variant. A pin SHALL name
an original candidate selector and a rationale, and SHALL select that candidate
ahead of dual preference or source ranking. A dual pin MAY therefore name a
dual-eligible baseline build even when the family has an available dual-screen
build, and SHALL keep that baseline build in the dual-screen pack in place of
the family's dual-screen build whether or not the two builds share a project
URL. A missing, ambiguous, excluded, wrong-family or target-ineligible pinned
candidate SHALL fail the build. A pin SHALL NOT implicitly override an
exclusion or eligibility restriction. Multiple pins for one family and target
SHALL fail. A pin whose candidate was removed by a denial or is eligible for no
variant belongs to no formed family, so it SHALL fail as a conflict with that
exclusion, identifying the pin and the denial or the ineligibility, before the
build-time formed-family comparison.

A pin SHALL name the family its candidate belongs to, as "Composition policy
assigns app families by project URL" defines: its explicit `app:` family, or
otherwise the normalized project URL of its candidate. A pin whose selector has
an explicit `app:` projection naming a different family SHALL fail when the
policy loads, identifying the pin and the projected family, whatever the
denylist says; the build SHALL check every other pin against its candidate's
formed family.

#### Scenario: A dual pin selects a baseline build over a dual-screen build

- **WHEN** a valid dual pin names a baseline build eligible for dual and the
  family has an available dual-screen build
- **THEN** the pinned build wins and the report identifies the explicit selection

#### Scenario: Pinned build disappears

- **WHEN** successful ingestion does not supply the pinned candidate
- **THEN** the build fails without selecting another build

#### Scenario: Pin conflicts with a denial

- **WHEN** a pin names a candidate whose project URL is denied
- **THEN** the build fails with the conflicting pin and denial identified

#### Scenario: A pin names another family for a denied projected candidate

- **WHEN** a pin selects a candidate whose rule projects `app:one`, names
  `app:two`, and a denial removes that candidate
- **THEN** policy loading fails with the pin and `app:one` identified

#### Scenario: A pin names a candidate removed before families form

- **WHEN** a pin names the URL family of a rule-less candidate that a denial
  removes or its source makes eligible for no variant
- **THEN** the build fails with the pin and the denial or the ineligibility
  identified rather than as wrong-family

#### Scenario: A pin selects a rule-less candidate projected into an explicit family

- **WHEN** a rule-less candidate is at the project URL of a candidate that a
  rule assigns `app:x`, and a pin selects the rule-less candidate
- **THEN** a pin naming `app:x` loads and selects it
- **AND** a pin naming the candidate's normalized project URL fails the build
  as wrong-family


### Requirement: Composition policy assigns app families by project URL

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
field and the offending value. A rule SHALL NOT recursively match other
rules. Unmatched or ambiguous selectors, duplicate selectors, invalid targets,
unknown fields and inconsistent rules SHALL fail with the affected selector
identified. A JSON object key repeated anywhere in the composition policy, at
any nesting level, SHALL fail policy loading with the repeated key identified,
in every command that loads the policy, rather than one occurrence silently
taking effect.

Families SHALL form once family rules and exclusions apply, over the
candidates that survive exclusions and are eligible for at least one variant.
Such a candidate SHALL belong to the explicit family of the family-rule
projection that covers it, whether or not the candidate a rule's selector
matches itself survives exclusions and eligibility filtering. Every other such
candidate SHALL belong to its default family, named by its normalized project
URL as "URLs are compared in a normalized form" in source-ingestion defines. A
shared package id SHALL NOT join candidates at different URLs. Excluded candidates and candidates eligible
for no variant SHALL neither join a family nor name a family. Explicit family
names SHALL use the `app:` namespace and SHALL NOT be inferred from names,
categories or repository ancestry.

A candidate rule SHALL contain a `match` selector and a `rationale`, SHALL
permit a family assignment (`family`) for candidates that are not track-only,
and SHALL preserve original provenance. Rules SHALL NOT change a candidate's
package id: a selected entry carries the id its source supplied. If the
ingested candidate has `trackOnly: true` in its normalized settings, a matching
rule containing `family` SHALL fail the build with the affected selector
identified. This restriction SHALL apply before exclusions and selection,
regardless of whether the candidate would win or be denied. A track-only
candidate SHALL retain its default family; a selector-and-rationale-only rule
SHALL remain valid.

A candidate-rule field other than `match`, `rationale` and `family` SHALL fail
as an unknown candidate-rule field with the rule and field identified. Only a
rule carrying `family` SHALL project a family, and a projection SHALL carry
that explicit `app:` family only. A family rule's URL is its selector's
normalized URL. When every family rule at a URL names one family, each of those
rules projects that family onto the whole URL, covering every candidate there.
When family rules at one URL name different families, each projects its family
onto its selector's package id at that URL only, covering the candidates there
that carry that id, and a candidate at that URL whose id no rule names belongs
to the URL's default family. Two family rules projecting onto one package id
and URL SHALL agree on family, failing with both rules identified otherwise,
so rendered-family interpretation is unambiguous. Projections SHALL
impose no offline eligibility restriction, because source-derived eligibility
cannot be reconstructed from rendered entries. Composition SHALL NOT serialize
the family, original identity, eligibility or selection reason it computes into
Obtainium app records.

#### Scenario: One project from several sources forms one family

- **WHEN** two sources contribute candidates with different package ids at one
  normalized project URL and no rule assigns either an explicit family
- **THEN** they form the family named by that URL and compete within it

#### Scenario: Different repositories sharing a package id stay separate

- **WHEN** candidates from different repositories carry one package
  id and no rule assigns either an explicit family
- **THEN** they form two families, one per normalized project URL

#### Scenario: Different repositories are joined by explicit rules

- **WHEN** rules assign a baseline build at one URL and a dual-screen build at
  another URL to one explicit family
- **THEN** they compete within that family for dual selection
- **AND** each selected output retains its build's own package id

#### Scenario: A family rule covers every build at its URL

- **WHEN** a rule assigns `app:x` to a BBoi candidate at project URL X, and
  Quiver and codm supply rule-less candidates at X with other package ids
- **THEN** all three belong to `app:x`

#### Scenario: Rules split one repository into two families

- **WHEN** one source contributes two candidates at one project URL with
  different package ids, and one rule assigns the first `app:a` and another
  assigns the second `app:b`
- **THEN** each candidate belongs to its rule's family, so each can be selected
  in the same variant
- **AND** a third candidate at that URL with another id belongs to the URL's
  default family

#### Scenario: Similar fork names have no family declaration

- **WHEN** two candidates have different project URLs and similar names or
  repository ancestry
- **THEN** they remain separate default families

#### Scenario: Rules disagree on a rendered identity

- **WHEN** two source-specific rules project to one id and URL but assign
  different families
- **THEN** configuration fails instead of making offline interpretation ambiguous

#### Scenario: A family rule sits on a candidate eligible for no variant

- **WHEN** a rule assigns `app:x` to an RJNY candidate eligible for no variant, a
  rule-less BBoi candidate is at the same project URL, and another eligible
  candidate is ruled into `app:x`
- **THEN** the BBoi candidate and the other candidate form `app:x`, and a pin
  naming `app:x` loads and selects within it

#### Scenario: A rule carries an unknown field

- **WHEN** a candidate rule carries a field other than `match`, `rationale` and
  `family`, such as `packageId`
- **THEN** configuration fails with the rule and the unknown field identified

#### Scenario: A selector pairs a source with another source's origin

- **WHEN** a candidate rule or a pin selects with a selector naming one source
  and an origin that belongs to a different source
- **THEN** configuration fails with the selector and the invalid origin
  identified, before any candidate is matched

#### Scenario: Track-only resource is assigned to an app family

- **WHEN** a rule assigns a family to an ingested track-only candidate
- **THEN** the build fails with that selector identified before a pin or source ranking can hide or select the candidate

#### Scenario: Track-only candidate would be excluded

- **WHEN** a track-only candidate has a prohibited rule assignment and a denial would remove it
- **THEN** the build fails on the invalid rule rather than ignoring it because of the denial

#### Scenario: Track-only candidate has a descriptive rule

- **WHEN** a track-only candidate has a matching rule containing only its selector and rationale
- **THEN** its ingested identity and default family remain unchanged and the rule does not cause rejection

#### Scenario: A selector's URL has no host

- **WHEN** a candidate rule or a pin selects with a `url` no host can be read
  from, one with a non-numeric or out-of-range port, or one containing
  whitespace
- **THEN** configuration fails with that field and the offending value
  identified, before any candidate is matched

#### Scenario: A denied candidate shares an explicit family

- **WHEN** a denied candidate shares an explicit family with candidates from
  other sources
- **THEN** the remaining candidates form families as if it were absent, so it
  neither keeps the family together nor names a family

#### Scenario: A candidate eligible for no variant shares an explicit family

- **WHEN** a candidate its source makes eligible for neither variant shares an
  explicit family with candidates from other sources
- **THEN** the remaining candidates form families as if it were absent, so it
  neither keeps the family together nor names a family

#### Scenario: A key outside the category map is repeated

- **WHEN** an object in the composition policy outside `categories`, such as a
  candidate rule, repeats a key such as `rationale`
- **THEN** policy loading fails with that key identified in `pack build`,
  `pack verify` and the offline gate alike, and neither occurrence takes effect


### Requirement: Composition stages run in a fixed order

The system SHALL normalize candidates, apply family rules, remove
excluded candidates, form families over the surviving candidates eligible for
at least one variant, validate explicit selections, select by family and
target, validate overlay
targets, apply overlays, assign categories, check family coverage and record
package ids repeated within a variant. Exclusions SHALL observe normalized
project URLs before selection and SHALL NOT be re-applied after overlays.
Because a removed candidate belongs to no formed family, its exclusion SHALL be
reported under its own normalized project URL, or under its explicit family
when a rule assigns one. Overlays SHALL NOT assign or delete `id`, `url`,
`overrideSource`, `family`, `variant` or `categories`, including by null
deletion. Failures SHALL preserve the previous output pair and diagnostics
already collected.

#### Scenario: An overlay cannot change an entry's identity

- **WHEN** an overlay record's patch contains an `id` or `url` field
- **THEN** the build fails because identity fields are forbidden in overlays

#### Scenario: Denylist removes an entry an overlay names

- **WHEN** candidate exclusions leave no selected entry matching an overlay record
- **THEN** the build fails with that stale record identified

#### Scenario: A removed candidate is reported under its own identity

- **WHEN** a denial removes a rule-less candidate and a candidate that a rule
  assigns `app:x`
- **THEN** the first exclusion is reported under its normalized project URL and
  the second under `app:x`


### Requirement: One candidate per family and variant is selected by fixed precedence

The system SHALL select within the families that "Composition policy assigns
app families by project URL" defines. It SHALL select at most one candidate
per family per variant, honoring a valid explicit pin first, as "Explicit
selections identify an eligible candidate" defines. Otherwise single
SHALL consider single-eligible candidates; dual SHALL consider dual-preferred
eligible candidates when any exist, or all dual-eligible candidates otherwise.
Within that tier, precedence SHALL be extras, RJNY, Quiver, BBoi34, then codm.
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

Every member of an explicit family is covered by a projection of that family,
and every member of a default family carries its project URL, so the family of
each selected entry SHALL be recoverable from its package id and normalized
project URL alone. Offline verification and the README catalog
rely on this, as "Offline verification labels and pairs rendered
entries by family" in pack-verification defines, and composition needs no separate
pairing check.

#### Scenario: Two sources contribute one project

- **WHEN** ordinary RJNY and BBoi entries at one project URL compete for one
  family and target
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

#### Scenario: One source contributes one project with different content

- **WHEN** one source contributes two different candidates tied at the winning tier
- **THEN** composition fails with both selectors rather than choosing by input order

#### Scenario: One source contributes an identical entry twice

- **WHEN** a source contributes an identical candidate twice
- **THEN** it contributes one candidate and does not create a selection conflict

#### Scenario: An extras entry collides with an upstream entry

- **WHEN** an extras entry shares a family with an upstream candidate at the same dual-preference tier and no pin applies
- **THEN** extras wins and its complete entry is selected

#### Scenario: Quiver ranks between RJNY and BBoi34

- **WHEN** a Quiver baseline competes within one family without a pin against a
  BBoi34 baseline, and separately against an RJNY or extras baseline
- **THEN** Quiver wins whole over the BBoi34 candidate
- **AND** the RJNY or extras candidate wins whole over Quiver

#### Scenario: Quiver supplies a missing baseline

- **WHEN** Quiver is the only baseline candidate of a project URL and codm
  supplies a dual-screen build at the same project URL
- **THEN** single selects Quiver and dual selects codm


### Requirement: Project denials exclude candidates from both variants

A denylist entry SHALL contain exactly a nonempty project `url` and a nonempty
`reason`, and its `url` SHALL be one the pipeline can normalize for
comparison, failing with the entry and the offending value identified
otherwise. The system SHALL exclude every candidate whose normalized project
URL equals the entry's from both variants before selection and report the
exclusion. A denial SHALL NOT remove candidates at other URLs merely because
they share a family or a package id, so a family SHALL be absent from a variant
after denials only when none of its remaining candidates is eligible there. An
entry matching no candidate SHALL be reported as a stale exclusion and SHALL NOT
fail the build. An entry whose only matching candidates are eligible for
neither variant SHALL count as matched: it removes nothing, reports no
exclusion and SHALL NOT be reported stale. Any other field SHALL fail
explicitly with the entry identified.

#### Scenario: Denied by project URL

- **WHEN** several sources contribute candidates at a denied project URL,
  spelled differently
- **THEN** no candidate at that URL is selected in either output

#### Scenario: A denial permits an alternative

- **WHEN** a preferred dual build's URL is denied and its explicit family has
  another eligible build at another URL
- **THEN** dual can select that alternative unless a conflicting pin fails validation

#### Scenario: A denial keeps another repository with the same package id

- **WHEN** a denied URL's candidates share a package id with a candidate at
  another URL
- **THEN** the other candidate remains selectable

#### Scenario: Denylist entry matches no candidate

- **WHEN** a denial names a URL no candidate carries
- **THEN** the exclusion is reported stale, changes nothing and does not fail the build

#### Scenario: Denylist entry carries an unknown field

- **WHEN** a denylist entry carries a field other than `url` and `reason`
- **THEN** the build fails with the entry and the unknown field identified

#### Scenario: A denial matches only candidates eligible for neither variant

- **WHEN** a denial names a URL carried only by candidates that are eligible
  for neither variant
- **THEN** nothing is removed, no exclusion is reported, and the denial is not
  reported stale


### Requirement: Overlay records patch selected entries by project URL

The overlay file SHALL contain an array of records with project `url` and
object `patch`. An overlay document that is not an array SHALL fail with the
overlay identified. A record SHALL carry no field other than `url` and `patch`,
and SHALL fail with the record and the unknown field identified otherwise. A
record's `url` SHALL be a nonempty string, failing with the record and the
offending field identified, and SHALL additionally be one a host can be read
from; one no host can be read from SHALL fail with the record, the field and
the offending value identified. Each record SHALL apply to every selected entry
whose normalized project URL equals the record's, in every variant that selects
one. Two records with one normalized URL SHALL fail. A non-object patch,
including null, SHALL fail.

Patches SHALL use recursive JSON Merge Patch, where null deletes an allowed key.
The protected patch fields SHALL be exactly `id`, `url`, `overrideSource`,
`family`, `variant` and `categories`: a patch SHALL NOT contain any of them with
any value, including null. Every other key SHALL be patchable, and all other
unpatched data SHALL remain unchanged. Shared settings for distinct project URLs
SHALL require explicit records for each project; a common package id or family
SHALL NOT make a patch transfer to another project. Whole-app removal SHALL
remain the denylist's responsibility, and categories SHALL remain the category
map's.

#### Scenario: Overlay changes a setting

- **WHEN** both variants select an entry at the record's normalized URL
- **THEN** a matching patch applies to both

#### Scenario: One family selects different repositories

- **WHEN** an explicit family's single and dual selections come from different
  project URLs
- **THEN** a patch naming the single repository does not affect the dual repository

#### Scenario: Overlay deletes a key

- **WHEN** a patch maps an allowed key to null
- **THEN** the key is deleted before normal rendering hydration

#### Scenario: Protected field is assigned or deleted

- **WHEN** a patch contains `id`, `url`, `overrideSource`, `family`,
  `variant` or `categories`, with any value including null
- **THEN** the build fails naming the record and forbidden field

#### Scenario: Overlay record carries an unknown field

- **WHEN** an overlay record carries a field other than `url` and `patch`
- **THEN** the build fails with that record and the unknown field identified,
  rather than ignoring the field or treating the record as matching nothing

#### Scenario: Overlay record has a blank or non-string URL

- **WHEN** an overlay record's `url` is blank or is not a string
- **THEN** the build fails with that record and the offending field identified

#### Scenario: Overlay record's URL has no host

- **WHEN** an overlay record's `url` is a nonempty string no host can be read
  from, such as `/owner/repo`
- **THEN** the build fails with that record, the field and the offending value
  identified

#### Scenario: Overlay document is not an array

- **WHEN** the overlay file holds a JSON object or another non-array value
- **THEN** the build fails with the overlay identified as not being an array
  of patch records

#### Scenario: Overlay record has a null patch

- **WHEN** an overlay record has a null patch
- **THEN** the build fails rather than removing the app

#### Scenario: Two overlay records name one project

- **WHEN** two overlay records' URLs normalize to the same value
- **THEN** the build fails with both records identified


### Requirement: An overlay record matching no selected entry fails the build

The system SHALL fail when an overlay record's URL matches no selected entry in
either variant. A record matching one variant SHALL be valid and apply only
where matched. Losing or excluded candidates SHALL NOT satisfy overlay targets.

#### Scenario: Old fork was replaced

- **WHEN** the family that held a record's project remains selected but from
  another project URL
- **THEN** the old fork's overlay fails as stale

#### Scenario: Overlay names a project present in one variant only

- **WHEN** a record's URL matches only a dual-screen selection
- **THEN** it is valid and applies only there

#### Scenario: Overlay names a project that no longer exists

- **WHEN** a record's URL matches no selected entry in either variant
- **THEN** the build fails with the stale record identified


### Requirement: Every single-screen family is selected in dual too

Every family selected in single SHALL have a selected build in dual. Upstream
eligibility restrictions, unresolved generated links, denials of other projects
in the family and verification failures SHALL NOT waive family coverage. An app
therefore cannot be published in single only. An app is kept out of both packs
by denying every project URL its family's builds carry, since a denial removes
builds, not families, as "Project denials exclude candidates from both
variants" defines. Different-repository replacements in one declared family
SHALL satisfy coverage. Dual-only additions SHALL NOT require a single
counterpart.

#### Scenario: Different-repository dual replacement

- **WHEN** single and dual select builds from different project URLs in the
  same declared family
- **THEN** family coverage passes without requiring the single build in dual

#### Scenario: An app is missing from the dual-screen variant

- **WHEN** single selects a family with no dual-eligible candidate
- **THEN** the build fails with the family coverage gap rather than copying an ineligible build

#### Scenario: The only dual build is denied

- **WHEN** the only dual-eligible candidate of a single-selected family is at a
  denied project URL
- **THEN** the build fails with the family coverage gap


### Requirement: A package id repeated within a pack is reported

Obtainium stores imported apps by package id, so two entries of one pack that
carry the same id would leave only one of them after import. Composition SHALL
NOT prevent this structurally, because families no longer form by package id.
After selection, the system SHALL record, for each variant, every package id
that more than one selected entry carries, together with those entries'
families and project URLs. The record SHALL NOT fail the build. The maintainer
resolves it with a family rule that puts the entries in one family.

#### Scenario: Two forks with one package id are selected in one pack

- **WHEN** single selects entries from two URL families that both carry
  package id `p`
- **THEN** the build succeeds and records `p` as repeated in single, naming
  both families and project URLs

#### Scenario: A family rule resolves the repeat

- **WHEN** a rule assigns both entries' candidates one explicit family
- **THEN** single selects one of them and records no repeated package id

#### Scenario: A package id repeated across variants only is not recorded

- **WHEN** single and dual each select one entry carrying package id `p`
- **THEN** no repeated package id is recorded

### Requirement: Family selections are reported with their reasons

The system SHALL report every selected family and variant with the winning
candidate's package id, project URL, source and origin, the other candidates of
that family it was chosen over, and one selection reason: pin, dual
preference, ordinary fallback or source precedence. The reason SHALL be the
pin whenever a pin selected the winner. Otherwise single SHALL report source
precedence, and dual SHALL report dual preference when the winner is a
dual-screen build and ordinary fallback when the family had no available
dual-screen build, including when source precedence chose among several
baseline builds. Exclusions and stale exclusions SHALL also be reported.

#### Scenario: Lower-source dual build wins

- **WHEN** a dual-preferred BBoi entry defeats an ordinary RJNY entry
- **THEN** the report names the winner, lists the RJNY candidate as considered
  and identifies dual preference as the reason

#### Scenario: Dual falls back among several baseline builds

- **WHEN** a family has no available dual-screen build and source precedence
  chooses among its dual-eligible baseline builds
- **THEN** the dual selection's reason is ordinary fallback and the single
  selection's reason is source precedence

## MODIFIED Requirements

### Requirement: Selected entries carry categories from one closed taxonomy

Every category in a rendered pack SHALL be one of Emulator, PC Emulation,
Decomps/Recomps, PC Ports, Frontend, Utilities, Streaming and Track Only. The
composition policy SHALL accept an optional `categories` object mapping a
family name to one category of that set other than Track Only, which only
track-only entries carry. A family name is an `app:` name or a normalized
project URL. A value outside those categories, a non-string value, a key that
is neither an `app:` name nor already in normalized project URL form, or a
family key that appears more than once in the object SHALL fail policy loading
with the key identified, rather than one occurrence silently taking effect.

After overlays apply, the system SHALL assign each selected entry's categories
in every variant:

- an entry whose final settings carry `trackOnly: true` SHALL carry exactly
  Track Only;
- otherwise an entry whose family the map names SHALL carry exactly the mapped
  category;
- otherwise the entry SHALL keep the categories its source supplied that belong
  to the set, other than Track Only, in their source order, and SHALL carry no
  category when none remain.

An entry is uncategorized when its final category list, after this
assignment, is empty; a track-only entry is therefore never uncategorized.
Because each variant selects its own winner, uncategorized SHALL be decided per
selected entry: a family SHALL be recorded as uncategorized when the selected
entry of any variant ends with no category, together with exactly the variants
where that happened. A map key is a stale category assignment when it set no
selected entry's category: a key naming no family any variant selects, and a
key whose family's selected entries are all track-only, are both stale. An
uncategorized entry and a stale category assignment SHALL NOT fail the build.

#### Scenario: A mapped family overrides its source category

- **WHEN** the map assigns a family PC Ports and the selected build's source
  tags it Dual Screen
- **THEN** that family's entry carries exactly PC Ports in every variant that
  selects it

#### Scenario: A URL family is mapped by its normalized URL

- **WHEN** the map assigns `github.com/owner/repo` Utilities and a rule-less
  selected entry's project URL is `https://github.com/Owner/Repo`
- **THEN** that entry carries exactly Utilities

#### Scenario: A map key not in normalized form fails policy loading

- **WHEN** the map has a key `https://github.com/Owner/Repo`
- **THEN** policy loading fails with that key identified

#### Scenario: A track-only entry is Track Only

- **WHEN** a selected entry's final settings carry `trackOnly: true`, whatever
  its source categories or map value
- **THEN** it carries exactly Track Only

#### Scenario: An unmapped source category outside the set is dropped

- **WHEN** an unmapped family's selected entry, whose final settings are not
  track-only, carries Dual Screen and Emulator from its source
- **THEN** its entry carries Emulator only

#### Scenario: An unmapped entry with no allowed category builds

- **WHEN** an unmapped family's selected entry, whose final settings are not
  track-only, carries no category from the set
- **THEN** the build succeeds, the entry carries no category, and its family is
  recorded as uncategorized for that variant

#### Scenario: An unmapped track-only entry without source categories is categorized

- **WHEN** an unmapped family's selected entry has final settings carrying
  `trackOnly: true` and its source supplies no category
- **THEN** the entry carries exactly Track Only and its family is not recorded
  as uncategorized

#### Scenario: Only one variant's entry ends without a category

- **WHEN** an unmapped family's single-screen entry keeps an allowed source
  category and its dual-screen entry's source supplies only Dual Screen
- **THEN** the dual-screen entry carries no category, and the family is
  recorded as uncategorized naming the dual variant only

#### Scenario: A category outside the set fails policy loading

- **WHEN** the map assigns a family a category that is not in the set
- **THEN** policy loading fails with that family identified

#### Scenario: A family key repeated in the map fails policy loading

- **WHEN** the `categories` object lists the same family key twice, whether
  with the same or different categories
- **THEN** policy loading fails with that family key identified, and no entry
  is categorized from either occurrence

#### Scenario: Track Only is reserved for track-only entries

- **WHEN** the map assigns a family Track Only, or an unmapped installable
  entry's source tags it Track Only
- **THEN** the map value fails policy loading, and the source tag is dropped

#### Scenario: A family key that names nothing selected is stale

- **WHEN** the map names a family that no variant selects
- **THEN** the build succeeds and the key is recorded as a stale category
  assignment

#### Scenario: A family key whose selected entries are all track-only is stale

- **WHEN** the map names a family whose selected entry in every variant that
  selects it has final settings carrying `trackOnly: true`
- **THEN** each of those entries carries exactly Track Only, the build
  succeeds, and the key is recorded as a stale category assignment


## REMOVED Requirements

### Requirement: Each build is a baseline build or a dual-screen build

**Reason**: Restated around URL-keyed families, URL denials and URL overlays.

**Migration**: Replaced by "Builds are baseline or dual-screen and each pack selects its kind".

### Requirement: Explicit selections identify an eligible candidate

**Reason**: Restated around URL-keyed families, URL denials and URL overlays.

**Migration**: Replaced by "Pins select an eligible candidate of their family".

### Requirement: Composition policy separates app families from package identities

**Reason**: Restated around URL-keyed families, URL denials and URL overlays.

**Migration**: Replaced by "Composition policy assigns app families by project URL".

### Requirement: Composition runs in a fixed stage order

**Reason**: Restated around URL-keyed families, URL denials and URL overlays.

**Migration**: Replaced by "Composition stages run in a fixed order".

### Requirement: One candidate is selected per family and variant under a fixed precedence

**Reason**: Restated around URL-keyed families, URL denials and URL overlays.

**Migration**: Replaced by "One candidate per family and variant is selected by fixed precedence".

### Requirement: Package denials exclude candidates from both variants

**Reason**: Restated around URL-keyed families, URL denials and URL overlays.

**Migration**: Replaced by "Project denials exclude candidates from both variants".

### Requirement: One overlay patches composed entries

**Reason**: Restated around URL-keyed families, URL denials and URL overlays.

**Migration**: Replaced by "Overlay records patch selected entries by project URL".

### Requirement: An overlay record that patches nothing fails the build

**Reason**: Restated around URL-keyed families, URL denials and URL overlays.

**Migration**: Replaced by "An overlay record matching no selected entry fails the build".

### Requirement: Every single-screen family has a dual-screen selection

**Reason**: Restated around URL-keyed families, URL denials and URL overlays.

**Migration**: Replaced by "Every single-screen family is selected in dual too".

### Requirement: Family selections are reported

**Reason**: Rules no longer correct package ids, so a selection has one package id instead of an original and an effective one.

**Migration**: Replaced by "Family selections are reported with their reasons".
