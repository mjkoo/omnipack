# Spec Delta

## MODIFIED Requirements

### Requirement: The check-live command reports unreachable projects

The system SHALL provide `pack check-live`. It SHALL request each distinct
project URL in the committed single-screen and dual-screen packs once, following
redirects and sending no credentials. Each request SHALL carry the request
headers the pack entry declares in its `requestHeader` additional setting, and
SHALL carry omnipack's default user agent when the entry declares none; when
several entries share a URL, the first entry in pack order SHALL supply the
headers. A project whose final response has a success (2xx) status SHALL be
reachable and SHALL appear in neither the unreachable nor the inconclusive
list. Reachability and update health are independent outcomes: a reachable
URL SHALL still appear in the stale, archived and health-inconclusive lists
when its health result requires it. A project whose final response is
HTTP 404 or 410 SHALL be unreachable. Every other outcome, including any other
error status, a timeout or a connection failure after the request's retries,
SHALL be inconclusive, with a reason that names the cause: the HTTP status when
the last attempt received one, otherwise the failure's own message. An entry
whose `additionalSettings` cannot be decoded to an object, or whose
`requestHeader` setting is malformed, SHALL make its URL inconclusive with a
reason naming the problem.

For each distinct project URL whose normalized project URL is
`github.com/<owner>/<repo>` and that is not unreachable, the command SHALL also determine the project's update health
from the GitHub API, using the settings of the first entry in pack order at
that URL. The project SHALL be archived when GitHub reports its repository
archived or disabled. A release SHALL qualify when it is not a draft, is not a
prerelease unless the entry sets `includePrereleases`, and either the entry
sets `trackOnly` or the release carries an asset whose name ends, ignoring
case, in `.apk`, `.xapk`, `.apkm` or `.apks`, or in `.zip` when the entry sets
`includeZips`. A release's date SHALL be the latest update time of its assets
when the entry sets `useLatestAssetDateAsReleaseDate` and the release has
assets, and its publication date otherwise. Among the newest 100 releases, the
project SHALL be stale when 180 or more whole days have elapsed between the
newest qualifying release's date and the check, or when no release qualifies. A stale result SHALL
record the qualifying release's tag and date when there is one. Every result
SHALL record the entry's name. URLs on any other host, gitlab.com included,
SHALL get no health lookup and no health result. A health lookup that fails for any reason, including an error status,
a rate limit, a timeout, a malformed response or an entry whose
`additionalSettings` cannot be decoded, SHALL make that URL's health
inconclusive with a reason naming the cause, and SHALL NOT affect its
reachability result.

GitHub API requests SHALL carry the token in the `GITHUB_TOKEN` environment
variable when it is set and non-empty, and SHALL NOT forward it on a redirect.
No other request SHALL carry it or any other credential. When the variable is
unset, the GitHub API requests SHALL be made without credentials.

The command SHALL enforce an overall time budget of 20 minutes. The budget SHALL
cover both the reachability requests and the health lookups. The command
SHALL start no request once the budget is spent. It SHALL report every URL
not yet requested as inconclusive, and every github.com repository URL whose
health lookup had not finished as health-inconclusive, each with the
reason "not checked: time budget spent".

Every invocation SHALL write, whole, under `.build/live-check/`, a report and a
run-summary rendering of it, on success and failure alike, replacing any
earlier run's report. The report's status SHALL record whether the check
ran: a run that checked the packs SHALL write a success report, even when a URL
is unreachable and the command exits nonzero, listing each unreachable URL with
its status, each inconclusive URL with its reason, each stale URL, each
archived URL and each health-inconclusive URL with its reason, in pack order, where an
inconclusive URL whose outcome was an error status the HTTP client does not
retry also records that status and no other inconclusive URL records one; a run that
could not check them, such as when the packs cannot be read, SHALL write a
failure report recording the error.
The run-summary rendering SHALL HTML-escape every URL, name, tag, reason and error inside
a preformatted block. The command SHALL print the unreachable, inconclusive, stale,
archived and health-inconclusive URLs. It SHALL exit zero when no URL is
unreachable, including when some are inconclusive, stale, archived or
health-inconclusive, and nonzero when any URL is unreachable. It SHALL exit nonzero
when the committed packs cannot be read. When the report or its run-summary
rendering cannot be written, the command SHALL exit nonzero with a concise
diagnostic whatever the findings, and SHALL leave neither file partially
written. It SHALL NOT write committed files, pack outputs, git history or PRs,
and SHALL keep no state between invocations.

#### Scenario: Every project answers

- **WHEN** every pack URL returns a success status, one of them after a
  redirect
- **THEN** the command exits zero with a success report listing no unreachable
  and no inconclusive URL

#### Scenario: A project is gone

- **WHEN** one pack URL returns HTTP 404 and another returns HTTP 410
- **THEN** the report lists both as unreachable with their statuses and the
  command exits nonzero

#### Scenario: An outcome is inconclusive

- **WHEN** one pack URL returns HTTP 403, another returns HTTP 429 after its
  retries, a third times out, and no URL is unreachable
- **THEN** the report lists each as inconclusive, the 403 and 429 reasons
  naming their statuses and the timeout's reason naming the timeout, and the
  command exits zero
- **AND** only the 403 entry records a status

#### Scenario: An entry declares request headers

- **WHEN** a pack entry declares `User-Agent: Obtainium/1.0` in its
  `requestHeader` setting and another entry declares no request header
- **THEN** the first URL is requested with that user agent and the second with
  omnipack's default user agent

#### Scenario: A URL appears in both packs

- **WHEN** the same project URL is in both packs and returns HTTP 404
- **THEN** it is requested once and listed once

#### Scenario: The time budget is spent

- **WHEN** the time budget is spent before every URL has been checked
- **THEN** no further request starts, each unchecked URL is listed as
  inconclusive with the reason "not checked: time budget spent", the report is
  written, and the command exits as the findings require

#### Scenario: The packs cannot be read

- **WHEN** a committed pack is missing or malformed
- **THEN** the command writes a failure report recording the error and exits
  nonzero

#### Scenario: The report cannot be written

- **WHEN** the report or its run-summary rendering cannot be written and no
  URL is unreachable
- **THEN** the command exits nonzero with a concise diagnostic and leaves
  neither file partially written

#### Scenario: A project's newest APK release is old

- **WHEN** a GitHub project's newest release carrying an APK asset was
  published 200 days before the check, and a newer release carries only
  desktop archives
- **THEN** the report lists the URL as stale with that release's tag, date and
  the entry's name, and the command's exit status is unchanged

#### Scenario: A recent release is fresh

- **WHEN** a GitHub project's newest release carrying an APK asset was
  published 179 days before the check
- **THEN** the URL is not listed as stale

#### Scenario: Prereleases count only where the entry opts in

- **WHEN** a project's only recent APK release is a prerelease and its older
  stable APK release is 200 days old
- **THEN** the URL is stale for an entry that does not set
  `includePrereleases`, and not stale for one that does

#### Scenario: A track-only entry needs no APK

- **WHEN** a track-only entry's project published a release without assets 10
  days before the check
- **THEN** the URL is not listed as stale

#### Scenario: A rolling release is dated by its assets

- **WHEN** an entry sets `useLatestAssetDateAsReleaseDate` and its project's
  one release was published 400 days before the check, with an APK asset
  updated 5 days before
- **THEN** the URL is not listed as stale

#### Scenario: No release qualifies

- **WHEN** none of a project's newest 100 releases qualifies
- **THEN** the URL is listed as stale with no tag or date

#### Scenario: A repository is archived

- **WHEN** GitHub reports a project's repository archived
- **THEN** the report lists the URL as archived, independently of whether it
  is stale

#### Scenario: A reachable project is archived and stale

- **WHEN** a GitHub project page answers 2xx, GitHub reports its repository
  archived, and its newest release carrying an APK asset was published 200
  days before the check
- **THEN** the report lists the URL as archived and as stale, does not list it
  as unreachable or inconclusive, and the command exits zero

#### Scenario: A health lookup fails

- **WHEN** the GitHub API answers a project's release lookup with HTTP 403 for
  a spent rate limit, and the project page answers 2xx
- **THEN** the report lists the URL as health-inconclusive with a reason
  naming the status, does not list it as stale, archived, unreachable or
  inconclusive, and the command exits zero

#### Scenario: A gone project gets no health lookup

- **WHEN** a GitHub project URL answers HTTP 404
- **THEN** it is listed as unreachable and receives no health lookup or health
  result

#### Scenario: Other hosts get no health lookup

- **WHEN** a pack entry's URL is on a host other than github.com
- **THEN** no health lookup is made for it and it has no health result

#### Scenario: A gitlab.com project gets no health lookup

- **WHEN** a pack entry's URL is a gitlab.com project that answers 2xx and
  whose releases link their APKs only from the release description, leaving
  the release asset links empty
- **THEN** no health lookup is made for it, and it is listed as neither stale,
  archived nor health-inconclusive

#### Scenario: The GitHub token reaches only the GitHub API

- **WHEN** `GITHUB_TOKEN` is set and the check requests a GitHub project page,
  a GitHub API endpoint that redirects, and a gitlab.com project page
- **THEN** only the first GitHub API request carries the token
