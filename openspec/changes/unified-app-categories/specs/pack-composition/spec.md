## ADDED Requirements

### Requirement: Selected entries carry categories from one closed taxonomy

Every category in a rendered pack SHALL be one of Emulator, PC Emulation,
Decomps/Recomps, PC Ports, Frontend, Utilities, Streaming and Track Only. The
composition policy SHALL accept an optional `categories` object mapping a
family name to one category of that set other than Track Only, which only
track-only entries carry; a value outside those categories, a non-string value,
or a key that is not a `package:` or `app:` family name SHALL fail policy
loading with the key identified.

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
where that happened. An uncategorized entry and a map key naming no selected
family SHALL NOT fail the build.

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

#### Scenario: Track Only is reserved for track-only entries

- **WHEN** the map assigns a family Track Only, or an unmapped installable
  entry's source tags it Track Only
- **THEN** the map value fails policy loading, and the source tag is dropped

#### Scenario: A family key that names nothing selected builds

- **WHEN** the map names a family that no variant selects
- **THEN** the build succeeds

## MODIFIED Requirements

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
