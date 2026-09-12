## ADDED Requirements

### Requirement: Main publication is one normal push

The publisher SHALL publish with one normal push of the verified commit, whose
parent SHALL be the main revision that the run checked out for building. Before
pushing, the write job SHALL confirm that main is still that revision, and SHALL
otherwise fail without a push or release write. If the push is rejected or
reports an error, the run SHALL fail visibly. It SHALL NOT rebase, cherry-pick
generated output, retry the push, rebuild, or inspect remote history to
reinterpret the push outcome. A later invocation SHALL build and verify its own
checkout, and output that already landed SHALL then be a verified no-op.

#### Scenario: Main advances during the run

- **WHEN** another commit lands on main after the run's checkout, whether the write job finds it before pushing or the push is rejected
- **THEN** the run fails without another build, push or release write

#### Scenario: Main advances before a no-op

- **WHEN** the verified output matches the checked-out main but main has since advanced
- **THEN** the write job fails before any release write, and the summary reports that main advanced
- **AND** a later run on the newer main synchronizes the release and publishes any resulting change

#### Scenario: Push succeeded but acknowledgement was lost

- **WHEN** the push reports an error but the commit reached main
- **THEN** the run fails without creating another commit or push
- **AND** the next run finds no change to publish and synchronizes the release

#### Scenario: Protected main rejects publication

- **WHEN** repository protection rejects the push
- **THEN** the run fails without changing repository protections or synchronizing the release

## MODIFIED Requirements

### Requirement: Scheduled and manual refreshes use main

The system SHALL offer a daily refresh at 03:00 in America/New_York, following
daylight saving time, and manual dispatch using the same publication policy.
Write-capable refreshes SHALL run only for main in the canonical repository.
Active publishers SHALL be serialized without canceling an executing publisher,
with a 60-minute limit on each of a run's jobs. Scheduling SHALL NOT promise
exact delivery or execution of every queued trigger. Each run SHALL build and
verify from one clean checkout of the main revision that triggered it, in a
read-only job, publish that job's verified commit from a fresh checkout of that
same revision in a write job, and make one refresh attempt.

#### Scenario: Nightly or manual refresh

- **WHEN** an eligible scheduled or manual run starts
- **THEN** it builds and verifies from one checkout of the main revision that triggered it, and publishes the verified commit from a checkout of that same revision, without moving to a newer main revision during the run

#### Scenario: Ineligible invocation

- **WHEN** the workflow is dispatched from another ref or runs in a fork
- **THEN** neither job runs, and no publication or release write occurs

#### Scenario: Overlapping triggers

- **WHEN** another refresh is triggered while a publisher executes
- **THEN** it neither runs concurrently with nor cancels that publisher

#### Scenario: Eastern time changes seasonally

- **WHEN** America/New_York changes between standard and daylight saving time
- **THEN** the scheduled local time remains 03:00

#### Scenario: Dirty initial checkout

- **WHEN** tracked changes already exist before the refresh starts
- **THEN** publication is rejected without treating those changes as generated output

### Requirement: Nightly completion includes rolling release synchronization

After a successful main push or a verified main no-op, the publisher SHALL
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

### Requirement: Actions records publication outcomes

Actions step results and logs SHALL be the failure record. The publisher SHALL
write a short step summary identifying the main outcome (the published commit, a
no-op, or the failing stage) and the release outcome (a new revision, a repair
of the served assets at the same revision, unchanged, or failure). A rejected or
erroring push SHALL appear as the failing main stage, and a release failure
SHALL state its reason, with bootstrap guidance when the release is absent,
unowned, malformed, a draft, not a prerelease, or immutable. The build report and structural verification report produced by
the run SHALL be uploaded as artifacts with 14-day retention on success and
failure when they exist. Missing reports after an early failure SHALL NOT imply
verification success. Verification reports SHALL be identified as
structural/offline without live-health claims. The workflow SHALL NOT maintain
failure issues or request issue-write permission. Summary or upload failure SHALL
remain a visible failed step without undoing publication.

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
persist a credential in the repository configuration. Summaries and artifacts SHALL exclude credentials, raw HTTP caches and APK
downloads, and source text SHALL be treated as data rather than executable
input. Documentation SHALL describe token permissions, direct-push prerequisites
and the one-time release bootstrap, without automatic repository-setting changes.

#### Scenario: Setup fails before reports exist

- **WHEN** runtime setup fails before any report is written
- **THEN** Actions shows the failed step and its logs, with no issue write or fabricated verification evidence

#### Scenario: Reused workspace fails before verification

- **WHEN** a workspace contains reports from a prior run and the current build fails before verification
- **THEN** only reports produced by the current run are uploaded

#### Scenario: Release fails after a confirmed push

- **WHEN** release synchronization fails after a successful main push
- **THEN** the workflow fails and its summary shows the pushed commit separately from the release failure

#### Scenario: Reporting fails after publication

- **WHEN** summary generation or artifact upload fails after a successful push
- **THEN** the failing step remains visible and the push is not undone

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

#### Scenario: Push outcome is summarized

- **WHEN** the push of the verified commit succeeds, or is rejected
- **THEN** the summary names the published commit, or the push failure for that commit, on its own line

#### Scenario: Sensitive or executable source text

- **WHEN** upstream diagnostics contain shell syntax or credential values
- **THEN** reporting neither executes that text nor exposes credentials

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
or accept a verification report from another run as authorization. Existing
non-blocking composition warnings SHALL retain their policy. Source-generation
failures SHALL be independent of nightly eligibility.

Verification SHALL use `pack verify` and SHALL make no network requests.
Building SHALL retain upstream JSON network ingestion and read the committed
codm2000 catalog locally, without README fetches or APK package-ID discovery.

#### Scenario: Candidate verifies with warnings

- **WHEN** the build and structural verification succeed with non-blocking build warnings
- **THEN** the candidate is eligible and warnings remain visible without running development CI checks

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

### Requirement: Publish only verified pack outputs and the README catalog

The publisher SHALL limit commits to `dist/single-screen.json`,
`dist/dual-screen.json` and `README.md`. It SHALL reject the run when any other
tracked file is modified, added or deleted, when an allowed file is missing, or
when an allowed file is not a regular file of mode 100644, such as a symbolic
link or a file whose executable bit changed.
Committed source catalogs, reviewed project policy and other configuration SHALL
NOT be published or modified by nightly. README changes SHALL be restricted to
the interior of exactly one valid catalog marker pair; bytes outside it,
including the markers, SHALL match the checked-out main. Changed allowed files
SHALL be published in one commit, and a candidate with no tracked changes SHALL
create no commit. Reports and transient caches SHALL NOT be committed. Before
pushing, the write job SHALL re-check that the handed-off commit changes only
allowed files, and that each changed file has mode 100644 in both the base
revision and the commit, rejecting symbolic links, submodule entries, additions,
deletions and mode changes.

Publication SHALL use a conventional commit identifying the UTC date, run and
base revision, and a normal fast-forward push to main. It SHALL NOT force-push
or alter repository protection settings to bypass a rejection.

#### Scenario: Resolver state or source catalog changes

- **WHEN** a nightly candidate changes a committed source catalog, the reviewed project policy or other configuration
- **THEN** publication is rejected as an out-of-scope tracked mutation

#### Scenario: Successful no-op

- **WHEN** no allowed file differs from the checked-out main
- **THEN** the run records a successful no-op without creating a commit

#### Scenario: Unexpected mutation

- **WHEN** an unrelated tracked file changes or an allowed file is deleted
- **THEN** publication is rejected

#### Scenario: Generated catalog refresh

- **WHEN** verified generated catalog bytes differ from the checked-out main
- **THEN** the README change is published with any changed packs in one commit

#### Scenario: Handwritten README mutation

- **WHEN** a candidate changes README content outside the generated section
- **THEN** publication fails even if structural verification succeeds

#### Scenario: Allowed file becomes a symlink or changes mode

- **WHEN** a candidate or a handed-off commit replaces an allowed file with a symbolic link, or changes an allowed file's mode
- **THEN** publication is rejected before any push or release write, and the release step reads no file through a link

## REMOVED Requirements

### Requirement: Main publication uses one refresh attempt

**Reason**: After a rejected or ambiguous push, the publisher no longer inspects
remote main history to confirm, deny or report uncertainty about publication.
This reverses the earlier choice to keep that check: a visible failure is
enough, because the next run treats a landed commit as a no-op and synchronizes
the release then. "Main publication is one normal push" replaces this
requirement and keeps its no-retry, no-rebuild and no-rebase rules.

**Migration**: None. A run that fails on an ambiguous push may leave the release
one run behind main.
