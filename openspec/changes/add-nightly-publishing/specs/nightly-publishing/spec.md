## Purpose

Keep the raw Obtainium import files on main current through scheduled,
verified refreshes, with explicit publication outcomes and recoverable failure
reporting for maintainers.

## ADDED Requirements

### Requirement: Scheduled and manual refreshes use main

The system SHALL offer a daily refresh at 06:23 UTC and a manual workflow
dispatch using the same publication policy. Write-capable refreshes SHALL run
only for main in the canonical repository. The system SHALL serialize active
publishers without canceling an executing publisher for a newer run. Each run
SHALL have a 60-minute execution limit. Scheduling SHALL NOT promise exact
delivery time or that every queued trigger executes.

#### Scenario: Nightly or manual refresh

- **WHEN** an eligible scheduled or manual run starts
- **THEN** it selects the current main revision and follows the same refresh gates

#### Scenario: Ineligible invocation

- **WHEN** the workflow is dispatched from another ref or runs in a fork
- **THEN** it skips publication and issue writes

#### Scenario: Overlapping triggers

- **WHEN** another refresh is triggered while a publisher is executing
- **THEN** the new trigger does not execute concurrently with or cancel that publisher

### Requirement: Publication requires fresh metadata verification

Each attempt SHALL check its selected revision using the repository's offline
Python checks, then build both packs and run fresh metadata-only live
verification on the resulting candidate. Publication SHALL require complete
successful verification evidence matching the candidate's current inputs and
verifier identity. Build failure, check failure, verification errors, absent
evidence, or incomplete evidence SHALL prevent publication of every candidate
file, including the package-id cache. Existing non-blocking warnings and
generated-source soft failures SHALL retain their existing policy.

Routine verification SHALL NOT probe assets. Building SHALL retain its existing
network and APK package-id discovery behavior. Prior-run success SHALL NOT
substitute for fresh live verification.

#### Scenario: Candidate verifies with warnings

- **WHEN** checks, build, and current live verification succeed with warnings only
- **THEN** the candidate is eligible for publication and warnings remain visible

#### Scenario: Failed refresh after cache updates

- **WHEN** building updates the local cache but building or verification fails
- **THEN** neither the cache nor the candidate packs are published to main

#### Scenario: Stale or incomplete evidence

- **WHEN** verification evidence is absent, incomplete, from another verifier,
  or does not match the candidate inputs
- **THEN** publication is rejected

### Requirement: Publish only the verified output and cache

The publisher SHALL limit commits to `dist/single-screen.json`,
`dist/dual-screen.json`, and `config/package-ids.json`. It SHALL reject missing
candidate files, symlink replacements, unexpected tracked modifications, and
changes to candidate bytes after verification. Both packs and the cache SHALL
be published in one commit when any allowed bytes differ from the base.
Unchanged files need not appear in the commit diff. Reports and transient
caches SHALL NOT be committed. A byte-identical candidate SHALL create no commit.

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

### Requirement: Concurrent changes require a fresh attempt

The publisher SHALL confirm main still matches the attempt's base before a
push or successful no-op. If main advances, the publisher SHALL discard the
candidate and perform one complete fresh attempt against the newer revision.
It SHALL NOT rebase or cherry-pick previously generated output or reuse its
verification. A run SHALL attempt refresh at most twice; further advancement
SHALL result in failure without publishing the stale candidate.

After a rejected or ambiguous push, the publisher SHALL inspect remote main.
An intended commit present in its history SHALL count as published. Otherwise,
an advanced main SHALL use the remaining retry budget. An unchanged main with
a rejected push, or an unreadable remote outcome, SHALL be reported as failure;
an uncertain outcome SHALL NOT be described as confirmed non-publication.

#### Scenario: Main advances during verification

- **WHEN** the first candidate verifies but main now points to a newer revision
- **THEN** a fresh attempt checks, builds, and verifies that revision before publishing

#### Scenario: Main advances twice

- **WHEN** main advances again during the second attempt
- **THEN** the run fails and does not push the stale candidate

#### Scenario: Push succeeded but acknowledgement was lost

- **WHEN** a push reports an error but the intended commit is found in main's history
- **THEN** publication is recorded as successful without creating another commit

#### Scenario: Protected main rejects publication

- **WHEN** pushing is rejected and main still matches the attempt's base
- **THEN** the run records publication failure without modifying protection settings

### Requirement: Failures maintain one owned tracking issue

Handled setup, check, build, verification, and publication failures SHALL open,
reopen, or update one automation-owned issue titled `Nightly build failing`.
Ownership SHALL require the exact marker
`<!-- obtainium-pack:nightly-publishing -->` and GitHub Actions bot authorship.
Title matches alone SHALL NOT authorize modification. Discovery SHALL include
all pages of open and closed issues and exclude pull requests. The
lowest-numbered owned issue SHALL be canonical; other open owned duplicates
SHALL be closed. Ambiguous creation SHALL trigger rediscovery before another
creation attempt.

The issue SHALL identify the failing stage, run URL, attempted base revision,
publication outcome including uncertainty, and available diagnostics. Repeated
failures SHALL update its body without adding repeated comments. Confirmed
publication or a verified no-op SHALL update and close existing open owned
issues with recovery evidence. Success SHALL NOT create a new issue.

#### Scenario: First and recurring failure

- **WHEN** a refresh fails and no owned issue exists
- **THEN** one owned issue is created
- **AND WHEN** a later run fails
- **THEN** the same issue is updated or reopened

#### Scenario: Unrelated issue has the same title

- **WHEN** a user-authored or unmarked issue is titled `Nightly build failing`
- **THEN** the publisher leaves that issue unchanged

#### Scenario: Recovery without new output

- **WHEN** a run produces a verified no-op and an owned failure issue is open
- **THEN** the issue records recovery and closes

#### Scenario: Issue update fails after publication

- **WHEN** publication is confirmed but issue maintenance fails
- **THEN** the workflow fails with both outcomes visible and does not undo the push

### Requirement: Diagnostics survive handled failures

The workflow SHALL produce a summary and retain available per-attempt build,
verification, and orchestration reports as artifacts for 14 days on handled
success and failure. The summary SHALL distinguish publication, no-op, failure,
uncertain publication, and issue-maintenance outcomes, with run/base/published
identifiers where available. Missing early-stage reports SHALL be identified as
unavailable. Diagnostics SHALL exclude credentials, raw HTTP caches, and APK
downloads; source text SHALL be treated as data, not executable input.

Issue maintenance or diagnostic upload errors SHALL remain visible as workflow
failures without undoing confirmed publication. Hard cancellation or runner
loss SHALL NOT be represented as a completed verification or guaranteed issue
delivery. The workflow SHALL document its required token permissions and
direct-push prerequisites without automatically changing repository settings.

#### Scenario: Early failure has no verification report

- **WHEN** setup or building fails before verification starts
- **THEN** the summary records the failure and missing verification evidence,
  and available diagnostics are retained

#### Scenario: Diagnostic upload fails

- **WHEN** artifact upload fails after a confirmed push
- **THEN** the workflow reports upload failure and preserves the published commit

#### Scenario: Sensitive or executable source text

- **WHEN** upstream diagnostics contain shell syntax or credential values
- **THEN** publication/reporting does not execute that text or expose credentials
