## ADDED Requirements

### Requirement: Release synchronization follows main publication without gating it

After a successful main push or a verified main no-op, the publisher SHALL
synchronize the owned rolling release from that run's verified JSON pair,
subject to the conditions "Release writes require an established main outcome"
in rolling-pack-release places on every release write.
Release readiness SHALL NOT be a prerequisite for otherwise valid main output.
Release failure SHALL fail the workflow without undoing a successful main push,
and the run summary SHALL report the main outcome separately from the release
outcome.

#### Scenario: Main push succeeds and release write fails

- **WHEN** main publication succeeds but release synchronization fails
- **THEN** the workflow fails with the pushed commit and the release failure reported separately
- **AND** no rollback or issue maintenance occurs

## MODIFIED Requirements

### Requirement: Actions summarizes and uploads each publication run's outcome

Actions step results and logs SHALL be the failure record. The publisher SHALL
write a short step summary identifying the main outcome (the published commit, a
candidate prepared for publication, a no-op, or the failing stage) and, when the
release stage runs, the release outcome (a new revision, a repair of the served
assets at the same revision, unchanged, or failure). A rejected or erroring push SHALL appear as
the failing main stage, and a release failure SHALL state its reason, with
the bootstrap guidance "Bootstrap is explicit" in rolling-pack-release
requires for the release states it names. The build report and structural verification report
produced by the run SHALL be uploaded as artifacts with 14-day retention on
success and failure when they exist. Missing reports after an early failure
SHALL NOT imply verification success. Verification reports SHALL be identified
as structural/offline without live-health claims. The workflow SHALL NOT
maintain failure issues or request issue-write permission. Summary or upload
failure SHALL remain a visible failed step without undoing a prepared candidate
or a completed push.

Summaries and artifacts SHALL exclude credentials, raw HTTP caches and APK
downloads, and source text SHALL be treated as data rather than executable
input.

#### Scenario: Setup fails before reports exist

- **WHEN** runtime setup fails before any report is written
- **THEN** Actions shows the failed step and its logs, with no issue write or fabricated verification evidence

#### Scenario: Reused workspace fails before verification

- **WHEN** a workspace contains reports from a prior run and the current build fails before verification
- **THEN** only reports produced by the current run are uploaded

#### Scenario: Release fails after a confirmed push

- **WHEN** release synchronization fails after a successful main push
- **THEN** the workflow fails and its summary shows the pushed commit separately from the release failure

#### Scenario: Diagnostics fail around publication

- **WHEN** summary generation fails after a successful push, or an artifact upload fails in the job that produced the diagnostics, before any push exists
- **THEN** the failing step remains visible and neither the prepared candidate nor a completed push is undone

#### Scenario: Push outcome is summarized

- **WHEN** the push of the verified commit succeeds, or is rejected
- **THEN** the summary names the published commit, or the push failure for that commit, on its own line

#### Scenario: A candidate is prepared but not yet published

- **WHEN** a run builds and verifies a candidate and hands it off without having pushed it
- **THEN** the summary names that prepared candidate as its own outcome, distinct from a published commit, a no-op and a failing stage

#### Scenario: Sensitive or executable source text

- **WHEN** upstream diagnostics contain shell syntax or credential values
- **THEN** reporting neither executes that text nor exposes credentials

### Requirement: The publication credential belongs to the write job alone

The workflow SHALL grant no permissions at workflow level. The publication
credential SHALL be available only to the write job, which alone SHALL hold
contents write access. Every step of the read-only job, including checkout and
runtime setup, SHALL run with a job token limited to reading repository
contents, and none SHALL receive the publication credential. The write job SHALL
install no project dependencies and run no build or verification: it SHALL
check out afresh the main revision that triggered the run, receive the verified
commit only as git objects handed off by the read-only job with one-day
retention, and run only publication code that needs nothing installed in order
to run, so the job that holds the credential executes none of the project's
dependencies. The triggering event
SHALL fix the revision whose code the write job runs: no output of the
read-only job SHALL select it, and the write job SHALL fail before any write
unless the base revision the read-only job reports is that triggering revision.
Outputs of the read-only job SHALL reach the write job's scripts only through
step environment variables, never interpolated into a command, and the scripts
SHALL reject any commit identifier that is not a full 40-character hexadecimal
SHA. Within the write job, the credential SHALL be
passed only to the checkout of the triggering revision and to the steps that
push to main or write the release, and every git command there SHALL run with
repository hooks disabled. No checkout SHALL
persist a credential in the repository configuration. Documentation SHALL
describe token permissions, direct-push prerequisites and the one-time release
bootstrap, without automatic repository-setting changes.

#### Scenario: Build runs without the publication credential

- **WHEN** the preparation, build and verification steps run
- **THEN** they run in the read-only job, whose token can only read repository contents, and the publication credential is not present in their environment
- **AND** the checkout step has not persisted a credential in the repository configuration

#### Scenario: Write job runs no project build

- **WHEN** the write job pushes the verified commit and synchronizes the release
- **THEN** it has installed no project dependency and run no build, test or verification, and its git commands run with repository hooks disabled
- **AND** nothing from the read-only job reaches it except the handed-off commit and the outputs naming it

#### Scenario: Read-only job names another revision

- **WHEN** the read-only job's outputs name a base other than the triggering revision, or a commit identifier that is not a full SHA
- **THEN** the write job fails before any push or release write, having run only code from the triggering revision

## REMOVED Requirements

### Requirement: Nightly completion includes rolling release synchronization

**Reason**: It stated the release write preconditions, the readiness failure
and the later-run repair in its own words beside rolling-pack-release, which
states the same rules about the same release. Those rules now have one owner
there. What remains here is what only a run can promise: synchronization
follows main publication, never gates it, fails the workflow without undoing
main, and is summarized separately.

**Migration**: The run-level rules are "Release synchronization follows main publication without gating it".
The write preconditions, with the scenarios "Main outcome is uncertain" and
"Write job rerun after main advanced", are "Release writes require an established main outcome"
in rolling-pack-release. "Missing release seed" is covered by "First normal
run has no seed" and "Unowned release conflicts with synchronization" there,
and "Later main no-op repairs the release" by "Served asset is missing or
unverifiable", "Interrupted upload, then the recorded pair returns" and
"Explicit seed creation enables a later run".
