## ADDED Requirements

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

## REMOVED Requirements

### Requirement: The settings block combines configuration with observed categories

**Reason**: The pack settings configuration was empty and is removed, so the
settings block no longer merges configured settings or configured category
colours. Replaced by "The settings block maps observed categories to derived
colours".

**Migration**: None. Category colours are derived from category names, and a
category colour or pack setting can no longer be configured.
