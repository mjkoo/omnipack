# nightly-publishing Specification

## Purpose

Keep the raw Obtainium import files on main current through scheduled,
verified refreshes, with explicit publication outcomes and recoverable failure
reporting for maintainers.

## Requirements

### Requirement: Scheduled and manual refreshes use main

The system SHALL offer a daily refresh at 03:00 in America/New_York, following
daylight saving time, and manual dispatch using the same publication policy.
Write-capable refreshes SHALL run only for main in the canonical repository.
Active publishers SHALL be serialized without canceling an executing publisher,
with a 60-minute limit per run. Scheduling SHALL NOT promise exact delivery or
execution of every queued trigger. Each run SHALL select main once in its Actions
checkout before locked runtime setup, record that base revision, and use that
same clean initial tracked workspace and revision throughout its single attempt.

#### Scenario: Nightly or manual refresh

- **WHEN** an eligible scheduled or manual run starts
- **THEN** it selects main once and uses that checkout for setup, build, verification and publication
- **AND** it does not create disposable attempt checkouts or switch revisions during the run

#### Scenario: Ineligible invocation

- **WHEN** the workflow is dispatched from another ref or runs in a fork
- **THEN** it skips publication and release writes

#### Scenario: Overlapping triggers

- **WHEN** another refresh is triggered while a publisher executes
- **THEN** it neither runs concurrently with nor cancels that publisher

#### Scenario: Eastern time changes seasonally

- **WHEN** America/New_York changes between standard and daylight saving time
- **THEN** the scheduled local time remains 03:00

#### Scenario: Dirty initial checkout

- **WHEN** tracked changes already exist before the refresh starts
- **THEN** publication is rejected without treating those changes as generated output

### Requirement: Publication requires fresh metadata verification

Each run SHALL set up its selected revision's locked runtime once, build once,
and run fresh structural verification once on the resulting candidate. Nightly
SHALL NOT repeat development CI formatting, lint, type, Python packaging or full
test-suite checks, verify old committed outputs before building, or replace those
checks with a CI-status polling gate. Publication SHALL require complete successful
evidence matching the current candidate inputs and selected revision's verifier
identity, input paths and report schema. Build failure, verification failure,
missing, stale or incomplete evidence SHALL prevent publication of every
candidate file, including the package-ID cache. Existing non-blocking warnings
and generated-source soft failures SHALL retain their policy.

Verification SHALL use `pack verify` without retired live flags and SHALL make
no network requests. Building SHALL retain its network and APK package-ID
discovery behavior. Prior-run success SHALL NOT substitute for fresh candidate
verification. Exact-byte staging and commit checks SHALL remain required.

#### Scenario: Candidate verifies with warnings

- **WHEN** the build and fresh structural verification succeed with non-blocking build warnings
- **THEN** the candidate is eligible and warnings remain visible without running development CI checks

#### Scenario: Failed refresh after cache updates

- **WHEN** the build updates the local cache but building or verification fails
- **THEN** no cache, catalog or pack candidate is published

#### Scenario: Stale or incomplete evidence

- **WHEN** evidence is absent, incomplete, from another verifier or mismatches candidate inputs
- **THEN** publication is rejected

#### Scenario: App metadata is unavailable after a successful build

- **WHEN** building and fresh structural verification succeed
- **THEN** eligibility requires no separate app-release metadata lookup
- **AND** ingestion and package-ID discovery retain their build-time failure policy

### Requirement: Publish only the verified output and cache

The publisher SHALL limit commits to `dist/single-screen.json`,
`dist/dual-screen.json`, `README.md`, and `config/package-ids.json`.
README changes SHALL be restricted to the interior of exactly one valid catalog
marker pair; prefix and suffix bytes, including markers, SHALL match the selected
base revision. This restriction SHALL be rechecked at candidate capture and
when staging finishes. It SHALL reject missing
candidate files, symlink replacements, unexpected tracked modifications, and
changes to candidate bytes after verification. Both packs, the README and the cache SHALL
be published in one commit when any allowed bytes differ from the base.
Unchanged files need not appear in the commit diff. Reports and transient
caches SHALL NOT be committed. A byte-identical candidate SHALL create no commit, even if file modes changed.
Publication SHALL preserve base file modes. The publisher SHALL recheck the
full tracked-change allowlist when staging finishes.

Publication SHALL use a conventional commit identifying the UTC date, run, and
base revision, and a normal fast-forward push to main. It SHALL NOT force-push
or alter repository protection settings to bypass a rejection.

#### Scenario: Pack and cache changes

- **WHEN** the verified candidate changes an output and the package-id cache
- **THEN** one commit publishes their verified bytes and no unrelated files

#### Scenario: Cache-only refresh

- **WHEN** both packs are unchanged but the verified package-id cache differs
- **THEN** one commit preserves the cache change

#### Scenario: Successful no-op

- **WHEN** all allowed bytes match the base and main is confirmed unchanged
- **THEN** the run records a successful no-op without creating a commit

#### Scenario: Unexpected mutation

- **WHEN** an unrelated tracked file changes or verified candidate bytes change
  before staging completes
- **THEN** publication is rejected

#### Scenario: Generated catalog refresh

- **WHEN** verified generated catalog bytes differ from the base
- **THEN** the README change is published with any changed packs and cache in one commit

#### Scenario: Handwritten README mutation

- **WHEN** a candidate changes README content outside the generated section
- **THEN** publication fails even if standalone verification succeeds

### Requirement: Nightly completion includes rolling release synchronization

After confirmed main publication or a verified main no-op, the publisher SHALL
synchronize the owned rolling release from that run's exact verified JSON pair.
Release readiness SHALL NOT be a prerequisite for otherwise valid main output.
Main publication and release synchronization SHALL have distinct outcomes.
Release failure SHALL fail the workflow without undoing a confirmed main push;
reporting failure SHALL NOT erase already logged confirmation. A later fresh
verified run SHALL attempt release synchronization even when main is a no-op.
Failed or uncertain main publication SHALL prohibit release writes.

#### Scenario: Main push succeeds and release write fails

- **WHEN** main publication succeeds but release synchronization fails
- **THEN** the workflow fails with the confirmed main SHA and release failure reported separately
- **AND** no rollback or issue maintenance occurs

#### Scenario: Missing release seed

- **WHEN** main output is eligible but the release seed is missing or invalid
- **THEN** main publication or verified no-op proceeds independently
- **AND** the release stage fails without unauthorized release writes

#### Scenario: Main outcome is uncertain

- **WHEN** the publisher cannot establish whether its push succeeded
- **THEN** it records uncertainty and performs no release writes

#### Scenario: Later main no-op repairs the release

- **WHEN** a later freshly verified run needs no main commit but release synchronization is incomplete
- **THEN** it attempts synchronization from that run's verified pair

### Requirement: Main publication uses one refresh attempt

The publisher SHALL confirm main still matches its base before pushing or
recognizing a verified no-op. If main advances, the run SHALL fail without
publishing the stale candidate or starting another attempt. A later invocation
SHALL build and verify its own selected revision. The publisher SHALL NOT rebase,
cherry-pick generated output, retry a main push, or rebuild within the same run.

After a rejected or ambiguous push, the publisher SHALL inspect remote main
history. Presence of the intended commit SHALL confirm publication even when
later commits follow it. Confirmed absence SHALL report failure. An unreadable
remote result SHALL report uncertainty, never confirmed non-publication. This
reconciliation SHALL NOT cause another push or refresh attempt.

#### Scenario: Main advances during verification

- **WHEN** the candidate verifies but main now points to a newer revision
- **THEN** the run fails without another build, push or release synchronization

#### Scenario: Main advances before a no-op

- **WHEN** generated bytes match the selected base but main has advanced
- **THEN** the run fails instead of claiming a current no-op or synchronizing the release

#### Scenario: Main advances after the final comparison

- **WHEN** a normal push is rejected because another commit landed after the comparison
- **THEN** the publisher reconciles the intended commit's presence without retrying the push or build

#### Scenario: Push succeeded but acknowledgement was lost

- **WHEN** a push reports an error but the intended commit is in main's history
- **THEN** publication is confirmed and release synchronization is eligible
- **AND** no additional commit or push is created

#### Scenario: Protected main rejects publication

- **WHEN** a push is rejected and the intended commit is confirmed absent
- **THEN** the run fails without changing repository protections or synchronizing the release

#### Scenario: Remote outcome cannot be read

- **WHEN** a push reports failure and reconciliation cannot read remote main
- **THEN** the result is uncertain and no release writes or push retries occur

### Requirement: Actions records publication outcomes

Actions step results and logs SHALL provide the fallback failure record. When
the publisher can report its outcome, it SHALL produce a concise summary and
run result identifying available run/base/candidate/confirmed-published identifiers,
failing stage, main outcome and release outcome. Confirmed main publication or
no-op SHALL be logged before release synchronization starts. Available build,
structural-verification and run-result reports SHALL be offered as allowlisted
artifacts with 14-day retention on success and failure. Missing reports after
early failure SHALL NOT imply verification success. Verification evidence SHALL
be identified as structural/offline without live-health claims.

The workflow SHALL NOT maintain failure issues or request issue-write permission.
Summary or artifact-upload failure SHALL remain visible as failed Actions steps
without undoing publication or erasing already logged confirmation. Actions
SHALL be the authority for upload status; uploaded results SHALL NOT claim an
upload outcome that was not known when captured. Missing artifacts after failure
before report creation SHALL be acceptable. Hard cancellation, runner loss or
helper failure SHALL NOT promise reconstructed summaries or completed operations.
No separate fallback-finalization or disposable-checkout cleanup contract applies.

Diagnostics SHALL exclude credentials, raw HTTP caches and APK downloads, and
source text SHALL be treated as data rather than executable input. Documentation
SHALL describe token permissions and direct-push prerequisites without automatic
repository-setting changes.

#### Scenario: Setup fails before reports exist

- **WHEN** runtime setup fails before the publisher creates diagnostic reports
- **THEN** Actions shows the failed setup step and logs, with no issue write or fabricated candidate evidence
- **AND** missing diagnostic files do not require a recovery helper

#### Scenario: Release fails after a confirmed push

- **WHEN** release synchronization fails after main publication was logged
- **THEN** the workflow fails and preserves the main confirmation separately from the release failure

#### Scenario: Reporting fails after publication

- **WHEN** summary generation or artifact upload fails after a confirmed push
- **THEN** the failing step remains visible and the logged published SHA remains evidence
- **AND** no rollback, issue operation or fallback reconstruction is attempted

#### Scenario: Sensitive or executable source text

- **WHEN** upstream diagnostics contain shell syntax or credential values
- **THEN** reporting neither executes that text nor exposes credentials
