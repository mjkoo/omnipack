# Reviewed codm source generation

Normal pack builds consume the committed Obtainium document at
`config/catalogs/codm.json`. Source generation is a separate operation that
reads the codm README, applies reviewed per-project policy, resolves APK
identities, and writes a candidate catalog under
`.build/source-generation/codm/`. It never changes the committed catalog,
packs, README or git history by itself; a separate workflow proposes its
output for review.

## Stateless generation

Generation keeps no state between runs and has no forced-refresh mode: every
run re-reads the README, the reviewed policy and fresh release data, and
resolves every eligible project from scratch, without reusing an identity or
a skip decision recorded by an earlier run. There is no metadata file binding
the committed catalog to particular README or policy bytes, and nothing to
force a refresh, because there is nothing that generation would otherwise
skip.

### Retained failures

A project that fails to resolve on a given run (an unreachable release, a
disagreeing or unreadable APK, and so on) keeps its entry from the committed
catalog, reported as a retained failure, but only when the current policy
would render that same entry: for an APK project, using the committed
package ID; for a track-only project, using the rule's own tracker ID. Both
compare against the committed URL. Any other failure, including a project
with no committed entry, or a project whose effective policy changed, fails
the whole run and offers no candidate catalog. A later run retries every
failure automatically; there is no maintainer action to acknowledge or retry
one.

A run in which every project's lookup fails, for example a GitHub API rate
limit, is not a visible failure: since every project already has a committed
entry with unchanged effective policy, every one is retained, so the
candidate catalog reproduces the committed catalog exactly. The proposal
workflow then reports its ordinary "unchanged" outcome, closing any open
proposal, and the run itself reports success. The only signal that anything
went wrong is the retained-failures list in that run's summary and generation
report; there is no separate failure indicator.

### Retained failures and an open proposal

Retention always compares against `main`'s committed catalog, never against
an open proposal's content. When an open proposal carries an update for a
project (a new entry, or a changed one) and a later run's lookup for that
same project fails transiently, the rebuilt candidate falls back to the
committed entry, so the proposal loses that update; if the update was the
proposal's only change, the workflow closes it. A later run that resolves
the project proposes the update again, either updating the reopened content
of the still-open PR or, if the earlier one was closed, in a new PR.

## Inputs and policy

The source configured under `codm` in `config/sources.json` names three
inputs:

- `readme_url`, the upstream README whose Project catalog tables supply
  eligible GitHub repositories;
- `project_policy` (`config/codm-projects.json`), the reviewed per-project
  policy;
- `catalog` (`config/catalogs/codm.json`), the committed catalog that normal
  builds read.

Policy keys use normalized GitHub repository identities. A project with no
rule defaults to APK discovery using stable releases. A reviewed `apk` rule
can set a name and supported Obtainium discovery settings such as prerelease
inclusion, release-title and APK filename filters, version extraction, and
the consumer `fallbackToOlderReleases` setting. APK package IDs always come
from inspected manifests; policy cannot supply them. Every eligible APK in
the selected release must be readable and agree on its package ID.

Regex rules use a restricted shared syntax. Use explicit character classes
such as `[0-9]` or `[A-Za-z0-9_]`; shorthand classes (`\d`, `\D`, `\s`, `\S`,
`\w`, `\W`) and word boundaries (`\b`, `\B`) are rejected because their
Python and Dart matching semantics differ. Existing reviewed rules use
explicit classes.

A `track-only` rule instead supplies a stable resource ID, rationale,
installation instruction, and optional supported settings. It creates an
Obtainium release tracker without downloading an APK. Failed APK resolution
never converts a project into a tracker, and a change of kind requires fresh
validation for the destination kind, with no cross-kind fallback.

Kanto Gear is intentionally track-only. Obtainium reports its releases but
cannot install the Lua mod or detect its installed version. Install or
update Kanto through official [Gen1Recomp](https://github.com/bryanthaboi/gen1recomp)
using its Mod Index or ZIP import. Gen1Recomp remains the Android host in
both packs.

## Generate and inspect a candidate

Run from the repository root:

```sh
uv run pack generate-source codm
```

Inspect `.build/source-generation/codm/report.json`. On success, the
directory also holds `catalog.json`, the candidate catalog; `pack report`
remains the build and structural-verification report viewer and does not
cover source generation.

Generation fails, with no `catalog.json` written, if the README tables are
malformed or empty, any eligible project is unaccounted for, a new APK or
tracker cannot be resolved, eligible APKs disagree, an ID collides, or a
project's effective policy changed and its fresh resolution failed. Partial
catalogs are never written.

Heimdall illustrates the distinction between generator and client behavior.
The generator selects the newest release matching its reviewed title rule
and fails if that release has no eligible readable APK; it never searches an
older release. The generated Obtainium entry sets
`fallbackToOlderReleases: true`, allowing the client to search older
matching releases when its selected release lacks an eligible asset.
Showdown and EmuLnk explicitly set that client option to false.

## Proposal workflow

The **Reviewed source catalog** Actions workflow runs daily at 04:17 UTC and
can be dispatched manually, with no inputs. It runs only for
`mjkoo/omnipack` on `main`, under one non-canceling concurrency group, and
splits into a read-only `check` job and a write-capable `publish` job so
that nothing which generates, tests, builds or verifies the candidate ever
shares a job or the write credential with the steps that push a branch or
touch a pull request.

**`check`** holds `permissions: contents: read`, with no step receiving a
write token. It checks out `${{ github.sha }}`, syncs the locked project
environment, and runs:

```sh
uv run --no-sync pack generate-source codm
uv run --no-sync python -m scripts.source_proposal stage
```

`stage` copies the generated candidate over `config/catalogs/codm.json`
(keeping its mode `100644`) and, when that differs from the checked-out
revision, commits only that file on a local `automation/codm-catalog`
branch created at `HEAD`, as `github-actions[bot]` with hooks disabled, and
writes a `git bundle create <dir>/candidate.bundle <base>..HEAD`. It writes
`changed`, `sha` and `base` as job outputs, and the base SHA, the catalog
changes and any retained failures to the step summary.

When the candidate changed, `check` goes on to run the full test suite,
`pack build` and `pack verify` against the candidate catalog, mirroring what
CI on `main` runs right after such a change merges, then requires
`git diff --quiet "$SHA" -- config/catalogs/codm.json` (with `SHA` the
`stage` commit) to confirm the working tree still matches the committed
candidate. Any of those steps failing blocks the proposal: the bundle and PR
body file are uploaded, as `source-handoff-<run-id>` with one-day retention,
only when every one of them succeeded. The generation report is always
uploaded, as `source-generation-report-<run-id>`, with 14-day retention.

**`publish`** needs `check`, holds `permissions: contents: write` and
`pull-requests: write`, and runs no `setup-uv` and no `uv`. It checks out
`${{ github.sha }}` shallowly, then a guard step,
`test "$BASE_SHA" = "$GITHUB_SHA"` with `BASE_SHA` mapped from
`needs.check.outputs.base`, before anything token-bearing. It downloads the
bundle and body file when `changed` is `true`, then runs, with `GH_TOKEN`:

```sh
python3 -m scripts.source_proposal publish \
  --bundle <downloaded bundle path> --body-file <downloaded body path>
```

`publish` first requires `git ls-remote origin refs/heads/main` to still
report the run's base SHA; if `main` has moved on, it writes nothing and
summarizes `publish failed: main advanced`. It then selects the open PR
whose head is `automation/codm-catalog` in the canonical repository (a PR
from a fork sharing that branch name is neither edited nor closed); more
than one such PR fails the run before any write.

When the candidate is unchanged, `publish` closes the selected PR, if any,
and makes no other write. When it changed, `publish` verifies the bundle and
the handed-off commit's parent and diff exactly as the nightly write job
does (see [nightly publishing](publishing.md)), then compares the commit's
tree with the remote `automation/codm-catalog` branch's tree: a branch
already at that tree, even from a different, hand-made commit, is left as it
is. Otherwise it overwrites the branch:

```sh
git push --force origin <sha>:refs/heads/automation/codm-catalog
```

and edits the selected PR's body, or creates the PR (`--base main --head
automation/codm-catalog`), from the downloaded body file. That body holds
the workflow run's URL, the base SHA and the catalog's added, removed and
changed projects, plus any retained failures, with upstream-derived text
HTML-escaped inside a `<pre>` block so upstream Markdown renders as literal
text rather than markup.

### Recovering from an advanced main

Both the workflow-level guard step and `publish`'s own `main` check exist to
keep a rerun of an old run from undoing a newer one. If `main` gained a
commit between `check`'s checkout and `publish`'s first write, `publish`
writes nothing; re-running that same failed job checks out the same stale
revision and fails the same `main` check again, since Actions' "re-run
failed jobs" replays the original triggering commit rather than picking up
`main`'s current tip. Recovery is a new workflow dispatch, which checks out
and validates the newer `main` and proposes or closes against it.

### PR checks and the PR-creation setting

A PR that this workflow opens is created with the job's own token, so it
does not trigger the project's `pull_request` CI. The PR body links the
workflow run whose test, build and verification steps validated its
content. If repository rules require `pull_request` checks before merging, a
maintainer can close and reopen the PR by hand to start them.

Creating or editing a PR through the job token also requires the
repository's **Allow GitHub Actions to create and approve pull requests**
setting (Settings > Actions > General > Workflow permissions) to be enabled;
without it, `publish`'s PR create or edit step fails. This setting is not
changed automatically by any workflow.

## Diagnostics and credentials

`check` performs no writes and receives no token; only `publish` holds
`contents: write` and `pull-requests: write`, and only its one step receives
`GH_TOKEN`. `scripts/source_proposal.py` serves both jobs and, like
`scripts/nightly_write.py`, imports only the standard library and the
`scripts` package and runs on the runner's preinstalled `python3` in the
write job. Source text, project URLs, asset names and other upstream-derived
strings are treated as data: credentials, downloaded APKs and raw HTTP
caches are excluded from summaries and artifacts.

Nightly pack publication remains independent of this workflow. It reads only
the committed source catalog on `main` and publishes
`dist/single-screen.json`, `dist/dual-screen.json` and the generated
interior of `README.md`; it never stages a catalog or policy change.
