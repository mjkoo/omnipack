# Spec Delta

## MODIFIED Requirements

### Requirement: Catalog changes are checked before PR publication

Before pushing a source's source-update branch, creating a PR or editing a PR's
body, the source-maintenance workflow's read-only job SHALL validate that
source's candidate catalog's shape, IDs and deterministic rendering, run the
project's full test suite with the candidate catalog in place, and build and
structurally verify both pack variants with the candidate catalog and main's
configuration. Any failure, including stale selectors and repeated entry ids,
SHALL block those writes. When a successful generation reproduces main's
committed catalog for that source, closing an open PR from that source's
source-update branch SHALL be the only permitted branch or PR write, and it
SHALL require no tests, build or verification; the alert job's issue
reconciliation SHALL still be permitted, as maintenance-alerts requires. Generated pack outputs and the pack README SHALL
serve only this run's checks and SHALL NOT be part of the proposal. The proposed catalog
SHALL be byte-identical to the checked candidate: the read-only job SHALL commit
the candidate before the checks and confirm afterwards that the workspace
catalog still matches that commit, and the write job SHALL push only that exact
commit, identified by its SHA, after confirming that its parent is the
checked-out main revision and that it changes only that source's committed
catalog, which SHALL be a regular file of mode 100644 in both the base revision
and the commit. A source's run SHALL NOT stage or publish another source's
catalog. The read-only job SHALL likewise reject a generated candidate or a
workspace catalog that is not a regular file. Diagnostics SHALL identify the
base revision, the catalog's added, removed and changed entries, skipped
listings and pack validation outcome; the PR body and the run summary SHALL
each show the added, removed and changed entries within the size GitHub
accepts, counting any listed lines beyond that bound, whether entries,
skipped listings or notes, only as "and N more",
and SHALL note a catalog whose bytes change with no entry change as such. The base revision SHALL appear in the PR body and in the run summary of
a run whose staging succeeds; a run whose staging fails SHALL summarize that
staging failed and its reason instead. The pack validation outcome SHALL be the
reported results of the run's test, build and verification steps.

#### Scenario: Candidate changes a pinned identity

- **WHEN** the proposed catalog makes an active composition selector stale
- **THEN** validation fails and the workflow does not publish the invalid source proposal

#### Scenario: Test suite fails with the candidate

- **WHEN** the full test suite fails with the candidate catalog in place
- **THEN** no branch or PR write occurs and the run fails visibly

#### Scenario: Candidate is valid

- **WHEN** the tests, source checks and composed-pack verification pass
- **THEN** only the checked source catalog is eligible for the proposal commit

#### Scenario: Bytes change after checking

- **WHEN** the workspace catalog no longer matches the checked commit after the checks ran
- **THEN** the read-only job fails before handing the commit off, and no branch or PR write occurs

#### Scenario: Handed-off commit is not the checked commit

- **WHEN** the commit the write job receives differs from the checked SHA, its parent is not the checked-out main revision, or it changes a file other than that source's catalog
- **THEN** the run fails before any branch push or PR write

#### Scenario: A source's commit touches another source's catalog

- **WHEN** the commit handed off in one source's run changes another supported source's committed catalog
- **THEN** the run fails before any branch push or PR write

#### Scenario: Catalog is replaced by a symlink or changes mode

- **WHEN** the generated candidate or the handed-off commit makes the source catalog a symbolic link, or changes its mode
- **THEN** the run fails before any branch push or PR write

### Requirement: One separate workflow maintains source update proposals

A daily scheduled workflow and manual dispatch SHALL operate from main in the
canonical repository, independently of nightly publication. The supported
sources are codm, whose source-update branch is `automation/codm-catalog`, and
Quiver, whose source-update branch is `automation/quiver-catalog`. Each
supported source SHALL have its own dedicated source-update branch, committed
catalog path and serialization group, and every rule below applies to each
source separately. A source's runs SHALL be serialized within its own group
without canceling active runs and SHALL NOT wait on another source's runs; runs
SHALL have a bounded runtime. Ineligible refs and forks SHALL perform no remote
writes.

When a source's checked candidate differs from main's committed catalog for that
source, the workflow SHALL rebuild that source's source-update branch from the
main revision that triggered the run as a single commit containing only the
candidate catalog, replace the branch's previous contents, and create or update
the one open PR from that branch to main. A source's source-update PR SHALL be
an open PR whose head is that source's branch in the canonical repository and
whose base is main. A PR from another repository whose branch has the same name
SHALL be neither edited nor closed. If more than one source-update PR is open
for one source, that source's run SHALL fail before any branch or PR write,
and the alert job SHALL still report that failure; open PRs
of other sources SHALL NOT count. Content equality SHALL be judged on the
branch's whole tree: a branch whose tree equals the rebuilt proposal's tree
SHALL be left as it is, even when its commits differ from the rebuilt commit,
and SHALL NOT be pushed again. Commits added to that branch by hand SHALL be
overwritten by the next push. When the candidate equals main's committed catalog
for that source, the workflow SHALL make no proposal and SHALL close an open
source-update PR of that source only, without running the tests, build or
verification. Upstream edits that leave the generated catalog unchanged SHALL
NOT produce a proposal. No automatic merge, direct-main
write or release write SHALL be introduced. A source's failures SHALL be raised
as findings as maintenance-alerts requires.

Each invocation SHALL make one generation and check attempt per source. A failed
branch or PR write SHALL fail that source's run visibly, and the next run SHALL
rebuild the branch and update the existing PR rather than open another. Before
any branch push, PR creation, PR edit or PR close, the write job SHALL confirm
that main is still the run's base revision. If main has advanced, the run SHALL
fail visibly without those writes, so a rerun of an earlier run cannot close or
replace a newer proposal, and a later run SHALL rebuild the proposal on the
newer main. Main advancing after that confirmation SHALL NOT be fenced: the PR
SHALL show as stale or conflicting until a later run rebuilds it.

#### Scenario: Candidate matches main

- **WHEN** a successful generation produces the committed catalog and main is still the run's base revision
- **THEN** no tests, build or verification are required, and no branch push, PR creation or PR edit occurs
- **AND** any open PR from that source's source-update branch is closed, which is the only branch or PR write the run makes, and the alert job still reconciles that source's issues

#### Scenario: Existing PR has the same candidate

- **WHEN** the rebuilt proposal's tree equals the tree already on the source-update branch, whatever commits produced that tree
- **THEN** no push occurs, the branch is left as it is, and no duplicate PR is created

#### Scenario: README changes again before merge

- **WHEN** a later checked candidate differs from the open proposal
- **THEN** the workflow rebuilds the branch and updates that PR instead of opening another

#### Scenario: Main advances during checking

- **WHEN** main gains a commit after the run's checkout and before the write job's first write
- **THEN** the run fails visibly without a branch push or any PR write, and a later run rebuilds the proposal on the newer main

#### Scenario: Branch ownership is unexpected

- **WHEN** someone pushes a commit to the source-update branch, a later run has a changed candidate, and the branch's tree differs from the rebuilt proposal's tree
- **THEN** the rebuilt branch replaces that commit

#### Scenario: A fork PR shares the branch name

- **WHEN** an open PR from another repository uses a source-update branch name
- **THEN** the workflow neither edits nor closes it, and a changed candidate gets its own PR from the canonical repository's branch

#### Scenario: Write job rerun after main advanced

- **WHEN** the write job of an earlier run is rerun after main has advanced past that run's base revision
- **THEN** it fails visibly without a branch push or any PR write, so a newer proposal is neither closed nor replaced by the earlier catalog

#### Scenario: Sources keep separate proposals

- **WHEN** codm and Quiver each have a changed candidate, or one source's catalog is unchanged while the other's changed
- **THEN** each source's run updates only its own branch and PR, neither closes nor counts the other source's PR, and neither run waits on the other's serialization group

### Requirement: Source maintenance keeps its credential and source text scoped

The workflow SHALL grant no permissions at workflow level and SHALL perform no
release operations. Its issue operations SHALL be only those of its alert job,
as maintenance-alerts requires. Its read-only job SHALL run generation, staging,
tests, building and verification; every step of that job, including checkout
and runtime setup, SHALL run with a job token limited to reading repository
contents, and none SHALL receive the write credential. The write credential
SHALL be available only to the write job, which alone SHALL hold the contents
and pull-request write access needed for its source's source-update branch and
PR. The write job SHALL install no project dependencies and run no generation,
tests, build or verification: it SHALL check out afresh the main revision that
triggered the run, receive from the read-only job only the checked commit, as
git objects, and the escaped PR body, and run only a publication script that
needs no project dependency and no dependency installation step, with repository
hooks disabled on every git command. The triggering
event SHALL fix the revision whose code the write job runs: no output of the
read-only job SHALL select it, and the write job SHALL fail before any write
unless the base revision the read-only job reports is that triggering revision.
Outputs of the read-only job SHALL reach the publication script only through
step environment variables, never interpolated into a command, and the script
SHALL reject any commit identifier that is not a full 40-character hexadecimal
SHA. No checkout SHALL persist a credential in the
repository configuration. Source text SHALL be handled as data:
upstream-derived text in the run summary and the PR body SHALL be HTML-escaped
inside a preformatted block, so it renders as literal text rather than markup.
Credentials and raw HTTP caches SHALL be excluded from
summaries and artifacts. Each source's current generation report SHALL be
retained as an artifact under a name distinct from other sources' for 14 days on
success and failure when available, and the run summary SHALL list the
catalog's added, removed and changed entries and the skipped listings. Missing reports after early failure SHALL NOT
imply successful validation. Actions SHALL expose failed generation, test,
validation and PR-operation stages for each source.

Checks SHALL execute within the source-maintenance workflow, without relying on
PR events to run them. Each PR body SHALL link the workflow run that checked its
current content and SHALL be refreshed whenever the branch is updated.
Documentation SHALL explain that PRs opened by the workflow do not trigger the
project's PR checks, how a maintainer can run them when repository rules
require them, and the token and PR-creation prerequisites, without
automatically changing repository settings.

#### Scenario: PR event does not run checks automatically

- **WHEN** a proposal is opened or updated
- **THEN** its body links the run whose test, build and verification results cover its content, and no automatic merge occurs

#### Scenario: Skipped listings are visible

- **WHEN** a Quiver row names a forge generation cannot form a URL for, or a
  new listed project is screened out for publishing no APK asset
- **THEN** the run summary lists that row or project with its reason

#### Scenario: Checks run without the write credential

- **WHEN** generation, staging, tests, building and verification run
- **THEN** they run in the read-only job, whose token can only read repository contents, and the write credential is not present in their environment
- **AND** no checkout has persisted a credential in the repository configuration

#### Scenario: Check job names another revision

- **WHEN** the read-only job's outputs name a base other than the triggering revision, or a commit identifier that is not a full SHA
- **THEN** the write job fails before any branch push or PR write, having run only code from the triggering revision

#### Scenario: Discovery is unavailable

- **WHEN** a source's discovery fails
- **THEN** Actions reports failure while that source's committed catalog remains available to nightly

### Requirement: The daily source catalog workflow checks that pack projects answer

The daily scheduled source catalog workflow SHALL run `pack check-live` against
main's committed packs, in the canonical repository only, in a job of its own
whose token can only read repository contents, with no write credential and no
checkout that persists a credential. Its runs SHALL be serialized in their own
group without canceling active runs and SHALL NOT wait on a source's runs. The
job's timeout SHALL be 30 minutes, above the command's own time budget, so the
command's report is written before the job is stopped. The job SHALL retain the
command's report as an artifact for 14 days whenever the report exists, and its
run summary SHALL show the unreachable and inconclusive URLs with their
reasons, or the error on a failed check, HTML-escaped inside a preformatted
block. The job SHALL change no branch, PR or committed file. A deny record
SHALL reach main only through the owner editing the deny list. A live check
that cannot run, and each URL that is unreachable or ends in a non-retried
error status, SHALL be raised as a finding as maintenance-alerts requires, by
an alert job of the live check's own that is serialized without canceling
active runs and does not wait on a source's runs.

The job SHALL fail visibly when any URL is unreachable or the check cannot run,
and SHALL succeed when every URL answered or was only inconclusive. Because each
run checks main's packs afresh, a project the owner denies, or that answers
again, SHALL stop failing the job on the next run.

#### Scenario: A project disappears

- **WHEN** a pack URL returns HTTP 404
- **THEN** the job fails, its run summary lists that URL with its status, its
  report is retained, a finding is raised for that URL, and no branch, PR or
  committed file changes

#### Scenario: Only inconclusive outcomes

- **WHEN** a run finds no unreachable URL but some inconclusive ones
- **THEN** the job succeeds and its run summary lists those URLs with their
  reasons
- **AND** a finding is raised only for each URL whose outcome was a
  non-retried error status

#### Scenario: The check cannot run

- **WHEN** main's committed packs cannot be read
- **THEN** the job fails, its run summary shows the error, its report is
  retained, and a finding is raised for the check that could not run

#### Scenario: The owner denies the project

- **WHEN** the owner commits a denial for an unreachable URL and main's rebuilt
  packs no longer contain it
- **THEN** the next run does not request that URL, does not fail on it, and
  closes that URL's issue as completed
