## ADDED Requirements

### Requirement: Every published pack app lets Obtainium adopt its installed package id

A source's package id for an app can differ from the id the app's APK
declares, and Obtainium refuses to install an imported app whose id disagrees
with its APK unless the app allows an id change. When rendering the published
packs from composed entries, every rendered app SHALL therefore carry
`allowIdChange` set to `true`, whatever its source record or an overlay patch
says, so an entry whose shipped id is wrong still installs and the install
adopts the APK's own package id. The canonical catalog rendering that source
generation uses for its committed catalogs SHALL NOT add `allowIdChange`, so a
generated catalog's bytes do not change.

Pack entries therefore do not keep Obtainium's protection against an id
change: Obtainium clears the flag only when an install actually changes the
stored id, and every import or re-import of the pack sets it back to `true`,
so if an upstream build later declares a different package id, Obtainium
adopts that id instead of reporting an id change. The flag does not stop
duplicates: Obtainium saves each imported record under its `id`, never
matching by URL, so while an entry's shipped id differs from its APK's, every
import after install adds a never-installed duplicate under the shipped id
beside the installed app. The owner fixes that entry's id with an overlay `id`
patch.

#### Scenario: A source's id differs from its APK

- **WHEN** a selected entry is rendered into a published pack, whether or not
  its id matches the package id its APK declares
- **THEN** the rendered app carries `allowIdChange: true`; rendering reads no
  APK and compares no ids, and Obtainium, given the flag, adopts the APK's own
  id when they differ

#### Scenario: A source record or overlay sets the flag false

- **WHEN** a source record or overlay patch sets `allowIdChange` to `false`
- **THEN** the rendered app still carries `allowIdChange: true`

#### Scenario: Source generation renders a committed catalog

- **WHEN** source generation renders a generated catalog through its
  canonical catalog rendering
- **THEN** no rendered record gains `allowIdChange`, and an unchanged catalog
  renders byte-for-byte as committed

## MODIFIED Requirements

### Requirement: Rendered output is deterministic

The nightly rebuild commits only when the pack actually changed, so rendering
the same composed pack twice must produce identical bytes. The system SHALL
emit entries in a total order derived from their content, ordering them by
primary category, then by name, then by package id, then by normalized project
URL, and finally by the entry's canonical serialized form, and SHALL emit
object keys and formatting identically across runs. A pack may carry one
package id in entries at different project URLs, so the project URL is needed
to order them, and the serialized form makes the order total whatever the
entries hold. An entry's primary category is the first category in its
category list; an entry carrying no category SHALL sort as though its primary
category were the empty string, which orders before every named category.

#### Scenario: Rebuilding unchanged input

- **WHEN** a variant is rendered twice from the same composed entries
- **THEN** both renderings are byte-identical

#### Scenario: Two entries sort equally on their primary key

- **WHEN** two entries would sort equally by their leading sort key
- **THEN** a further key breaks the tie so that their relative order is the
  same on every run

#### Scenario: Entries at different URLs share category, name and package id

- **WHEN** a variant holds two entries with the same primary category, name
  and package id at different normalized project URLs, and it is rendered from
  each permutation of its composed entries
- **THEN** the entries are ordered by normalized project URL and every
  rendering is byte-identical

#### Scenario: An entry carries no category

- **WHEN** a composed entry carries an empty category list
- **THEN** it sorts as though its primary category were the empty string, so it
  precedes every entry whose primary category is a named one

## REMOVED Requirements

### Requirement: Package ids are unique within a rendered file

**Reason**: Families no longer form by package id, so two selected entries of a pack can carry one id; composition reports that instead of failing.

**Migration**: See "A package id repeated within a pack is reported" in pack-composition.
