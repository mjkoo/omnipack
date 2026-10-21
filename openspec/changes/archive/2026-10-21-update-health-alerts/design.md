# Design

## Context

`pack check-live` (`src/omnipack/live_check.py`) reads the committed pair. It
keeps one target per distinct URL, holding the first entry's
`additionalSettings`, and sends one GET per target through `HttpClient`
under a 20-minute monotonic budget. It writes `.build/live-check/report.json`
and `summary.md` whole. `scripts/alerts.py` `emit_live_check` maps the report to
findings under the `live-check/` prefix, and builds the re-check scope from
the report's lists. Keys of inconclusive URLs without a status go in
`unchecked`. `HttpClient` documents and enforces "no credentials":
`_build_request` refuses URLs with embedded user information and sends only the
`User-Agent` and the caller's headers. Through urllib, those headers are
forwarded on every redirect.

Nearly all of the pack's entries are GitHub URLs. Aurora Store is on
gitlab.com, where it links its APKs from the release description and leaves
the release's `assets.links` empty, so an asset-name test could never qualify
one of its releases. A few entries are track-only, Ghostship sets `includeZips`, and
rolling-release entries such as Silent Hill Decomp set
`useLatestAssetDateAsReleaseDate`. Obtainium's own test for an installable asset
is the extension list `.apk`, `.xapk`, `.apkm`, `.apks`, plus `.zip` when an
entry includes archives.

## Goals / Non-Goals

**Goals:**

- One health result per GitHub repository URL per run, derived from two API
  reads.
- A lookup that cannot finish leaves its URL's alert state untouched.
- The workflow token reaches only `api.github.com`, and never follows a
  redirect.

**Non-Goals:**

- Obtainium's other health rules. Failed checks and hidden newer releases
  depend on device state or on per-entry release selection: APK filter, title
  and notes filters, version extraction and fallback.
- Configurable thresholds or a committed exception list. The 180 days is a
  constant; a mute is the exception.
- Health for HTML, direct-link or other hosts.
- Health for gitlab.com projects. Their APKs may be linked only from the
  release description, as Aurora Store's are, which an asset-name test cannot
  see, so such a project would read as stale on every run.
- Health for self-hosted GitLab.
- Pagination beyond the newest 100 releases.

## Decisions

**Health lives in `pack check-live`, in a separate module.** A new
`omnipack.forge_health` module owns URL classification, the two lookups and
release qualification. It exposes one function from a URL, the entry's
decoded settings, an `HttpClient`, a GitHub token and the current time, to a
result that is stale, archived, both, healthy or inconclusive with a reason.
`check_live` calls it after a URL's reachability request unless that URL was
unreachable, whatever else the reachability outcome was, checks the budget before each forge request, and appends the
result to the new report lists. The alternative was a separate command and
job with its own report and alert owner. That costs a second producer, a
second early-failure key and a second checkout and sync for the same targets,
and buys nothing, since the two checks share their URLs, budget and
inconclusive semantics. Health keys use the pack URL, as reachability keys
do, so two pack URLs that normalize to one repository each get their own
lookup and keys. Simplicity wins over deduplicating that rare case.

**URL classification uses the normalized project URL.** A target is a forge
target when its normalized URL (`omnipack.urls`) is `github.com/<owner>/<repo>`.
The lookups target `https://api.github.com/repos/<owner>/<repo>` plus
`/releases?per_page=100`. A target whose normalized URL has another shape,
such as a GitHub URL with no repository or any gitlab.com URL, is not a forge
target and gets no result. That way only a lookup that was made can be inconclusive.

**Qualification follows the spec over GitHub's fields.** GitHub releases
supply `draft`, `prerelease`, `published_at`, `tag_name` and
`assets[].name`/`updated_at`. Drafts, and prereleases the entry does not opt
into through `includePrereleases`, are dropped before any date is parsed or
sorted, since GitHub lists drafts to a token with push access and gives them
`published_at: null`. The remaining candidate releases are sorted by date,
newest first, before the newest qualifying one is chosen, as Obtainium sorts
by date. A JSON shape the code does not expect, such as a non-list body or a
remaining candidate release without a parseable date, makes the URL
health-inconclusive and is not skipped, since a skipped release could turn a
fresh project stale. A dropped draft or prerelease never makes the URL
health-inconclusive.

**The token is an unredirected header.** `HttpClient.get` gains an optional
`credential` argument: an `Authorization` value sent through urllib's
`Request.add_unredirected_header`, which urllib never forwards to a redirect
target. `forge_health` passes `Bearer <GITHUB_TOKEN>` only on
`api.github.com` requests. A renamed repository's API redirect is then
followed without the token. It usually still succeeds anonymously, and at
worst it is rate-limited and inconclusive. `_build_request` keeps refusing
embedded URL credentials. The module docstring's "no credentials" changes to
"no credentials unless a caller passes one", and every existing caller passes
none. The alternative was a transport that refuses cross-host redirects. That
changes behavior for every caller to protect one header.

**The token comes from the environment at the CLI edge.** The `check-live`
CLI handler reads `GITHUB_TOKEN` and passes it into `check_live`, which tests
override. A missing or empty variable means anonymous lookups. Locally that
works, but rate limits after about 60 GitHub requests, so later URLs read as
health-inconclusive. The workflow sets `GITHUB_TOKEN: ${{ github.token }}` on
the `pack check-live` step only, with job permissions unchanged
(`contents: read`).

**Report shape.** The existing lists keep their shapes. New lists, in pack
order:

- `stale`: `{url, name, tag?, date?}`, with `date` an ISO 8601 UTC date.
- `archived`: `{url, name}`.
- `healthInconclusive`: `{url, name, reason}`, with a reason in the existing
  `_failure_reason` style, `HTTP <status>` or the error's message.

The run summary gains three sections in the same escaped `<pre>` block.

**Alert mapping.** It adds the prefixes `LIVE_STALE = "live-check/stale/"` and
`LIVE_ARCHIVED = "live-check/archived/"`, added to the scope whenever the
report status is success. For each `healthInconclusive` URL and each
`unreachable` URL, both health keys go in `unchecked`. A GitHub URL the time
budget cut is covered without matching its reason text, since the check lists
it as health-inconclusive. Every other health key under the two prefixes
counts as re-checked, including the keys of a URL no longer in the packs, so
its stale and archived issues are closed. That leaves health keys unchecked
only for URLs the lookup never reached or could not finish, as the spec
requires.

Finding titles:
- "Project has had no qualifying release in 180 days: <url>"
- "Project has no qualifying release: <url>"
- "Project repository is archived: <url>"

Details give the URL, the entry name and, for stale, the tag and date. Health
findings are left out of `accounted`, because a stale or archived URL never
fails the check step.

**"Now" is injected.** `check_live` takes `now: datetime`, which defaults to
the UTC wall clock. Age is counted in whole elapsed days and is stale at 180
or more, as Obtainium's default threshold is. Tests can then pin the 179-day and 180-day boundary
without a monotonic clock, which only measures the budget.

## Risks / Trade-offs

- [Up to two requests more per GitHub URL lengthen the run] -> About two API
  calls per GitHub project, a little over 200 in all, at sub-second latency fit well inside the 20-minute budget. A run that
  does spend the budget reports the remaining URLs as not checked, and their
  alert state is left untouched.
- [The workflow token's 1,000-requests-per-hour limit is shared with other
  jobs in the repository] -> One run uses about two per GitHub project, a
  little over 200. A limit that is spent
  reads as health-inconclusive, which raises and closes nothing.
- [A first run opens an issue per dormant or archived project] -> Expected
  and documented. The owner
  mutes each dormant upstream once, by closing its issue as not planned.
- [The heuristic differs from Obtainium for entries whose APK filter rejects
  every recent APK] -> The URL reads as fresh here while Obtainium has
  nothing to install. That gap is accepted, and keeping per-entry selection
  out is the point of the design.
- [A mute clears on any qualifying release, even a minor one] -> As designed:
  the project is no longer dormant, and later dormancy raises a new
  occurrence.
- [Changing the report schema] -> The only consumer is the alert emitter in
  the same repository, and both change together.

## Migration Plan

Merging deploys the change, and the next scheduled live check raises the
initial findings. Rollback is a revert. Open health issues then stop being
re-checked and stay as they are until closed by hand.
