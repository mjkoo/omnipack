## MODIFIED Requirements

### Requirement: Failures maintain one owned tracking issue

Handled setup, check, build, verification, and publication failures SHALL open,
reopen, or update one automation-owned issue titled `Nightly build failing`.
Ownership SHALL require the exact marker
`<!-- obtainium-pack:nightly-publishing -->` and GitHub Actions bot authorship.
The legacy marker SHALL remain stable across the omnipack rename so existing
issues remain discoverable. Title matches alone SHALL NOT authorize modification. Discovery SHALL include
all pages of open and closed issues and exclude pull requests. The
lowest-numbered owned issue SHALL be canonical; other open owned duplicates
SHALL be closed. Ambiguous creation SHALL trigger rediscovery before another
creation attempt.

The issue SHALL identify the failing stage, run URL, attempted base revision,
publication outcome including uncertainty, and available diagnostics. Repeated
failures SHALL update its body without adding repeated comments. Confirmed main publication or a verified main no-op SHALL authorize issue recovery only after rolling-release synchronization succeeds. Release failures SHALL update the owned issue and preserve the confirmed main outcome without rollback. Successful combined publication SHALL update and close existing open owned issues with recovery evidence. Success SHALL NOT create a new issue.

#### Scenario: First and recurring failure

- **WHEN** a refresh fails and no owned issue exists
- **THEN** one owned issue is created
- **AND WHEN** a later run fails
- **THEN** the same issue is updated or reopened

#### Scenario: Unrelated issue has the same title

- **WHEN** a user-authored or unmarked issue is titled `Nightly build failing`
- **THEN** the publisher leaves that issue unchanged

#### Scenario: Recovery without new output

- **WHEN** a run produces a verified main no-op, release synchronization succeeds and an owned failure issue is open
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
unavailable. A retained offline verification report SHALL be labeled offline
and SHALL NOT count as available live verification evidence. Diagnostic JSON
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

- **WHEN** setup or building fails before live verification starts
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

## ADDED Requirements

### Requirement: Nightly completion includes rolling release synchronization

After confirmed main publication or a verified main no-op, the publisher SHALL synchronize the owned rolling release from that attempt's exact verified JSON pair. Existing main verification, allowlist, concurrency and retry policies SHALL remain intact. Summaries and diagnostic records SHALL distinguish main publication, release synchronization, pending release revision, issue maintenance and cleanup outcomes. Release failure SHALL fail the workflow without undoing a confirmed main push. Cleanup or diagnostic failures SHALL NOT erase confirmed main or release outcomes. Issue recovery after a confirmed main push, including cleanup failure, SHALL additionally require confirmed release synchronization.

#### Scenario: Main push succeeds and release write fails

- **WHEN** release synchronization fails after confirmed main publication
- **THEN** the workflow fails with the main SHA preserved and release failure reported separately, and the owned issue remains open

#### Scenario: Main outcome is uncertain

- **WHEN** the publisher cannot establish whether its main push succeeded
- **THEN** it records uncertainty and performs no release writes
