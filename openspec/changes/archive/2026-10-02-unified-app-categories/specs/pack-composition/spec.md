## ADDED Requirements

### Requirement: Selected entries carry categories from one closed taxonomy

Every category in a rendered pack SHALL be one of Emulator, PC Emulation,
Decomps/Recomps, PC Ports, Frontend, Utilities, Streaming and Track Only. The
composition policy SHALL accept an optional `categories` object mapping a
family name to one category of that set other than Track Only, which only
track-only entries carry; a value outside those categories, a non-string value,
a key that is not a `package:` or `app:` family name, or a family key that
appears more than once in the object SHALL fail policy loading with the key
identified, rather than one occurrence silently taking effect.

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

## MODIFIED Requirements

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
identified. A JSON object key repeated anywhere in the composition policy, at
any nesting level, SHALL fail policy loading with the repeated key identified,
in every command that loads the policy, rather than one occurrence silently
taking effect.

Candidates SHALL form families transitively from shared identity once identity
corrections and exclusions apply, over the candidates that survive exclusions
and are eligible for at least one variant: candidates sharing an effective
package id, and candidates assigned the same explicit family, SHALL belong to
one family. No other shared field, including a project URL, SHALL join
candidates. A surviving eligible candidate SHALL be assigned an explicit family
when a rule carrying `family` matches it, or when its effective package id and
normalized project URL equal that rule's projection, whether or not the ruled
candidate itself survives exclusions and eligibility filtering. Excluded
candidates and candidates eligible for no variant SHALL neither join a family
nor name a family. A family containing an explicit assignment SHALL take that
`app:` name; any other family holds exactly one effective package id and SHALL
be named `package:<id>` after it, its default family. Two different explicit families joined
through a shared effective package id SHALL fail the build with both families
and the joining candidates identified.
Explicit family assignments SHALL use the separate `app:` namespace and SHALL
NOT be inferred from names, categories or repository ancestry. A candidate rule SHALL
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
it. Only a rule carrying `family` SHALL project a family, and a projection
SHALL carry that explicit `app:` family only; a rule without `family` neither
names a family offline nor takes part in the agreement check. Rules assigning
explicit families that project to the same effective id and normalized URL
SHALL agree on family, so rendered-family interpretation is unambiguous.
Projections SHALL impose no offline eligibility restriction, because
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

#### Scenario: An identity-only rule shares a rendered key with a family rule

- **WHEN** a rule with only `packageId` or only a rationale and a rule assigning
  `app:x` project to one effective id and normalized URL
- **THEN** the policy loads and both candidates join `app:x`

#### Scenario: A family rule sits on a candidate eligible for no variant

- **WHEN** a rule assigns `app:x` to an RJNY candidate eligible for no variant, a
  rule-less BBoi candidate carries the same effective id at the same project URL,
  and another eligible candidate is ruled into `app:x`
- **THEN** the BBoi candidate and the other candidate form `app:x`, and a pin
  naming `app:x` loads and selects within it

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

#### Scenario: A denied candidate shares a package id or an explicit family

- **WHEN** a denied candidate shares an effective package id or an explicit
  family with candidates from other sources
- **THEN** the remaining candidates form families as if it were absent, so it
  neither joins two apps into one family nor names a family

#### Scenario: A candidate eligible for no variant shares a package id or an explicit family

- **WHEN** a candidate its source makes eligible for neither variant shares an
  effective package id or an explicit family with candidates from other sources
- **THEN** the remaining candidates form families as if it were absent, so it
  neither joins two apps into one family nor names a family

#### Scenario: Different repositories carry one package id

- **WHEN** candidates from different repositories carry one effective package id
- **THEN** they form one family and selection places that package id once per variant

#### Scenario: Shared identity joins two explicit families

- **WHEN** a candidate assigned one explicit family shares an effective package id
  with a candidate assigned another explicit family
- **THEN** the build fails with both families and the joining candidates identified

#### Scenario: A key outside the category map is repeated

- **WHEN** an object in the composition policy outside `categories`, such as a
  candidate rule, repeats a key such as `rationale`
- **THEN** policy loading fails with that key identified in `pack build`,
  `pack verify` and the offline gate alike, and neither occurrence takes effect

### Requirement: Composition runs in a fixed stage order

The system SHALL normalize candidates, apply identity and family rules, remove
excluded candidates, form families from shared identity over the surviving
candidates eligible for at least one variant, validate explicit selections, select by family and target, check
that each family's selected entries pair, validate overlay targets, apply
overlays, assign categories, and check family coverage. Each package id SHALL occur at most once
per variant because candidates sharing an effective package id form one family
and overlays cannot change `id`; no separate uniqueness stage runs, and the
offline gate reports any repeat. Exclusions SHALL
observe corrected package identities before selection and SHALL NOT be
re-applied after overlays. Because a removed candidate belongs to no formed
family, its exclusion SHALL be reported under `package:<its own effective id>`,
or under its explicit family when a rule assigns one. Overlays SHALL NOT assign
or delete `id`, `url`, `overrideSource`, `family`, `packageId`, `variant` or
`categories`, including by null deletion. Failures SHALL preserve the previous output pair
and diagnostics already collected.

#### Scenario: An overlay cannot move an entry onto a denylisted package id

- **WHEN** an overlay record's patch contains an id field naming a denied
  package
- **THEN** the build fails because identity fields are forbidden in overlays

#### Scenario: Denylist removes an entry an overlay names

- **WHEN** candidate exclusions leave no selected entry matching an overlay selector
- **THEN** the build fails with that stale selector identified

#### Scenario: A removed candidate is reported under its own identity

- **WHEN** a denial removes a rule-less candidate and a candidate that a rule
  assigns `app:x`
- **THEN** the first exclusion is reported under `package:<its own effective
  id>` and the second under `app:x`

### Requirement: One overlay patches composed entries

The overlay file SHALL contain an array of records with effective package `id`,
project `url` and object `patch`. An overlay document that is not an array
SHALL fail with the overlay identified. A record SHALL carry no field other
than `id`, `url` and `patch`, and SHALL fail with the record and the unknown
field identified otherwise. A record's `id` and its `url` SHALL each be a
nonempty string, failing with the record and the offending field identified. A
nonempty `url` SHALL additionally be one a host can be read from, and one no
host can be read from SHALL fail with the record, the field and the offending
value identified, because there the value is what the maintainer has to look
at. Each record SHALL apply to the matching selected entry in every variant
that selects it. Matching SHALL use both effective id and normalized project
URL. Duplicate selectors SHALL fail. A non-object patch, including null,
SHALL fail.

Patches SHALL use recursive JSON Merge Patch, where null deletes an allowed key.
The protected patch fields SHALL be exactly `id`, `url`, `overrideSource`,
`family`, `packageId`, `variant` and `categories`: a patch SHALL NOT contain any of them with
any value, including null. Every other key SHALL be patchable, and all other
unpatched data SHALL remain unchanged. Shared settings for distinct project URLs
SHALL require explicit records for each project; a common package id SHALL NOT
make a patch transfer to another fork. Whole-app removal SHALL remain the
denylist's responsibility, and categories SHALL remain the category map's.

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
  `packageId`, `variant` or `categories`, with any value including null
- **THEN** the build fails naming the selector and forbidden field

#### Scenario: Overlay record carries an unknown field

- **WHEN** an overlay record carries a field other than `id`, `url` and `patch`
- **THEN** the build fails with that record and the unknown field identified,
  rather than ignoring the field or treating the record as matching nothing

#### Scenario: Overlay record has a blank or non-string key

- **WHEN** an overlay record's `id` or `url` is blank or is not a string
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

#### Scenario: Overlay patch contains the source-type field

- **WHEN** an overlay record's patch contains overrideSource
- **THEN** the build fails with the selector and protected field identified

#### Scenario: Overlay patch contains the package-id field

- **WHEN** an overlay record's patch contains id
- **THEN** the build fails with the selector and protected field identified

#### Scenario: Overlay patch maps the source-type or package-id field to null

- **WHEN** a patch maps overrideSource or id to null
- **THEN** the build fails because protected fields cannot be deleted
