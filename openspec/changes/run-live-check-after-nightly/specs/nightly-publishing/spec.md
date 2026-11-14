# Spec Delta

## ADDED Requirements

### Requirement: A live check runs after each nightly publish

The live check SHALL start when each nightly publishing run completes, whatever
that run's outcome, and on manual dispatch. It SHALL run `pack check-live`
against the committed packs of the main commit current when it is triggered, in
the canonical repository only.

#### Scenario: A nightly publishes a fix

- **WHEN** the owner merges a denial for an unreachable URL and the next
  nightly publishing run commits packs without it
- **THEN** a live check starts when that nightly run completes, reads the packs
  that run committed, and closes that URL's issue as completed

#### Scenario: A nightly run fails

- **WHEN** a nightly publishing run completes with a failure and commits no
  packs
- **THEN** a live check still starts and checks the packs already on main

### Requirement: The live check job holds only read access

The live check SHALL run in a job of its own whose token can only read
repository contents, with no write credential and no checkout that persists a
credential. Its runs SHALL be serialized in their own group without
canceling active runs. Its timeout SHALL be 30 minutes, above the
command's own time budget, so the command's report is written before the job is
stopped. It SHALL change no branch, PR or committed file. A deny record
SHALL reach main only through the owner editing the deny list.

#### Scenario: A live check is triggered while another runs

- **WHEN** a live check is triggered while an earlier live check is running
- **THEN** the earlier run is not cancelled

### Requirement: The live check reports its outcome in the run

The live check job SHALL retain the command's report as an artifact for 14 days
whenever the report exists, and its run summary SHALL show the unreachable and
inconclusive URLs with their reasons, the stale and archived URLs, and the
health-inconclusive URLs with their reasons, or the error on a failed check,
HTML-escaped inside a preformatted block.

#### Scenario: A project disappears

- **WHEN** a pack URL returns HTTP 404
- **THEN** the job fails, its run summary lists that URL with its status, its
  report is retained, a finding is raised for that URL, and no branch, PR or
  committed file changes

#### Scenario: The check cannot run

- **WHEN** main's committed packs cannot be read
- **THEN** the job fails, its run summary shows the error, its report is
  retained, and a finding is raised for the check that could not run

### Requirement: The live check's verdict follows reachability, not health

The live check job SHALL fail visibly when any URL is unreachable or the check
cannot run, and SHALL succeed when every URL answered or was only inconclusive,
whatever its health result.

#### Scenario: Only inconclusive outcomes

- **WHEN** a run finds no unreachable URL but some inconclusive ones
- **THEN** the job succeeds and its run summary lists those URLs with their
  reasons
- **AND** a reachability finding is raised only for each URL whose outcome
  was a non-retried error status, and stale and archived findings follow each
  URL's health result

### Requirement: The live check raises findings through its own alert job

A live check that cannot run, each URL that is unreachable or ends in a
non-retried error status, and each URL reported stale or archived, SHALL be
raised as a finding as maintenance-alerts requires, by an alert job of the live
check's own that is serialized without canceling active runs. Because each run
checks main's packs afresh, a project the owner denies, or that answers again,
SHALL stop failing the job on the next run.

#### Scenario: The owner denies the project

- **WHEN** the owner commits a denial for an unreachable URL and main's rebuilt
  packs no longer contain it
- **THEN** the next run does not request that URL, does not fail on it, and
  closes that URL's issue as completed
