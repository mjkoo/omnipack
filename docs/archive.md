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

## Bucket layout

The bucket holds only versions under `apps/`:

```
<prefix>/apps/<source-key>/releases/<version-slug>/
    assets/<file>            every asset of the release
    release.json             the forge's release record
    release.md               the release notes
    source/repo.bundle.zst   every ref, as a zstd-compressed git bundle
    manifest.json
```

- `<source-key>` is the project's normalized URL without its scheme, with each
  path segment percent-escaped, prefixed `html/` for an HTML source.
- `<version-slug>` is the version with characters outside `A-Za-z0-9._-`
  replaced, truncated, then `-` and the first 8 hex digits of the SHA-256 of
  the raw version.
- A GitLab release also stores APKs linked only from its description. An HTML
  source stores just the resolved file, and its manifest lists the URLs
  fetched to find it (`fetchedUrls`).
- `manifest.json` records the pack entry, version, tag, dates and every
  object with its size and SHA-256. When the source history could not be
  captured, `sourceHistory.reason` says why and there is no bundle.

A version counts as archived exactly when its manifest exists. Every other
object is stored first and the manifest last, so an interrupted version has no
manifest and is archived again by the next run. A prefix with a manifest is
never written again. Earlier versions are kept and nothing is pruned.

## Creating the environment

The bucket credentials reach only the archive job, as secrets of a GitHub
environment named `release-archive` (Settings, Environments). Add these as
environment secrets, not repository secrets:

| Secret | Meaning |
| --- | --- |
| `ARCHIVE_S3_ENDPOINT` | The S3 API endpoint URL |
| `ARCHIVE_S3_BUCKET` | The bucket name |
| `ARCHIVE_S3_ACCESS_KEY_ID` | Access key id |
| `ARCHIVE_S3_SECRET_ACCESS_KEY` | Secret access key |
| `ARCHIVE_S3_PREFIX` | Optional key prefix |

The key needs read and write on the bucket. After the first manual dispatch
archives everything, a second should report every target unchanged. The first
run may take several nights if it exceeds the job's time budget; the targets
it did not reach are reported not checked and the next run continues.

## Running it

```
uv sync --locked --group archive
uv run pack archive [--budget-minutes N]
uv run pack archive --dry-run
```

`--budget-minutes` stops starting new targets after that long and abandons
the target in flight without a manifest. `--dry-run` resolves every target
and reports versions with no credentials, downloads, clones or bucket writes.
`GITHUB_TOKEN`, when set, authenticates GitHub API requests.

The report is `.build/archive/report.json` and `summary.md`. The command exits
non-zero only for a run-level error: unreadable packs, or a bucket that cannot
be reached or authenticated to. The report's `status` is `failed` with an
`error` in that case and `success` otherwise.

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

Only the run-level failure raises a [maintenance alert](alerts.md). A target
that fails stays in the report.

## Restoring an app

Fetch the objects with any S3 client, for example the AWS CLI:

```
aws s3 sync --endpoint-url "$ENDPOINT" \
  "s3://$BUCKET/<prefix>/apps/<source-key>/releases/<version-slug>/" restore/
```

The assets are ready to install under `restore/assets/`; compare them with
the SHA-256 values in `restore/manifest.json`. To recover the source,
decompress the bundle and clone it:

```
zstd -d restore/source/repo.bundle.zst -o repo.bundle
git clone repo.bundle app
```

The clone has every branch (as `origin/<branch>`) and tag the repository had
when that version was archived. Without the `zstd` tool, Python 3.14 reads it
with `compression.zstd`.
