# Release archive

The release archive keeps a durable copy of each packed app's current release,
its release notes and its source history in an S3-compatible bucket, so an
app stays recoverable when its upstream disappears. It runs after each
[nightly publishing](publishing.md) run and on manual dispatch, and it never
affects the publication.

`pack archive` reads both committed packs and processes each distinct project
once, serially. Only GitHub, GitLab and HTML sources are archived; track-only
and other entries are reported skipped. The version it archives is the one
Obtainium would show for the entry, so "unchanged" here means "no update in
Obtainium".

Some HTML versioning settings are exceptions. An HTML entry versioned by
`partialAPKHash`, `ETag` or `releaseDateAsVersion` is reported failed and
nothing is stored for it. One versioned by `APKLinkHash` gets a stable
stand-in version derived from the resolved link, not the value Obtainium
displays.

## Bucket layout

The bucket holds only keys under `apps/`:

```
<prefix>/apps/<source-key>/source/repo.bundle    every branch and tag, as one git bundle
<prefix>/apps/<source-key>/releases/<version-slug>/
    assets/<file>            every asset of the release
    release.json             the forge's release record
    release.md               the release notes, when present
    manifest.json
```

- `<source-key>` is the project's normalized URL without its scheme, with each
  path segment percent-escaped, prefixed `html/` for an HTML source. A key too
  long for an object key is cut and ends in `-` and a digest of the full key.
- `<version-slug>` is the version with characters outside `A-Za-z0-9._-`
  replaced, truncated, then `-` and the first 8 hex digits of the SHA-256 of
  the raw version.
- A GitLab release also stores APKs linked only from its description. An HTML
  source stores just the resolved file, and its manifest lists the URLs
  fetched to find it (`fetchedUrls`).
- `manifest.json` records the pack entry, version, tag, dates and every
  object with its size and SHA-256. `sourceHistory` records the key, size and
  SHA-256 of the bundle captured with that version, or `reason` when it could
  not be captured.
- The bundle is a single uncompressed file per app, outside the version
  prefixes. It is made from a bare clone, so it holds branches and tags but
  not a forge's pull or merge request refs. Each newly archived version replaces it with a fresh capture; a
  failed capture leaves the earlier bundle in place. An HTML source has none.

A version counts as archived exactly when its manifest exists. Every other
object is stored first and the manifest last, so an interrupted version has no
manifest and is archived again by the next run. A prefix with a manifest is
never written again.

## Retention

After a new version's manifest is stored, the app keeps its three most
recently archived versions, ranked by when their manifests were stored, and
deletes older ones. The version just archived is always kept. A pruned
version's manifest is deleted first, so a partly
pruned version never reads as archived. A prefix without a manifest is an
unfinished attempt and is left alone. A pruned version that is selected again
is archived again.

## Creating the environment

The bucket credentials reach only the archive job, as secrets of a GitHub
environment named `release-archive` (Settings, Environments). Under the
environment's deployment branches, allow only `main`, so a workflow on another
branch cannot run a job in it. Add these as environment secrets, not
repository secrets:

| Secret | Meaning |
| --- | --- |
| `ARCHIVE_S3_ENDPOINT` | The S3 API endpoint URL |
| `ARCHIVE_S3_BUCKET` | The bucket name |
| `ARCHIVE_S3_ACCESS_KEY_ID` | Access key id |
| `ARCHIVE_S3_SECRET_ACCESS_KEY` | Secret access key |
| `ARCHIVE_S3_PREFIX` | Optional key prefix |

The key needs list, read, write and delete on the bucket. After the first manual dispatch
archives everything, a second should report every target unchanged. The first
run may take several nights if it exceeds the job's time budget; the targets
it did not reach are reported not checked and the next run continues.

## Running it

```
uv sync --locked --group archive
uv run pack archive [--budget-minutes N]
uv run pack archive --dry-run
```

`--budget-minutes`, a positive number, stops starting new targets after that
long and abandons the target in flight without a manifest; that target is
reported failed. `--dry-run` resolves every target and reports versions with
no credentials, downloads, clones or bucket writes. `GITHUB_TOKEN`, when set,
authenticates GitHub API requests only and is never sent across a redirect.

The report is `.build/archive/report.json` and `summary.md`, rewritten after
each target so a run cut short keeps the outcomes it reached. The command
exits non-zero for a run-level error, unreadable packs or a bucket error, and
when the report cannot be written. The report's `status` is `failed` with an
`error` in the first case and `success` otherwise. A bucket error is
reported by a fixed description; its full message, which can name the
endpoint or bucket, goes only to the job log.

## Outcomes

| Outcome | Meaning |
| --- | --- |
| archived | The version was new and is now stored |
| unchanged | The version's manifest already exists; nothing was downloaded |
| unreachable | The project answers HTTP 404 or 410 |
| no release | No release qualifies under the entry's settings |
| failed | Something else went wrong for this target; the report says what |
| skipped | Track-only or an unsupported source |
| not checked | The run stopped before reaching the target |

Only the run-level failure raises a [maintenance alert](alerts.md), along
with the job's early-failure alert (`release-archive/run`) when the archive
job fails, is cancelled or times out. A target that fails stays in the report.

## Restoring an app

Fetch the objects with any S3 client, for example the AWS CLI:

```
aws s3 sync --endpoint-url "$ENDPOINT" \
  "s3://$BUCKET/apps/<source-key>/releases/<version-slug>/" restore/
```

With `ARCHIVE_S3_PREFIX` set, the path is
`s3://$BUCKET/<prefix>/apps/<source-key>/releases/<version-slug>/`.

The assets are ready to install under `restore/assets/`; compare them with
the SHA-256 values in `restore/manifest.json`. The source is the app's single
bundle at `apps/<source-key>/source/repo.bundle` (under `<prefix>/` when
`ARCHIVE_S3_PREFIX` is set); it stays in place even when a version's
`sourceHistory` records only why that capture failed. Fetch it and clone it
directly:

```
aws s3 cp --endpoint-url "$ENDPOINT" \
  "s3://$BUCKET/apps/<source-key>/source/repo.bundle" repo.bundle
git clone repo.bundle app
```

The clone has every branch (as `origin/<branch>`) and tag the repository had
when the latest version was archived.
