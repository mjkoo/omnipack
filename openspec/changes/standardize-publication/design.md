## Context

See proposal.md for motivation. The current state that shapes the design:

- **Nightly** (`.github/workflows/nightly.yml`) runs one Python entry point,
  `scripts/nightly.py publish`. It drives seven modules (about 2,060 lines):
  - its own git remote wrapper, with remote-history reconciliation;
  - two hand-written GitHub HTTP clients, with duplicated redirect handlers;
  - the verification-evidence freshness checks and a `--validate-evidence`
    subprocess;
  - mode and symlink checks;
  - `run-result.json` and redaction reporting;
  - a rolling-release state machine with pending state, post-upload readback
    and a bootstrap subcommand.
- **The source workflow** (`.github/workflows/source-catalog.yml`) runs three
  steps of `scripts/source_publication.py` (1,087 lines): `observe`, `check`
  and `publish`. That module imports nightly's HTTP client and redaction but
  reimplements its git, push, staging and reporting code. It opens PRs with
  `github.token`, so GitHub starts no `pull_request` CI for them, and it never
  runs the test suite.
- **Generation** (`src/omnipack/source_generation.py`):
  - gates on `config/catalogs/codm.source.json`, which binds the README hash,
    the policy hash and the catalog digest;
  - reuses package IDs from `config/package-ids.json`, keyed by release ID and
    policy fingerprint;
  - re-checks its own output with `validate_generation_output` (about 130
    lines).

  The build reads neither state file; it reads only
  `config/catalogs/codm.json`, which has no metadata.
- **`pack verify`** writes `.build/verify.json` with fingerprints and verifier
  identity. `pack report` uses them to label a report stale, and nightly uses
  them as a publication authorization.
- **Rolling release.** The omnipack tracker in `config/extras.json` matches only
  the release title `^omnipack revision [0-9]+$`, so bumping the title is the
  whole notification mechanism.
- **Workflow guards.** Each workflow today is one job guarded by
  `github.repository == 'mjkoo/omnipack' && github.ref == 'refs/heads/main'`,
  with workflow-level `permissions: {}`, a non-canceling concurrency group
  (`omnipack-nightly-publisher`, `omnipack-reviewed-source-catalog`),
  `timeout-minutes: 60` and a full-history checkout of `ref: main`. Nightly is
  scheduled at `0 3 * * *` in America/New_York and the source workflow at
  `17 4 * * *` UTC, both with manual dispatch. The single job holds
  `contents: write` (and, for the source workflow, `pull-requests: write`) for
  every step, including the build.
- **Runners.** GitHub-hosted runners provide `git`, `gh` and a preinstalled
  `python3`, which is 3.12 on the ubuntu-latest image, while `pyproject.toml`
  requires Python 3.14, which `setup-uv` installs for the project environment.
  `actions/checkout` cleans ignored files by default, so each run starts
  without a previous run's `.build/`.
- **Imports.** Today's write-side code is not self-contained:
  `scripts/nightly_publish.py` imports `omnipack.catalog`, `omnipack.report`
  and `omnipack.verify`, and `scripts/source_publication.py` imports
  `omnipack.source_generation`. Only the release and reporting modules import
  nothing outside the standard library and `scripts`.

## Goals / Non-Goals

**Goals:**

- Every GitHub write goes through `git` or `gh`, from a small script that is
  easy to test.
- The write credential is available only to the write job. Every step of the
  read-only check job, including checkout and `setup-uv`, runs with a job token
  limited to `contents: read`, and no step there receives `GH_TOKEN`. The
  write job installs nothing from the project and runs only standard-library
  scripts from a fresh checkout of the triggering revision, `github.sha`, which
  no check-job output can change, so nothing that a build, generation, test or
  upstream input writes can run with the token. Every checkout sets
  `persist-credentials: false`.
- Nightly still publishes only bytes verified in the same run, within the
  allowlist and the README boundary.
- No write job writes anything once main has moved past its run's base, so a
  rerun of an old run cannot publish an older pack pair or close or replace a
  newer proposal.

**Non-Goals:**

- The composition-side simplifications, which belong to the follow-up
  composition change:
  - history records;
  - one-pass policy;
  - the app model;
  - `offline.py` trimming;
  - configuration generality;
  - build-report compatibility.
- Moving per-app wording (Heimdall, Kanto) out of the source-generation specs.
  This change touches those requirements only where the state model changes.
- A GitHub App or personal token for CI on bot PRs.
- Changing either schedule, the allowlist, or the rolling release's tag, asset
  names or title format.

## Decisions

### 1. GitHub writes use `git` and `gh`

Both publishers use four kinds of command: `git push`, `gh release
view/upload/edit`, `gh pr list/create/edit/close`, and `gh auth setup-git` to
hand the step's token to git. `gh` is preinstalled on GitHub-hosted runners and
reads `GH_TOKEN` from the step environment. Only the write job of each workflow
runs these commands; see decision 6.

Alternatives considered:
- Keeping the Python clients: they are the duplication this change removes.
- A third-party create-pull-request action: it adds another pinned action that
  receives a write token, only to replace a handful of `gh` calls.

### 2. Nightly workflow shape and credential split

The nightly workflow keeps its triggers and guards: the `0 3 * * *` schedule in
America/New_York plus `workflow_dispatch`, workflow-level `permissions: {}`,
and the `omnipack-nightly-publisher` concurrency group with
`cancel-in-progress: false`, which serializes whole runs. It has two jobs, each
with the job-level condition `github.repository == 'mjkoo/omnipack' &&
github.ref == 'refs/heads/main'`, `runs-on: ubuntu-latest` and
`timeout-minutes: 60`.

**Job `prepare`**, with `permissions: contents: read` and no `GH_TOKEN`:

1. **Checkout** with `ref: ${{ github.sha }}`, `fetch-depth: 0` and
   `persist-credentials: false`, then `setup-uv` and `uv sync --locked`.
2. **`uv run --no-sync python -m scripts.nightly prepare`**:
   - reject a dirty checkout, or a `HEAD` other than `GITHUB_SHA`;
   - run `pack build`;
   - reject any tracked change outside the three allowed paths, and any
     missing allowed file (`git status --porcelain`);
   - reject any allowed path that is not a regular, non-executable file
     (checked with `lstat`), so a symlink or an executable-bit change fails the
     allowlist stage and every committed allowed file has mode `100644`;
   - check the README boundary against `HEAD:README.md`;
   - commit the allowed files locally when any changed;
   - run `pack verify`;
   - require `git status --porcelain` to be empty again, so the verified
     working tree is exactly the local commit;
   - when it committed, confirm that `HEAD` is the commit and write `git
     bundle create <dir>/candidate.bundle <base>..HEAD`.

   It writes `changed=true|false`, `sha` (the commit, or `HEAD` for a no-op)
   and `base` (`HEAD` at checkout) to `GITHUB_OUTPUT`, and the job exports them
   as outputs. Its step summary line is `no-op at <sha>`, `prepared <sha>`, or
   the failing stage: checkout (dirty, or not at `GITHUB_SHA`), build,
   allowlist (including file modes), README boundary, verify, drift after
   verify, or bundle.
3. **Upload the bundle** when `changed` is true, with one-day retention.
4. **Upload** `.build/report.json` and `.build/verify.json`, always, with
   14-day retention.

**Job `publish`**, with `needs: prepare`, `permissions: contents: write`, and
the same job condition with no status function, so Actions' implicit success
gate runs it only when `prepare` succeeded:

1. **Checkout** with `ref: ${{ github.sha }}`, `fetch-depth: 1` and
   `persist-credentials: false`. There is no `setup-uv` and no `uv sync`.
2. **Guard** the base: with `BASE_SHA: ${{ needs.prepare.outputs.base }}` in
   the step's `env:`, run `test "$BASE_SHA" = "$GITHUB_SHA"`, so the job fails
   before the download and every token-bearing step unless `prepare` built on
   the triggering revision.
3. **Download the bundle** when `needs.prepare.outputs.changed == 'true'`.
4. **`python3 -m scripts.nightly_write push`**, with `GH_TOKEN`, gated only on
   `needs.prepare.outputs.changed == 'true'`, with no status function in its
   condition. It reads `CANDIDATE_SHA` and `BASE_SHA` from its `env:`, which
   map prepare's `sha` and `base` outputs, and rejects either unless it matches
   `^[0-9a-f]{40}$`, summarizing `push failed` without echoing the value. It
   runs every git command with `-c core.hooksPath=/dev/null`, and:
   - requires `HEAD` to be `<base>`, then runs `git bundle verify` and fetches
     the bundle's `HEAD`;
   - requires the fetched commit to be `<sha>`, its only parent to be
     `<base>`, and every entry of `git diff --raw <base> <sha>` to name one of
     the three allowed paths with mode `100644` on both sides, so a symlink
     (`120000`), a gitlink (`160000`), an addition, a deletion or a mode change
     fails;
   - runs `gh auth setup-git`, requires `git ls-remote origin
     refs/heads/main` to report `<base>`, and runs `git push origin
     <sha>:refs/heads/main`;
   - detaches to `<sha>`, so `dist/` holds exactly the verified bytes, as
     regular files.

   On success it appends `published <sha>` to the step summary. When any of
   these fails it appends `push failed for <sha>`, or `push failed for <sha>:
   main advanced` when main has moved past `<base>`, and exits nonzero, and
   Actions then skips the release step. A rejected hand-off fails before any
   push.
5. **`python3 -m scripts.nightly_write release`**, with `GH_TOKEN`, no
   check-job output and no `if` condition, so Actions' implicit success gate
   runs it only when the push succeeded or was skipped; see decision 4. For a
   no-op it runs on the base checkout, which is the main revision that
   `prepare` verified, and it writes nothing unless main is still that
   revision.

Every step summary line has one owner. The main outcome comes from prepare
(no-op or a failing stage) or from the push step (published or push failure),
and the release outcome comes from the release step alone, so a release failure
after a push shows the pushed commit on its own line. Summary lines hold only
SHAs, revision numbers and fixed text, plus the release step's failure reason.

The commit subject keeps the current conventional form. The body identifies
the run URL and the base SHA.

Both publishers commit with `git -c user.name=github-actions[bot] -c
user.email=41898282+github-actions[bot]@users.noreply.github.com -c
core.hooksPath=/dev/null commit`, as the current code does. GitHub-hosted
runners have no configured git identity, and automation commits must not run
repository hooks. The write jobs disable hooks on every git command for the
same reason, and because those commands run with the token.

`prepare` stays in `scripts/nightly.py`, runs in the synced environment and may
import `omnipack`: the README boundary uses `omnipack.catalog`. `push` and
`release` live in `scripts/nightly_write.py`, which must run on the runner's
`python3`; see decision 6.

Why a script and not inline shell: the allowlist, the README boundary, the
hand-off checks and the digest logic are the parts worth testing, and tests
that assert workflow YAML text only detect changes; they do not check
behavior.

### 3. Binding publication to verification with a local commit

Both publishers commit locally in the read-only job before their checks, and
the write job pushes that exact commit afterwards. A commit is
content-addressed, so the pushed SHA names exactly the bytes that existed when
the checks started. A clean `git status`, or `git diff --quiet <sha>`, after the
checks shows that the working tree did not drift while they ran. Beyond that,
the publishers trust the checks' exit status.

The job split keeps this binding across checkouts. The read-only job hands the
commit to the write job as a git bundle and names it in its `sha` output. The
write job fetches the bundle's `HEAD` into a fresh checkout of `<base>`, and
requires the fetched commit to equal `<sha>` and its only parent to equal
`<base>`. Git checks object hashes on fetch, so the commit the write job pushes
is byte for byte the one the checks read. The write job runs only when the
read-only job succeeded, which stands in for the verification result. A local
probe showed that `git bundle create` refuses a range ending in a raw SHA as an
empty bundle, because a bundle records refs, so the read-only job bundles
`<base>..HEAD` after confirming that `HEAD` is `<sha>`.

The evidence file only restated the exit status plus byte equality. Across the
split, the SHA check provides the byte equality, and the job dependency the
exit status.

Alternatives considered:
- Hashing the files in Python before verification and comparing them
  afterwards, or passing a digest through a step output: both reimplement what
  git's object store already provides.
- Uploading the changed files and committing them in the write job: the write
  job would push a commit that no check read, and would need its own allowlist
  and boundary logic to trust the files.
- Re-running `pack verify` in the write job: it needs the project environment,
  which the write job must not install.

### 4. Release digest record and served-asset digests

The `release` step writes the whole release body on every edit, from a fixed
template:
- the ownership marker `<!-- omnipack:rolling-pack -->`;
- fixed descriptive text naming the stable download URLs,
  `https://github.com/mjkoo/omnipack/releases/download/continuous/single-screen.json`
  and the matching `dual-screen.json` URL;
- one record line:

  ```
  <!-- omnipack:digests single-screen.json=<sha256> dual-screen.json=<sha256> commit=<sha> -->
  ```

Prior body text is discarded, including the seed's "not yet published"
statement and any rolling-state block left by the old bootstrap. The seed body
is documented separately in `docs/publishing.md`.

The `release` step runs in the write job on the runner's `python3`, with
`hashlib` and `gh`. It works as follows:
1. Hash the two JSON files at `HEAD`. In the write job `HEAD` is `<sha>` after
   the push step's detach, or `<base>` for a no-op, and the checkout is fresh,
   so the working-tree files the upload sends are the bytes it hashed. They
   are regular files: `<base>` is the triggering main revision, and the push
   step accepted only mode `100644` entries in `<sha>`.
2. Run `gh auth setup-git` and require `git ls-remote origin refs/heads/main`
   to report `HEAD`. Otherwise write `release failed: main advanced` and stop
   before any write, without the bootstrap guidance. A rerun of an old run's
   write job therefore cannot upload an older pair and advance the revision.
3. Run `gh release view continuous --json
   name,body,assets,isDraft,isPrerelease,isImmutable`; gh 2.100.0 returns all
   three state fields. For each asset, `digest` is `sha256:<hex>` of the
   uploaded bytes (checked with gh 2.100.0 against `shasum -a 256` of the
   downloaded asset).
4. Require the marker, a title matching `^omnipack revision ([0-9]+)$`, and a
   published mutable prerelease: `isDraft` false, `isPrerelease` true and
   `isImmutable` false. `gh release view` also finds drafts, whose stable
   download URLs serve nothing, so a draft fails here rather than receiving
   assets.
5. Compare the record line with the hashes, and each served asset's `digest`
   with its hash. A missing asset, or a null or absent `digest`, is a mismatch.
6. When the record and both served digests match, write `unchanged at revision
   N` to the step summary and stop.
7. When the record matches but a served digest does not, run `gh release upload
   continuous dist/single-screen.json dist/dual-screen.json --clobber`, make no
   edit, and write `repaired at revision N`. The title revision does not
   advance, because the pair it names is already the recorded one.
8. When the record differs, or there is none, run the same upload, then one
   `gh release edit continuous --title "omnipack revision N+1" --notes-file
   <body>` with the canonical body carrying the new record, and write
   `revision N+1`.

Any failure writes `release failed: <reason>` and fails the step. A missing
release, a missing marker, a malformed title, a draft, a release that is not a
prerelease, or an immutable release fails before any write and adds the
bootstrap guidance: the documented `gh release create` command in
`docs/publishing.md`.

The body record keeps the source commit and the revision bookkeeping. GitHub's
per-asset digests check what is actually served.

Consequences:
- An interrupted upload leaves the old record. The next run with the new pair
  repeats both uploads and bumps once. A next run whose pair returns to the
  recorded one finds a served-digest mismatch and restores both assets without
  a bump.
- Assets deleted or replaced by hand are restored by the next run, also without
  a bump.
- A lost edit response is harmless, because the next run finds a matching
  record and matching served digests.
- The seed carries no record, so its first sync bumps it from 0 to 1 and
  replaces its body with the canonical one.
- A write job whose main has moved on, such as a rerun of an earlier run's
  write job, fails before any release write, so the release never moves back
  to an older pair. The next run on the newer main synchronizes it.

Bootstrap becomes a documented one-off `gh release create continuous
--prerelease --title "omnipack revision 0"` with a notes file that contains the
marker.

Alternatives considered:
- GitHub's per-asset `digest` alone, without a body record: the record carries
  the source commit and the revision bookkeeping, and it tells the last
  completed pair apart from an interrupted target.
- The body record alone: it describes the last completed pair, not the served
  assets. An interrupted upload followed by a run whose pair returns to the
  recorded one would report "unchanged" over mixed assets.
- Invalidating the record before each upload: one extra edit per change, and it
  still misses assets deleted or replaced by hand.
- Keeping the existing body and replacing only the record line: the seed's "not
  yet published" statement would stay on the public release page.

### 5. Source proposal flow

The source workflow keeps its guards: the `17 4 * * *` schedule plus
`workflow_dispatch` (with no inputs once `force` is gone), workflow-level
`permissions: {}`, and the `omnipack-reviewed-source-catalog` concurrency group
with `cancel-in-progress: false`. It has two jobs, each with the job-level
condition `github.repository == 'mjkoo/omnipack' && github.ref ==
'refs/heads/main'`, `runs-on: ubuntu-latest` and `timeout-minutes: 60`.

**Job `check`**, with `permissions: contents: read` and no `GH_TOKEN`:

1. **Checkout** with `ref: ${{ github.sha }}`, `fetch-depth: 0` and
   `persist-credentials: false`, then `setup-uv` and `uv sync --locked`.
2. **`pack generate-source codm`.** Generation stays unauthenticated, as it is
   today, and makes about 30 API reads a day.
3. **`uv run --no-sync python -m scripts.source_proposal stage`**:
   - require `HEAD` to equal `GITHUB_SHA`, and require the generated
     `.build/source-generation/codm/catalog.json` and
     `config/catalogs/codm.json` to be regular files, rejecting a symlink at
     either;
   - copy the generated catalog over `config/catalogs/codm.json`, which keeps
     its mode `100644`;
   - when it differs from `HEAD`, commit only that file on a local
     `automation/codm-catalog` branch created at `HEAD`, with the bot identity
     and hooks disabled as in decision 2, and write `git bundle create
     <dir>/candidate.bundle <base>..HEAD`;
   - write `changed`, `sha` (the commit SHA) and `base` (`HEAD` before the
     branch commit) to `GITHUB_OUTPUT`, exported as job outputs;
   - write the base SHA, the catalog changes and the retained failures to the
     step summary and, when changed, the same content with the run URL to a PR
     body file.

   Project URLs, retained-failure messages, asset names and other
   upstream-derived strings go into the summary and the body file HTML-escaped
   inside a `<pre>` block, as the current publisher does with `html.escape`, so
   upstream Markdown renders as literal text.
4. **When changed, `uv run pytest`.** Tests run before the build, which mirrors
   CI on main right after a merge: new catalog, old `dist/`.
5. **When changed, `pack build` and `pack verify`.** Their outputs stay
   unstaged diagnostics.
6. **When changed, `git diff --quiet "$SHA" -- config/catalogs/codm.json`**,
   with `SHA` mapped from the stage step's `sha` output in the step's `env:`,
   so the catalog the checks read is the committed one.
7. **When changed, upload the bundle and the PR body file**, with one-day
   retention. Actions' implicit success gate uploads them only when steps 2 to
   6 succeeded.
8. **Upload** the generation report, always, with 14-day retention.

**Job `publish`**, with `needs: check`, `permissions: contents: write` and
`pull-requests: write`, and the same job condition with no status function:

1. **Checkout** with `ref: ${{ github.sha }}`, `fetch-depth: 1` and
   `persist-credentials: false`. There is no `setup-uv` and no `uv sync`.
2. **Guard** the base as in nightly: `test "$BASE_SHA" = "$GITHUB_SHA"`, with
   `BASE_SHA` mapped from `needs.check.outputs.base` in the step's `env:`.
3. **Download** the bundle and the body file when `changed` is true.
4. **`python3 -m scripts.source_proposal publish`**, with `GH_TOKEN` and no
   `if` condition. It reads `CHANGED`, `CANDIDATE_SHA` and `BASE_SHA` from its
   `env:`, and rejects a `CHANGED` other than `true` or `false`, a `BASE_SHA`
   and, when changed, a `CANDIDATE_SHA` that does not match `^[0-9a-f]{40}$`,
   without echoing the value. It runs every git command with `-c
   core.hooksPath=/dev/null`.

   It first runs `gh auth setup-git` and requires `git ls-remote origin
   refs/heads/main` to report `<base>`. Otherwise it writes `publish failed:
   main advanced` and exits before any write, on either path, so a rerun of an
   old run's write job cannot close a newer proposal or force-push an older
   catalog.

   It then selects the source-update PR with `gh pr list --repo mjkoo/omnipack
   --head automation/codm-catalog --base main --state open --json
   number,isCrossRepository,headRepositoryOwner`, keeping only PRs whose
   `isCrossRepository` is false and whose head owner is `mjkoo`. `--head`
   matches the branch name alone, so a fork PR whose branch shares the name is
   dropped here and is never edited or closed. When more than one PR remains,
   the step fails before any write.

   When the candidate is unchanged, publish closes the selected PR, if any.
   The close needs no tests, build or verification: a successful generation
   that reproduced main's catalog shows the proposal is stale. It is the only
   write on this path.

   Otherwise it:
   1. requires `HEAD` to be `<base>`, runs `git bundle verify`, fetches the
      bundle's `HEAD`, and requires the fetched commit to be `<sha>`, its only
      parent to be `<base>`, and `git diff --raw <base> <sha>` to hold exactly
      one entry, `config/catalogs/codm.json` with mode `100644` on both sides,
      all before any remote write;
   2. runs `git ls-remote --heads origin
      refs/heads/automation/codm-catalog`. An absent branch, as on the first
      changed run or after a merge deletes it, counts as differing trees and
      goes straight to the push. Otherwise it fetches the branch tip and skips
      the push when `<sha>^{tree}` equals the remote branch's tree. Tree
      equality is the authority: a branch whose tree equals the rebuild, such
      as one where a maintainer merged main into it, is left as it is even
      though its commits differ;
   3. otherwise runs `git push --force origin
      <sha>:refs/heads/automation/codm-catalog`;
   4. edits the selected PR's body, or creates the PR with `--base main --head
      automation/codm-catalog`, from the body file.

   The PR body holds the run URL, the base SHA and the catalog change summary,
   with upstream-derived strings HTML-escaped inside a `<pre>` block as in
   the stage summary. The body file is data for `gh`; publish does not
   interpret it.

The pack validation outcome is the result of the pytest, build and verify
steps in the run that the PR body links; no separate record restates it.

Committing in the stage step fixes the pushed commit before any test runs. The
one `git diff` guards against a test that rewrites the catalog in the working
tree, the SHA and parent checks bind the write job's push to that commit, and
the main check keeps a write job whose base is no longer main from writing.
Together they replace the old fencing.

`scripts/source_proposal.py` serves both jobs, so the whole module follows the
write-job runtime rules in decision 6. `stage` needs nothing from `omnipack`:
it copies a file, commits it and renders JSON reports.

### 6. Read-only check jobs, write jobs and the hand-off

Each workflow runs its project code in a read-only job and its GitHub writes in
a separate write job. This replaces one job whose steps shared one workspace:
there, anything a tokenless step wrote to `.git/hooks`, `.git/config` (a
`core.fsmonitor` command or a credential helper, for example) or the
virtualenv would later run in a step that had `GH_TOKEN`.

- **Permissions.** Workflow-level `permissions: {}`. The check job holds
  `contents: read`, so every step there, including checkout and `setup-uv`,
  sees only a read-only job token. Only the write job holds `contents: write`
  (and, for the source workflow, `pull-requests: write`), and only its push,
  release and publish steps receive `GH_TOKEN`.
- **Hand-off.** The check job's outputs carry `changed`, `sha` and `base`.
  When changed, a `git bundle` of `<base>..HEAD`, holding only the candidate
  commit, its trees and its changed blobs, travels as a one-day artifact, with
  the source workflow's escaped PR body beside it. The diagnostics stay in the
  check job's own 14-day artifacts. The download uses a SHA-pinned
  `actions/download-artifact`, like the other actions.
- **Pinned revision.** Both jobs check out `${{ github.sha }}`, the main commit
  that triggered the run; the job condition already requires `refs/heads/main`
  in the canonical repository. The check job requires `HEAD` to equal
  `GITHUB_SHA` and reports it as `base`. The write job checks out the same
  commit, shallowly and with `persist-credentials: false`, and its first step
  after checkout fails unless the check job's `base` output equals
  `github.sha`. No check-job output selects a ref, so the scripts the write job
  runs with the token come from the triggering revision, and a commit that
  lands on main between the jobs changes neither them nor the parent check.
- **Outputs as data.** Check-job outputs reach the write job's scripts only
  through step `env:`, never through a `${{ }}` expression inside `run:`, so an
  output cannot inject shell. The scripts reject a SHA that does not match
  `^[0-9a-f]{40}$` and a `changed` other than `true` or `false`, and never
  echo a rejected value into the summary.
- **Main has not moved.** Before its first remote write, each token-bearing
  step runs `git ls-remote origin refs/heads/main` and requires `<base>`, or
  `HEAD` for nightly's release step, which is `<sha>` after this run's push.
  Otherwise it fails without writes. Actions' "Re-run failed jobs" reuses the
  earlier check job's outputs, and a no-op needs no bundle, so the one-day
  artifact retention does not bound a rerun. This check keeps such a rerun, or
  any write job that starts after main moved, from publishing an older pack
  pair under a new revision or closing or replacing a newer proposal.
- **Checks on the hand-off.** Before any remote write the write job requires
  the fetched commit to be `<sha>`, its only parent to be `<base>`, and every
  entry of `git diff --raw <base> <sha>` to be one of that workflow's allowed
  files with mode `100644` on both sides. The check job already rejects a
  non-regular allowed file; the write job repeats the allowlist and the mode
  rule in one git command, because `git diff --name-only` reports a symlink
  or mode change under the allowed name. This keeps nightly's detach to
  `<sha>` from changing anything but the regular files
  `dist/single-screen.json`, `dist/dual-screen.json` and `README.md` under the
  `python3` that then runs the release step. A compromised check job can
  therefore propose only bad bytes in regular allowed files. It cannot choose
  the code the write job runs, inject shell through an output, point the
  token-bearing release step at a runner file such as `/proc/self/environ`
  through a symlink, or make the write job act on a main that has moved.
- **Runtime.** The write job runs no `setup-uv` and no `uv sync`. Its scripts,
  `scripts/nightly_write.py` and `scripts/source_proposal.py`, import only the
  standard library and the `scripts` package, and run on the runner's
  preinstalled `python3`. They target the oldest `python3` on ubuntu-latest,
  3.12, although the project requires 3.14:
  - both modules start with `from __future__ import annotations`, so no
    annotation, including a forward reference, is evaluated at import, where
    3.12 would raise `NameError` for an unquoted forward reference that 3.14's
    lazy annotations accept;
  - ruff's `per-file-target-version` sets `py312` for both files, so syntax
    newer than 3.12 fails lint;
  - a `just check-py312` recipe imports both modules and runs their tests
    under a real CPython 3.12, from nixpkgs locally and the runner's `python3`
    in CI, because ruff cannot see standard-library APIs added after 3.12 or
    differences in annotation evaluation;
  - a test parses both modules, and every `scripts` module they import, and
    fails on any import outside the standard library and `scripts`.
- **Hooks.** Every git command in the write job's scripts runs with `-c
  core.hooksPath=/dev/null`. The write job's checkout is fresh and no project
  code runs before its scripts, so no hook should exist; disabling them anyway
  keeps a hook that a future checkout option or runner image installs from
  running with the token.

Cost: about 20 to 40 seconds more per run, for a second runner and a shallow
checkout, and a hand-off of at most about 770 KB uncompressed. A live bundle
probe on GitHub was not run; the round-trip test in decision 9 establishes the
hand-off against a local bare remote, from a shallow repository built the way
`actions/checkout` builds one.

Alternatives considered:
- One job, with the guarantee narrowed to "the token is absent from every step
  that builds, generates, tests or verifies": honest, but the push, release and
  publish steps would still run from a workspace those steps wrote.
- One job, hardened with hooks disabled on token-bearing git commands and a
  check that `.git/config` is unchanged: it misses the virtualenv and any other
  file an earlier step can write, and each new vector needs another check.
- A write job that runs `uv sync` and the same scripts: it would install and
  run the locked dependencies with the token for no gain, since the write
  scripts need none.

### 7. Stateless generation

`generate_codm` loses:
- metadata and state loading;
- the input gate and the `force` parameter;
- the legacy bootstrap;
- metadata and state validation;
- fingerprint-based fallback compatibility.

A failed project is retained only when main's catalog has an entry for its URL
and the current rule, rendered with the identity that rule is authoritative
for, reproduces the entry exactly:
- an APK rule is rendered with the committed entry's package ID and URL, since
  the package ID comes from APK inspection, not from policy;
- a track-only rule is rendered with the rule's `trackerId` and the committed
  URL, so a changed `trackerId` fails the comparison.

The committed entry is then used byte for byte and reported under
`retainedFailures`. Otherwise the project is unresolved, and generation fails.

This comparison replaces the policy fingerprint. Nearly every rule field is
rendered into the entry: settings, name, kind and, for trackers, the tracker
ID. So equality means the project's effective policy is unchanged, while
reformatting the policy file changes nothing. For trackers it is the exact-match
rule that `_fallback_compatible` already applies today, which renders with
`rule.tracker_id`; APK entries now follow the same rule. Two alternatives were
rejected:
- Retaining regardless of policy changes would let a failed policy edit
  silently leave the old entry in place.
- Emitting an entry freshly rendered from a changed policy with the old package
  ID, instead of failing, could pair a new APK filter with an identity it does
  not select.

Outputs are `catalog.json` and `report.json`. The report keeps its inputs
(README hash and URL) as diagnostics and gains `changed` URLs next to `added`
and `removed`.

`validate_generation_output` goes. It re-derived the generator's own
construction, and the candidate now gets the full test suite, a build and
structural verification instead.

`ProjectRule.fingerprint` goes if nothing else reads it. The `--force` flag is
removed from the CLI, so argparse rejects it.

### 8. Single-capture verification

`verify.py` reads each input once and checks and fingerprints those bytes. It
writes `.build/verify.json` once, at the end, with the same schema-2 fields, so
`pack report` and the pack-cli contract are unchanged.

This replaces the second capture that detected edits during a run. It belongs
here because this change rewrites the evidence requirement the second capture
served.

### 9. Test strategy

- **`prepare` and `stage`** run against a temporary git repository with a
  local bare remote. `pack build` and `pack verify` are injected, so the test
  exercises real staging, allowlist and boundary behavior. Git runs in an
  isolated environment (`HOME` and `GIT_CONFIG_GLOBAL` inside the temporary
  directory, `GIT_CONFIG_NOSYSTEM=1`), so a developer's identity cannot mask a
  missing one, and the tests assert the commit's author and committer.
- **The hand-off** is tested end to end with temporary git repositories. The
  write side is built as `actions/checkout` builds it: `git init`, the bare
  remote's `file://` URL as `origin`, `git fetch --depth 1 origin <base>` and
  `git checkout --detach FETCH_HEAD`. Each test asserts that `git rev-parse
  --is-shallow-repository` prints `true` before running `push` or `publish`,
  because `git clone --depth 1` of a local path ignores the depth and makes a
  full clone. The bundle that `prepare` or `stage` writes is fetched there,
  with `gh auth setup-git` stubbed through the command-runner seam, and:
  - nightly `push` lands exactly `<sha>` on the remote's main, leaves `HEAD`
    detached at `<sha>` and writes `published <sha>`;
  - a remote main that advanced after the checkout fails the main check before
    any push and writes `push failed for <sha>: main advanced`, and a push the
    remote itself rejects, through a pre-receive hook on the bare remote
    (which runs whatever hooks setting the client passes), writes `push failed
    for <sha>`; both exit nonzero;
  - a bundle whose commit's parent is not `<base>`, a bundle whose `HEAD` is
    not `<sha>`, a commit that changes a path outside the allowed files, a
    commit that replaces an allowed file with a symlink, and a commit that
    sets an allowed file's executable bit are each rejected before any push,
    with the remote unchanged;
  - a `CANDIDATE_SHA` or `BASE_SHA` that is not 40 lowercase hex characters is
    rejected before any fetch or push;
  - source `publish` force-pushes exactly `<sha>` to the bot branch, and
    rejects the same mismatches, the symlink and the mode change before any
    push or PR write.
- **`release` and `publish`** take a command-runner seam for `gh`, and git runs
  for real against the temporary bare remote. Tests stub `gh` responses and
  assert decisions, not command transcripts:
  - no write when the record and both served digests match;
  - upload both, then one edit with the canonical body, when the record
    differs;
  - re-upload without an edit when only a served digest differs, is null or is
    missing, including after an interrupted upload whose next pair returns to
    the recorded one;
  - failure without writes for a missing marker, a malformed title, a draft, a
    release that is not a prerelease, or an immutable release;
  - close versus create versus edit, with only a close for an unchanged
    candidate;
  - a same-named fork PR ignored, and more than one selected PR failing before
    any write;
  - no push when trees are equal, and a push when the remote branch is absent;
  - for `release`, failure without writes, summarized `release failed: main
    advanced`, when the remote's main is not `HEAD`, as for a rerun of an old
    no-op after a later run changed main;
  - for source `publish`, no close on the unchanged path and no push or PR
    write on the changed path when the remote's main is not `<base>`,
    summarized `publish failed: main advanced`.
- **The write-job runtime** is guarded by a test that parses
  `scripts/nightly_write.py`, `scripts/source_proposal.py` and every `scripts`
  module they import, and fails on an import outside
  `sys.stdlib_module_names` and `scripts`, or on a module without `from
  __future__ import annotations`; by ruff's `py312` per-file target; and by
  `just check-py312`, which runs both modules' tests under CPython 3.12. Those
  test files import only the standard library, `pytest` and the modules under
  test, so they run without the project environment.
- **One structured workflow test** parses both YAML files with PyYAML, added to
  the `test` dependency group only, and asserts for each workflow:
  - the triggers (the schedule, nightly's timezone, and `workflow_dispatch`
    with no inputs), workflow-level `permissions: {}`, and the named
    concurrency group with `cancel-in-progress: false`;
  - both jobs carry the canonical-repository and `refs/heads/main` condition,
    `runs-on: ubuntu-latest` and `timeout-minutes: 60`;
  - the check job has `permissions: {contents: read}`, checks out
    `${{ github.sha }}`, and no step in it sets `GH_TOKEN` or references
    `github.token` or a secret;
  - the write job `needs` the check job, has exactly the write permissions
    named above, checks out `${{ github.sha }}` with `fetch-depth: 1`, runs
    the base guard comparing the check job's `base` output with `GITHUB_SHA`
    before the download and every step that sets `GH_TOKEN`, has no
    `setup-uv` step and no step that runs `uv`, and sets `GH_TOKEN` only on
    the push and release steps (nightly) or the publish step (source);
  - no `run:` in either job contains a `needs.` or `steps.` expression, so
    outputs reach commands only through `env:`;
  - the bundle hand-off: the check job uploads it when `changed` is true, and
    the write job downloads the same artifact name under the same condition;
  - every checkout step sets `persist-credentials: false`;
  - the nightly push step's condition is only the check job's `changed`
    output, with no status function;
  - no status function (`always()`, `failure()`, `cancelled()` or
    `!cancelled()`) appears in either write job's condition or steps, and in
    the check jobs only on their diagnostics uploads, so a failed build,
    generation, stage or check step permits no remote write.

  The YAML substring tests are deleted, and actionlint and zizmor stay.
- **The three live-catalog pin tests** become invariants over the committed
  catalog:
  - unique IDs and URLs;
  - kind-appropriate IDs and flags;
  - composition with the frozen captured sources without errors;
  - a single-screen pack unchanged, since codm is dual-only.

  Each invariant is shown not to pin data by running it on a test-local
  catalog with one project added and one removed.

## Risks / Trade-offs

- **[Risk] The daily unauthenticated API reads hit a rate limit.** Mitigation:
  the failure is visible, committed entries are retained, and the next day
  retries. Give generation a read-only token only if this is observed.
- **[Trade-off] A transient failure can revert an open proposal.** Retention
  uses main's committed entry, not the open proposal's. When a project whose
  update an open PR carries fails to resolve, the rebuilt proposal drops that
  update, and the PR is closed if nothing else remains. The next successful
  run proposes it again, in the open PR or a new one. No freeze on proposals
  during retained failures is added: it would need state for a loss that the
  next day corrects.
- **[Trade-off] Closing a stale PR runs no checks.** When successful generation
  reproduces main's catalog, publish closes the open PR without tests, build or
  verification. The close proposes no content.
- **[Risk] GitHub reports an asset digest late or not at all.** How soon a
  digest appears after an upload was not probed. Mitigation: a null or absent
  digest counts as a mismatch, so the cost is a redundant re-upload without a
  revision bump.
- **[Trade-off] A policy edit that fails to resolve blocks every catalog update**
  until it resolves or is corrected. The maintainer who made the edit sees the
  failed run, and upstream flakiness for unchanged projects never blocks.
- **[Trade-off] The force-push discards commits added to the bot branch by
  hand** whenever the branch's tree differs from the rebuild. A hand commit
  whose tree equals the rebuild stays. The docs direct maintainers to change
  policy or the README instead.
- **[Trade-off] Bot PRs get no `pull_request` CI.** The PR body links the run
  that ran the full suite. The docs explain that closing and reopening the PR
  as a maintainer starts the PR checks when repository rules require them.
- **[Trade-off] An ambiguous push is reported as a failure even if it landed.**
  The next run no-ops and synchronizes the release, which lags by one run.
- **[Risk] Flaky tests block the day's proposal.** Mitigation: a visible
  failure and a rerun, which is the same cost as CI.
- **[Trade-off] The tree-equality skip compares the whole tree.** A PR is
  therefore re-pushed whenever main moves. That is intended: it keeps the PR
  current.
- **[Trade-off] The job split costs about 20 to 40 seconds a run** and a
  hand-off artifact of at most about 770 KB uncompressed, kept for one day. In
  exchange, no step that runs project code, dependencies or upstream data
  shares a job or a workspace with the write token.
- **[Risk] The bundle hand-off has not run on GitHub.** Mitigation: the
  round-trip test covers the bundle, a shallow repository built as
  `actions/checkout` builds one and asserted shallow, the parent and mode
  checks and the push against a local bare remote, and the first live runs are
  checked after main is pushed.
- **[Risk] The runner's `python3` changes.** A newer image stays compatible
  with the 3.12 floor. An image without `python3` fails the write job visibly
  before any write, and a rerun after the fix publishes. The modules need no
  packages, so nothing else about the image matters.
- **[Trade-off] The write job trusts the check job's result.** It re-checks
  the commit's SHA, parent, paths and file modes, not its content, and runs
  only code from the triggering revision. A compromised check job could hand
  off bad bytes in the regular allowed files, as a single job could, but
  cannot choose the code that runs with the token, inject shell through an
  output, or make the release step read a file outside the checkout through a
  symlink.
- **[Trade-off] A write job fails once main has moved past its run's base.** A
  run triggered before another run's push, such as a manual dispatch queued
  behind a publishing nightly or a source run that overlaps the nightly push,
  and any rerun of an old run's jobs, fails visibly without writes. A rerun
  keeps the run's original commit, so recovery is a new dispatch, and the next
  run on the newer main publishes, proposes or synchronizes the release.

## Migration Plan

The project has no users, so no migration step is planned.

1. The implementation branch deletes `config/catalogs/codm.source.json` and
   `config/package-ids.json`, removes the workflow `force` input, and rewrites
   both workflows and the docs. It retires `scripts/source_publication.py`, the
   workflow `force` input and the forced generation step first, before the
   generation and nightly modules they call change, so no workflow step invokes
   a removed flag and the
   old source workflow proposes nothing on intermediate commits until the new
   one lands. Main stays unpushed until this change lands, so no run sees that
   gap.
2. After main is pushed, a maintainer:
   - creates the release seed with the documented command, if it does not
     exist;
   - checks the first nightly and source runs, including the bundle hand-off
     between their jobs and the write jobs running on the runner's `python3`,
     and the PR-creation repository setting.

   The first source run is expected to reproduce the committed catalog and
   open no PR, so the source hand-off is first exercised by its first changed
   run.
3. **Rollback:** revert the change.
