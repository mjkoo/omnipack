# Spec Delta

## MODIFIED Requirements

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
variant, the package id and each entry's family and project URL. No release archive target's outcome SHALL raise a finding,
whatever that outcome is; per-target outcomes stay in the run report. A stale or
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
