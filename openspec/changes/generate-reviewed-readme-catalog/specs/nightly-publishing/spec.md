## ADDED Requirements

### Requirement: Publication requires fresh verification of committed-source builds

Each run SHALL set up its selected revision's locked runtime once, build once,
and run fresh structural verification once on the resulting candidate. Nightly
SHALL NOT repeat development CI formatting, lint, type, Python packaging or full
test-suite checks, verify old committed outputs before building, or replace those
checks with a CI-status polling gate. Publication SHALL require complete successful
evidence matching the current candidate inputs and selected revision's verifier
identity, input paths and report schema. Build failure, verification failure,
missing, stale or incomplete evidence SHALL prevent publication of every
candidate file. Existing non-blocking composition warnings SHALL retain their
policy. Source-generation failures SHALL be independent of nightly eligibility.

Verification SHALL use `pack verify` without retired live flags and SHALL make
no network requests. Building SHALL retain upstream JSON network ingestion and read the accepted
codm2000 JSON locally, without README fetches or APK package-ID discovery. Prior-run success SHALL NOT substitute for fresh candidate
verification. Exact-byte staging and commit checks SHALL remain required.

#### Scenario: Candidate verifies with warnings

- **WHEN** the build and fresh structural verification succeed with non-blocking build warnings
- **THEN** the candidate is eligible and warnings remain visible without running development CI checks

#### Scenario: Failed refresh

- **WHEN** building or verification fails
- **THEN** no README or pack candidate is published and accepted source state remains unchanged

#### Scenario: Stale or incomplete evidence

- **WHEN** evidence is absent, incomplete, from another verifier or mismatches candidate inputs
- **THEN** publication is rejected

#### Scenario: App metadata is unavailable after a successful build

- **WHEN** building and fresh structural verification succeed
- **THEN** eligibility requires no separate app-release metadata lookup
- **AND** upstream JSON ingestion and committed-source validation retain their build-time failure policy

### Requirement: Publish only verified pack outputs and the README catalog

The publisher SHALL limit commits to `dist/single-screen.json`,
`dist/dual-screen.json` and `README.md`. Committed source catalogs, source
metadata and resolution state SHALL NOT be published or modified by nightly.
README changes SHALL be restricted to the interior of exactly one valid catalog
marker pair; prefix and suffix bytes, including markers, SHALL match the selected
base revision. This restriction SHALL be rechecked at candidate capture and
when staging finishes. It SHALL reject missing
candidate files, symlink replacements, unexpected tracked modifications, and
changes to candidate bytes after verification. Both packs and the README SHALL
be published in one commit when any allowed bytes differ from the base.
Unchanged files need not appear in the commit diff. Reports and transient
caches SHALL NOT be committed. A byte-identical candidate SHALL create no commit, even if file modes changed.
Publication SHALL preserve base file modes. The publisher SHALL recheck the
full tracked-change allowlist when staging finishes.

Publication SHALL use a conventional commit identifying the UTC date, run, and
base revision, and a normal fast-forward push to main. It SHALL NOT force-push
or alter repository protection settings to bypass a rejection.

#### Scenario: Resolver state or source catalog changes

- **WHEN** a nightly candidate changes resolution state, source metadata or a committed source catalog
- **THEN** publication is rejected as an out-of-scope tracked mutation

#### Scenario: Successful no-op

- **WHEN** all allowed bytes match the base and main is confirmed unchanged
- **THEN** the run records a successful no-op without creating a commit

#### Scenario: Unexpected mutation

- **WHEN** an unrelated tracked file changes or verified candidate bytes change
  before staging completes
- **THEN** publication is rejected

#### Scenario: Generated catalog refresh

- **WHEN** verified generated catalog bytes differ from the base
- **THEN** the README change is published with any changed packs in one commit

#### Scenario: Handwritten README mutation

- **WHEN** a candidate changes README content outside the generated section
- **THEN** publication fails even if standalone verification succeeds

## REMOVED Requirements

### Requirement: Publication requires fresh metadata verification

**Reason**: Nightly no longer performs APK discovery or persists resolver cache updates.
**Migration**: Use "Publication requires fresh verification of committed-source builds" and the separate readme-source-generation contract. Retained output safety and composition behavior are included in the replacement.


### Requirement: Publish only the verified output and cache

**Reason**: Resolution state moves to the source-update PR; cache-only nightly commits are retired.
**Migration**: Use "Publish only verified pack outputs and the README catalog" and the separate readme-source-generation contract. Retained output safety and composition behavior are included in the replacement.
