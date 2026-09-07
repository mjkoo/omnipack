## MODIFIED Requirements

### Requirement: The build command produces both variants

The system SHALL provide a build command that ingests every source, composes
and renders both variants, verifies the rendered pair offline, and writes them
to the distribution directory only after offline verification succeeds. The
build SHALL NOT perform live verification. Existing ingestion network requests
and generated package-id discovery SHALL remain part of building.

#### Scenario: Successful build

- **WHEN** the build command runs, every source is reachable, and the rendered
  pair passes offline verification
- **THEN** the single-screen and dual-screen import files are written and the
  command exits successfully

#### Scenario: Offline verification rejects newly rendered output

- **WHEN** either newly rendered variant fails offline verification
- **THEN** neither distribution file is replaced, the command exits nonzero,
  and the build report identifies the offline verification stage and findings

## ADDED Requirements

### Requirement: Build diagnostics include the offline verification verdict

The build report SHALL include an offline-verification section with status and
findings. Failure before this stage SHALL mark verification as not run. Failure
during verification SHALL preserve the existing build diagnostics and candidate
diff. Building SHALL NOT replace `.build/verify.json` or claim live health.

#### Scenario: Build fails before verification

- **WHEN** source ingestion fails
- **THEN** the build report identifies ingestion failure and verification as not run

### Requirement: The verify command inspects existing output

The system SHALL implement `pack verify` to check both current distribution
files and local configuration offline without network requests. It SHALL
implement `pack verify --live` to add live checks only after offline success.
Both modes SHALL record verification evidence and exit zero only on a complete,
error-free run; warnings alone SHALL not fail the command. Report write failure
SHALL cause a nonzero exit with a concise stderr diagnostic. Verification SHALL
not rebuild, update package ids, alter distribution/configuration files or
overwrite the last build report.

#### Scenario: Offline verification is invoked without a build report

- **WHEN** both distribution files and the local configuration are valid but no
  build report exists
- **THEN** `pack verify` succeeds, records offline evidence and makes no network call

#### Scenario: Invalid output is passed to live verification

- **WHEN** `pack verify --live` finds malformed output
- **THEN** it reports offline errors, performs no live request and exits nonzero

#### Scenario: Live check has warnings only

- **WHEN** every entry resolves and meets reachability requirements but some
  versions receive lint warnings
- **THEN** `pack verify --live` records the warnings and exits zero

### Requirement: The report command displays available evidence and its freshness

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
format without a schema field SHALL remain readable.

#### Scenario: Configuration changed after successful live verification

- **WHEN** an overlay changes after the recorded run
- **THEN** `pack report` displays the recorded results as stale

#### Scenario: A report describes failure

- **WHEN** a valid available report records a failed build or failed verification
- **THEN** `pack report` displays its failure details and exits zero

#### Scenario: Only a build report exists

- **WHEN** a valid build report exists and no verification report exists
- **THEN** the report command displays the build and says standalone verification
  has not been recorded, without treating it as a successful verification
