# Tasks

## 1. Setup

- [x] 1.1 Add an `archive` dependency group with boto3 via `uv add --group archive boto3`; verify `uv lock --check` passes and the core `dependencies` list stays empty
- [x] 1.2 Create the `src/omnipack/archive/` package. Its outcome `StrEnum` names archived, unchanged, unreachable, no release, failed, skipped and not checked. Its `ResolvedRelease` model carries version, tag, date, notes, raw record and assets. Verify `just typecheck` passes

## 2. HTTP streaming

- [x] 2.1 Add `HttpClient.download` to `src/omnipack/http.py`. It streams to a destination file, computes SHA-256, applies the existing retry policy and header-forwarding rules, and waits on rate-limit reset headers within a caller-supplied deadline. Verify with new tests in `tests/test_http.py` using an injected transport: chunked body, retry then success, 404, a 429 with reset, and no credential sent after a redirect

## 3. Targets

- [x] 3.1 Implement target selection on top of `live_check.read_targets`. It dedupes on the normalized URL with single-first precedence, skips track-only entries and sources other than GitHub, GitLab and HTML, and derives the source key. Verify with synthetic-pack tests: an app in both packs, a track-only entry, an unsupported source, and HTML key prefixing

## 4. Obtainium-equivalent resolution

- [ ] 4.1 Pin an Obtainium upstream commit and cite it in the resolver package docstring. Verify the docstring names the commit hash
- [ ] 4.2 Extract GitHub release filtering from `src/omnipack/forge_health.py` into one shared function that also implements the remaining settings: title and notes regexes, `sortMethodChoice`, `fallbackToOlderReleases` with the APK filter, invert and zips options, `releaseTitleAsVersion`, `releaseDateAsVersion`, `versionExtractionRegEx` / `matchGroupToUse`, and `verifyLatestTag`. Verify the existing `tests/test_forge_health.py` passes unchanged, and add a table-driven resolver test per setting
- [ ] 4.3 Implement the GitHub resolver, which returns every asset of the selected release plus its notes and raw record. Verify with fixture tests for prerelease exclusion, fallback to an older release, version extraction, no qualifying release, and a 404 repository
- [ ] 4.4 Implement the GitLab resolver against the releases API with the same shared settings. It returns the installable files linked only from the release description as well as the asset links, deduplicated. Verify with synthetic fixture tests for selection, asset links, a release whose APK is linked only from its description, and 404
- [ ] 4.5 Implement the HTML resolver. It sends `requestHeader`, follows `intermediateLink` steps, applies the link filters, sorts, and extracts the version from the link or the whole page. Verify with synthetic page fixtures: a direct link, a two-step intermediate chain, whole-page extraction from a JSON body, and a page answering 410

## 5. Storage and source history

- [ ] 5.1 Implement the bucket store, configured from `ARCHIVE_S3_*` environment variables. It handles JSON get and put, existence checks and file upload, and raises a run-level error on configuration or auth failure. Verify with a dict-backed fake and `botocore` Stubber tests for missing configuration and access denied
- [ ] 5.2 Implement source capture. It makes a mirror clone, builds a bundle of every ref, and compresses it to `.zst` with `compression.zstd`, reporting failure as a reason rather than raising. Verify against a local temporary git repo: the decompressed bundle clones with every branch and tag, and a missing remote returns a reason

## 6. Orchestration and command

- [ ] 6.1 Implement the per-target archive flow. It resolves the release, checks whether the resolved version's manifest exists, uploads every object to the version-slug prefix and writes the manifest last. Verify with fake-store tests for: unchanged skip with no downloads when the manifest exists, a new version alongside an old one, an asset 404 leaving no manifest and a failed outcome, a clone failure archived without a bundle, and an A-to-B-to-A return that downloads nothing and leaves A's objects and manifest untouched
- [ ] 6.2 Implement the run loop. It processes targets serially, enforces a time budget that stops starting new targets, reports the rest not checked and passes a deadline to the in-flight target's downloads and clone, isolates each target's failure, and writes `.build/archive/report.json` and `summary.md`. Verify with tests for budget exhaustion, a deleted repository among healthy targets, and a run-level bucket failure exiting non-zero
- [ ] 6.3 Add the `pack archive` subcommand with `--dry-run`, which resolves and reports versions with no credentials, downloads or writes. Verify with a CLI test that a dry run on synthetic packs makes no download, clone or store call
- [ ] 6.4 Document the archive in `docs/archive.md` and add a pointer from `docs/publishing.md`. Cover the bucket layout, creating the `release-archive` environment and secrets, the outcomes, and restoring an app from its bundle and assets. Verify the restore commands work as written against a bundle produced by the 5.2 test

## 7. Alerts

- [ ] 7.1 Add the `release-archive` producer to `scripts/alerts.py`: the job and key prefixes, an owner, `emit_release_archive` raising only the run-level finding. Verify with tests in the existing alerts suite: a report with failed, unreachable and not-checked targets raises no finding; a run that cannot read the packs or reach its bucket raises the run-level finding; a missing report raises the early-failure finding. Run `just check-py312`

## 8. Workflow

- [ ] 8.1 Add `.github/workflows/release-archive.yml`. It triggers on `workflow_run` of "Nightly publishing" (completed) and on `workflow_dispatch`, with `permissions: {}`, an inline `# zizmor: ignore[dangerous-triggers]` on the `workflow_run` trigger with a comment that the job checks out main, consumes no artifact from the triggering run and holds only `contents: read`, the canonical-repo and main guards, and a `release-archive` environment holding the secrets. The archive job has `contents: read`, a 330-minute limit, `uv sync --locked --group archive`, and shows the report in the job summary and uploads it, with the alert findings, as a workflow artifact; the alert job has `issues: write`. Concurrency is `omnipack-release-archive`, not canceling. Verify `lint-actions` (actionlint, zizmor) and `tests/test_publication_workflows.py` pass, and add a test asserting no nightly or source-catalog job references an `ARCHIVE_S3_*` secret

## 9. Integration checks

- [ ] 9.1 Run `uv run pack archive --dry-run` against the committed `dist/*.json` and confirm every target reports a resolved version or a skipped, unreachable or no-release outcome, with no crash. Record the summary in the change directory
- [ ] 9.2 Run `just test lint-check typecheck format-check` and confirm all pass

## Workflow follow-up

- The owner creates the `release-archive` environment and secrets, then runs a first manual dispatch. A second dispatch should report every target unchanged.
