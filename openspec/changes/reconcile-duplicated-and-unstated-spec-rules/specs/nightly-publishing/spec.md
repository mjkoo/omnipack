## MODIFIED Requirements

### Requirement: Main publication is one normal push

The publisher SHALL publish with one normal push of the verified commit, whose
parent SHALL be the main revision that the run checked out for building. Before
pushing, the write job SHALL confirm that main is still that revision, and SHALL
otherwise fail without a push or release write. If the push is rejected or
reports an error, the run SHALL fail visibly. It SHALL NOT rebase, cherry-pick
generated output, retry the push, rebuild, or inspect remote history to
reinterpret the push outcome. A later invocation SHALL build and verify its own
checkout, and output that already landed SHALL then be a verified no-op.
What a rerun of an earlier run's write job does once main has moved off the
revision that run checked out, that run's own landed push included, is defined
by "Release writes require an established main outcome" in rolling-pack-release.

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
live-health claims. The workflow SHALL NOT maintain failure issues or request
issue-write permission. Summary or upload failure SHALL remain a visible failed
step and SHALL NOT undo a completed push. A failure in the job that prepares the
candidate, a summary or upload failure there included, SHALL keep that
attempt's write job from running, so the attempt publishes nothing, and a rerun
or a later run SHALL make its own attempt.

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
