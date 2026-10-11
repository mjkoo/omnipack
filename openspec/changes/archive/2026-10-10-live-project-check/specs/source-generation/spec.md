# Spec Delta

## ADDED Requirements

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
SHALL reach main only through the owner editing the deny list.

The job SHALL fail visibly when any URL is unreachable or the check cannot run,
and SHALL succeed when every URL answered or was only inconclusive. Because each
run checks main's packs afresh, a project the owner denies, or that answers
again, SHALL stop failing the job on the next run.

#### Scenario: A project disappears

- **WHEN** a pack URL returns HTTP 404
- **THEN** the job fails, its run summary lists that URL with its status, its
  report is retained, and no branch, PR or committed file changes

#### Scenario: Only inconclusive outcomes

- **WHEN** a run finds no unreachable URL but some inconclusive ones
- **THEN** the job succeeds and its run summary lists those URLs with their
  reasons

#### Scenario: The check cannot run

- **WHEN** main's committed packs cannot be read
- **THEN** the job fails, its run summary shows the error, and its report is
  retained

#### Scenario: The owner denies the project

- **WHEN** the owner commits a denial for an unreachable URL and main's rebuilt
  packs no longer contain it
- **THEN** the next run does not request that URL and does not fail on it
