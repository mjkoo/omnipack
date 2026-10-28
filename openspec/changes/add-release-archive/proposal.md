# Proposal

## Why

The packs point at projects the owner does not control. When a repository is
deleted, a release is pulled or a download site disappears, the app becomes
unrecoverable through Obtainium. A durable, versioned mirror of each app's
current release, its release notes and its source history would let the owner
recover any packed app independently of its upstream.

## What Changes

- Add a scheduled archive workflow that runs after each nightly publishing run,
  and on manual dispatch. It reads both committed packs from `main` and archives
  each fetchable app to an S3-compatible bucket whose credentials come from GitHub
  secrets.
- For each app, resolve the latest release the way Obtainium would, from the
  entry's `additionalSettings`, for GitHub, GitLab and HTML sources. When the
  resolved version matches the last archived version, skip the app with no further
  downloads.
- Archive each new version under its own prefix. The archive holds:
  - every release asset;
  - the release description;
  - for forge-hosted projects, a full-history git bundle compressed with zstd,
    plus the README;
  - for HTML sources, the resolved APK and a snapshot of the fetched pages.

  Earlier versions are kept, with no retention policy.
- A version is recorded as archived only after every one of its objects is
  stored. An interrupted or failed archive is therefore retried on the next run.
- Report each app's outcome: archived, unchanged, unreachable, no release,
  failed, skipped or not checked. Unreachable projects and partial failures never
  stop the other apps.
- Raise a maintenance-alert finding only for an archive run that fails. Per-app
  outcomes, failures included, stay in the run report and raise no finding.
- Add a `pack archive` command, with a `--dry-run` mode that resolves versions
  without a bucket.
- Add a streaming download to the HTTP client. Add boto3 in a separate dependency
  group, so the core package keeps no runtime dependencies.

Nothing is retired. Track-only entries, and entries whose source is not GitHub,
GitLab or HTML, are skipped.

The estimated size is:

| Item | Estimate |
|---|---|
| Requirements | 12 new, 1 modified |
| Scenarios | 22 new, 1 added to the modified requirement |
| Implementation | about 1,200 lines (resolvers about 500, orchestration and storage about 400, workflow and alerts about 300) |
| Tests | about 1,000 lines |

## Capabilities

### New Capabilities

- `release-archive`: the scheduled mirror of each packed app's resolved release.
  It covers:
  - target selection from the committed packs;
  - Obtainium-equivalent version resolution;
  - change detection against the bucket;
  - the archived contents and bucket layout;
  - completion semantics;
  - per-app outcomes;
  - the workflow's schedule and credential scope;
  - the `pack archive` command.

### Modified Capabilities

- `maintenance-alerts`: the archive workflow becomes a producer. Only a failed archive
  run raises a finding; per-app outcomes stay in the run report.

## Impact

- New code:
  - the `src/omnipack/archive/` package (targets, resolvers, store, source
    bundling, orchestration);
  - the `archive` subcommand in `src/omnipack/cli.py`;
  - a streaming download in `src/omnipack/http.py`;
  - shared settings filtering in `src/omnipack/forge_health.py`.
- New workflow: `.github/workflows/release-archive.yml`. It runs in a
  `release-archive` environment holding the `ARCHIVE_S3_*` secrets, and has its
  own concurrency group.
- `scripts/alerts.py` gains a `release-archive` producer.
- Dependencies: a new uv dependency group `archive` with boto3. Python 3.14's
  stdlib `compression.zstd` handles compression.
- Docs: a new `docs/archive.md` (layout, secrets setup, restoring from a bundle)
  and a pointer from `docs/publishing.md`.
- Nightly publishing is unchanged. It holds no bucket credential, and an archive
  failure cannot affect publication.
