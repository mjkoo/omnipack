# Proposal

## Why

Obtainium 1.7 marks an app with a red "This app config may prevent updates"
indicator when its latest release is 180 or more whole days old, its default
threshold, or its source is archived. On a Retroid Pocket 5 with the pack installed, 20 apps carried it.
Each was a real upstream condition, and three of them needed curation: an
archived OpenMW port, a dead Citra fork and a Pegasus entry that skipped
current builds by excluding prereleases. The owner learned of all three from
a device, not from omnipack. The live check already reaches every pack project
daily and raises an issue per problem, but its contract excludes releases and
archive state. Adding those two lookups gives omnipack the same signal
Obtainium gives, before a device shows it, and the existing issue mute serves
as the per-project exception.

The project dropped the generator's release and APK inspection for its
complexity. This change brings back only one narrow lookup per GitHub project:
the newest release carrying an APK-like asset, and whether the repository is
archived. It does not copy Obtainium's per-entry release selection: no APK
filters, title filters, version extraction or fallback rules.

## What Changes

- `pack check-live` adds an update-health lookup for every distinct GitHub
  repository URL it checks, one whose normalized project URL is
  `github.com/<owner>/<repo>`. The URL is **stale**
  when the newest qualifying release is 180 or more whole days old, as
  Obtainium counts its default threshold, or when none of
  the newest 100 releases qualifies. It is **archived** when GitHub reports the
  repository archived or disabled.
  - A qualifying release is one that carries an asset ending in `.apk`,
    `.xapk`, `.apkm` or `.apks`, or `.zip` for entries that set `includeZips`.
    For track-only entries, any release qualifies.
  - Prereleases qualify only for entries that set `includePrereleases`, and
    drafts never qualify.
  - A release is dated by its newest asset when the entry sets
    `useLatestAssetDateAsReleaseDate`, and by its publication date otherwise.
- URLs on other hosts, gitlab.com included, get no health lookup and no
  health result. Some gitlab.com projects, such as Aurora Store, link their
  APKs from the release description and leave the release's asset links empty,
  so the asset-name test would report them stale on every run. A URL that
  answers 404 or 410 gets no health lookup. A lookup that fails for any reason
  is inconclusive for health: it raises no stale or archived finding and
  closes no health issue, and leaves the URL's reachability result and
  findings unaffected. A reachable URL is still reported stale, archived or
  health-inconclusive as its health result requires.
- GitHub API requests carry the token in the `GITHUB_TOKEN` environment
  variable when it is set, and only as a header that is never forwarded on a
  redirect. Project-page requests stay credential-free. The live-check job passes `github.token` with its existing
  `contents: read` permission. This retires the check-live rule that the
  command sends no credentials at all.
- **BREAKING** (report schema): the live-check report gains `stale`,
  `archived` and `healthInconclusive` lists. Stale and archived results do not
  change the command's exit status.
- The alert emitter raises one finding per stale URL (`live-check/stale/<url>`)
  and per archived URL (`live-check/archived/<url>`). A live check that read
  the packs counts as re-checking every stale and archived key except those of
  a health-inconclusive URL, an unreachable URL and a URL the time budget left
  unchecked, so the health issues of a URL no longer in the packs are closed.
- `docs/alerts.md` documents the new findings and how to mute one, and expects
  a first run to open an issue for each currently dormant upstream.

Retired: the check-live sentence "The check SHALL be the same for every host
and SHALL NOT inspect releases, assets or a project's archive state", the
blanket "sending no credentials" clause, which narrows to every request
other than a GitHub API request, and the source-ingestion clause "the system
SHALL keep no HTTP credential configuration", which narrows to the build and
source generation. The source-generation workflow sentence that limits the
live check's findings and run summary to reachability outcomes widens to the
health outcomes.

Estimated size:
- 5 modified requirements and about 11 new scenarios.
- About 150 to 200 implementation lines across `live_check.py`, a new
  forge-lookup module, `scripts/alerts.py` and the workflow.
- About 300 to 400 test lines.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-cli`: the check-live requirement adds the update-health lookups, the
  report lists and the scoped GitHub credential, and drops the
  same-for-every-host and no-release-inspection clauses.
- `maintenance-alerts`: the findings requirement adds stale and archived
  findings, and the re-check requirement defines when a URL's health keys
  count as re-checked.
- `source-ingestion`: the no-credentials requirement scopes its
  no-credential-configuration clause to the build and source generation, and
  leaves the live check's GitHub API credential to the check-live requirement.
- `source-generation`: the daily live-check workflow requirement shows the
  health lists in its run summary and raises the stale and archived findings
  maintenance-alerts defines.

## Impact

- `src/omnipack/live_check.py`, plus a new module for the GitHub lookups.
- `src/omnipack/http.py`: a way to send a header that is never forwarded on a
  redirect.
- `scripts/alerts.py`: the live-check emitter and its key prefixes.
- `.github/workflows/source-catalog.yml`: the live-check step's environment.
- `docs/alerts.md` and the live-check section of the docs that describe
  `pack check-live`.
- Tests: `tests/test_live_check.py` and `tests/test_alerts.py`, using
  synthetic fixtures.
- GitHub API usage is about two requests per project per run, within the
  workflow token's hourly limit.
