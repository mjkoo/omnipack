## MODIFIED Requirements

### Requirement: Verification evidence belongs to an exact input snapshot

Standalone verification SHALL write `.build/verify.json` separately from the
build report. It SHALL include schema and verifier versions, the compatibility
baseline, mode (`offline`, `live`, or `live-probe`), observation times, completion
and status, input fingerprints,
errors, warnings, and per-variant entry results with resolution and probe evidence.
Fingerprints SHALL cover exact bytes of both output files, the denylist, both
overlays, composition policy, pack settings, README and HTTP configuration, identifying missing/unreadable
inputs explicitly and excluding token values. Input changes during a run SHALL
prevent a successful result for the current files.

The system SHALL write an incomplete running record before live requests and
atomically replace it on completion, including failed completion. Offline errors
SHALL prevent live requests. After offline success, independent live failures
SHALL be collected across both variants instead of stopping at the first entry.
Equivalent resolution inputs SHALL share requests within a run, but each variant
and id SHALL retain its own result. HTML resolution identity SHALL preserve the
exact configured request URL, including scheme, authority, path, trailing slash
and query, unless request equivalence is established; project URL normalization
SHALL NOT establish this equivalence. Success SHALL require completion and no
errors, regardless of any cached package id or prior verification report.

#### Scenario: Same package id has different variant settings

- **WHEN** single-screen and dual-screen entries share an id but differ in URL or
  resolution settings
- **THEN** each is resolved with its own configuration and reported separately

#### Scenario: Trailing-slash HTML endpoints have different results

- **WHEN** two HTML entries have identical settings and configured URLs differing
  only by a trailing slash, but the endpoints serve different versions and
  relative download links
- **THEN** each entry resolves its own version and download URL using its own
  final response URL as the relative base
- **AND** project-normalized URL equality does not permit sharing their results

#### Scenario: A live attempt is interrupted

- **WHEN** verification stops after writing its running record but before completion
- **THEN** the stored report is incomplete and cannot be presented as a success

#### Scenario: A second entry fails independently

- **WHEN** two entries fail at different live stages after offline validation passes
- **THEN** the completed report contains both failures and the run fails

#### Scenario: Policy changes during verification

- **WHEN** the composition policy bytes change during a run
- **THEN** the result cannot be successful for the current input snapshot

#### Scenario: Old evidence lacks composition policy

- **WHEN** recorded evidence predates the policy fingerprint or current verifier identity
- **THEN** it is stale rather than proof that current family constraints passed

#### Scenario: README changes during verification

- **WHEN** README bytes change during a verification run
- **THEN** the result cannot be successful for the current files

#### Scenario: Old evidence lacks README

- **WHEN** recorded evidence predates the README fingerprint or current verifier identity
- **THEN** reports remain readable but evidence is stale and cannot authorize publication

## ADDED Requirements

### Requirement: Offline verification checks the generated catalog

Verification SHALL reject a missing, unreadable or malformed README and a catalog
that differs from deterministic generation using the captured serialized packs
and current composition policy. Handwritten content SHALL NOT affect catalog
comparison but SHALL be included in the exact input fingerprint. Verification
SHALL NOT rewrite any inputs or fetch sources to generate the expected catalog.
Catalog errors SHALL prevent live requests like other offline errors.

#### Scenario: Stale import link

- **WHEN** an app's exported configuration differs from its README import payload
- **THEN** offline verification fails without repairing either file

#### Scenario: Handwritten instructions change

- **WHEN** README instructions change outside valid markers and the catalog remains current
- **THEN** a new offline verification succeeds and fingerprints the new README bytes

