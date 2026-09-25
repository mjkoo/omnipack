# readme-catalog Specification

## Purpose

Help consumers install full packs or individual programs using a readable catalog
that stays consistent with the published Obtainium app configurations.

## Requirements

### Requirement: Consumer instructions identify installation routes and sources

The README SHALL present labeled raw main-branch single-screen and dual-screen JSON download links for mjkoo/omnipack immediately below its title, with device guidance. It SHALL provide a prominent ordered installation list before the individual catalog: install Obtainium, download the suitable pack, import the downloaded JSON through Import/Export, and install desired apps in Obtainium. It SHALL distinguish importing configurations from installing apps.

It SHALL explain that individual links require import confirmation and subsequent installation in Obtainium, and identify track-only entries as tracking resources rather than necessarily installable apps. It SHALL credit RJNY's source JSON, BBoi34's two release JSON catalogs, codm2000's project catalog, Obtainium, and individual app developers through a bulleted credits list with direct source links, including the app sources in catalog rows.

Development, build, verification, and detailed publishing guidance SHALL be available under docs. The root README SHALL provide a brief Contributing section linking to docs rather than embedding development commands or a documentation index.

#### Scenario: New visitor chooses a pack

- **WHEN** a visitor reads the README without Obtainium installed
- **THEN** both device-labeled downloads are immediately visible below the title
- **AND** ordered instructions explain Obtainium installation before importing the selected file and installing apps

#### Scenario: Visitor looks for attribution or development information

- **WHEN** a visitor reads beyond the catalog
- **THEN** credits are a bulleted list and a brief Contributing section links to documentation under docs

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

### Requirement: Individual links preserve exported app configuration

Each link SHALL use the documented Obtainium HTTPS redirect with an app deep link
carrying the complete final exported JSON object. Decoding the redirect parameter
and deep-link payload SHALL recover that app object exactly, preserving field
types, unknown fields and string-valued additionalSettings. Pack-wide settings
SHALL NOT be included. Link generation SHALL be deterministic and network-free.

#### Scenario: Encoded values contain reserved characters

- **WHEN** app fields contain Unicode, percent signs, ampersands, hashes or regex escapes
- **THEN** decoding the generated link recovers every value and type unchanged

### Requirement: Generation only replaces a marked catalog section

README SHALL contain exactly one ordered pair of standalone markers
`<!-- omnipack:catalog:start -->` and `<!-- omnipack:catalog:end -->`.
Generation SHALL replace only the interior bytes, preserve the prefix and suffix
including markers byte-for-byte, and fail for missing, duplicated or reversed
markers. Identical exports and policy SHALL generate identical catalog bytes.

#### Scenario: Invalid marker layout

- **WHEN** either marker is missing, duplicated, not standalone, or reversed
- **THEN** generation fails without replacing README or either pack

#### Scenario: Handwritten text surrounds the table

- **WHEN** catalog generation succeeds
- **THEN** every byte outside the marker interior remains unchanged
