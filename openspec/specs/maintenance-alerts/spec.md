# maintenance-alerts Specification

## Purpose

Puts every actionable problem found by omnipack's unattended scheduled
workflows in front of the owner as a GitHub issue that tracks the problem
until a later run no longer sees it, since failed-run notifications do not
reach the owner.

## Requirements

### Requirement: Unattended problems raise findings

The scheduled nightly publishing, source catalog and release archive workflows
SHALL raise a finding for each of these problems, and for no other outcome:

- a nightly preparation stage that fails, one finding per stage;
- a nightly push or release synchronization that fails;
- a source's generation, staging, test, build, verification or catalog guard
  step that fails, one finding per source and step;
- a source's publication that fails;
- a live check that cannot read the committed packs;
- a pack URL whose live check ends in HTTP 404 or 410, one finding per URL,
  and a pack URL whose live check ends in any other error status the HTTP
  client does not retry, a separate finding per URL;
- a pack URL the live check reports stale, and a pack URL it reports
  archived, a separate finding per URL for each;
- each family the build report lists as uncategorized, each stale denial and
  each stale category assignment, one finding per item;
- each patch key that changes nothing in an overlay record the build report
  lists, one finding per record and key, the key identified by its dotted
  path, which names one patch location because patch keys contain no `.`;
  because patch keys also contain no `/`, distinct URL and key pairs give
  distinct finding subjects, the alert-key shortening that cuts a subject
  over the key length limit and appends a digest keeps them distinct, each
  finding's details carry the full `URL:` and `Key:`, and a later dead key in
  the same record raises its own finding;
- each project URL at which the build report lists one or more extras as
  listed by a catalog, one finding per URL covering every such extra there;
- each package id the build report lists as repeated within a variant, one
  finding per variant and package id;
- a release archive run that cannot read the committed packs or reach its
  bucket;
- a producing job whose findings do not reach the alert job intact, that
  fails for a reason none of its other findings reports, or that is cancelled,
  one finding per job, so a job stopped by its time limit raises this finding
  whether its result reads cancelled or failed.

A nightly push or release synchronization, or a source publication, refused
because `main` advanced past the run's base revision SHALL raise no finding. Skipped listings SHALL raise no finding, and live-check reachability
outcomes that end in a retried status, a timeout, a connection failure or the
time budget running out SHALL raise no reachability finding. A URL's reachability outcome and
its health outcome, as `pack check-live` defines them, SHALL be mapped to
findings independently. A health-inconclusive result SHALL raise no stale or
archived finding and SHALL NOT suppress that URL's reachability findings. An
inconclusive reachability outcome SHALL raise no reachability finding other
than the finding for an error status the HTTP client does not retry, and SHALL
NOT suppress that URL's conclusive stale or archived findings. A
stale or archived finding's details SHALL name the URL and the entry, and a
stale finding's details SHALL give the qualifying release's tag and date or
say that no release qualified. A finding for a patch key
that changes nothing SHALL name the project URL and that key, and a finding
for the extras a catalog lists at a project URL SHALL name the project URL
and, for each such extra, its package id, each listing source and that
source's differing fields. A finding for a repeated package id SHALL name the
variant, the package id and each entry's family and project URL. No release
archive target's outcome SHALL raise a finding, whatever that outcome is;
per-target outcomes stay in the run report. A stale or
archived finding SHALL NOT be
accounted as the live-check job's failure. Each finding SHALL have a key that
stays the same while the same problem persists, independent of the problem's
error text, and each key SHALL belong to exactly one producing job, so the
same job run for two sources owns two distinct sets of keys. A key SHALL be
spelled only from characters the alert job accepts, whatever characters the
URL, family or stage name it is derived from contains. Raising findings SHALL
NOT change whether any job succeeds or fails, including when raising or
uploading them fails.

#### Scenario: A source's candidate fails verification

- **WHEN** a codm candidate fails pack verification
- **THEN** a finding for codm's verification step is raised, no source PR is
  written, and the job fails as it does today

#### Scenario: Main advanced during publication

- **WHEN** a nightly push or release synchronization is refused because main
  advanced past the run's base
- **THEN** no finding is raised for the refused push or release

#### Scenario: Live check outcomes

- **WHEN** one pack URL answers 404, another 403, another 429 after retries,
  and another times out
- **THEN** reachability findings are raised for the 404 and 403 URLs only

#### Scenario: Build warnings

- **WHEN** a nightly build report lists two uncategorized families and one
  stale denial
- **THEN** three findings are raised, one per item, and the nightly run's
  verdict is unchanged

#### Scenario: A producer dies early

- **WHEN** a producing job fails before reporting its findings
- **THEN** one finding names that job as having failed without findings

#### Scenario: A producer fails outside its reported stages

- **WHEN** a producing job's runtime setup, base guard or artifact upload
  fails, and the job still reports a findings file with no other finding
- **THEN** one finding names that job as having failed
- **AND** a job that succeeds with an empty findings file raises nothing

#### Scenario: A producer times out

- **WHEN** a producing job is stopped because it exceeds its time limit,
  whether its result reads cancelled or failed
- **THEN** one finding names that job as having failed without findings, and
  no other finding or re-check comes from that job's run

#### Scenario: Raising findings fails

- **WHEN** a producing job's findings cannot be written or uploaded
- **THEN** the job's verdict, and whether any job that depends on it runs, is
  as it would be without alerting, and one finding names that job as having
  failed without findings

#### Scenario: Subjects carry unusual characters

- **WHEN** a finding's subject is a URL with a query string or a stage name
  containing spaces
- **THEN** its key is accepted, the same subject maps to the same issue on
  every run, and the producer's other findings are kept

#### Scenario: Two sources report the same step

- **WHEN** codm and Quiver run in the same workflow run and only codm's check
  job fails early
- **THEN** only codm's early-failure finding is raised, and Quiver's
  reconciliation leaves codm's issue alone

#### Scenario: Health findings

- **WHEN** a live check reports one URL stale, another archived, and a third
  health-inconclusive
- **THEN** a stale finding is raised for the first and an archived finding for
  the second, no stale or archived finding is raised for the third, and the
  live-check job's verdict is unchanged
- **AND** each URL's reachability findings are raised or not by its
  reachability outcome alone

#### Scenario: A blocked page with a rate-limited health lookup

- **WHEN** a URL's project page answers HTTP 403, its health lookup is rate
  limited, and it has an open stale issue and an open archived issue
- **THEN** the HTTP 403 finding is raised, and its stale and archived issues
  are left open and unchanged

#### Scenario: Overrides that change nothing

- **WHEN** a nightly build report lists one overlay record with two keys that
  change nothing and one extra a catalog lists
- **THEN** three findings are raised: one per key, each naming the record's
  project URL and its key, and one for the extra's project URL naming the
  extra's package id, the listing source and its differing fields, and the
  nightly run's verdict is unchanged

#### Scenario: A muted dead key and a later one

- **WHEN** a patch key's finding was closed as not planned and a later build
  report lists another key of the same overlay record as changing nothing
- **THEN** a separate finding is raised for the new key, and the muted key's
  issue stays closed

#### Scenario: Two listed extras at one project URL

- **WHEN** a nightly build report lists two extras a catalog lists at one
  project URL, each with its own package id
- **THEN** one finding is raised for that URL, naming both package ids, each
  extra's listing sources and their differing fields

#### Scenario: A pack repeats a package id

- **WHEN** a nightly build report lists package id `p` as repeated in single and
  in dual
- **THEN** two findings are raised, one per variant, each naming `p` and the
  entries' families and project URLs, and the nightly run's verdict is
  unchanged

#### Scenario: Release archive outcomes

- **WHEN** a release archive run reports one target failed, one unreachable and
  one not checked
- **THEN** no finding is raised for any of those targets, the outcomes stay in
  the run report, and the run's verdict is unchanged

### Requirement: Each finding has one issue that follows its latest re-check

Each finding SHALL have one GitHub issue labelled `omnipack-alert` that
identifies the finding's key on the first line of its body; an issue SHALL be
taken to identify a key only when that first line is exactly one key
identifier, whatever its later lines contain. When a run raises a finding with no issue, an
issue SHALL be opened. When an open issue's finding is raised again, the issue
SHALL be updated with the latest details, and the issue SHALL be left
unedited when its title and details are unchanged; a different run raising
the same details SHALL NOT count as a change. When a run re-checks a finding's key and does not raise it, that
finding's open issue SHALL be closed as completed.

A run SHALL NOT close an issue for a key it did not re-check. A key is
re-checked only when the stage or step it names actually ran: for nightly
preparation, the stages preparation reports having run, so a run with nothing
to publish re-checks neither the commit nor the bundle stage, and a failure
before the checkout stage does not re-check checkout; for a source's
steps, those that succeeded or failed; for publication, a push or publish
that was attempted and not refused because main advanced. A skipped step, or
a stage after the failing one, is not re-checked. A source's test, build,
verification and catalog guard steps SHALL count as re-checked when they were
skipped only because generation and staging succeeded with a candidate equal
to main's catalog. A producing job's early-failure key SHALL count as
re-checked whenever that job ran, including when it was cancelled; a
cancelled job SHALL re-check no other key. A live check that read the packs SHALL count
as re-checking every unreachable and error-status URL key except those of URLs the time budget
left unchecked and of inconclusive URLs that recorded no status, such as a
retried status after retries, a timeout or a connection failure, so the issue
of a URL no longer in the packs is closed. A live check that read the packs
SHALL count as re-checking every stale and archived key except those of a
health-inconclusive URL, an unreachable URL and a URL the time budget left
unchecked, so the health issues of a URL no longer in the packs are closed. A build SHALL count as re-checking
the build-warning keys only when its report records success; a failed
build's report SHALL still raise the warnings it lists but SHALL close no
build-warning issue. A release archive run whose archive step ran and wrote a
readable report SHALL count as re-checking its run-level key.

An issue the owner closed as not planned SHALL stay closed while its finding
persists. A mute SHALL last one occurrence: when a run re-checks a muted key
and does not raise it, the issue SHALL be marked closed as completed with a
comment naming that run, so that a later recurrence reopens it; a run that did
not re-check the key SHALL leave the mute in place. An issue closed as
completed whose finding is raised again SHALL be reopened. Issues carrying the
label but identifying no valid key SHALL be left alone.

#### Scenario: A finding appears and clears

- **WHEN** a run raises a finding and a later run re-checks it without raising
  it
- **THEN** the first run opens an issue and the later run closes it as
  completed

#### Scenario: A finding persists with new details

- **WHEN** consecutive runs raise the same finding with a different error
  message
- **THEN** the same issue is updated rather than a second issue opened

#### Scenario: The owner mutes a finding

- **WHEN** the owner closes an issue as not planned and later runs still raise
  its finding
- **THEN** the issue stays closed

#### Scenario: A muted finding clears and recurs

- **WHEN** the owner closes an issue as not planned, a later run re-checks its
  key without raising it, and a run after that raises it again
- **THEN** the run that saw it clear marks the issue closed as completed with
  a comment naming that run, and the run that sees it again reopens it

#### Scenario: A mute survives a run that did not re-check

- **WHEN** the owner closes an issue as not planned and a later run does not
  re-check its key, as when its URL was left unchecked by the time budget
- **THEN** the issue stays closed as not planned

#### Scenario: A muted error status becomes unreachable

- **WHEN** the owner mutes a URL's HTTP 403 issue and the URL later answers
  HTTP 404
- **THEN** a separate issue for the URL's unreachability is opened

#### Scenario: The owner closes a finding that is not fixed

- **WHEN** the owner closes an issue as completed and the next run still
  raises its finding
- **THEN** the issue is reopened

#### Scenario: A URL leaves the packs

- **WHEN** a URL with an open issue is denied and main's rebuilt packs no
  longer contain it
- **THEN** the next live check closes that URL's issue as completed

#### Scenario: A URL with health issues leaves the packs

- **WHEN** a URL has an open stale issue and a muted archived issue, and it is
  denied so that main's rebuilt packs no longer contain it
- **THEN** the next live check closes the stale issue as completed, and marks
  the archived issue closed as completed with a comment naming that run

#### Scenario: A key is not re-checked

- **WHEN** an open issue's key was not re-checked by a run, as when
  preparation failed before the release step
- **THEN** the issue is left open and unchanged

#### Scenario: An earlier step fails

- **WHEN** a source's verification issue is open and that source's generation
  fails the next day, or a nightly stage issue is open for a stage after the
  one that fails
- **THEN** the later step's or stage's issue is left open and unchanged

#### Scenario: A persisting finding in a later run

- **WHEN** consecutive runs raise the same finding with the same details
- **THEN** the later run leaves the issue unedited

#### Scenario: A nightly run has nothing to publish

- **WHEN** a nightly commit or bundle stage issue is open and the next
  preparation succeeds with nothing to commit, so neither stage runs
- **THEN** that issue is left open and unchanged

#### Scenario: Preparation fails before checkout

- **WHEN** a nightly checkout stage issue is open and the next preparation
  fails while removing reports left by an earlier run, before checkout runs
- **THEN** the checkout issue is left open and unchanged

#### Scenario: A release publishes a new revision

- **WHEN** a nightly release issue is open and the next release publishes a
  new revision
- **THEN** the release issue is closed as completed

#### Scenario: An inconclusive outcome does not clear an error status

- **WHEN** a URL's HTTP 403 issue is open and the next live check times out
  on that URL or receives HTTP 429 after retries
- **THEN** the issue is left open and unchanged

#### Scenario: A build fails before checking categories

- **WHEN** an uncategorized-family issue is open and the next nightly build
  fails before category assignment, writing a failed report with empty
  warning lists
- **THEN** the issue is left open and unchanged

#### Scenario: A dormant project the owner accepts

- **WHEN** the owner closes a stale issue as not planned, later live checks
  still report the URL stale, and then the project publishes a qualifying
  release
- **THEN** the issue stays closed while the URL is stale, and the first live
  check after the release marks it closed as completed with a comment naming
  that run

#### Scenario: A failed health lookup does not clear a health issue

- **WHEN** a URL's stale issue is open and the next live check's health lookup
  for it is rate limited
- **THEN** the issue is left open and unchanged

### Requirement: Alerting holds only issue access and treats findings as data

Jobs that read upstream-derived data and raise findings SHALL gain no new
permission. A calling job that grants a reusable workflow issue write access
only so the called alert job can hold it is not a producing job; the
producing jobs it calls SHALL still declare their own permissions without
issue write access. Only a separate alert job SHALL write issues, holding issue write
access and no other permission, running even when the producing jobs fail,
and only in the canonical repository on `main`, including when a producing job
uploaded no findings. The alert job SHALL install
no project dependency, persist no credential, and receive producer results
only through step environment variables, never interpolated into a command.
It SHALL reject a producer's findings whose keys are not owned by that
producer, whose titles exceed GitHub's title limit, or whose fields are
malformed, raise that producer's early-failure finding instead, and change no
other issue for that producer; details SHALL NOT be rejected for their length.
Producers SHALL report a finding's details as raw text, and
the alert job SHALL itself HTML-escape them inside a preformatted block, so an
issue carries no markup a producer wrote; upstream-derived text in an issue
body SHALL be HTML-escaped inside a preformatted block and fit GitHub's issue body limit, counting lines
beyond it as "and N more"; an issue title is plain text and carries the
subject unencoded. A failed alert job SHALL fail visibly; it is the
one failure no issue reports, and documentation SHALL say so.

#### Scenario: Findings carry markup

- **WHEN** a finding's details contain HTML or a sequence that would end the
  issue's key identifier
- **THEN** the details render as literal text and the key is rejected or
  escaped so the issue still identifies its finding

#### Scenario: Details name another finding's key

- **WHEN** a finding's details contain another finding's key identifier
- **THEN** the issue identifies only its own finding, and the other finding's
  issue is unaffected

#### Scenario: Details exceed the issue body limit

- **WHEN** a finding's raw details are longer than GitHub's issue body limit
- **THEN** its issue carries the details that fit, counting the rest as "and
  N more", and no early-failure finding is raised for its producer

#### Scenario: A producer reports a key it does not own

- **WHEN** the live check reports a key belonging to nightly
- **THEN** the alert job rejects those findings, raises the live check's
  early-failure finding, and changes no other issue

#### Scenario: Producing jobs keep their permissions

- **WHEN** generation, checks, builds and the live check run
- **THEN** their jobs hold no issue write access, and the alert job holds no
  contents or pull-request write access
