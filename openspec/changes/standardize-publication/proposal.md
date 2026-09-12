## Why

Two publishers reimplement what git, `gh` and Actions already provide. Together
they take 3,147 implementation lines and 4,222 test lines:
- nightly publication with its rolling release;
- the source-catalog PR workflow.

Source generation keeps hash-gate and resolution state only to skip about 30
API reads a day.

The source workflow also has a defect that will break its first real PR:
- It opens PRs with the workflow token, so GitHub runs no CI on them.
- It never runs the test suite itself.
- Tests pin the live catalog's exact URLs and counts.

As a result, an automated PR shows no checks, gets merged, and then fails CI
on main. This must land before main is pushed and the source workflow first
runs.

## What Changes

- **Source proposals.**
  - Before pushing the bot branch or creating or editing a PR, the source
    workflow runs the full test suite and then builds and verifies the packs
    with the candidate catalog.
  - The workflow becomes two jobs. A read-only `check` job generates, stages,
    tests, builds and verifies, and hands the exact candidate commit to a
    `publish` job as a git bundle. Only `publish` holds write access. It runs
    from the commit that triggered the run, checks the handed-off commit's SHA,
    parent, paths and file modes, and confirms that main has not moved, all
    before any write.
  - Each run rebuilds one bot branch from main as a single catalog-only commit,
    force-pushes it, and creates or edits one PR from that branch in this
    repository to main. PRs from forks that reuse the branch name are ignored.
  - The PR body links the checking run, names the base commit, and is refreshed
    on every update. Upstream-derived text in the summary and PR body is
    HTML-escaped inside a `<pre>` block.
  - A branch whose tree already equals the rebuild is left as it is.
  - When the candidate equals main, the workflow opens no PR and closes a stale
    one. That close needs no checks.
  - **BREAKING** for maintainers: commits pushed to the bot branch by hand are
    overwritten. Race fencing, ownership provenance and uncertain-write
    reconciliation are removed; one check that main is still the run's base
    replaces the fencing.
- **Stateless generation.**
  - Every run resolves every project afresh from the README, the policy and
    fresh APK inspection.
  - A project already in main's catalog that fails to resolve keeps its
    committed entry, reported as a retained failure, when the current policy
    still renders that same entry: an APK rule with the committed package ID,
    a tracker rule with its own tracker ID. A failure after a policy change,
    including a changed tracker ID, or for a new project, blocks the proposal. The rendered entry takes over the policy
    fingerprint's job without any stored state.
  - Because retention uses main's entry, a transient failure for a project
    whose update an open PR carries can drop that update or close the PR. The
    next successful run proposes it again.
  - A PR opens only when `config/catalogs/codm.json` changes, so README prose
    edits no longer need a PR.
  - **BREAKING**:
    - `config/catalogs/codm.source.json` and `config/package-ids.json` are
      deleted;
    - `pack generate-source codm --force` and the workflow's `force` input are
      removed;
    - policy fingerprints and the `legacy_default_projects` bootstrap are
      removed.
- **Nightly.** A short workflow of two jobs and two small scripts. A read-only
  `prepare` job builds, checks the allowlist and README boundary, commits
  locally, verifies, and hands the exact commit to a `publish` job as a git
  bundle. `publish` checks out the same revision, confirms the commit's SHA,
  parent, paths and file modes and that main has not moved, makes a normal
  push of it and runs the release step, which also writes nothing once main
  has moved.
  Each summary line belongs to one step. Removed:
  - the verification-evidence freshness protocol and its subprocess;
  - remote-history reconciliation after a rejected or ambiguous push, which
    reverses an earlier decision to keep it;
  - the snapshot-based mode and symlink checks, which become one regular-file
    check on each side of the hand-off;
  - `run-result.json`, redaction and custom reporting. A short step summary
    replaces them.
- **Credentials, both workflows.**
  - The write credential is available only to the write job. Every step of the
    read-only job, including checkout and setup-uv, runs with a job token that
    can only read contents, and no checkout persists a credential.
  - Both jobs check out the commit that triggered the run (`github.sha`), and
    the write job fails unless the check job built on it, so no check-job
    output selects the code that runs with the token. Check-job outputs reach
    scripts only through step environment variables and must be full 40-hex
    SHAs.
  - The write job runs no setup-uv or `uv sync`. Its scripts import only the
    standard library and run on the runner's preinstalled `python3` (3.12),
    guarded by a stdlib-only import test, ruff's `py312` target for those
    files and a test run under CPython 3.12. Its git commands run with hooks
    disabled.
  - This replaces one job per workflow, in which build and test steps shared a
    workspace with the token-bearing steps. It costs about 20 to 40 seconds a
    run and a hand-off of at most about 770 KB.
- **Rolling release.**
  - The release body is fixed text with one line recording both JSON digests
    and the source commit. Each edit rewrites the whole body.
  - The release step compares the run's pair with that record and with GitHub's
    reported digests of the two served assets.
  - When the record differs, the release step replaces both assets with
    `gh release upload --clobber`, then bumps the title and records the new
    digests in one edit.
  - When only a served asset differs, is missing or has no digest, it
    re-uploads both assets without a bump.
  - The release step writes nothing unless main is still at the run's commit,
    so a rerun of an old run's write job cannot publish an older pair under a
    new revision.
  - The ownership marker check stays, and the release must be a published,
    mutable prerelease: a draft, a non-prerelease or an immutable release
    fails the release step without writes. Bootstrap becomes a documented
    one-off `gh release create`.
  - Removed: pending state, post-upload readback, the bounded retrying
    transport, ambiguous-write reconciliation and the bootstrap subcommand.
- **Verification.**
  - `pack verify` checks one captured set of inputs and writes its report
    once.
  - The report stays a diagnostic that `pack report` uses for staleness. It no
    longer authorizes publication.
  - The running record and in-run change detection are removed.
- **Tests and dead code.**
  - The live-catalog pin tests become invariants that hold for any valid
    catalog.
  - `validate_generation_output` is removed; the candidate gets the test suite,
    a build and structural verification instead.
  - `validate_candidate`, the `SyncResult` fields, the duplicated source
    publication checks and the YAML substring tests go with their modules.
  - The nightly spec no longer mentions "Python packaging" checks.
  - Resolution-state and cached package-ID wording is swept from the pack-cli,
    pack-verification and source-ingestion specs.

**Retired, in total:**
- **Files:** the seven `scripts/nightly*.py` modules, `scripts/source_publication.py`,
  the two state files, and about 250 lines of generation state handling.
- **Spec requirements:**
  - the README and policy gate;
  - accepted resolution state;
  - resumable and bounded release synchronization;
  - "Main publication uses one refresh attempt", which is replaced.

**Size estimate:**
- **Specs:** 2 requirements added, 22 modified and 4 removed. Across the six
  touched specs, scenarios go from 172 to 186.
- **Implementation:** about 3,400 lines retired and 440 added (three scripts of
  about 100, 160 and 180 lines, plus workflow YAML). That takes `src/` and
  `scripts/` from 8,791 to about 5,800 lines.
- **Tests:** about 4,600 lines retired and 600 added. That takes `tests/` from
  12,224 to about 8,200 lines.

**"Would a visible failure plus a rerun suffice?"** The review rule asks this of
each requirement on retries, ownership, races, diagnostics or evidence that
this change adds or keeps:
- **Retained entries for known projects:** no. Failing the whole run on one
  broken upstream would block every other catalog update until the README
  changed. Retries themselves need no machinery, because the daily run is the
  retry.
- **The single normal push:** yes, and that is what the requirement now says.
- **Release interruption:** yes. The next run compares both the record and
  GitHub's digests of the served assets with its verified pair, and re-uploads
  on any mismatch. Checking the served assets is what lets it repair a mixed
  pair when its pair returns to the recorded one, at the cost of one more field
  in the same `gh release view`.
- **The release ownership marker check:** no. A rerun cannot undo an overwrite
  of a release this project does not own.
- **Pushing the checked local commit, guarded by one `git diff`:** no. Without
  it, a test that rewrote the catalog would produce an unchecked PR rather than
  a visible failure. The guard is one git command.
- **Retained failures in the run summary:** kept as a plain list. It is the only
  signal that an entry is stale.
- **The write job's SHA, parent, path and mode checks on the handed-off
  commit:** no. A rerun cannot take back a push of the wrong commit to main or
  the bot branch, or a public upload of a runner file that a symlinked allowed
  file names. The checks are three git commands.
- **The write jobs' check that main has not moved:** no. A rerun of an old
  write job would publish an older pack pair under a new revision, which the
  tracker announces as an update, or close or replace a newer proposal. The
  check is one `git ls-remote`.
- **The release's published-prerelease check:** no. Uploading to a draft
  release would report a new revision while the stable URLs serve nothing, and
  later runs would report it unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `nightly-publishing`: publication becomes one normal push with no remote-history reconciliation. A read-only job builds and verifies, then hands the exact commit to a write job, which alone holds the write token, installs nothing from the project, runs from the triggering revision, checks the commit's SHA, parent, paths and file modes before pushing it, and writes nothing once main has moved past the run's base. A step summary replaces `run-result.json`, and the snapshot-based mode and symlink checks shrink to one regular-file check on each side of the hand-off.
- `rolling-pack-release`: the release writes a fixed body with a digest record. A later run compares that record and GitHub's served-asset digests with its verified pair, so it repairs an interrupted sync or mismatched assets, without a revision bump when the pair is already recorded. The routine check also requires a published, mutable prerelease, and no release write happens once main has moved past the run's commit. The separate resumable-and-bounded synchronization requirement, with its retries and ambiguous-write reconciliation, is removed, and bootstrap becomes a documented one-off command.
- `readme-source-generation`: generation becomes stateless with retained-entry fallback, and the README and policy gate and accepted resolution state are removed. The test suite runs before any branch push or PR creation or edit, while closing a stale PR needs no checks. Checks run in a read-only job, and a write job that installs nothing from the project and runs from the triggering revision pushes the exact checked commit, whose catalog must be a regular file, and writes the PR only while main is still the run's base. The bot branch is rebuilt each run and left alone when its tree already matches, its PR is limited to this repository's branch, and its PR body links the run and names the base commit with upstream text escaped. A transient failure can revert an open proposal until the next successful run. State-model wording changes in the policy, package-ID and track-only requirements, and a tracker's retention uses its rule's tracker ID.
- `pack-verification`: the verification report is a diagnostic of one captured input set. The running record, in-run change detection, publication authorization and the cached package-ID wording are removed.
- `pack-cli`: `pack generate-source codm` loses `--force` and the unchanged no-op, always generates a full candidate, and persists no state. The build, build-failure and verify requirements drop their resolution-state and package-ID update wording.
- `source-ingestion`: the canonical-location, HTTP-credential, URL-normalization and failed-fetch requirements drop the resolved-ID cache and resolution state. The shared HTTP helper owns ingestion and discovery requests, while release and PR operations use `gh` and branch pushes use `git`.

## Impact

- **Code:**
  - `scripts/nightly.py` is rewritten to hold `prepare`.
  - New `scripts/nightly_write.py` (push and release) and
    `scripts/source_proposal.py` are added. Both import only the standard
    library and run on Python 3.12 or later.
  - Deleted: `scripts/nightly_git.py`, `nightly_publish.py`,
    `nightly_release.py`, `nightly_release_sync.py`,
    `nightly_release_transport.py`, `nightly_reporting.py` and
    `source_publication.py`.
  - `src/omnipack/source_generation.py`, `project_policy.py`, `cli.py` and
    `verify.py` change.
- **Config:** `config/catalogs/codm.source.json` and `config/package-ids.json`
  are deleted.
- **Workflows:** `.github/workflows/nightly.yml` and `source-catalog.yml` are
  rewritten as a read-only job plus a write job each, adding a SHA-pinned
  `actions/download-artifact`. `.github/workflows/ci.yml` gains a step that
  runs the write-side tests under the runner's `python3`.
- **Tests:**
  - Deleted: `tests/test_nightly_*.py`, `test_source_publication.py` and
    `test_source_workflow.py`.
  - Rewritten in part: `test_source_generation*.py` and `test_verify.py`.
  - The `package-ids.json` bindings leave `tests/test_cli.py` and
    `tests/test_verification_integration.py`.
  - New tests for the three scripts, including the bundle round trip, a
    stdlib-only import test, and one structured workflow test.
- **Tooling:** `flake.nix` adds `lychee` to the devShell and the `justfile`
  adds a `check-links` recipe for the docs, and a `check-py312` recipe that
  runs the write-side tests under CPython 3.12. `pyproject.toml` sets ruff's
  `per-file-target-version` to `py312` for the two write-side modules.
- **Docs:**
  - `docs/publishing.md` and `docs/source-generation.md` are rewritten.
  - Publication and state references change in `docs/verification.md`,
    `docs/development.md` and `docs/curation.md`.
- **External behavior:**
  - Bot-branch hand edits are overwritten.
  - Generation makes about 30 GitHub API reads a day, plus APK range reads.
  - Each workflow run takes about 20 to 40 seconds longer.
- **Dependencies:** PyYAML is added to the `test` dependency group only, for
  the structured workflow test, which changes `pyproject.toml` and `uv.lock`.
  Runtime dependencies stay empty. The workflows rely on the `gh` CLI and the
  `python3` (3.12 on ubuntu-latest) preinstalled on GitHub-hosted runners, and
  `just check-py312` takes CPython 3.12 from nixpkgs locally.
