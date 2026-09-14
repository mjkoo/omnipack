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
using the default value for any key the entry does not set.

#### Scenario: Entry sets one setting

- **WHEN** a composed entry sets exactly one per-app setting
- **THEN** the rendered entry's settings carry that value together with the
  default value for every other key defined for the source type that entry
  carries

#### Scenario: Overlaid value survives hydration

- **WHEN** an overlay set a value for a key that also has a default
- **THEN** the rendered entry carries the overlaid value, not the default

### Requirement: Rendered output is deterministic

The nightly rebuild commits only when the pack actually changed, so rendering
the same composed pack twice must produce identical bytes. The system SHALL
emit entries in a total order derived from their content, ordering them by
primary category, then by name, then by package id, and SHALL emit object keys
and formatting identically across runs. An entry's primary category is the
first category in its category list; an entry carrying no category SHALL sort
as though its primary category were the empty string, which orders before every
named category.

#### Scenario: Rebuilding unchanged input

- **WHEN** a variant is rendered twice from the same composed entries
- **THEN** both renderings are byte-identical

#### Scenario: Two entries sort equally on their primary key

- **WHEN** two entries would sort equally by their leading sort key
- **THEN** a further key breaks the tie so that their relative order is the
  same on every run

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

### Requirement: Package ids are unique within a rendered file

The system SHALL fail the build rather than write a file containing two apps
with the same package id.

#### Scenario: Duplicate id reaches rendering

- **WHEN** a variant's entries contain two apps sharing a package id
- **THEN** the build fails with an error naming that id
