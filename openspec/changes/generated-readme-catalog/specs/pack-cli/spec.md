## MODIFIED Requirements

### Requirement: The build command produces both variants

The system SHALL provide a build command that ingests every source, composes
and renders both variants, generates the README catalog, verifies the rendered
pair and catalog offline, and publishes all three files only after verification
succeeds. Handwritten README content SHALL be preserved byte-for-byte. Missing
or malformed catalog markers SHALL fail the build. The
build SHALL NOT perform live verification. Existing ingestion network requests
and generated package-id discovery SHALL remain part of building.

#### Scenario: Successful build

- **WHEN** the build command runs, every source is reachable, and the rendered
  pair passes offline verification
- **THEN** the single-screen and dual-screen import files and README catalog are written and the
  command exits successfully

#### Scenario: Offline verification rejects newly rendered output

- **WHEN** either newly rendered variant fails offline verification
- **THEN** neither distribution file nor the README is replaced, the command exits nonzero,
  and the build report identifies the offline verification stage and findings

### Requirement: A failed build leaves previous output intact

Automation commits whatever the distribution directory holds, so a partially
written pack would be published. The system SHALL leave the existing output
files unchanged when a build fails at any stage, and SHALL exit with a
non-zero status. The two import files and README SHALL be published as a recoverable unit.
A handled failure during replacement SHALL restore every replaced file to its
previous bytes or absence. Before publication, a README changed since capture
SHALL cause failure without overwriting that edit. Recovery covers handled
exceptions, not process termination, runner loss or rollback storage failure. The resolved package id cache is exempt: a newly
resolved id SHALL be written to the cache as soon as it resolves, so that a
build failing later keeps the resolution work it already paid for.

#### Scenario: Build fails after some output was rendered

- **WHEN** rendering succeeds for one variant and the build then fails
- **THEN** neither output file is modified and the command exits non-zero

#### Scenario: Build fails on the first run

- **WHEN** the build fails and no output files exist yet
- **THEN** no output files are created

#### Scenario: Build fails between replacing the two output files

- **WHEN** one import file has been replaced with its newly rendered contents
  and the build then fails before the other is replaced
- **THEN** both import files hold the contents they had before the build, and
  neither is present if the distribution directory held no output before it

#### Scenario: Build fails after resolving a new package id

- **WHEN** a build resolves a package id that was not previously cached and
  then fails before the output is written
- **THEN** the import files are unchanged and the cache retains the newly
  resolved id

#### Scenario: README replacement fails

- **WHEN** the JSON replacements succeed but replacing README fails
- **THEN** both JSON files are restored and README retains its previous bytes

#### Scenario: README is edited during building

- **WHEN** README differs from the bytes captured for catalog generation
- **THEN** publication fails before replacing outputs and preserves the edit
