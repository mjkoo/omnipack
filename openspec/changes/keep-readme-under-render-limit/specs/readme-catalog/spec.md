# Spec Delta

## MODIFIED Requirements

### Requirement: Catalog rows pair final variant configurations by family label

The catalog SHALL pair a single-screen entry with the dual-screen entry
carrying the same family label, the label offline verification assigns, and
SHALL contain one row per such pair across both exports, plus one row per
entry left unpaired. Entries of different family labels SHALL never share a row, even
when they share a package id or name. Track-only entries SHALL be labelled and
paired by the same projections as installable entries, and an entry with no
pair in the other variant SHALL still get its own row. Generation SHALL fail, naming the
variant and the family, when one variant holds more than one entry of a family
label. Columns SHALL be Program, Single-screen and Dual-screen. Each available
variant SHALL include its own source URL and Add to Obtainium link; an
unavailable variant SHALL display a hyphen. The single-screen record SHALL
supply the row name and first category when present, otherwise the dual-screen
record SHALL supply them. Empty categories SHALL use Other. Each category
SHALL be a closed collapsible section. Categories and rows SHALL have
deterministic, case-insensitive ordering with exact text, then family label
breaking ties. Source text SHALL be escaped so it cannot change the table
structure or create HTML elements.

#### Scenario: Variant builds differ

- **WHEN** a family uses different package IDs, repositories or settings across variants
- **THEN** one row presents both configurations, each with its own source link
  and an import link carrying that variant's record as the individual link
  requirement defines it

#### Scenario: Dual-only uncategorized app

- **WHEN** a selected family is present only in dual with no categories
- **THEN** its row appears in Other with a hyphen in the single-screen column

#### Scenario: Single-only family

- **WHEN** a single entry has no dual entry carrying its family label, because
  a denial removes the family's builds from dual
- **THEN** its row appears with its single-screen configuration and a hyphen
  in the dual-screen column, and generation succeeds

#### Scenario: Names contain markup

- **WHEN** an upstream name or category contains markup or table delimiters
- **THEN** it is rendered as text without altering the catalog structure

#### Scenario: Entries of different repositories share a package id

- **WHEN** a single entry and a dual entry share a package id, carry different
  normalized project URLs, and no projection covers either
- **THEN** they appear in separate rows

#### Scenario: One repository publishes two families

- **WHEN** two entries of one variant share a project URL and rules at that
  URL assign them different families
- **THEN** each appears in its own row, under its own family label

#### Scenario: A family label repeats within one variant

- **WHEN** one variant holds two entries that carry the same family label,
  whether through rules at different URLs naming one family or through one URL
- **THEN** catalog generation fails naming the variant and the family

### Requirement: Individual links preserve exported app configuration

Each link SHALL use the documented Obtainium HTTPS redirect with an app deep link
carrying the final exported JSON object, except that for an entry whose source
type is GitHub or GitLab, each additionalSettings key whose value equals that
source's value in omnipack's committed settings defaults table SHALL be left
out. Decoding the redirect parameter and deep-link payload SHALL recover every
other field and setting exactly, preserving field types, unknown fields and
string-valued additionalSettings. Pack-wide settings SHALL NOT be included. Link
generation SHALL be deterministic and network-free.

#### Scenario: Encoded values contain reserved characters

- **WHEN** app fields contain Unicode, percent signs, ampersands, hashes or regex escapes
- **THEN** decoding the generated link recovers every value and type unchanged

#### Scenario: A GitHub entry carries default-valued settings

- **WHEN** a GitHub entry's additionalSettings hold one setting at its value
  in the GitHub defaults table and one setting at another value
- **THEN** decoding its link recovers the entry without the default-valued
  setting, with the other setting and every other field unchanged

#### Scenario: An HTML entry carries default-valued settings

- **WHEN** an HTML entry's additionalSettings hold settings at their values in
  the HTML defaults table
- **THEN** decoding its link recovers the entry exactly, those settings
  included

#### Scenario: A GitHub entry's settings are not a JSON object

- **WHEN** a GitHub entry's additionalSettings string does not decode to a JSON
  object
- **THEN** decoding its link recovers the entry exactly
