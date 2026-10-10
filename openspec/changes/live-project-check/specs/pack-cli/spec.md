# Spec Delta

## ADDED Requirements

### Requirement: The check-live command reports unreachable projects

The system SHALL provide `pack check-live`. It SHALL request each distinct
project URL in the committed single-screen and dual-screen packs once, sending
no credentials and following redirects. Each request SHALL carry the request
headers the pack entry declares in its `requestHeader` additional setting, and
SHALL carry omnipack's default user agent when the entry declares none; when
several entries share a URL, the first entry in pack order SHALL supply the
headers. A project whose final response has a success (2xx) status SHALL be
reachable and SHALL NOT appear in the report. A project whose final response is
HTTP 404 or 410 SHALL be unreachable. Every other outcome, including any other
error status, a timeout or a connection failure after the request's retries,
SHALL be inconclusive, with a reason that names the cause: the HTTP status when
the last attempt received one, otherwise the failure's own message. An entry
whose `additionalSettings` cannot be decoded to an object, or whose
`requestHeader` setting is malformed, SHALL make its URL inconclusive with a
reason naming the problem. The check
SHALL be the same for every host and SHALL NOT inspect releases, assets or a
project's archive state.

The command SHALL enforce an overall time budget of 20 minutes. It SHALL start
no request once the budget is spent, and SHALL report every URL not yet checked
as inconclusive with the reason "not checked: time budget spent".

Every invocation SHALL write, whole, under `.build/live-check/`, a report and a
run-summary rendering of it, on success and failure alike, replacing any
earlier run's report. The report's status SHALL record whether the check
ran: a run that checked the packs SHALL write a success report, even when a URL
is unreachable and the command exits nonzero, listing each unreachable URL with
its status and each inconclusive URL with its reason, in pack order; a run that
could not check them, such as when the packs cannot be read, SHALL write a
failure report recording the error.
The run-summary rendering SHALL HTML-escape every URL, reason and error inside
a preformatted block. The command SHALL print the unreachable and inconclusive
URLs. It SHALL exit zero when no URL is unreachable, including when some are
inconclusive, and nonzero when any URL is unreachable. It SHALL exit nonzero
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
