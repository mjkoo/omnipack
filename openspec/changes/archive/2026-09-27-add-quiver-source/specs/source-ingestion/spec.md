## ADDED Requirements

### Requirement: Committed Quiver entries are baseline builds with generated provenance

Routine ingestion SHALL read Quiver entries from its configured committed
Obtainium catalog without requesting Quiver lists, release metadata or APKs.
A missing, unreadable or malformed catalog or repeated entry ID SHALL fail the
build while preserving previous outputs. Valid entries SHALL carry source
`quiver`, generated origin `quiver-generated`, their committed package identities,
explicit GitHub source type and reviewed discovery settings. They SHALL be
baseline candidates eligible for both packs, subject to ordinary normalization,
composition policy, denials and overlays. Every valid entry SHALL reach
composition, including entries sharing another source's project URL. Routine
ingestion SHALL NOT modify the catalog or generate missing entries. Source
records SHALL obey the existing prohibition on composition fields and preserve
generated provenance in reports without claiming a fresh APK check.

#### Scenario: Quiver hosting is unavailable during build

- **WHEN** the committed Quiver catalog and the other build inputs are valid
- **THEN** building succeeds without requesting Quiver hosting or APK data

#### Scenario: Broken committed Quiver catalog

- **WHEN** the configured catalog is missing, malformed or repeats an entry ID
- **THEN** the build fails naming Quiver and leaves published outputs unchanged

#### Scenario: Quiver record carries policy fields

- **WHEN** a committed Quiver record includes a top-level family or packageId field
- **THEN** ingestion rejects it under the source-record policy-field prohibition
