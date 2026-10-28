# Design

## Context

See proposal.md (Why). The current state that shapes this design:

- **Packs:** `dist/single-screen.json` and `dist/dual-screen.json` are Obtainium
  exports. Each entry's `additionalSettings` is a JSON string. Almost every
  entry is GitHub. A handful are HTML (some with intermediate-link chains,
  whole-page version extraction or a JSON page). One is GitLab, and a few are
  track-only or have no recognised source.
- **Existing GitHub release selection:** `src/omnipack/forge_health.py` already
  reads GitHub releases via REST and implements a partial Obtainium filter: drafts,
  prereleases, installable-asset suffixes, `includeZips`, and
  `useLatestAssetDateAsReleaseDate`. It deliberately omits the APK regex,
  title and notes filters, sort method, fallback and version extraction.
  `decode_settings` parses the settings string.
- **Missing source support:** there is no HTML link scraping and no GitLab API
  client.
- **HTTP client:** `src/omnipack/http.py` is a stdlib client. Its retry policy is
  shared, and it never forwards credentials across redirects. It buffers whole
  bodies in memory.
- **Shared pack reader:** `live_check.read_targets` already reads both packs
  single-first and dedupes on project URL.
- **Alerts:** `scripts/alerts.py` is stdlib-only and must not import `omnipack`.
  Producers write a `FindingsFile`; `reconcile` maps a producer's result and file
  to issues.
- **Workflow rules:** workflows pin actions by SHA, disable caches and use
  `permissions: {}` at the top level. The nightly publisher's credential isolation
  is a spec guarantee.
- **Dependencies:** the core package has no runtime dependencies. The runtime is
  Python 3.14, whose stdlib includes `compression.zstd`.

## Goals / Non-Goals

**Goals:**
- Version resolution that matches Obtainium closely enough that "unchanged here"
  means "Obtainium shows no update".
- Bounded memory and disk, even on a first full backfill.
- Archived state is only what the bucket holds. Nothing is committed and nothing is
  cached in Actions.

**Non-Goals:**
- Retention or pruning.
- Incremental or delta git bundles.
- Deduplicating identical assets across versions.
- Archiving track-only or unsupported sources.
- Per-device arch narrowing (`autoApkFilterByArch`) or Obtainium's
  installed-version comparison. The archive compares only against its own archived
  manifests.
- Serving the archive publicly, or restore tooling beyond documentation.

## Decisions

### A separate workflow triggered by `workflow_run`, not more nightly jobs

`.github/workflows/release-archive.yml` triggers on `workflow_run` of "Nightly
publishing" (`completed`) and on `workflow_dispatch`. An `archive` job runs in a
GitHub Environment named `release-archive` that holds the `ARCHIVE_S3_*` secrets,
with `contents: read` and `timeout-minutes: 330`. An `alert` job holds
`issues: write`. The concurrency group is `omnipack-release-archive`, with
`cancel-in-progress: false`.

Folding it into `nightly.yml` was rejected for three reasons:
- It would put a second credential into a workflow whose isolation is specified.
- Backfill would blow through the 60-minute per-job limit.
- A bucket outage would turn the publishing run red.

`workflow_run` runs the default branch's workflow file, and `actions/checkout` of
`main` picks up the packs the nightly just pushed. A plain cron trigger offset from
03:00 ET was rejected: it could overlap a slow nightly and read stale packs.

zizmor's pedantic persona flags `workflow_run` as a dangerous trigger. The
trigger line carries an inline `# zizmor: ignore[dangerous-triggers]` with a
comment saying why it is safe here: the job checks out `main`, consumes no
artifact from the triggering run and holds only `contents: read`. Having the
nightly dispatch the archive instead was rejected because it would need
`actions: write` in `nightly.yml`.

### Port Obtainium's source logic at a pinned upstream commit

The resolvers port the release-selection and version logic from Obtainium's
`lib/app_sources/github.dart`, `gitlab.dart` and `html.dart`, plus the shared
filtering in `source_provider.dart`, at one pinned upstream commit. The module
docstring cites that commit, so a future re-sync has a diff base.

Each resolver returns one `ResolvedRelease`:
- `version`, `tag`, `date`, `notes` and `raw_record`;
- `assets`, a list of name and URL pairs.

GitHub selection extends forge_health's filter into one shared function rather
than keeping two copies. forge_health keeps its narrower call by passing only the
settings it uses. Approximating Obtainium with our own heuristics was rejected:
skip-if-unchanged must match what Obtainium shows, and only a port achieves that.

### Assets: "all assets" overrides Obtainium's APK filter for storage only

The APK filter (`apkFilterRegEx`, `invertAPKFilter`, `includeZips`) still decides
which release is selected, and therefore which version results, as Obtainium
does. Once a release is selected, every asset on it is stored, together with every
installable file the resolution selects, including APKs a GitLab release links
only from its description; a file reached both ways is stored once. For HTML sources,
the resolved link is the only asset.

### Manifest existence is the change detector

The source key is the normalized pack URL from `src/omnipack/urls.py`, with the
scheme stripped and HTML sources prefixed `html/`. The layout:

```
<prefix>/apps/<source-key>/releases/<version-slug>/{assets/*, release.json, release.md,
                                                    source/repo.bundle.zst, manifest.json}
```

The bucket holds only `apps/...`. `version-slug` is the version sanitized to
`[A-Za-z0-9._-]` and truncated, then a `-` and the first 8 hex digits of the
SHA-256 of the raw version.

The commit protocol:
1. Upload every object.
2. Upload `manifest.json`.

A version counts as archived exactly when its manifest exists under its version
prefix. A target is unchanged when the resolved version's manifest exists,
checked with a HEAD request, and nothing is downloaded. This also covers a
release that is pulled so that selection returns to an older archived version:
that version's manifest exists, so its objects are left untouched. A prefix with a
manifest is never written again, so only incomplete prefixes are retried.

A target's last outcome and error live only in the run report.

Keeping state in a committed file was rejected for three reasons: PRs carry
sources only, the nightly publisher is the only writer, and a committed file
cannot record a half-finished upload.

### Storage through boto3, in an `archive` dependency group

The S3 API covers AWS, R2, B2 and GCS interop with one endpoint setting.
`upload_file` gives managed multipart uploads straight from a temporary file.
boto3 lives in `[dependency-groups] archive`, so `uv sync --locked` for
everything else stays dependency-free. The workflow syncs with
`--group archive`. Shelling out to the preinstalled `aws` CLI was rejected: it is
hard to fake in tests and its error surface is opaque.

### Bounded resources

The run's resource limits:
- **HTTP:** `HttpClient.download(url, dest, headers)` streams in chunks to a
  temporary file and computes SHA-256 as it goes.
- **Rate limits:** a 403 or 429 with rate-limit headers sleeps until the reset,
  capped by the remaining budget, then retries once.
- **Serial processing:** targets are processed one at a time. Each target deletes
  its temporary directory before the next starts.
- **Source:** `git clone --mirror --quiet`, then `git bundle create --all`, then
  zstd streaming compression at level 10 into the upload file.
- **Time budget:** the remaining time to the job's limit minus 15 minutes. The
  run stops starting new targets when the budget is reached, and passes the
  deadline to the in-flight target's downloads and clone, so that target is
  abandoned without a manifest.

### Outcomes and alerts

Outcomes are a `StrEnum` defined once in the archive package:
- `ARCHIVED`
- `UNCHANGED`
- `UNREACHABLE`
- `NO_RELEASE`
- `FAILED`
- `SKIPPED`
- `NOT_CHECKED`

`pack archive` writes `.build/archive/report.json` and `summary.md`, which the
workflow shows in the job summary and uploads as a workflow artifact. The report
is not stored in the bucket. The command exits non-zero only for run-level
errors: an unreadable pack, or a bucket the run cannot reach or authenticate to.

`scripts/alerts.py` gains:
- an `UnsourcedJob` value `release-archive`, with its key prefixes;
- an `Owner`;
- `emit_release_archive`, which reads the report file and raises only the
  run-level finding. Per-target outcomes, `FAILED` included, stay in the run
  report and raise no finding: the archive mirrors releases and does not
  validate apps.

## Risks / Trade-offs

- **The port drifts from Obtainium behavior over time.** Mitigation: pin and cite
  the upstream commit, keep the dry-run output easy to compare by hand, and
  re-sync on demand.
- **Full bundles of large repositories, re-stored at every release, cost
  storage.** Mitigation: this was accepted by the owner, and retention is
  explicitly deferred. The manifest records sizes, so the cost is visible.
- **A first backfill exceeds one job.** Mitigation: the budget and `NOT_CHECKED`
  let consecutive nights resume, and the work is idempotent.
- **A huge clone exhausts runner disk.** Mitigation: a clone failure falls back to
  archiving without a bundle and records the reason. Serial processing keeps
  peak disk use to one target at a time.
- **The GitHub API rate limit is shared with checkout.** Mitigation: the job's
  token allows plenty of requests for a few hundred targets. Rate-limit handling
  backs off within the budget.
- **HTML pages change their markup, so the resolved version flips and triggers
  re-archives.** Mitigation: this matches what Obtainium would then report. Each
  version is stored once under its slug.
- **A `workflow_run` trigger fires even when the nightly was skipped or
  cancelled.** Mitigation: the archive is useful regardless, and the jobs keep the
  canonical-repo and main guard.

## Migration Plan

1. Create the `release-archive` environment and its secrets in the repository
   settings. This is an owner action, documented in `docs/archive.md`.
2. Merge. The first `workflow_run` or a manual dispatch performs the backfill
   across one or more nights.
3. Rollback: disable the workflow. Nothing else depends on the bucket.

## Open Questions

- The exact pinned Obtainium commit is chosen when the port starts.
