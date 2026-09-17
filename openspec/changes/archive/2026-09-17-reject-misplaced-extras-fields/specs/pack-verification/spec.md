## MODIFIED Requirements

### Requirement: Structural verification evidence belongs to an exact input snapshot

Standalone verification SHALL write `.build/verify.json` separately from the
build report, as a diagnostic. It SHALL identify structural/offline scope, schema
and verifier versions, observation times, status, fingerprints of the exact
input bytes it checked, and errors with variant, entry and field context where
applicable. Fingerprints SHALL cover both output files, denylist, overlay,
composition policy and README. Missing and unreadable inputs SHALL be explicit.
HTTP configuration and credentials SHALL NOT be required, read, or fingerprinted
by structural verification. Reports SHALL NOT contain resolved versions, asset
probes, compatibility classifications, or an Obtainium compatibility guarantee.

Verification SHALL check and fingerprint one captured set of input bytes,
collect independently discoverable errors across both variants, and succeed
only when those bytes have no errors. The command's exit status SHALL be the
verification outcome; the report SHALL NOT serve as authorization for
publication. Previous reports SHALL NOT bypass these checks. A verification
report with any schema other than the current one SHALL require regeneration
with `pack verify`.

#### Scenario: Independent errors in both variants

- **WHEN** both exports contain structurally invalid entries
- **THEN** verification reports independently discoverable failures in both variants without network access

#### Scenario: Interrupted verification

- **WHEN** verification stops before it finishes checking its captured inputs
- **THEN** the command does not exit successfully, and any existing report describes only the inputs that report's run checked

#### Scenario: Inputs change during verification

- **WHEN** an input file changes after verification captured it
- **THEN** the report describes the captured bytes, and `pack report` labels it stale for the current files

#### Scenario: Network configuration is absent

- **WHEN** all structural inputs are valid but HTTP configuration and API credentials are absent
- **THEN** structural verification succeeds without consulting either

#### Scenario: Obsolete evidence

- **WHEN** a report uses a schema other than the current one
- **THEN** the user is instructed to regenerate it with `pack verify`
