## MODIFIED Requirements

### Requirement: Catalog groups final variant configurations by family

The catalog SHALL contain one row per pair that offline verification's pairing
produces across both exports, plus one row per entry that pairing leaves
unpaired. Rows sharing a family label SHALL never be merged. Columns SHALL be
Program, Single-screen and Dual-screen. Each available
variant SHALL include its own source URL and Add to Obtainium link; an unavailable
variant SHALL display a hyphen. The single-screen record SHALL supply the row name
and first category when present, otherwise the dual-screen record SHALL supply
them. Empty categories SHALL use Other. Each category SHALL be a closed collapsible
section. Categories and rows SHALL have deterministic, case-insensitive ordering
with exact text, then family label, then the row's package ids breaking ties. Source text SHALL be escaped
so it cannot change the table structure or create HTML elements.

#### Scenario: Variant builds differ

- **WHEN** a family uses different package IDs, repositories or settings across variants
- **THEN** one row presents both exact configurations and their own source links

#### Scenario: Dual-only uncategorized app

- **WHEN** a selected family is present only in dual with no categories
- **THEN** its row appears in Other with a hyphen in the single-screen column

#### Scenario: Names contain markup

- **WHEN** an upstream name or category contains markup or table delimiters
- **THEN** it is rendered as text without altering the catalog structure

#### Scenario: Entries of different explicit families share a package id

- **WHEN** a single entry and a dual entry share a package id and their
  projections name different explicit families
- **THEN** they appear in separate rows

#### Scenario: Package-id pair and a dual entry share a family label

- **WHEN** a single entry projecting an explicit family shares its package id with
  a dual entry that has no explicit projection, and another dual entry projects
  that same explicit family
- **THEN** the package-id pair and the other dual entry appear as separate rows
  under that family label, so both dual configurations stay represented
