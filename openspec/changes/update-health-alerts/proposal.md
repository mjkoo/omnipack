# Proposal

## Why

Obtainium 1.7 marks an app with a red "This app config may prevent updates"
indicator when its latest release is more than 180 days old or its source is
archived. On a Retroid Pocket 5 with the pack installed, 20 apps carried it.
Each was a real upstream condition, and three of them needed curation: an
archived OpenMW port, a dead Citra fork and a Pegasus entry that skipped
current builds by excluding prereleases. The owner learned of all three from
a device, not from omnipack. The live check already reaches every pack project
daily and raises an issue per problem, but its contract excludes releases and
archive state. Adding those two lookups gives omnipack the same signal
Obtainium gives, before a device shows it, and the existing issue mute serves
as the per-project exception.

The project dropped the generator's release and APK inspection for its
complexity. This change brings back only one narrow lookup per forge project:
the newest release carrying an APK-like asset, and whether the repository is
archived. It does not copy Obtainium's per-entry release selection: no APK
filters, title filters, version extraction or fallback rules.

## What Changes

- `pack check-live` adds an update-health lookup for every distinct GitHub or
  gitlab.com project URL it checks. The URL is **stale** when the newest
  qualifying release is 180 or more days old, or when none of the newest 100
  releases qualifies. It is **archived** when the forge reports the repository
  archived or disabled.
  - A qualifying release is one that carries an asset ending in `.apk`,
    `.xapk`, `.apkm` or `.apks`, or `.zip` for entries that set `includeZips`.
    For track-only entries, any release qualifies.
  - Prereleases qualify only for entries that set `includePrereleases`, and
    drafts never qualify.
  - A release is dated by its newest asset when the entry sets
    `useLatestAssetDateAsReleaseDate`, and by its publication date otherwise.
- URLs on other hosts get no health lookup and no health result. A URL that
  answers 404 or 410 gets no health lookup. A lookup that fails for any reason
  is inconclusive for health, raises nothing and closes nothing.
- GitHub API requests carry the token in the `GITHUB_TOKEN` environment
  variable when it is set, and only as a header that is never forwarded on a
  redirect. Project-page requests and gitlab.com requests stay
  credential-free. The live-check job passes `github.token` with its existing
  `contents: read` permission. This retires the check-live rule that the
  command sends no credentials at all.
- **BREAKING** (report schema): the live-check report gains `stale`,
  `archived` and `healthInconclusive` lists. Stale and archived results do not
  change the command's exit status.
- The alert emitter raises one finding per stale URL (`live-check/stale/<url>`)
  and per archived URL (`live-check/archived/<url>`). A health key counts as
  re-checked only when that URL's health lookup completed.
- `docs/alerts.md` documents the new findings and how to mute one, and expects
  a first run to open an issue for each currently dormant upstream.

Retired: the check-live sentence "The check SHALL be the same for every host
and SHALL NOT inspect releases, assets or a project's archive state", and the
blanket "sending no credentials" clause, which narrows to project-page and
gitlab.com requests.

Estimated size:
- 3 modified requirements and about 10 new scenarios.
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

## Impact

- `src/omnipack/live_check.py`, plus a new module for the GitHub and GitLab
  lookups.
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
