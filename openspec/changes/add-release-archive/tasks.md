# Tasks

## 1. Setup

- [x] 1.1 Add an `archive` dependency group with boto3 via `uv add --group archive boto3`; verify `uv lock --check` passes and the core `dependencies` list stays empty
- [x] 1.2 Create the `src/omnipack/archive/` package. Its outcome `StrEnum` names archived, unchanged, unreachable, no release, failed, skipped and not checked. Its `ResolvedRelease` model carries version, tag, date, notes, raw record and assets. Verify `just typecheck` passes

## 2. HTTP streaming

- [x] 2.1 Add `HttpClient.download` to `src/omnipack/http.py`. It streams to a destination file, applies the existing retry policy and header-forwarding rules, and waits on rate-limit reset headers within a caller-supplied deadline; the archive hashes each stored file once, when it uploads it. Verify with new tests in `tests/test_http.py` using an injected transport: chunked body, retry then success, 404, a 429 with reset, and no credential sent after a redirect by a deadline-bounded request

## 3. Targets

- [x] 3.1 Implement target selection on top of `live_check.read_targets`. It dedupes on the normalized URL with single-first precedence, skips track-only entries and sources other than GitHub, GitLab and HTML, and derives the source key. Verify with synthetic-pack tests: an app in both packs, a track-only entry, an unsupported source, and HTML key prefixing

## 4. Obtainium-equivalent resolution

- [x] 4.1 Pin an Obtainium upstream commit and cite it in the resolver package docstring. Verify the docstring names the commit hash
- [x] 4.2 Extract GitHub release filtering from `src/omnipack/forge_health.py` into one shared function that also implements the remaining settings: title and notes regexes, `sortMethodChoice`, `fallbackToOlderReleases` with the APK filter, invert and zips options, `releaseTitleAsVersion`, `releaseDateAsVersion`, `versionExtractionRegEx` / `matchGroupToUse`, and `verifyLatestTag`. Verify the existing `tests/test_forge_health.py` passes unchanged, and add a table-driven resolver test per setting
- [x] 4.3 Implement the GitHub resolver, which returns every asset of the selected release plus its notes and raw record. Verify with fixture tests for prerelease exclusion, fallback to an older release, version extraction, no qualifying release, and a 404 repository
- [x] 4.4 Implement the GitLab resolver against the releases API with the same shared settings. It returns the installable files linked only from the release description as well as the asset links, deduplicated. Verify with synthetic fixture tests for selection, asset links, a release whose APK is linked only from its description, and 404
- [x] 4.5 Implement the HTML resolver. It sends `requestHeader`, follows `intermediateLink` steps, applies the link filters, sorts, and extracts the version from the link or the whole page. Verify with synthetic page fixtures: a direct link, a two-step intermediate chain, whole-page extraction from a JSON body, and a page answering 410

## 5. Storage and source history

- [x] 5.1 Implement the bucket store, configured from `ARCHIVE_S3_*` environment variables. It handles JSON put, existence checks, file upload, listing keys under a prefix and deleting keys, and raises a run-level error on configuration or auth failure. Verify with a dict-backed fake and `botocore` Stubber tests for missing configuration and access denied
- [ ] 5.2 Implement source capture. It makes a bare clone, which fetches branches and tags only, and builds an uncompressed bundle of them, reporting failure as a reason rather than raising, including for git output that is not UTF-8. Verify against a local temporary git repo carrying an extra non-branch ref: the bundle clones directly with every branch and tag and holds no pull request ref, git output that is not UTF-8 does not raise, and a missing remote returns a reason

## 6. Orchestration and command

- [ ] 6.1 Implement the per-target archive flow. It resolves the release, checks whether the resolved version's manifest exists, uploads every object to the version-slug prefix, uploads the source bundle to the per-target key (replaced only on a successful capture, with the manifest recording its key, size and sha256 or why none was captured) and writes the manifest last. Verify with fake-store tests for: unchanged skip with no downloads when the manifest exists, a new version alongside an old one, an asset 404 leaving no manifest and a failed outcome, a clone failure archived without a bundle, an A-to-B-to-A return that downloads nothing, captures nothing and leaves A's objects and manifest untouched, a track-only target making no HTTP request, an HTML target resolved through an intermediate page with no capture, and an asset 404 followed by a successful run that archives the version in full over the partial prefix
- [ ] 6.2 Implement the run loop. It processes targets serially, enforces a time budget that stops starting new targets, reports the rest not checked and passes a deadline to the in-flight target's downloads and clone, isolates each target's failure, and writes `.build/archive/report.json` and `summary.md`. Verify with tests for budget exhaustion, a deleted repository among healthy targets that also has an earlier archived version left untouched, a run-level bucket failure exiting non-zero, and the budget leaving a 30-minute margin below the job timeout
- [ ] 6.3 Add the `pack archive` subcommand with `--dry-run`, which resolves and reports versions with no credentials, downloads or writes, and implement the archive command contract: nonzero exit only for a run-level error or an unwritable report, a failed report on a run-level error, the report rewritten after each target, `--budget-minutes` a positive finite number, only a fixed description of a bucket error published, an HTML-escaped summary, and the in-flight target at the deadline reported failed. Verify with CLI tests that a dry run on synthetic packs makes no download, clone or store call, that a failed target carrying a version shows its error in the summary and the printed line, that a bucket error and an unwritable report exit nonzero, and that an invalid budget is rejected
- [x] 6.4 Document the archive in `docs/archive.md` and add a pointer from `docs/publishing.md`. Cover the bucket layout with the per-target bundle, retention, creating the `release-archive` environment and secrets (the key needs list, read, write and delete permission), the outcomes, and restoring an app from its bundle, cloned without decompression, and assets. Verify the restore commands work as written against a bundle produced by the 5.2 test
- [x] 6.5 Implement retention. After a new version's manifest is stored, keep the target's three most recently archived versions (ranked by manifest storage time) and delete older ones, deleting each pruned version's manifest before its other objects and leaving prefixes without a manifest alone. Verify with fake-store tests: a fourth version prunes the oldest, the manifest is deleted first, an incomplete prefix is untouched, and a pruned version selected again is archived again

## 7. Alerts

- [x] 7.1 Add the `release-archive` producer to `scripts/alerts.py`: the job and key prefixes, an owner, `emit_release_archive` raising only the run-level finding. Verify with tests in the existing alerts suite: a report with failed, unreachable and not-checked targets raises no finding; a run that cannot read the packs or reach its bucket raises the run-level finding; a missing report raises the early-failure finding. Run `just check-py312`

## 8. Workflow

- [x] 8.1 Add `.github/workflows/release-archive.yml`. It triggers on `workflow_run` of "Nightly publishing" (completed) and on `workflow_dispatch`, with `permissions: {}`, an inline `# zizmor: ignore[dangerous-triggers]` on the `workflow_run` trigger with a comment that the job checks out main, consumes no artifact from the triggering run and holds only `contents: read`, the canonical-repo and main guards, and a `release-archive` environment holding the secrets. The archive job has `contents: read`, a 330-minute limit, `uv sync --locked --no-default-groups --group archive`, and shows the report in the job summary and uploads it, with the alert findings, as a workflow artifact; the alert job has `issues: write`. Concurrency is `omnipack-release-archive`, not canceling. Verify `lint-actions` (actionlint, zizmor) and `tests/test_publication_workflows.py` pass, and add a test asserting no nightly or source-catalog job references an `ARCHIVE_S3_*` secret

## 9. Integration checks

- [x] 9.1 Run `uv run pack archive --dry-run` against the committed `dist/*.json` and confirm every target reports a resolved version or a skipped, unreachable or no-release outcome, with no crash. Record the summary in the change directory
- [x] 9.2 Run `just test lint-check typecheck format-check` and confirm all pass

## Workflow follow-up

- The owner creates the `release-archive` environment and secrets, then runs a first manual dispatch. A second dispatch should report every target unchanged.
