## ADDED Requirements

### Requirement: Actions summarizes and uploads each publication run's outcome

Actions step results and logs SHALL be the failure record. The publisher SHALL
write a short step summary identifying the main outcome (the published commit, a
candidate prepared for publication, a no-op, or the failing stage) and, when the
release stage runs, the release outcome (a new revision, a repair of the served
assets at the same revision, unchanged, or failure). A rejected or erroring push SHALL appear as
the failing main stage, and a release failure SHALL state its reason, with
bootstrap guidance when the release is absent, unowned, malformed, a draft, not
a prerelease, or immutable. The build report and structural verification report
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
retention, and run only publication scripts that import nothing outside the
standard library, on the runner's preinstalled Python. The triggering event
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

## MODIFIED Requirements

### Requirement: Nightly completion includes rolling release synchronization

After a successful main push whose pushed commit the publisher can establish as
its own local revision, or after a verified main no-op, the publisher SHALL
synchronize the owned rolling release from that run's verified JSON pair.
Release readiness SHALL NOT be a prerequisite for otherwise valid main output.
Release failure SHALL fail the workflow without undoing a successful main push,
and the run summary SHALL report the main outcome separately from the release
outcome. A main push that is rejected or reports an error SHALL prohibit release
writes in that run. Release writes SHALL also require main to still be at the
run's pushed commit or, after a verified no-op, at the run's base revision;
otherwise the release stage SHALL fail without writes, so no run publishes an
older pair after main has moved on. A later run whose verified output is
already on main SHALL synchronize the release as a verified no-op.

#### Scenario: Main push succeeds and release write fails

- **WHEN** main publication succeeds but release synchronization fails
- **THEN** the workflow fails with the pushed commit and the release failure reported separately
- **AND** no rollback or issue maintenance occurs

#### Scenario: Missing release seed

- **WHEN** main output is eligible but the release seed is missing or unowned
- **THEN** main publication or the verified no-op proceeds independently
- **AND** the release stage fails without release writes

#### Scenario: Main outcome is uncertain

- **WHEN** the main push reports an error, whether or not the commit actually landed
- **THEN** the run fails and performs no release writes
- **AND** a later run that finds the commit on main treats it as a verified no-op and synchronizes the release

#### Scenario: Later main no-op repairs the release

- **WHEN** a later verified run needs no main commit but the release does not match its verified pair
- **THEN** it synchronizes the release from that run's verified pair

#### Scenario: Write job rerun after main advanced

- **WHEN** the write job of an earlier run is rerun after a later run changed main
- **THEN** it fails without a push or release write, and the summary reports that main advanced
- **AND** the release keeps the later run's pair and revision

### Requirement: Publication requires fresh verification of committed-source builds

Each run SHALL set up the checked-out revision's locked runtime once, build
once, and run structural verification once on the resulting candidate, all in
the read-only job. The publisher SHALL publish only bytes that passed that run's
verification: the read-only job SHALL commit the candidate before verification,
and the write job SHALL push only that exact commit, identified by its SHA, so
the pushed commit contains exactly the allowed-file bytes that verification
checked. The write job SHALL reject a handed-off commit that is not the verified
SHA, or whose parent is not the checked-out main revision, before any push or
release write. A failed verification SHALL prevent publication of every
candidate file and SHALL keep the write job from running. Nightly SHALL NOT repeat development CI formatting, lint, type or
test-suite checks, verify old committed outputs before building, poll CI status,
or accept a verification report from another run as authorization. Non-blocking
composition diagnostics SHALL retain their policy: they SHALL NOT block
publication, and the run's build report SHALL record them. Source-generation
failures SHALL be independent of nightly eligibility.

Verification SHALL use `pack verify` and SHALL make no network requests.
Building SHALL retain upstream JSON network ingestion and read the committed
codm2000 catalog locally, without README fetches or APK package-ID discovery.

#### Scenario: Candidate verifies with warnings

- **WHEN** the build and structural verification succeed with non-blocking composition diagnostics
- **THEN** the candidate is eligible and those diagnostics stay recorded in the run's uploaded build report, without running development CI checks

#### Scenario: Failed refresh

- **WHEN** building or verification fails
- **THEN** no README or pack candidate is published

#### Scenario: Stale or incomplete evidence

- **WHEN** a verification report from an earlier run exists, or this run's verification does not complete successfully
- **THEN** publication depends only on this run's verification succeeding, and is rejected otherwise

#### Scenario: Bytes change after verification

- **WHEN** an allowed file in the workspace no longer matches the local commit after verification
- **THEN** publication is rejected

#### Scenario: Handed-off commit is not the verified commit

- **WHEN** the commit the write job receives differs from the verified SHA, or its parent is not the checked-out main revision
- **THEN** the run fails before any push or release write

#### Scenario: App metadata is unavailable after a successful build

- **WHEN** building and structural verification succeed
- **THEN** eligibility requires no separate app-release metadata lookup
- **AND** upstream JSON ingestion and committed-source validation retain their build-time failure policy

## REMOVED Requirements

### Requirement: Actions records publication outcomes

**Reason**: One requirement covered two subjects, what a run reports and which job may hold the publication credential, so restating either meant restating both. It is replaced by "Actions summarizes and uploads each publication run's outcome" and "The publication credential belongs to the write job alone", which carry every rule and every scenario forward between them. The reporting half additionally gains the prepared candidate as a summarized main outcome, which the enumeration omitted, and restates its diagnostics-failure scenario over sequences the workflows can produce: both artifact uploads run in the read-only job, so none can follow a push.

**Migration**: None. The workflows and publication scripts are unchanged. Rules about summaries, artifacts and the content of either are now stated by the reporting requirement; rules about workflow permissions, the credential's reach, what the write job may run and how the read-only job's outputs reach it are stated by the isolation requirement.
