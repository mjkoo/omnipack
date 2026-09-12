## 1. Stateless source generation

- [ ] 1.1 Retire the old source publisher before anything it imports changes. Delete `scripts/source_publication.py`, `tests/test_source_publication.py` and `tests/test_source_workflow.py`. In `.github/workflows/source-catalog.yml`, remove:
  - the `observe`, `check` and `publish` steps;
  - the final record step that imports `scripts.nightly_reporting`;
  - the `force` input of `workflow_dispatch` and the `generate_forced` step that runs `pack generate-source codm --force`;
  - the `inputs.force` term from the remaining generation step's condition.

  This lands before 1.2 removes `--force` from the CLI, so no workflow step ever invokes a removed flag. Until 4.3 rewrites it, the source workflow generates but proposes nothing; main stays unpushed until this change lands, so no run sees that gap. Verify that `git grep` finds no reference to `source_publication` outside `docs/` and `openspec/`, that `git grep -e '--force' -e 'inputs.force' .github/workflows` finds nothing, that actionlint and zizmor pass, and that `just check-all` passes.
- [ ] 1.2 Rewrite `generate_codm` to resolve every project on every run. When a project fails, retain main's committed entry byte for byte only if the current rule reproduces it exactly when rendered with the identity the rule is authoritative for: an APK rule with the committed entry's package ID and URL, and a track-only rule with the rule's `trackerId` and the committed URL. Fail generation for every other failure. Remove:
  - the metadata and state loading;
  - the input gate and the `force` parameter and CLI flag;
  - `legacy_default_projects`;
  - metadata and accepted-state validation;
  - fingerprint-based fallback compatibility.

  Write only `catalog.json` and `report.json`, with added, removed and changed URLs and `retainedFailures`. Verify with tests for:
  - a retained entry for an unchanged or merely reformatted policy;
  - a blocking failure after a real policy change, and after a switch between APK and track-only;
  - a blocking failure when a committed tracker's `trackerId` changes in policy and its release lookup fails, with no candidate and the old entry not retained;
  - a failed new project that leaves no candidate;
  - `--force` rejected by argument parsing;
  - unchanged inputs reproducing the committed catalog byte for byte.
- [ ] 1.3 Delete `validate_generation_output` and `ProjectRule.fingerprint` if nothing else reads them, and remove tests that only covered the gate, the state, the legacy bootstrap or fingerprints. Verify that `git grep` finds no remaining references and the generation tests pass.
- [ ] 1.4 Delete `config/catalogs/codm.source.json` and `config/package-ids.json`, and drop their bindings from test fixtures, including the baseline index:
  - in `tests/test_cli.py`, `test_build_failure_does_not_mutate_resolution_state` stops writing a `package-ids.json` state file and asserts instead that a failed build leaves `config/catalogs/codm.json` unchanged, and is renamed to match; `test_build_runs_the_real_pipeline_with_transport_only_fixtures` drops `package-ids.json` from its fixture files and its final assertion that the file is unchanged, since the retained app already comes from the committed catalog;
  - in `tests/test_verification_integration.py`, the `inputs` fixture stops writing `config/package-ids.json`, so the protected-file snapshot covers only inputs that still exist.

  Verify that the captured 92/109 regression still passes and `git grep` finds no production or test reference to either file.
- [ ] 1.5 Rewrite the three live-catalog pin tests in `tests/test_source_generation_fixtures.py` as invariants over the committed catalog, with no URL, count or ID pins:
  - unique IDs and URLs;
  - kind-appropriate IDs and flags;
  - error-free composition with the frozen captured sources;
  - a single-screen pack unchanged.

  Verify that they pass on the committed catalog and on a test-local catalog with one project added and one removed.
- [ ] 1.6 Run `uv run pack generate-source codm` live and compare `.build/source-generation/codm/catalog.json` with `config/catalogs/codm.json`. Record the result, and explain any difference, in `openspec/changes/standardize-publication/validation.md`.

## 2. Structural verification report

- [ ] 2.1 Make `verify.py` read each input once, check and fingerprint those bytes, and write `.build/verify.json` once on completion, keeping the schema-2 fields. Update `tests/test_verify.py`: drop the running-record and in-run change tests, and add a test that the report fingerprints the captured bytes. Verify that the `pack report` tests pass unchanged.

## 3. Nightly publisher

- [ ] 3.1 Implement `python -m scripts.nightly prepare`, following the nightly flow in design.md. It runs in the synced environment of the read-only `prepare` job and may import `omnipack` for the README boundary. It requires `HEAD` to equal `GITHUB_SHA` at the start, and rejects any allowed path that is not a regular, non-executable file. It commits locally before verification, as `github-actions[bot]` with its noreply email and with hooks disabled (`core.hooksPath=/dev/null`), and writes `changed`, `sha` and `base` to `GITHUB_OUTPUT`. When it commits, it confirms that `HEAD` is the commit and writes `git bundle create <dir>/candidate.bundle <base>..HEAD`. Its step summary line is `no-op at <sha>`, `prepared <sha>`, or the failing stage (checkout, build, allowlist, README boundary, verify, drift after verify, or bundle). Verify with tests against a temporary git repository and bare remote, run in an isolated git environment with no global identity (`HOME` and `GIT_CONFIG_GLOBAL` inside the temporary directory, `GIT_CONFIG_NOSYSTEM=1`), with injected build and verify commands, each asserting the summary line as well as the outcome, covering:
  - a dirty checkout, and a `HEAD` other than `GITHUB_SHA`;
  - a no-op, summarized as `no-op at <sha>`;
  - a changed pack or README catalog becoming one conventional commit whose author and committer are `github-actions[bot]`, summarized as `prepared <sha>`;
  - a changed run's bundle, which `git bundle list-heads` shows holding `HEAD` at `<sha>` with `<base>` as its prerequisite, and no bundle for a no-op;
  - an out-of-scope tracked change;
  - a deleted allowed file;
  - an allowed file replaced by a symlink, and an allowed file whose executable bit was set, each failing the allowlist stage with no commit or bundle;
  - a README change outside the markers;
  - a verification failure;
  - an allowed file changed during verification.
- [ ] 3.2 Implement `python3 -m scripts.nightly_write push --bundle <path>` for the write job, following design.md. It reads `CANDIDATE_SHA` and `BASE_SHA` from its environment, rejects either unless it matches `^[0-9a-f]{40}$` (summarizing `push failed` without echoing the value), and runs every git command under `-c core.hooksPath=/dev/null`. It requires `HEAD` to be `<base>`, runs `git bundle verify`, fetches the bundle's `HEAD`, and requires the fetched commit to be `<sha>`, its only parent to be `<base>`, and every entry of `git diff --raw <base> <sha>` to name `dist/single-screen.json`, `dist/dual-screen.json` or `README.md` with mode `100644` on both sides. It then runs `gh auth setup-git` through a command-runner seam, requires `git ls-remote origin refs/heads/main` to report `<base>`, runs `git push origin <sha>:refs/heads/main`, and detaches to `<sha>`. It appends `published <sha>` to the step summary on success, or `push failed for <sha>` on any failure (`push failed for <sha>: main advanced` when the main check fails) before exiting nonzero. Verify with temporary git repositories in the isolated git environment from 3.1. Build the write-side repository as `actions/checkout` does, with `git init`, `file://<bare>` as `origin`, `git fetch --depth 1 origin <base>` and `git checkout --detach FETCH_HEAD`, assert that `git rev-parse --is-shallow-repository` prints `true` before running `push`, and fetch the bundle from a real `prepare` commit into it. Each case asserts the summary line as well as the remote state:
  - a successful round trip lands exactly `<sha>` on the remote's main, leaves `HEAD` detached at `<sha>`, and summarizes `published <sha>`;
  - a remote main that advanced after the checkout fails the main check before any push, leaves the remote's main unchanged, and summarizes `push failed for <sha>: main advanced`;
  - a push the remote rejects, through a pre-receive hook on the bare remote, summarizes `push failed for <sha>` and exits nonzero;
  - a bundle whose commit's parent is not `<base>` is rejected before any push, with the remote unchanged and `push failed for <sha>` summarized;
  - a bundle whose `HEAD` is not `<sha>`, a commit that changes a path outside the three allowed files, a commit that replaces `dist/single-screen.json` with a symlink, and a commit that sets `README.md`'s executable bit are each rejected before any push, with the remote unchanged;
  - a `CANDIDATE_SHA` or `BASE_SHA` that is a ref name or shorter than 40 hex characters is rejected before any fetch or push.
- [ ] 3.3 Implement `python3 -m scripts.nightly_write release` with the digest record over the two JSON files at `HEAD`, the check that `git ls-remote origin refs/heads/main` reports `HEAD` (after `gh auth setup-git`) before any write, the served-asset digest check and published-prerelease check from `gh release view continuous --json name,body,assets,isDraft,isPrerelease,isImmutable`, the marker and title checks, the canonical body template, the "upload both, then one edit" order and the release summary lines from design.md. Verify with stubbed `gh` responses and git run for real against a temporary bare remote, each asserting the summary line as well as the writes:
  - a matching record and matching served-asset digests make no write and summarize `unchanged at revision N`;
  - a differing or missing record uploads both assets, then makes one edit with revision N+1 whose body equals the canonical template and lacks the seed's "not yet published" statement, and summarizes `revision N+1`;
  - a matching record with a differing served-asset digest re-uploads both assets, makes no edit and summarizes `repaired at revision N`;
  - a missing asset, or a null or absent asset digest, re-uploads both assets without an edit or revision bump;
  - pair A published, then an interrupted upload of pair B, then a run whose pair is A again: both assets are re-uploaded as A with no edit, and the revision stays at A's;
  - a missing release, a missing marker or a malformed title fails without writes and summarizes `release failed: <reason>` with the bootstrap guidance;
  - a draft release, a release that is not a prerelease, and an immutable release each fail without writes and summarize `release failed: <reason>` with the bootstrap guidance;
  - an upload failure prevents the edit and summarizes `release failed: <reason>`;
  - a remote main other than `HEAD`, as when the write job of an earlier no-op run is rerun after a later run changed main, fails without writes and summarizes `release failed: main advanced`, without the bootstrap guidance.
- [ ] 3.4 Guard the write-side runtime of `scripts/nightly_write.py`, which runs on the runner's preinstalled `python3` (3.12 on ubuntu-latest) while the project requires 3.14:
  - the module starts with `from __future__ import annotations` and imports only the standard library and the `scripts` package;
  - `pyproject.toml` sets `[tool.ruff] per-file-target-version = {"scripts/nightly_write.py" = "py312"}`;
  - a test parses the module and every `scripts` module it imports, and fails on an import outside `sys.stdlib_module_names` and `scripts`, or a missing `from __future__ import annotations`;
  - a `just check-py312` recipe imports the module and runs its test file under CPython 3.12, taken from `nix shell nixpkgs#python312` locally (for example through `uv run --no-project --python <interpreter> --with pytest`); `check-all` runs it, and CI's `check` job gains a step that runs the same tests under the runner's `python3`.

  The module's test file imports only the standard library, `pytest` and the module under test. Verify that `just check-py312` and `just lint-check` pass, that the import test fails on a planted `import omnipack`, and that `just check-py312` fails on a planted unquoted forward reference in an annotation once the future import is removed.
- [ ] 3.5 Rewrite `.github/workflows/nightly.yml` as two jobs, keeping its guards:
  - workflow level: the `0 3 * * *` schedule with `timezone: America/New_York`, `workflow_dispatch`, `permissions: {}`, and concurrency group `omnipack-nightly-publisher` with `cancel-in-progress: false`;
  - both jobs: `if: github.repository == 'mjkoo/omnipack' && github.ref == 'refs/heads/main'`, `runs-on: ubuntu-latest` and `timeout-minutes: 60`;
  - job `prepare`: `permissions: contents: read`; checkout with `ref: ${{ github.sha }}`, `fetch-depth: 0` and `persist-credentials: false`; `setup-uv` and `uv sync --locked`; `prepare` without a token; the bundle uploaded with one-day retention when `changed` is true; `.build/report.json` and `.build/verify.json` always uploaded with 14-day retention; job outputs `changed`, `sha` and `base`;
  - job `publish`: `needs: prepare`, `permissions: contents: write`, no status function in its condition; checkout with `ref: ${{ github.sha }}`, `fetch-depth: 1` and `persist-credentials: false`; then a guard step running `test "$BASE_SHA" = "$GITHUB_SHA"` with `BASE_SHA` mapped from `needs.prepare.outputs.base` in its `env:`; no `setup-uv` or `uv sync`; the bundle downloaded with a SHA-pinned `actions/download-artifact` when `changed` is true; the push step gated only on `needs.prepare.outputs.changed == 'true'`, running `python3 -m scripts.nightly_write push` with `GH_TOKEN`, and `CANDIDATE_SHA` and `BASE_SHA` mapped from prepare's outputs in its `env:`; the release step running `python3 -m scripts.nightly_write release` with `GH_TOKEN` and no `if` condition.

  Add PyYAML to the test dependency group only, with `uv add --group test pyyaml`, leaving runtime dependencies empty. Verify with actionlint and zizmor, and with one structured test that parses the YAML with PyYAML, not matching substrings, and asserts every property listed above, and that:
  - `GH_TOKEN` appears only in the push and release steps, and no step of `prepare` references the job token or a secret;
  - every checkout step sets `persist-credentials: false`;
  - `publish` has no step that uses `setup-uv` or runs `uv`;
  - the push step's condition is only prepare's `changed` output, with no status function;
  - both checkout steps use `ref: ${{ github.sha }}`, and the guard step comparing prepare's `base` output with `GITHUB_SHA` precedes the download and every step that sets `GH_TOKEN`;
  - no `run:` contains a `needs.` or `steps.` expression, so outputs reach commands only through `env:`;
  - no status function (`always()`, `failure()`, `cancelled()` or `!cancelled()`) appears in `publish`'s condition or steps, and in `prepare` only on the diagnostics upload.
- [ ] 3.6 Delete these modules and their tests, including the YAML substring checks in `tests/test_nightly_workflow.py`:
  - `scripts/nightly_git.py`, `nightly_publish.py` and `nightly_release.py`;
  - `nightly_release_sync.py`, `nightly_release_transport.py` and `nightly_reporting.py`;
  - the old `nightly.py` bootstrap subcommand and HTTP client.

  Verify that `git grep` finds no imports of the removed modules and that `just check-all` passes.

## 4. Source proposal publisher

- [ ] 4.1 Implement `python -m scripts.source_proposal stage`, which:
  - requires `HEAD` to equal `GITHUB_SHA`, and the generated candidate and `config/catalogs/codm.json` to be regular files, rejecting a symlink at either;
  - copies the candidate over `config/catalogs/codm.json`, which keeps mode `100644`;
  - when it differs from `HEAD`, commits only the catalog on a local `automation/codm-catalog` branch created at `HEAD`, as `github-actions[bot]` with its noreply email and with hooks disabled, and writes `git bundle create <dir>/candidate.bundle <base>..HEAD`;
  - writes `changed`, `sha` (the commit SHA) and `base` (`HEAD` before the branch commit) to `GITHUB_OUTPUT`;
  - writes the base SHA, the catalog changes and the retained failures to the step summary and, when changed, to a PR body file that also holds the run URL, with upstream-derived strings HTML-escaped inside a `<pre>` block.

  `scripts/source_proposal.py` serves both jobs, so it follows the write-side runtime rules of 3.4. Verify with tests run in an isolated git environment with no global identity, as in 3.1, for:
  - a changed candidate's bundle holding `HEAD` at the commit with the base as its prerequisite, and a body file holding the run URL and the base SHA; an unchanged candidate writing neither;
  - a changed candidate producing a commit that contains only the catalog, whose author and committer are `github-actions[bot]`, even though `dist/` and `README.md` are later modified in the working tree;
  - an unchanged candidate producing no commit;
  - a symlinked generated candidate, a symlinked `config/catalogs/codm.json`, and a `HEAD` other than `GITHUB_SHA` each failing with no commit or bundle;
  - the base SHA line in the summary naming the commit the branch was created at;
  - retained failures appearing in the summary;
  - a retained failure whose message carries a Markdown-bearing asset name, such as ``[x](https://example.test) ![i](https://example.test/i.png) `y` ``, appearing HTML-escaped inside the `<pre>` block rather than as Markdown.
- [ ] 4.2 Implement `python3 -m scripts.source_proposal publish` for the write job, running every git command with `-c core.hooksPath=/dev/null`. It reads `CHANGED`, `CANDIDATE_SHA` and `BASE_SHA` from its environment, and rejects a `CHANGED` other than `true` or `false` and a SHA that does not match `^[0-9a-f]{40}$`, without echoing the value. It first runs `gh auth setup-git` and requires `git ls-remote origin refs/heads/main` to report the base; otherwise it summarizes `publish failed: main advanced` and exits before any write, on both paths. It then selects the source-update PR with `gh pr list --repo mjkoo/omnipack --head automation/codm-catalog --base main --state open --json number,isCrossRepository,headRepositoryOwner`, keeping only PRs that are not cross-repository and whose head owner is `mjkoo`, and fails before any write when more than one remains. It handles the unchanged case by closing the selected PR, with no tests, build or verification required and no other write. For a changed candidate it requires `HEAD` to be the base, verifies the bundle and fetches its `HEAD`, and requires the fetched commit to be `<sha>`, its only parent to be the base, and `git diff --raw <base> <sha>` to hold exactly one entry, `config/catalogs/codm.json` with mode `100644` on both sides, all before any remote write. It then treats a remote branch absent from `git ls-remote --heads origin refs/heads/automation/codm-catalog` as differing, skips the push when the commit's tree equals the remote branch's tree, force-pushes that commit otherwise, and edits or creates the PR from the body file, which holds the run URL, the base SHA and the catalog change summary, with upstream-derived strings HTML-escaped inside a `<pre>` block. Add the module to the stdlib-only import test, the `py312` per-file target and `just check-py312` from 3.4. Verify with a temporary git repository and bare remote plus stubbed `gh`, with the write-side repository built as in 3.2 (`git init`, a `file://` origin, `git fetch --depth 1 origin <base>`, `git checkout --detach FETCH_HEAD`) and asserted shallow before `publish` runs, and the bundle from a real `stage` commit fetched into it:
  - unchanged closes an open PR and makes no push, PR creation or PR edit;
  - changed with no open PR creates one whose body is the body file, holding the run URL and the base SHA;
  - changed with an open PR edits its body;
  - equal trees make no push, including when the remote branch holds a different hand-made commit whose tree equals the rebuild;
  - a bare remote without the branch ends with the branch at exactly `<sha>` and a PR created;
  - a matching PR from a fork is neither edited nor closed, and a changed candidate creates its own PR;
  - two selected same-repository PRs fail before any write;
  - a bundle whose commit's parent is not the base, a bundle whose `HEAD` is not `<sha>`, a commit that changes a file other than the catalog, a commit that replaces the catalog with a symlink, and a commit that sets the catalog's executable bit each fail before any push or PR write;
  - a remote main other than the base, as for a rerun of an earlier run's write job, closes no PR on the unchanged path and makes no push, PR creation or PR edit on the changed path, and summarizes `publish failed: main advanced`;
  - a `BASE_SHA` or `CANDIDATE_SHA` that is not a full SHA, and a `CHANGED` other than `true` or `false`, fail before any fetch, push or PR write;
  - a Markdown-bearing asset name in the change summary appears HTML-escaped in the PR body.
- [ ] 4.3 Rewrite `.github/workflows/source-catalog.yml`, whose `force` input 1.1 already removed, as two jobs, keeping its guards:
  - workflow level: the `17 4 * * *` schedule, `workflow_dispatch` with no inputs, `permissions: {}`, and concurrency group `omnipack-reviewed-source-catalog` with `cancel-in-progress: false`;
  - both jobs: `if: github.repository == 'mjkoo/omnipack' && github.ref == 'refs/heads/main'`, `runs-on: ubuntu-latest` and `timeout-minutes: 60`;
  - job `check`: `permissions: contents: read`; checkout with `ref: ${{ github.sha }}`, `fetch-depth: 0` and `persist-credentials: false`; `setup-uv` and `uv sync --locked`; generate, stage, then (when changed) `uv run pytest`, `pack build`, `pack verify` and `git diff --quiet "$SHA" -- config/catalogs/codm.json` with `SHA` mapped from the stage step's output in its `env:`, all without a token; when changed, the bundle and the PR body file uploaded with one-day retention; the generation report always uploaded with 14-day retention; job outputs `changed`, `sha` and `base`;
  - job `publish`: `needs: check`, `permissions: contents: write` and `pull-requests: write`, no status function in its condition; checkout with `ref: ${{ github.sha }}`, `fetch-depth: 1` and `persist-credentials: false`; then the guard step running `test "$BASE_SHA" = "$GITHUB_SHA"` with `BASE_SHA` mapped from `needs.check.outputs.base` in its `env:`; no `setup-uv` or `uv sync`; the hand-off downloaded when `changed` is true; `python3 -m scripts.source_proposal publish` with `GH_TOKEN`, `CHANGED`, `CANDIDATE_SHA` and `BASE_SHA` mapped from the check job's outputs in its `env:`, and no `if` condition.

  Verify with actionlint and zizmor, and extend the structured workflow test from 3.5 to this workflow: every property listed above; `GH_TOKEN` only in the publish step, and no step of `check` referencing the job token or a secret; every checkout step setting `persist-credentials: false`; both checkout steps using `ref: ${{ github.sha }}`, and the base guard preceding the download and the publish step; no `run:` containing a `needs.` or `steps.` expression; no `setup-uv` or `uv` step in `publish`; the catalog guard after `pack verify` and before the hand-off upload; and no status function in `publish`'s condition or steps, and in `check` only on the generation report upload, so a failed generation, stage or check step permits no remote write. Verify that `just check-all` passes.

## 5. Documentation

- [ ] 5.1 Add `pkgs.lychee` to the flake devShell next to `pkgs.actionlint` and `pkgs.zizmor`, and a `just check-links` recipe that runs `lychee --offline` over `docs/` and `README.md`. Then rewrite `docs/publishing.md` to cover:
  - the two-job nightly flow and credential split, the bundle hand-off, and the write job's runtime (no project environment, standard library only, the runner's `python3`);
  - permissions and the direct-push prerequisites;
  - the one-off `gh release create` bootstrap, with the exact command and seed body, and that the release must stay a published, mutable prerelease;
  - the digest record, the served-asset digest check and the canonical body each release edit writes;
  - failure and rerun behavior, including the ambiguous-push case, served-asset repair without a revision bump, and that a write job fails without writes once main has moved past its run's base, so recovery is a new dispatch rather than a rerun, which keeps the run's original commit;
  - the step summary lines and the diagnostics artifacts;
  - rollback.

  Verify with `just check-links`, a no-dash check and `nix flake check`.
- [ ] 5.2 Rewrite `docs/source-generation.md` to cover:
  - stateless generation and retained failures;
  - that a transient resolution failure for a project whose update an open proposal carries can close that proposal or drop that update from it, and that the next successful run restores it as a new or updated proposal;
  - that generation keeps no state between runs and has no forced-refresh mode, since every run resolves every project;
  - the proposal workflow's read-only check job, its write job and the hand-off between them, and the bot-branch overwrite, including the force-push command and that a branch whose tree already equals the rebuild is left as it is;
  - the run link and base SHA in the PR body;
  - that the write job writes nothing once main has moved past the run's base, and that a new dispatch, not a rerun, recovers from that failure;
  - that workflow-created PRs get no PR CI, and that a maintainer can close and reopen the PR to run it;
  - the PR-creation setting.

  Verify with `just check-links`.
- [ ] 5.3 Update `docs/verification.md`, `docs/development.md`, `docs/curation.md` and any other guide that mentions the retired pieces. Verify with `just check-links`, and verify that a case-insensitive `git grep` over `docs/`, `README.md` and `AGENTS.md` finds none of these outside archived changes:
  - `codm.source.json`, `package-ids.json` and `package-ID state`;
  - the retired flag and input: `generate-source codm --force`, `--force` standing alone as a code span, and `inputs.force`. Other `--force` uses, such as the bot branch's `git push --force`, stay allowed;
  - `run-result.json`, `bootstrap-release` and `rolling-state`;
  - `validate-evidence`;
  - the retired verification wording: `running record`, `Input changes during`, `incomplete evidence`, `authorize publication` and `fresh structural evidence`.

## 6. Final checks and review

- [ ] 6.1 Run `just check-all` in the dev shell. Then run a live `uv run pack build` and confirm `git diff --exit-code dist/ README.md`, followed by `uv run pack verify`. Finally run `openspec validate standardize-publication --strict`. Verify that all pass.
- [ ] 6.2 Write `openspec/changes/standardize-publication/validation.md` with:
  - the test count against the 771 at the start of this change;
  - the implementation and test line deltas against 8,791 and 12,224;
  - the live generation comparison from 1.6;
  - what remains unestablished: no GitHub run (so no bundle hand-off between real jobs and no write job on the runner's `python3`), no PR, no release write, no device check.
- [ ] 6.3 Run an independent review of the branch diff against the delta specs and design, fix its findings, and re-run 6.1. Verify that the review's final pass reports no unresolved findings.
