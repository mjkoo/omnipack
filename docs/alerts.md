# Maintenance alerts

Scheduled workflows open one GitHub issue per problem, update it while the
problem persists, and close it when a run that re-checked it no longer sees it.
Issues are the only state: the workflows keep none of their own. Every alert
issue carries the `omnipack-alert` label, which the first alert job creates.

## What raises a finding

| Owner (job that produces findings) | Raises |
| --- | --- |
| `nightly-prepare` (**Nightly publishing**, `prepare`) | A failed preparation stage; build warnings from `.build/report.json`: a family with no category, a denial matching nothing, a category assignment matching nothing, an overlay patch key that changes nothing, a project URL where a catalog lists an extra |
| `nightly-publish` (`publish`) | A failed push to `main`; a failed rolling-release synchronization |
| `codm-check`, `quiver-check` (**Reviewed source catalog**, `check`) | A failed generation, staging, test, build, verification or catalog-guard step |
| `codm-publish`, `quiver-publish` (`publish`) | A failed publication of the source proposal |
| `live-check` (`live-check`) | From `.build/live-check/report.json`: packs that cannot be read; a project URL answering 404 or 410; a URL answering another error status that the client does not retry, such as a 403; a GitHub project the check reports stale (no qualifying release in 180 days, or none at all) or archived |

Each owner also has an early-failure finding, titled "<owner> job failed
without reporting findings". A cancelled job raises only that finding and
closes nothing. A failed job that nothing above accounts for, such as one whose
`uv sync` failed, raises it too, and so does any job whose findings file is
missing or invalid, for example because its upload or the download failed.

What does not raise a finding:

- A push, release or proposal publication refused because `main` advanced. It
  self-heals on the next run.
- Routine screening results, such as the listings a source skips.
- Live-check outcomes with no usable status: one of the statuses the client
  retries (408, 425, 429, 500, 502, 503, 504) after its retries, a timeout, a
  connection failure, or URLs left unchecked when the budget runs out.
  Malformed request settings land here too. Such a URL neither raises nor
  closes anything, so an existing issue for it stays as it is.
- A skipped job, such as nightly `publish` after `prepare` failed. A `publish`
  job whose upstream did not succeed never started, so it counts as skipped
  even when Actions reports it as failed or cancelled.

## Keys

Each issue is identified by a key written as the first line of its body, for
example `<!-- omnipack-alert-key: nightly/prepare/verify -->`. A key is the
owner's prefix, the stage or kind, and a subject where there is one:

| Prefix | Keys |
| --- | --- |
| `nightly/prepare/` | `<stage>`: `checkout`, `build`, `allowlist`, `readme-boundary`, `commit`, `verify`, `drift-after-verify`, `bundle` |
| `build/` | `uncategorized/<family>`, `stale-denial/<url>`, `stale-category/<key>`, `redundant-patch/<url>/<dotted key>`, `listed-extra/<url>` |
| `nightly/publish/` | `push`, `release` |
| `<source>/check/` | `generation`, `stage`, `tests`, `build`, `verify`, `guard` |
| `<source>/publish/` | `proposal` |
| `live-check/` | `read`, `gone/<url>`, `status/<url>`, `stale/<url>`, `archived/<url>` |

Every owner also has a `run` key under its first prefix (for example
`nightly/prepare/run`, `codm/check/run`, `live-check/run`) for the
early-failure finding. `<source>` is `codm` or `quiver`.

A subject is percent-encoded: each UTF-8 byte of a character outside letters,
digits and `/:._~+-` becomes `%XX`. So
`https://dolphin-emu.org/download/?ref=btn` raised as a gone URL has the key
`live-check/gone/https://dolphin-emu.org/download/%3Fref%3Dbtn`. A subject too
long for the key limit is cut and ends in `~` and a digest. The 404 and 410
class and the other-status class are separate keys, so a muted 403 does not hide
a later 404 for the same project. Stale and archived are separate keys too,
independent of the URL's reachability keys. The issue title carries the
unencoded subject. Issues without a valid key on the first line of the body are
ignored, so do not delete or edit that line; if one is removed, the next run
opens a fresh issue.

## How an issue opens, updates and closes

Each workflow ends in an alert job that downloads its producers' findings
artifacts (`alert-findings-<owner>-<run id>`) and reconciles them with the
labelled issues, open and closed:

- **Opens.** A finding with no issue opens one, titled for the problem and
  carrying the details and a link to the run.
- **Updates.** An open issue is edited only when its title or details changed;
  an unchanged persisting finding gets no edit, so the run link names the run
  that last changed it. A hand edit to the title or details is overwritten by
  the next run that still raises the finding; the run line is regenerated
  whenever the issue is edited or reopened. Put your own notes in comments.
- **Closes.** An open issue whose key was re-checked and not raised is closed
  as completed with the comment "Not seen in run <url>".
- **Reopens.** A finding whose issue was closed as completed reopens it and
  refreshes its body.

A run closes only what it re-checked. Each key is in scope only when the stage
or step it names actually ran: a failed `prepare` does not close a release
issue, a failed generation does not close a verification issue, and build
warnings count as re-checked only when the build report records success. For
live check, URL keys are re-checked only by a successful report, and URLs the
budget left unchecked or that came back inconclusive without a status are left
alone, so a host alternating between 403 and a timeout does not open and close
an issue each night. A URL no longer in the packs does close. Stale and
archived keys are re-checked by every successful report except for a URL whose
health lookup did not finish (health inconclusive, such as a spent rate limit
or the budget running out) or that is unreachable, which leave those issues
as they were. The stale and archived issues of a URL no longer in the packs
close too.

### Stale and archived projects

`pack check-live` reads the newest 100 releases and the archive state of each
GitHub repository URL that is not unreachable;
[source generation](source-generation.md#live-project-check) describes which
releases qualify. A stale finding is titled "Project has had no qualifying
release in 180 days: <url>", with the newest qualifying release's tag and date
in its details, or "Project has no qualifying release: <url>" when none of
those releases qualifies. An archived finding is titled "Project repository is
archived: <url>". Each names the pack entry. Neither fails the live-check job.

A project that is already dormant or archived gets an issue on the first live
check that sees it. Review each one, and either act on it (a curation change,
a deny record) or mute it, as below, to accept a project that is simply quiet.
A muted stale issue clears when the project publishes a qualifying release, and
a later dormancy opens it again.

### Overrides that change nothing

The build report records two kinds of owner override that no longer change
what a catalog would publish; [composition](composition.md#denials-and-patches)
defines both and says how to retire them. Each overlay patch key that changes
nothing raises its own finding, keyed `build/redundant-patch/<url>/<dotted
key>` and titled "Overlay patch key changes nothing: <url> <key>", with the
full URL and key in its details; the key is the dotted path through the patch,
and patch keys may not contain `.` or `/`, so the subject names exactly one
record and key even when it is shortened. Each project URL where a catalog
lists an extra raises one finding, keyed `build/listed-extra/<url>` and titled
"A catalog lists an extra at: <url>", whose details name every such extra's
package id followed by each listing source and the fields that differ, or "no
differences".

Review each one and either retire the override or mute the issue. A mute on a
redundant-patch issue covers that one key: another key of the same record that
goes dead later raises its own finding, and a muted key that the source drifts
away from clears when the build stops reporting it. A mute on a listed-extra
issue covers every extra at that URL, including one a catalog starts listing
later, until the URL stops being reported. The first run after these findings
arrive is expected to open one issue per dead key and one per listed extra's
URL; each is ordinary curation triage.

## Muting an issue

Close an issue as not planned to mute it: while the finding keeps recurring,
the issue stays closed and silent. The mute lasts one occurrence. The first run
that re-checks the key and does not raise it reopens the issue and closes it as
completed with the comment "Cleared in run <url>"; a later recurrence then
reopens it as usual. A run that did not re-check the key leaves the mute in
place. Any other closure, as completed or as a duplicate, does not mute: a
recurrence reopens the issue.

## Residual risks

- **The alert job fails or issues are disabled.** The red run is the only
  trace; no issue is opened. The alert jobs are `alert` in **Nightly
  publishing** and in the source maintenance workflow, and `alert-live-check`
  in **Reviewed source catalog**. A producer's own verdict never depends on
  them.
- **Health lookups that never finish.** A URL whose GitHub lookup fails on
  every run, for example because the token is missing or the API rate limit
  is spent each time, is health inconclusive on every run and raises nothing.
  The run summary lists such URLs with their reasons. A renamed repository's
  API redirect is followed without the token, so its lookup is anonymous and
  more likely to be rate limited until its pack URL is updated.
- **A flake opens an issue and the next clean run closes it.** This costs two
  notifications; it is accepted to keep the workflows stateless.
- **A queued live check replaced by a newer one.** Its group does not cancel
  a running check, but a pending run replaced by a newer one is reported as
  cancelled, which raises a one-run early-failure issue (`live-check/run`)
  that the next live check closes. Accepted rather than guarded.
- **A manual re-run of an older alert job.** Re-running an older run's alert job
  after a newer run reconciled can close, reopen or clear the mute of an issue
  from stale findings. The next scheduled run corrects it, except that a
  cleared mute must be re-muted by hand. Scheduled runs cannot cause this,
  because each alert job is serialized in a non-canceling concurrency group.
- **A manual re-run attempt whose producer dies before uploading.** Findings
  artifact names carry only the run ID, so the alert job of a re-run attempt
  whose producer failed before uploading its findings can reconcile the
  previous attempt's file instead. Accepted beside the manual re-run risk
  above; the next scheduled run corrects it.
- **The repository becomes private.** The alert job's checkout holds no
  `contents` permission and relies on the repository being public, so making
  it private fails every alert job visibly, with no issue opened.
- **A manual cancellation** of a producer raises its early-failure issue too.
- **Duplicate issues for one key** are not merged; the lowest-numbered one is
  used.

## Security

Findings files are written next to upstream-derived data, so they are treated
as untrusted. The alert job holds only `issues: write`, runs from a sparse
checkout of `scripts/`, and renders detail lines HTML-escaped inside `<pre>`
within the issue size limit. See [nightly publishing](publishing.md) and
[source generation](source-generation.md) for the producing jobs.
