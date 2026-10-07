# pack-rendering Specification

## Purpose

Serializes a composed variant into the import file Obtainium actually reads,
so that importing it configures every app exactly as the pack intends and
rebuilding an unchanged pack produces an unchanged file.

## Requirements

### Requirement: Output uses Obtainium's import shape

The system SHALL write each variant as an import object carrying an app list
and a settings block, with each app carrying the fields Obtainium reads on
import.

#### Scenario: Rendered file imports cleanly

- **WHEN** a rendered variant is imported into Obtainium
- **THEN** every app in it is added without an import error

### Requirement: Per-app settings are rendered as a JSON-encoded string

Obtainium decodes each app's settings from a string on import; a nested object
in that position fails to import. The system SHALL encode each entry's per-app
settings as a JSON string in the rendered file.

#### Scenario: Entry carries structured settings

- **WHEN** a composed entry's per-app settings are structured data
- **THEN** the rendered entry's settings field is a string that decodes to
  those settings

### Requirement: Per-app settings are hydrated with the full default key set

Obtainium's app settings UI only shows a control for a key that is present, so
an entry carrying a partial settings object hides the rest of its switches.
The system SHALL fill each rendered entry's settings with every key defined for
the source type the entry carries, as established when the entry was ingested,
using the default value for any key the entry does not set, for every source
type the system holds defaults for. An entry with another source type, or with
no source type, SHALL be rendered with exactly the settings it carries, and SHALL NOT
fail rendering.

#### Scenario: Entry sets one setting

- **WHEN** a composed entry sets exactly one per-app setting
- **THEN** the rendered entry's settings carry that value together with the
  default value for every other key defined for the source type that entry
  carries

#### Scenario: Overlaid value survives hydration

- **WHEN** an overlay set a value for a key that also has a default
- **THEN** the rendered entry carries the overlaid value, not the default

#### Scenario: An entry's source type has no defaults

- **WHEN** a composed entry carries no source type, or one the system holds no
  defaults for
- **THEN** it renders with exactly its own settings and the build succeeds

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

### Requirement: The settings block maps observed categories to derived colours

The system SHALL render each variant's settings block with a `categories` field
holding the union of the categories used by the entries in that variant, so
that Obtainium can group and colour every app the pack contains. An entry
carrying no category contributes nothing to that union. The field SHALL be a
JSON-encoded string mapping each category name to its colour as an ARGB
integer. Each colour SHALL be derived from the category name alone, being the
first three bytes of the SHA-256 digest of the name as the red, green and blue
channels with the alpha channel fully opaque, so that the same category name
renders the same colour on every run and in both variants. The settings block
SHALL carry no other pack settings.

#### Scenario: Entry uses a category

- **WHEN** a composed entry carries a category
- **THEN** the rendered settings block includes that category, mapped to the
  ARGB value derived from the category name, and a later run renders the same
  value

#### Scenario: A category is unused in one variant

- **WHEN** entries in the dual-screen variant use a category that no
  single-screen entry uses
- **THEN** the single-screen settings block omits that category

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

#### Scenario: Every published entry may adopt its APK id

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
