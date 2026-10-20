# Spec Delta

## MODIFIED Requirements

### Requirement: Release synchronization follows main publication without gating it

After a successful main push or a verified main no-op, the publisher SHALL
synchronize the owned rolling release from that run's verified JSON pair,
subject to the conditions that
"Release writes require an established main outcome" in rolling-pack-release
places on every release write.
Release readiness SHALL NOT be a prerequisite for otherwise valid main output.
Release failure SHALL fail the workflow without undoing a successful main push,
and the run summary SHALL report the main outcome separately from the release
outcome.

#### Scenario: Main push succeeds and release write fails

- **WHEN** main publication succeeds but release synchronization fails
- **THEN** the workflow fails with the pushed commit and the release failure reported separately
- **AND** no rollback occurs, and the release failure is raised as a finding as
  maintenance-alerts requires

### Requirement: Actions summarizes and uploads each publication run's outcome

Actions step results and logs SHALL be the failure record. The publisher SHALL
write a short step summary identifying the main outcome (the published commit, a
candidate prepared for publication, a no-op, or the failing stage) and, when the
release stage runs, the release outcome (a new revision, a repair of the served
assets at the same revision, unchanged, or failure). A rejected or erroring push
SHALL appear as the failing main stage, and a release failure SHALL state its
reason, with the bootstrap guidance that "Bootstrap is explicit" in
rolling-pack-release requires for the release states it names. The build report
and structural verification report produced by the run SHALL be uploaded as
artifacts with 14-day retention on success and failure when they exist. Missing
reports after an early failure SHALL NOT imply verification success.
Verification reports SHALL be identified as structural/offline without
live-health claims. Failures and build warnings SHALL be raised as findings as
maintenance-alerts requires; only the workflow's alert job SHALL hold issue
write access. A summary failure, or a failure uploading the build and
verification reports or the hand-off, SHALL remain a visible failed step and
SHALL NOT undo a completed push. A failure in the job that prepares the
candidate, such a summary or upload failure there included, SHALL keep that
attempt's write job from running, so the attempt publishes nothing, and a rerun
or a later run SHALL make its own attempt. A failure writing or uploading the
findings file SHALL change neither the job's verdict nor whether the write job
runs, as maintenance-alerts requires.

Summaries and artifacts SHALL exclude credentials, raw HTTP caches and APK
downloads, and source text SHALL be treated as data rather than executable
input.

#### Scenario: Setup fails before reports exist

- **WHEN** runtime setup fails before any report is written
- **THEN** Actions shows the failed step and its logs, with no fabricated verification evidence
- **AND** the preparation job's early-failure finding is raised, and no open
  stage issue is closed

#### Scenario: Reused workspace fails before verification

- **WHEN** a workspace contains reports from a prior run and the current build fails before verification
- **THEN** only reports produced by the current run are uploaded

#### Scenario: Release fails after a confirmed push

- **WHEN** release synchronization fails after a successful main push
- **THEN** the summary names the pushed commit as the main outcome and, separately, the release failure with its reason as the release outcome

#### Scenario: Diagnostics fail around publication

- **WHEN** summary generation fails after a successful push, or an artifact upload fails in the job that produced the diagnostics, before any push exists
- **THEN** the failing step remains visible, a completed push is not undone, and a failure before any push keeps that attempt's write job from running, so the attempt publishes nothing and a rerun or a later run makes its own attempt

#### Scenario: Push outcome is summarized

- **WHEN** the push of the verified commit succeeds, or is rejected
- **THEN** the summary names the published commit, or the push failure for that commit, on its own line

#### Scenario: A candidate is prepared but not yet published

- **WHEN** a run builds and verifies a candidate and hands it off without having pushed it
- **THEN** the summary names that prepared candidate as its own outcome, distinct from a published commit, a no-op and a failing stage

#### Scenario: Sensitive or executable source text

- **WHEN** upstream diagnostics contain shell syntax or credential values
- **THEN** reporting neither executes that text nor exposes credentials

