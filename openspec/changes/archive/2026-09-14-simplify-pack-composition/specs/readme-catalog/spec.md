## MODIFIED Requirements

### Requirement: Catalog groups final variant configurations by family

The catalog SHALL contain one row per current selected family across both exports,
using current policy projection and its package-family fallback. Columns SHALL be
Program, Single-screen and Dual-screen. Each available
variant SHALL include its own source URL and Add to Obtainium link; an unavailable
variant SHALL display a hyphen. The single-screen record SHALL supply the row name
and first category when present, otherwise the dual-screen record SHALL supply
them. Empty categories SHALL use Other. Each category SHALL be a closed collapsible
section. Categories and rows SHALL have deterministic, case-insensitive ordering
with exact text and family identity breaking ties. Source text SHALL be escaped
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
