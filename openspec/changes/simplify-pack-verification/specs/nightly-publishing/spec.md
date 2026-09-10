## MODIFIED Requirements

### Requirement: Publication requires fresh metadata verification

Each attempt SHALL check its selected revision using the repository's offline
Python checks, then build both packs and run fresh structural
verification on the resulting candidate. Publication SHALL require complete
successful verification evidence matching the candidate's current inputs and
verifier identity. Evidence validation SHALL use the selected attempt revision's
runtime, including its verifier identity, input paths, and report schema. Build failure, check failure, verification errors, absent
evidence, or incomplete evidence SHALL prevent publication of every candidate
file, including the package-id cache. Existing non-blocking warnings and
generated-source soft failures SHALL retain their existing policy.

Verification SHALL use `pack verify` without retired live flags and SHALL make no network requests. Building SHALL retain its existing
network and APK package-id discovery behavior. Prior-run success SHALL NOT
substitute for fresh structural verification.

#### Scenario: Candidate verifies with warnings

- **WHEN** checks, build, and fresh structural verification succeed while build diagnostics contain non-blocking warnings
- **THEN** the candidate is eligible for publication and warnings remain visible

#### Scenario: Failed refresh after cache updates

- **WHEN** building updates the local cache but building or verification fails
- **THEN** neither the cache nor the candidate packs are published to main

#### Scenario: Stale or incomplete evidence

- **WHEN** verification evidence is absent, incomplete, from another verifier,
  or does not match the candidate inputs
- **THEN** publication is rejected

#### Scenario: App metadata is unavailable after a successful build

- **WHEN** checks, build and fresh structural verification succeed
- **THEN** publication eligibility does not depend on a separate lookup of each configured app's release metadata
- **AND** build-time source ingestion and package-ID discovery retain their existing failure policy

### Requirement: Diagnostics survive handled failures

The workflow SHALL produce a summary and retain available per-attempt build,
verification, and orchestration reports as artifacts for 14 days on handled
success and failure. The summary SHALL distinguish publication, no-op, failure,
uncertain publication, and issue-maintenance outcomes, with run/base/published
identifiers where available. Missing early-stage reports SHALL be identified as
unavailable. A retained pre-build verification report SHALL be labeled as pre-build evidence
and SHALL NOT substitute for fresh verification of the built candidate. Candidate
verification SHALL be labeled structural/offline, without live-health claims. Diagnostic JSON
updates SHALL replace files atomically so an interrupted rewrite preserves the
last complete result for fallback finalization. Fallback SHALL preserve missing-report
markers and SHALL keep a triggering helper failure visible as workflow failure,
even when publication is confirmed and issue recovery succeeds. Diagnostics SHALL exclude credentials, raw HTTP caches, and APK
downloads; source text SHALL be treated as data, not executable input.

Cleanup errors SHALL be recorded separately, fail the workflow, and preserve
confirmed publication status, its SHA, and available per-attempt reports.
Issue maintenance or diagnostic upload errors SHALL remain visible as workflow
failures without undoing confirmed publication. Hard cancellation or runner
loss SHALL NOT be represented as a completed verification or guaranteed issue
delivery. The workflow SHALL document its required token permissions and
direct-push prerequisites without automatically changing repository settings.

#### Scenario: Early failure has no verification report

- **WHEN** setup or building fails before structural verification starts
- **THEN** the summary records the failure and missing verification evidence,
  and available diagnostics are retained

#### Scenario: Checkout cleanup fails after publication

- **WHEN** removing a disposable checkout fails after a confirmed push
- **THEN** the workflow fails with cleanup failure and confirmed publication
  separately visible in diagnostics
- **AND** confirmed publication authorizes issue recovery only when release synchronization is also confirmed
- **AND** the published SHA and captured attempt reports remain available

#### Scenario: Diagnostic upload fails

- **WHEN** artifact upload fails after a confirmed push
- **THEN** the workflow reports upload failure and preserves the published commit

#### Scenario: Sensitive or executable source text

- **WHEN** upstream diagnostics contain shell syntax or credential values
- **THEN** publication/reporting does not execute that text or expose credentials

