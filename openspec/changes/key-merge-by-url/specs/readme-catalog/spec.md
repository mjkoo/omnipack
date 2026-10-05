## ADDED Requirements

### Requirement: Catalog rows pair final variant configurations by family label

The catalog SHALL contain one row per pair that offline verification's pairing
produces across both exports, plus one row per entry that pairing leaves
unpaired. Entries of different family labels SHALL never share a row, even
when they share a package id or name. Track-only
entries SHALL be labelled and paired by the same projections as installable
entries, and a single entry with no dual pair, which verification reports as a
nonfatal single-only coverage finding, SHALL still get its own row. Columns SHALL be
Program, Single-screen and Dual-screen. Each available
variant SHALL include its own source URL and Add to Obtainium link; an unavailable
variant SHALL display a hyphen. The single-screen record SHALL supply the row name
and first category when present, otherwise the dual-screen record SHALL supply
them. Empty categories SHALL use Other. Each category SHALL be a closed collapsible
section. Categories and rows SHALL have deterministic, case-insensitive ordering
with exact text, then family label breaking ties. Source text SHALL be escaped
so it cannot change the table structure or create HTML elements.

#### Scenario: Variant builds differ

- **WHEN** a family uses different package IDs, repositories or settings across variants
- **THEN** one row presents both exact configurations and their own source links

#### Scenario: Dual-only uncategorized app

- **WHEN** a selected family is present only in dual with no categories
- **THEN** its row appears in Other with a hyphen in the single-screen column

#### Scenario: Single-only family

- **WHEN** a single entry has no dual entry carrying its family label
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

## REMOVED Requirements

### Requirement: Catalog groups final variant configurations by family

**Reason**: Rows now follow verification's one-pass pairing by explicit projection or normalized URL, so the package-id pairing scenarios no longer apply.

**Migration**: Replaced by "Catalog rows pair final variant configurations by family label".
