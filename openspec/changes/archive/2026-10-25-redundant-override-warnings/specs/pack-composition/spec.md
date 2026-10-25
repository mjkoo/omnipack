# Spec Delta

## ADDED Requirements

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
fails to render, plus `variants` when packs differ. Recording SHALL NOT
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

- **WHEN** an extra offered only to dual is selected over a catalog candidate
  at the same project URL that is offered to both packs and has equal settings
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

## MODIFIED Requirements

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
