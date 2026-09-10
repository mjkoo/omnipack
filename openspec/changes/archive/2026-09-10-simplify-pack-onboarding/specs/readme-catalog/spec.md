## MODIFIED Requirements

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
