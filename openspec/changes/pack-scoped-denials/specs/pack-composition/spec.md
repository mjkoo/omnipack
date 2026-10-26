# Spec Delta

## ADDED Requirements

### Requirement: Pins select a candidate of their family

Policy SHALL permit one candidate pin per family and variant. A pin SHALL name
an original candidate selector and a rationale, and SHALL select that candidate
ahead of kind preference or source ranking. A dual pin MAY therefore name a
baseline build even when the family has an available dual-screen build, and
SHALL keep that baseline build in the dual-screen pack in place of the family's
dual-screen build whether or not the two builds share a project URL; a single
pin MAY likewise name a dual-screen build. A missing or wrong-family pinned
candidate SHALL fail the build. A pin cannot match more than one candidate,
because different records sharing one original identity fail before any pin is
read. A pin SHALL NOT implicitly override an exclusion. Multiple pins for one
family and target SHALL fail. A pin whose candidate a denial removes from the
pin's variant SHALL fail, identifying the pin and the denial. A candidate a
denial removes from every variant belongs to no formed family, so its pin SHALL
fail this way before the build-time formed-family comparison. A denial that
removes the candidate from the other variant only SHALL NOT affect the pin.

A pin SHALL name the family its candidate belongs to, as "App families form by project URL under the composition policy" defines: its explicit `app:` family, or
otherwise the normalized project URL of its candidate. A pin whose selector has
an explicit `app:` projection naming a different family SHALL fail when the
policy loads, identifying the pin and the projected family, whatever the
denylist says; the build SHALL check every other pin against its candidate's
formed family.

#### Scenario: A dual pin selects a baseline build over a dual-screen build

- **WHEN** a valid dual pin names a baseline build and the family has an
  available dual-screen build
- **THEN** the pinned build wins and the report identifies the explicit selection

#### Scenario: Pinned build disappears

- **WHEN** successful ingestion does not supply the pinned candidate
- **THEN** the build fails without selecting another build

#### Scenario: Pin conflicts with a denial

- **WHEN** a pin names a candidate whose project URL a denial removes from the
  pin's variant
- **THEN** the build fails with the conflicting pin and denial identified

#### Scenario: A denial of the other pack leaves a pin valid

- **WHEN** a single pin names a candidate whose project URL a denial naming
  only the dual-screen pack names
- **THEN** single selects the pinned candidate, dual does not select it, and
  the build succeeds

#### Scenario: A pin names another family for a denied projected candidate

- **WHEN** a pin selects a candidate whose rule projects `app:one`, names
  `app:two`, and a denial removes that candidate
- **THEN** policy loading fails with the pin and `app:one` identified

#### Scenario: A pin names a candidate removed before families form

- **WHEN** a pin names the URL family of a rule-less candidate that a denial
  removes from every variant
- **THEN** the build fails with the pin and the denial identified rather than
  as wrong-family

#### Scenario: A pin selects a rule-less candidate projected into an explicit family

- **WHEN** a rule-less candidate is at the project URL of a candidate that a
  rule assigns `app:x`, and a pin selects the rule-less candidate
- **THEN** a pin naming `app:x` loads and selects it
- **AND** a pin naming the candidate's normalized project URL fails policy
  loading, naming the projected family `app:x`

### Requirement: App families form by project URL under the composition policy

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
candidates that no denial removes from every variant. Such a candidate SHALL
belong to the explicit family of the family-rule projection that covers it,
whether or not the candidate a rule's selector matches itself survives
exclusions. Every other such
candidate SHALL belong to its default family, named by its normalized project
URL as "URLs are compared in a normalized form" in source-ingestion defines. A
shared package id SHALL NOT join candidates at different URLs. A candidate a
denial removes from every variant SHALL neither join a family nor name a
family. A candidate a denial removes from one variant only SHALL keep its
family, and that variant's selection SHALL pass over it. Explicit family
names SHALL use the `app:` namespace and SHALL NOT be inferred from names,
categories or repository ancestry.

A candidate rule SHALL contain a `match` selector and a `rationale`, SHALL
permit a family assignment (`family`), and SHALL preserve original provenance.
Rules SHALL NOT change a candidate's package id: a selected entry carries the
id its source supplied. A candidate whose normalized settings carry
`trackOnly: true` SHALL be treated like every other candidate at its URL: a
rule matching it MAY carry `family`, and the projections below cover it exactly
as they cover an installable build. Rules at one URL that name different
families therefore separate a track-only candidate from an installable build
sharing that URL, so that each forms its own family and each can ship.

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
impose no offline kind restriction, because a build's source-derived kind
cannot be reconstructed from rendered entries. Composition SHALL NOT serialize
the family, original identity, kind or selection reason it computes into
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

#### Scenario: A rule carries an unknown field

- **WHEN** a candidate rule carries a field other than `match`, `rationale` and
  `family`, such as `packageId`
- **THEN** configuration fails with the rule and the unknown field identified

#### Scenario: A selector pairs a source with another source's origin

- **WHEN** a candidate rule or a pin selects with a selector naming one source
  and an origin that belongs to a different source
- **THEN** configuration fails with the selector and the invalid origin
  identified, before any candidate is matched

#### Scenario: Track-only candidate has a descriptive rule

- **WHEN** a track-only candidate has a matching rule containing only its selector and rationale
- **THEN** its ingested identity remains unchanged and the rule does not cause rejection

#### Scenario: A track-only candidate joins the family ruled onto its URL

- **WHEN** every family rule at project URL X assigns `app:x`, and a rule-less
  track-only candidate is at X
- **THEN** the track-only candidate belongs to `app:x` and competes within it
  like any other build there

#### Scenario: Split rules let a tracker and an installable build both ship

- **WHEN** a track-only candidate and an installable build sit at one project
  URL with different package ids, one rule assigns the installable build
  `app:a`, and another assigns the track-only candidate `app:a-tracker`
- **THEN** each belongs to its rule's family, each variant that can select
  them selects both, and neither replaces the other

#### Scenario: A selector's URL has no host

- **WHEN** a candidate rule or a pin selects with a `url` no host can be read
  from, one with a non-numeric or out-of-range port, or one containing
  whitespace
- **THEN** configuration fails with that field and the offending value
  identified, before any candidate is matched

#### Scenario: A denied candidate shares an explicit family

- **WHEN** a denied candidate shares an explicit family with candidates from
  other sources
- **THEN** it names no family of its own and does not hold candidates at other
  URLs together: the remaining candidates form the families their own rules and
  URLs give them, and its denial is reported under the explicit family

#### Scenario: A candidate denied in one pack keeps its family

- **WHEN** rules assign builds at project URLs X and Y to `app:x`, and a denial
  naming only the single-screen pack names X
- **THEN** both builds belong to `app:x`, dual selects within both, and single
  selects only the build at Y

#### Scenario: A key outside the category map is repeated

- **WHEN** an object in the composition policy outside `categories`, such as a
  candidate rule, repeats a key such as `rationale`
- **THEN** policy loading fails with that key identified in `pack build`,
  `pack verify` and the offline gate alike, and neither occurrence takes effect

### Requirement: Project denials exclude candidates from the packs they name

A denylist entry SHALL contain a nonempty project `url` and a nonempty
`reason`, and MAY contain `packs`, a nonempty list of distinct variant names
(`single`, `dual`); an entry without `packs` SHALL apply to both variants. Its
`url` SHALL be one the pipeline can normalize for comparison, failing with the
entry and the offending value identified otherwise, and any other `packs` value
SHALL fail with the entry identified. The system SHALL exclude every candidate
whose normalized project URL equals the entry's from each variant the entry
applies to, before selection, and report the exclusion with those variants. A
denial SHALL NOT remove candidates at other URLs merely because they share a
family or a package id, and SHALL NOT remove candidates from a variant it does
not apply to, so a family SHALL be absent from a variant after denials only
when none of its candidates remains there. An entry matching no candidate SHALL
be reported as a stale exclusion and SHALL NOT fail the build. Any other field
SHALL fail explicitly with the entry identified.

#### Scenario: Denied by project URL

- **WHEN** several sources contribute candidates at a denied project URL,
  spelled differently
- **THEN** no candidate at that URL is selected in either output

#### Scenario: A denial permits an alternative

- **WHEN** a preferred dual build's URL is denied and its explicit family has
  another build at another URL
- **THEN** dual can select that alternative unless a conflicting pin fails validation

#### Scenario: A denial keeps another repository with the same package id

- **WHEN** a denied URL's candidates share a package id with a candidate at
  another URL
- **THEN** the other candidate remains selectable

#### Scenario: Denylist entry matches no candidate

- **WHEN** a denial names a URL no candidate carries
- **THEN** the exclusion is reported stale, changes nothing and does not fail the build

#### Scenario: Denylist entry carries an unknown field

- **WHEN** a denylist entry carries a field other than `url`, `reason` and
  `packs`
- **THEN** the build fails with the entry and the unknown field identified

#### Scenario: A denial names one pack

- **WHEN** a denial whose `packs` is `["single"]` names project URL X
- **THEN** no candidate at X is selected in single, X's candidates remain
  selectable in dual, and the exclusion is reported under X with the
  single-screen variant

#### Scenario: A denial's pack list is invalid

- **WHEN** a denylist entry's `packs` is empty, is not a list, repeats a name,
  or holds a value other than `single` and `dual`
- **THEN** the build fails with the entry identified

## MODIFIED Requirements

### Requirement: Builds are baseline or dual-screen and each pack selects its kind

Every candidate build SHALL be either a baseline build or a dual-screen build,
and its kind SHALL come only from its source, as source ingestion defines for
each source. A build's kind SHALL be a selection preference only: every
candidate SHALL be selectable in both packs, and only a project denial SHALL
remove a build from a pack. No candidate rule or other composition setting
SHALL change a build's kind.

The single-screen pack SHALL prefer a family's baseline builds and the
dual-screen pack its dual-screen builds. A valid pin comes first, as "Pins
select a candidate of their family" defines. Absent a pin, each pack SHALL
select among the family's available builds of its preferred kind, a family with
none available SHALL use its available builds of the other kind, and source
precedence SHALL decide among builds of one kind. Nothing other than a pin
naming a specific candidate SHALL make a pack select a build of the other kind
over an available build of its preferred kind.

A project denial removes builds, not families, from the packs it names, as
"Project denials exclude candidates from the packs they name" defines,
including where a family's baseline and dual-screen builds share the denied
project URL.

#### Scenario: A dual-screen build replaces the baseline in dual

- **WHEN** a family has a baseline build and a dual-screen build, and no pin
  applies
- **THEN** single selects the baseline build and dual selects the dual-screen
  build, even when the baseline build comes from a higher-precedence source

#### Scenario: A family has no dual-screen build

- **WHEN** a family's builds are all baseline builds, and no pin applies
- **THEN** both packs select among those baseline builds by source precedence

#### Scenario: A family has only a dual-screen build

- **WHEN** a family's only build is a dual-screen build, and no denial or pin
  applies
- **THEN** both packs select it

#### Scenario: Single prefers a lower-precedence baseline build

- **WHEN** a family has an extras dual-screen build and a BBoi34 baseline
  build, and no pin applies
- **THEN** single selects the BBoi34 baseline build and dual selects the extras
  dual-screen build

#### Scenario: A single-scoped denial keeps a dual-only family out of single

- **WHEN** a family's only build is a dual-screen build and a denial naming only
  the single-screen pack names its project URL
- **THEN** dual selects the build and single has no entry for that family

#### Scenario: A denied URL shared by both builds leaves other projects selectable

- **WHEN** a denial names a project URL carrying both a family's baseline
  build and its dual-screen build, and an explicit family also holds a
  baseline build at another URL
- **THEN** neither denied build is selected in either pack, and the
  other-URL baseline build is selected in both

#### Scenario: A dual pin keeps a baseline build that shares its project

- **WHEN** a family's baseline build and its dual-screen build share a project
  URL, and a valid dual pin names the baseline build
- **THEN** both packs select the baseline build, the dual-screen build is
  selected in neither, and the dual selection's reason is the pin

### Requirement: Composition stages run in a fixed order

The system SHALL normalize candidates, apply family rules, remove
excluded candidates from the variants their denials name, form families over
the candidates left in at least one variant, validate explicit selections,
select by family and target, validate overlay targets, apply overlays, assign
categories and record package ids repeated within a variant. Exclusions SHALL observe normalized
project URLs before selection and SHALL NOT be re-applied after overlays.
Each denial's exclusions SHALL be reported under the denied normalized project
URL, listing the variants it names and the families whose candidates it
removed as the family rules project them, so one denial is reported under one
label however many families it touches. Overlays SHALL NOT assign or delete `url`,
`overrideSource`, `family`, `variant` or `categories`, including by null
deletion. An overlay MAY assign `id`; because family formation, exclusions,
explicit selections, selection and overlay matching all run before overlays
apply, none of them SHALL read a patched id, while the record of package ids
repeated within a variant SHALL use each entry's patched id. Failures SHALL
preserve the previous output pair and diagnostics already collected.

#### Scenario: An overlay cannot change an entry's project URL

- **WHEN** an overlay record's patch contains a `url` field
- **THEN** the build fails because the project URL is forbidden in overlays

#### Scenario: An overlay id patch does not move an entry between families

- **WHEN** an overlay record patches `id` to `q` at a URL whose candidates
  carry source id `p`, and another family's entry carries `q`
- **THEN** family formation, denials, pins and selection see only `p`, the
  patched entry stays in its own family, and the build records `q` as a
  package id repeated within each variant that selects both entries

#### Scenario: Denylist removes an entry an overlay names

- **WHEN** candidate exclusions leave no selected entry matching an overlay record
- **THEN** the build fails with that stale record identified

#### Scenario: A denial's exclusions are reported under its URL

- **WHEN** rules at URL X assign id `a` to `app:a` and id `b` to `app:b`, a
  third build at X carries id `c` and no rule, and a denial at X removes all
  three
- **THEN** the exclusions are reported once under X, listing both variants and
  the families `app:a`, `app:b` and X

### Requirement: One candidate per family and variant is selected by fixed precedence

The system SHALL select within the families that "App families form by project URL under the composition policy" defines. It SHALL select at most one candidate
per family per variant, honoring a valid explicit pin first, as "Pins select
a candidate of their family" defines. Otherwise each variant SHALL consider
the family's candidates that no denial removes from it, and among them the
builds of its preferred kind, baseline builds for single and dual-screen builds
for dual, when any exist, or all of them otherwise.
Within that tier, precedence SHALL be extras, RJNY, Quiver, BBoi34, then codm.
The winning candidate SHALL be retained whole, not merged with losing entries.

A family having no candidate of a variant's preferred kind left after
successful ingestion and deliberate exclusions SHALL be an ordinary outcome:
that variant SHALL select among the family's remaining candidates and the build
SHALL NOT fail for the absence, unless a pin names a candidate that is absent. A source that cannot be
fetched SHALL abort the build instead, as "A failed fetch aborts the build" in
source-ingestion defines, so a missing preferred candidate and a missing source
are never confused.

Identical duplicates SHALL collapse. When different candidates tie at the
winning rank, which happens when one source lists several builds at one project
URL that no family rule separates, composition SHALL NOT fail: it SHALL select
the tied candidate whose canonical serialized form sorts first, and SHALL record
the tie as a nonfatal same-rank tie finding naming the family, the variant, the
tied candidates' selectors and the chosen winner. The tie SHALL NOT fail the
build, so one family's ambiguity never blocks the rest of the run. The
maintainer resolves it with a pin or with family rules that split the tied
builds into separate families. Ties among nonwinning candidates SHALL NOT
displace a unique winner and SHALL NOT be recorded. A candidate's canonical
serialized form is its import record as ingested, before overlays, category
assignment and the `allowIdChange` override, serialized with the canonical
serializer rendering uses for its ordering key. No ordering other than that
canonical serialized form, such as iteration order, input order or release
dates, SHALL break ties, so the same candidates select the same winner in any
input order.

Every member of an explicit family is covered by a projection of that family,
and every member of a default family carries its project URL, so the family of
each selected entry SHALL be recoverable from its package id and normalized
project URL alone. This holds for rendered entries carrying an overlay `id`
patch too, since such a patch is accepted only at a URL whose candidates form
one family, where the family does not depend on the id. Offline verification and the README catalog
rely on this, as "Offline verification labels and pairs rendered
entries by family" in pack-verification defines, and composition needs no separate
pairing check. Composition, offline verification and the README catalog SHALL
apply the same projections to track-only entries as to installable ones, so a
track-only entry's family and its rendered label never disagree.

#### Scenario: Two sources contribute one project

- **WHEN** ordinary RJNY and BBoi entries at one project URL compete for one
  family and target
- **THEN** RJNY wins and retains its complete entry

#### Scenario: Dual suitability outranks source precedence

- **WHEN** ordinary RJNY and dual-preferred BBoi builds compete for the same dual family
- **THEN** BBoi wins dual selection while single selects the ordinary RJNY build

#### Scenario: Standard extra does not suppress a dual fork

- **WHEN** an ordinary extra and a dual-preferred generated build compete without a pin
- **THEN** dual selects the preferred build and single selects the extra

#### Scenario: Preferred build is absent from a valid source snapshot

- **WHEN** all source acquisition succeeds, no preferred candidate exists, and no pin requires one
- **THEN** dual selection uses an ordinary candidate if available

#### Scenario: One source contributes one project with different content

- **WHEN** one source contributes two different candidates tied at the winning
  tier, for example stable and nightly builds with different package ids at
  one repository URL that no family rule separates
- **THEN** the build succeeds, the family publishes the tied candidate whose
  canonical serialized form sorts first, and a same-rank tie finding records
  the family, the variant, both selectors and the chosen winner

#### Scenario: A same-rank tie is resolved the same way in any input order

- **WHEN** the same tied candidates are composed from each permutation of the
  source's input order
- **THEN** every build selects the same winner and records the same tie finding

#### Scenario: A pin or split rules resolve a same-rank tie

- **WHEN** a pin names one of the tied candidates, or family rules place the
  tied candidates in different families
- **THEN** no same-rank tie finding is recorded for that family and variant

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

### Requirement: A package id repeated within a pack is reported

Obtainium stores imported apps by package id, so two entries of one pack that
carry the same id would leave only one of them after import. Composition SHALL
NOT prevent this structurally, because families no longer form by package id.
After overlays apply, the system SHALL record, for each variant, every package
id that more than one selected entry carries, using each entry's id after any
overlay `id` patch, together with those entries' families and project URLs.
The record SHALL NOT fail the build. The maintainer resolves it with a family
rule that puts the entries in one family, or by correcting an overlay `id`
patch that produced it.

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

#### Scenario: A baseline original and a dual-screen fork share a package id

- **WHEN** an upstream supplies a baseline build at URL A and a dual-screen
  build at URL B carrying package id `p`, and no rule joins their URLs
- **THEN** both URL families are selected in both packs and `p` is recorded as
  repeated in single and in dual
- **AND** when a rule assigns both builds `app:x`, single selects A and dual
  selects B within `app:x` and no repeated package id is recorded

### Requirement: Family selections are reported with their reasons

The system SHALL report every selected family and variant with the winning
candidate's package id, project URL, source and origin, the other candidates of
that family it was chosen over, and one selection reason: pin, dual
preference, ordinary fallback or source precedence. The reason SHALL be the
pin whenever a pin selected the winner. Otherwise single SHALL report source
precedence, whether its winner is a baseline build or, for a family with no
available baseline build, a dual-screen build, and dual SHALL report dual preference when the winner is a
dual-screen build and ordinary fallback when the family had no available
dual-screen build, including when source precedence chose among several
baseline builds. A selection decided by a same-rank tie SHALL keep the reason
its rank gives, and the tie SHALL be reported as a same-rank tie finding, as
"One candidate per family and variant is selected by fixed precedence"
defines. Exclusions and stale exclusions SHALL also be reported.

#### Scenario: Lower-source dual build wins

- **WHEN** a dual-preferred BBoi entry defeats an ordinary RJNY entry
- **THEN** the report names the winner, lists the RJNY candidate as considered
  and identifies dual preference as the reason

#### Scenario: Dual falls back among several baseline builds

- **WHEN** a family has no available dual-screen build and source precedence
  chooses among its baseline builds
- **THEN** the dual selection's reason is ordinary fallback and the single
  selection's reason is source precedence

#### Scenario: Single falls back to a dual-screen build

- **WHEN** a family's only available build is a dual-screen build and no pin
  applies
- **THEN** the single selection's reason is source precedence and the dual
  selection's reason is dual preference

## REMOVED Requirements

### Requirement: Pins select an eligible candidate of their family

**Reason**: Replaced by "Pins select a candidate of their family", which drops pack eligibility: a pin now fails only for a missing, wrong-family or pack-excluded candidate.

**Migration**: Pins in `config/composition.json` need no change; a pin that relied on failing for an ineligible candidate now fails only when a denial removes its candidate from its variant.

### Requirement: Project denials exclude candidates from both variants

**Reason**: Replaced by "Project denials exclude candidates from the packs they name", which adds the optional `packs` field and drops the case of candidates eligible for neither variant.

**Migration**: Existing denials keep their meaning, since an entry without `packs` applies to both variants.

### Requirement: Composition policy assigns app families by project URL

**Reason**: Replaced by "App families form by project URL under the composition policy", which forms families over candidates a denial leaves in at least one variant instead of over candidates eligible for at least one variant.

**Migration**: No configuration change; family rules and projections are unchanged.

### Requirement: A single-screen family without a dual build is published and reported

**Reason**: Every candidate is now selectable in both packs, so a family selected
in single is missing from dual only when the owner's denial removes it from dual,
which needs no finding. The upstream pattern the finding caught, a baseline
original and a dual-screen fork at different URLs sharing a package id, now
selects both families in both packs and is recorded as a package id repeated
within a pack.

**Migration**: Readers of the build report's single-only coverage list stop
reading it. A baseline original and a dual-screen fork that share a package id
are still joined with a family rule, found through the repeated package id
finding and its maintenance alert.
