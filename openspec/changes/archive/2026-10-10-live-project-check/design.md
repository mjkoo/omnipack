# Design

## Context

`source-catalog.yml` is the daily scheduled workflow that calls the reusable
`source-maintenance.yml` once per generated source; each call has its own
concurrency group. `omnipack.http.HttpClient` already sends uncredentialed
GETs, follows redirects, retries 408/425/429/5xx and connection failures, and
raises `HttpStatusError` with the status for any other error status. Its
defaults are a 30-second timeout and 2 retries with 0.5 s and 1 s backoff, and
it sends only its own `User-Agent` header.

Obtainium's HTML source has a per-app `requestHeader` additional setting: a
list of `{"requestHeader": "Name: value"}` lines in the entry's
`additionalSettings`, which Obtainium sends with its requests. In the committed
packs each entry's `additionalSettings` is a JSON-encoded string, not an
object, so the setting is read only after decoding that string.
dolphin-emu.org answers 403 to every client, a browser user agent included,
except the `User-Agent: Obtainium/1.0` its pack entry declares; for that header
it redirects to an `/update/obtainium` page carrying the APK link. Several
HTML-source entries declare that header.

A deny record cannot be staged automatically. The committed `dist/` packs are
checked against `config/deny.json`: `pack verify` and the committed-pair test
report a pack entry at a denied URL as an error, an overlay record whose
target is pruned is a stale-overlay error, and a composition pin on a denied
candidate fails the build. Denying a URL that is still in the packs therefore
needs the deny record, any overlay record or pin for that URL, and rebuilt
packs to land together, which is the owner's hand edit, not a generated
proposal.

## Goals / Non-Goals

**Goals:**

- Detect a deleted or private project with one request per pack URL on hosts
  that answer a missing project with 404 or 410.
- Put the finding in front of the owner daily without writing anything.

**Non-Goals:**

- Proposing, staging or publishing deny records. The owner denies by hand.
- Release, asset, APK-filter, version or archive checks.
- Treating 451 or any status other than 404 and 410 as gone. A later change
  can widen the set if the owner rules on it.

## Decisions

**The command writes only a report, not a candidate deny list.** No PR
consumes a candidate, and a hand denial also has to remove overlay records or
pins and rebuild the packs, so a candidate file would cover only part of the
edit. The report under `.build/live-check/` lists unreachable URLs with their
statuses and inconclusive URLs with their reasons; the owner writes the deny
record, with a reason of their choosing, from it. The command also writes the
same findings as an escaped Markdown summary so the workflow can append it to
the run summary without its own rendering code.

**The command exits nonzero when a project is unreachable.** Like
`pack verify`, its exit status is the verdict, so the scheduled job fails with
no extra step and GitHub's failed-run notification reaches the owner. An
inconclusive outcome alone exits zero: it is not evidence the project is gone,
and failing on a transient 429 or 5xx would train the owner to ignore the job.
The alternative, a green run with the list only in the summary, leaves a
finding unseen unless someone opens the run.

**URLs come from the committed `dist/` packs, deduplicated in pack order
(single-screen first).** These are what consumers import. Checking the
committed packs rather than a fresh build keeps the command free of source
ingestion; the packs are at most a day behind the source lists. Denied URLs
are already absent from the packs, so the command does not read the deny list.

**Each request carries the entry's own request headers.** For each URL the
command JSON-decodes the first pack entry's `additionalSettings` string and
sends the headers it declares in `requestHeader`, each line split at its first
colon, and omnipack's default user agent when the entry declares none. When the
settings cannot be decoded to an object, or `requestHeader` is not a list of
objects with string `requestHeader` lines, that URL is inconclusive with a
reason naming the problem, the same path as a header line without a colon. The check then requests what
Obtainium requests, so dolphin-emu.org answers as it does for Obtainium, with
no rule for that host. `HttpClient.get` accepts the headers for the request.

**Requests run sequentially with the default `HttpClient`, inside a 20-minute
budget.** About 150 GETs usually finish in a few minutes and stay well below
github.com's rate limits; a 429 is inconclusive rather than a failure. The
worst case is not small: a URL that stalls on every attempt costs three
30-second timeouts plus backoff, about 90 s, so a slow host behind many URLs
could outrun any job timeout and lose the report. The command therefore checks
a monotonic clock, injectable for tests, before each request and starts none
once 20 minutes have passed; each URL not yet checked is inconclusive with the
reason "not checked: time budget spent". A request already running when the
budget runs out can add about 90 s, so the job's 30-minute `timeout-minutes`
leaves ample room for the report to be written. The run then passes or fails on
its findings alone.

**Outcomes are classified per URL.** A request that raises nothing ended in a
success status, possibly after redirects, so the project is reachable and is
left out of the report. `HttpStatusError` with 404 or 410 is unreachable. Any
other per-URL failure, including any other `HttpStatusError`, a
`TransientHttpError` or `HttpError`, and a `ValueError` raised while building
the request (a URL without a usable scheme or with embedded credentials, or a
`requestHeader` line without a colon, or settings that do not decode to
well-formed request headers), is inconclusive, and the check continues
with the next URL. The inconclusive reason names the cause: the HTTP status
when the last attempt received one (for example 429 or 503, read from the
error the retries ended on), otherwise that error's own message (for example a
timeout). A rate limit and a timeout therefore read differently in the report.

**The report is always written and records failures.** Like
`pack generate-source`, every invocation writes `report.json` and `summary.md`
whole, on success and failure alike, with a success or failure status and, on
failure, the error, such as unreadable packs. A fresh report always replaces
the previous one, so no stale report survives a run. Each file is written to a
temporary file and renamed into place; when either cannot be written, the
command exits nonzero with a concise diagnostic whatever the findings and
leaves neither partially written.

**The scheduled job is a plain read-only job in `source-catalog.yml`.** It is
not a call of `source-maintenance.yml`, which exists to stage and publish a
proposal. The `live-check` job has `permissions: contents: read`, the same
canonical-repository and main-ref condition as the source jobs, its own
concurrency group `omnipack-live-check` without cancellation, and
`timeout-minutes: 30`, comfortably above the command's 20-minute budget. Its steps are checkout with `persist-credentials: false`, uv setup
with caching disabled, `uv sync --locked`, `uv run --no-sync pack check-live`,
then, under `if: always()`, appending `.build/live-check/summary.md` to the
run summary when it exists (it is missing only when it could not be written) and uploading `.build/live-check/report.json` with
`if-no-files-found: ignore` and 14-day retention. The job has no inputs, so
nothing reaches a command through interpolation.

## Risks / Trade-offs

- [A host returns 404 to a bot for a page that exists] -> Nothing is denied
  automatically; the owner checks the URL before denying. The job keeps failing
  daily until the owner denies it or the host answers, which is the intended
  nag; a persistent false positive is a reason to revisit the status set.
- [Denying by hand breaks the committed checks] -> A deny record for a URL
  still in the packs fails `pack verify` and the committed-pair test until the
  packs are rebuilt, and an overlay record or composition pin for that URL
  fails verify or the build. The owner removes those, runs `pack build`, and
  commits the deny record, the config edits and the rebuilt packs together.
- [A host redirects an anonymous request for a missing project to a sign-in
  page] -> The outcome follows the sign-in page's final status: an error status
  makes the project inconclusive (gitlab.com ends in 403), and a 2xx makes it
  reachable, so it is not detected at all. Either way it never fails the job.
  The check stays the same for every host; the docs tell the owner that an
  inconclusive URL on such a host may be gone and is worth a look.
- [github.com rate-limits the runner] -> Those URLs are inconclusive with
  their 429 status as the reason and listed; the job does not fail on them.
- [A slow host spends the time budget] -> The URLs after it are inconclusive
  as not checked and the job still passes or fails on what was checked; a run
  that keeps spending its budget is visible in the report.

## Migration Plan

No data migration. The first scheduled run after merge reports the current
state; an existing unreachable project fails it until the owner denies that
project as above. Rollback: delete the `live-check` job.
