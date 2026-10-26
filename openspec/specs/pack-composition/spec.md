# pack-composition Specification

## Purpose

Selects one candidate per app family and variant from the entries supplied by
source ingestion. It owns families, package identities, explicit pins,
dual-screen preference, source precedence, package denials, dual coverage,
overlays and selection reporting.

## Requirements

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
rely on this, as "Offline verification labels rendered
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

### Requirement: Overlay records patch selected entries by project URL

The overlay file SHALL contain an array of records with project `url` and
object `patch`. An overlay document that is not an array SHALL fail with the
overlay identified. A record SHALL carry no field other than `url` and
`patch`, and SHALL fail with the record and the unknown field identified
otherwise. A record's `url` SHALL be a nonempty string, failing with the
record and the offending field identified, and SHALL additionally be one the
pipeline can normalize for comparison: a host SHALL be readable from it, any
port SHALL be numeric and in the valid range, and it SHALL contain no
whitespace; any other SHALL fail with the record, the field and the offending
value identified. Each record SHALL apply to every selected entry whose
normalized project URL equals the record's, in every variant that selects one.
Two records with one normalized URL SHALL fail. A non-object patch, including
null, SHALL fail. An empty patch object, and an empty object nested within
the patch's objects (not inside array values), SHALL fail with the record identified: a record that
patches nothing is removed, not emptied.

Patches SHALL use recursive JSON Merge Patch, where null deletes an allowed key.
The protected patch fields SHALL be exactly `url`, `overrideSource`, `family`,
`variant` and `categories`: a patch SHALL NOT contain any of them with any
value, including null. A patch key SHALL NOT contain a `.` or a `/`
character at any depth, whether it is a top-level key or a key of an object
nested within the patch, and such a key SHALL fail with the record and the
offending key identified; keys inside array values are part of a value, not
patch keys. A dotted path therefore names exactly one location in a patch and
contains no `/`, so distinct pairs of project URL and dotted path joined by
`/` are distinct strings. Every other key
SHALL be patchable, and all other unpatched data SHALL remain unchanged. Shared settings for distinct project URLs
SHALL require explicit records for each project; a common package id or family
SHALL NOT make a patch transfer to another project. Whole-app removal SHALL
remain the denylist's responsibility, and categories SHALL remain the category
map's.

A patch MAY assign `id`, a nonempty string, which is how the owner fixes a
source's wrong package id by hand, exactly as a name or an APK filter is fixed.
Obtainium saves every imported record under its `id` and, after an install
whose APK declares another id, re-saves the installed app under the APK's id,
so a shipped id that differs from the APK's makes each later pack import add a
never-installed duplicate beside the installed app; the owner patches `id` to
the APK's id when Obtainium shows such a duplicate or an id error. An `id`
patch SHALL change only the selected entry's rendered output: family
formation, deduplication, denials, pins and overlay matching SHALL stay keyed
by normalized project URL and source data and SHALL NOT read a patched id. The
record of package ids repeated within a pack, offline verification and the
README catalog SHALL see the patched id, since it is the id the pack ships.
An `id` patch SHALL be accepted only at a URL whose candidates form one family,
that is, a URL no family rule names or one whose family rules all name the same
family. A record that patches `id` at a URL whose family rules name different
families is an owner configuration error: it SHALL fail when the overlay and
composition policy load, before any patch is applied or output is written,
identifying the record and the families its URL's rules name, in `pack build`
and `pack verify` alike, as two records with one normalized URL fail. A record
at such a URL that does not patch `id` SHALL remain valid and SHALL apply to
every selected entry at that URL, whichever family it belongs to; overlays are
not scoped per family, so a setting meant for only one of those families
belongs in its source.

An `id` patch applies to every selected entry at its URL in every variant. When
one family's single and dual selections at one URL are different APKs
declaring different real ids, no overlay record fixes both, and the entry left
wrong shows the recurring duplicate described above. This is an accepted
limitation; no current family has this shape.

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

- **WHEN** a patch contains `url`, `overrideSource`, `family`, `variant` or
  `categories`, with any value including null
- **THEN** the build fails naming the record and forbidden field

#### Scenario: Patch key contains a dot or a slash

- **WHEN** a patch carries a key containing a `.` or a `/`, either at the top
  level, such as `guard.flag` or `guard/flag`, or nested, such as
  `additionalSettings` holding `apk.filter` or `apk/filter`
- **THEN** the build fails with an overlay error naming the record and the
  offending key, and no pack is published

#### Scenario: Overlay fixes a wrong source id

- **WHEN** a record at URL X patches `id` to the APK's package id `p`, and the
  selected entry at X carries a different source id
- **THEN** the rendered entry at X carries `p` in every variant that selects
  it, and the entry's family, selection and denial checks are unchanged

#### Scenario: Overlay deletes the id

- **WHEN** a patch maps `id` to null or to a value that is not a nonempty
  string
- **THEN** the build fails naming the record and the field

#### Scenario: Overlay patches the id at a split URL

- **WHEN** rules at URL X assign builds with ids `a` and `b` to `app:a` and
  `app:b`, and a record at X patches `id` to `c`
- **THEN** `pack build` and `pack verify` each fail when the overlay and
  composition policy load, naming the record and the families `app:a` and
  `app:b`, and no pack is published
- **AND** a record at X whose patch does not set `id` loads

#### Scenario: Overlay patches every family at a split URL

- **WHEN** rules at URL X assign builds to `app:a` and `app:b`, both are
  selected, and a record at X patches `name` without patching `id`
- **THEN** the patch applies to the selected entries of both `app:a` and
  `app:b`

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

#### Scenario: Overlay record patches nothing

- **WHEN** an overlay record's patch is an empty object, or holds an object
  such as `additionalSettings` that is empty
- **THEN** the build fails with an overlay error naming the record, and no pack
  is published

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

### Requirement: Each variant is composed independently

The system SHALL compose the single-screen and dual-screen variants
separately, so that a package id may carry different content in each.

#### Scenario: Variants disagree on one id

- **WHEN** a package id has different candidate entries in each variant
- **THEN** each variant's rendered entry reflects its own candidate, and
  neither overwrites the other

### Requirement: Selected entries carry categories from one closed taxonomy

Every category in a rendered pack SHALL be one of Emulator, PC Emulation,
Decomps/Recomps, PC Ports, Frontend, Utilities, Streaming and Track Only. The
composition policy SHALL accept an optional `categories` object mapping a
family name to one category of that set other than Track Only, which only
track-only entries carry. A family name is an `app:` name or a normalized
project URL. A map key SHALL be either an `app:` family name or a project URL
already in normalized form with both a host and a path and no whitespace. A
value outside those categories, a non-string value, a key that is neither,
including one without a path such as `melonds` or `com.dishii.zelda3`, or a
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

#### Scenario: A map key without a path fails policy loading

- **WHEN** the map has a key `melonds` or `com.dishii.zelda3`, neither an
  `app:` name nor a URL with a path
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

### Requirement: Overlay patch keys that change nothing are reported

After overlays apply, the system SHALL record each overlay record with patch
keys that change nothing, once, with its normalized project URL and those
keys' dotted paths. A key, a path to a non-object value including null,
SHALL be recorded only when merging it alone into each entry the record
targets in every variant, before the record applied, leaves the entry's
published form, as pack rendering publishes it, unchanged.
Recording SHALL NOT change selection or output or fail the build.

#### Scenario: A patch whose value the source now ships

- **WHEN** an overlay record sets `name` to the name its selected entry
  already carries in every variant
- **THEN** the build succeeds, publishes the same entries, and records the
  record's URL with the key `name`

#### Scenario: A patch with one live and one dead key

- **WHEN** a record sets `name`, which changes the entry, and
  `additionalSettings.includeZips` to the value the entry already holds
- **THEN** the record's URL is recorded with `additionalSettings.includeZips`
  only

#### Scenario: A key that matters in one variant

- **WHEN** a record applies to a single and a dual entry and its key changes
  only the dual entry
- **THEN** the key is not recorded

#### Scenario: A patch setting a rendering default

- **WHEN** a record sets a setting the entry does not carry to the value
  rendering would publish for it by default
- **THEN** the key is recorded as changing nothing

#### Scenario: A patch on a field rendering forces

- **WHEN** a record sets `allowIdChange` to false
- **THEN** the key is recorded as changing nothing, because rendering
  publishes every entry with `allowIdChange` true

#### Scenario: A null deleting an absent key

- **WHEN** a record's patch holds null for a key the entry does not carry and
  rendering gives no default for
- **THEN** the key is recorded as changing nothing

#### Scenario: A null deleting a defaulted setting

- **WHEN** a record's patch holds null for an `additionalSettings` key that
  has a rendering default for the entry's source type, and the entry either
  does not carry that key or holds it at that default
- **THEN** the build publishes the same entries and the key is recorded as
  changing nothing

#### Scenario: A null under a parent the entry lacks

- **WHEN** a record's patch is `{"foo": {"bar": null}}` and the entry it
  targets carries no `foo`
- **THEN** the key `foo.bar` is not recorded, because merging it alone gives
  the entry `foo: {}` and so changes its published form

### Requirement: Extras a catalog lists are reported

The system SHALL record each extra its family's selection chose in a variant
over a considered candidate of another source at its normalized URL, once per
URL and published package id across variants. Per source it SHALL list the
union over its candidates of fields whose published forms differ from the
extra's under the same overlay, or `unpublishable` for a candidate that alone
fails to render, plus `variants` when the two are builds of different kinds. Recording SHALL NOT
change selection or output or fail the build.

#### Scenario: A catalog lists an extra's project

- **WHEN** an extra is selected over a Quiver candidate at the same project URL
  whose name and APK filter differ from the extra's
- **THEN** the build succeeds, the extra is still published, and the extra is
  recorded with its URL, package id, Quiver as a source, and the name and the
  APK filter setting as differing fields

#### Scenario: Differences rendering erases

- **WHEN** an extra is selected over a catalog candidate at the same project
  URL that differs only in carrying `allowIdChange: false` or in omitting
  `author`
- **THEN** the extra is recorded with that catalog as a source and no
  differing fields

#### Scenario: A dual-screen extra over a both-pack candidate

- **WHEN** an extra that is a dual-screen build is selected over a catalog
  candidate at the same project URL that is a baseline build and has equal
  settings
- **THEN** the extra is recorded with `variants` as a differing field

#### Scenario: An extra replaces another project in its family

- **WHEN** an extra is selected over a catalog candidate at a different project
  URL that a family rule puts in the same family
- **THEN** no listed extra is recorded

#### Scenario: Family rules split a project URL

- **WHEN** family rules at one project URL put an extra and a Quiver build in
  different families, so both are published
- **THEN** no listed extra is recorded

#### Scenario: Two extras at one project URL

- **WHEN** family rules at one project URL put two extras in separate
  families, and each is selected over a catalog candidate at that URL in its
  own family
- **THEN** two listed extras are recorded at that URL, each with its own
  package id, listing sources and differing fields

#### Scenario: Fields a listed extra is compared on

- **WHEN** an extra is selected over a catalog candidate at the same project
  URL that differs from it only in its categories, in the spelling of its
  project URL, and in one `additionalSettings` key `k`
- **THEN** the extra is recorded with `additionalSettings.k` as its only
  differing field: fields are compared as top-level keys and as keys under
  `additionalSettings`, categories are not compared because the category map
  assigns them, and the project URL is not compared because the two match on
  it by construction

#### Scenario: Two candidates from one source at one project URL

- **WHEN** an extra is selected over two Quiver candidates at its project URL,
  one differing from it in `name` and the other in an `additionalSettings` key
- **THEN** the extra is recorded with Quiver once as a source, its differing
  fields the union of both candidates' differences

#### Scenario: A listing candidate that cannot be published

- **WHEN** an extra is selected over a Quiver candidate at its project URL
  whose import data, with the same overlay applied, pack rendering rejects,
  while the extra renders
- **THEN** the build succeeds and the extra is recorded with Quiver as a
  source and `unpublishable` as its field, not with no differing fields
- **AND** when the extra itself also fails to render, that source records no
  differing fields, and the build fails at rendering
