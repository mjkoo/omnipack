## ADDED Requirements

### Requirement: The verify command performs structural checks only

The system SHALL implement `pack verify` to check both current distribution files,
local configuration and generated catalog offline without network requests.
The retired `--live` and `--probe-assets` flags SHALL be rejected as unsupported
arguments with nonzero exit before verification runs. The command SHALL record
structural evidence and exit zero only on a complete, error-free run. Report
write failure SHALL cause nonzero exit with a concise stderr diagnostic.
Verification SHALL NOT rebuild, update package IDs, alter distribution or
configuration files, or overwrite the build report.

#### Scenario: No build report is available

- **WHEN** the current exports, configuration and catalog pass local checks without a previous build report
- **THEN** `pack verify` succeeds and writes structural evidence without network access

#### Scenario: A retired flag is supplied

- **WHEN** either `--live` or `--probe-assets` is supplied, alone or together
- **THEN** argument parsing fails without network requests or replacement verification evidence

#### Scenario: Report persistence fails

- **WHEN** verification cannot write its report
- **THEN** it exits nonzero with a concise diagnostic

### Requirement: The report command displays structural evidence and its freshness

The system SHALL implement `pack report` to display the available build and
verification reports as separate human-readable sections without network access
or file changes. It SHALL show recorded failures, warnings, incomplete attempts,
verification mode and observation time. It SHALL compare verification input
fingerprints and verifier identity against the current files/configuration and
label nonmatching evidence stale. A current local fingerprint SHALL NOT be
described as proof of current upstream health.

One missing report SHALL be acceptable if the other can be displayed. When both
are missing, or an existing report is unreadable, malformed or has an unsupported
schema, the command SHALL exit nonzero with a useful diagnostic. Successfully
displaying a recorded failed operation SHALL exit zero. The existing build-report
format without a schema field SHALL remain readable. New build reports SHALL
also display family selections, fallback reasons, identity transitions and
candidate conflicts. The composition policy SHALL participate in freshness checks. Unsupported old
verification schemas SHALL produce a regeneration diagnostic directing the user
to `pack verify`, rather than being interpreted as current structural evidence.
Reports SHALL describe structural scope without resolved versions or live-health
claims. A supported schema with a different verifier identity SHALL be stale.

#### Scenario: Configuration changed after successful structural verification

- **WHEN** an overlay changes after the recorded run
- **THEN** `pack report` displays the recorded results as stale

#### Scenario: A report describes failure

- **WHEN** a valid available report records a failed build or failed verification
- **THEN** `pack report` displays its failure details and exits zero

#### Scenario: Only a build report exists

- **WHEN** a valid build report exists and no verification report exists
- **THEN** the report command displays the build and says standalone verification
  has not been recorded, without treating it as a successful verification

#### Scenario: Only composition policy changed

- **WHEN** config/composition.json changes while both pack files remain identical
- **THEN** recorded verification is displayed as stale


## REMOVED Requirements

### Requirement: The verify command inspects existing output

**Reason**: The live-capable command and report contracts are replaced by structural-only contracts.

**Migration**: Run `pack verify` without live flags and regenerate obsolete verification reports. Retained build reports remain readable.

### Requirement: The report command displays available evidence and its freshness

**Reason**: The live-capable command and report contracts are replaced by structural-only contracts.

**Migration**: Run `pack verify` without live flags and regenerate obsolete verification reports. Retained build reports remain readable.

