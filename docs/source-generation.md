# Reviewed source generation

Normal pack builds consume committed Obtainium documents, without fetching
source discovery lists or APKs. Generation is a separate operation that writes
candidate catalogs and reports for review. It never changes the committed
catalogs, packs, README or git history itself.

| Source | Discovery | Policy | Accepted catalog | Candidate and report directory | Proposal branch |
| --- | --- | --- | --- | --- | --- |
| `codm` | codm README project tables | `config/codm-projects.json` | `config/catalogs/codm.json` | `.build/source-generation/codm/` | `automation/codm-catalog` |
| `quiver` | Quiver catalog index and every required list | `config/quiver-projects.json` | `config/catalogs/quiver.json` | `.build/source-generation/quiver/` | `automation/quiver-catalog` |

## Stateless generation

Generation keeps no state between runs and has no forced-refresh mode: every
run re-reads its discovery input, the reviewed policy and fresh release data, and
resolves every eligible project from scratch, without reusing an identity or
a skip decision recorded by an earlier run. There is no metadata file binding
the committed catalog to particular README or policy bytes, and nothing to
force a refresh, because there is nothing that generation would otherwise
skip.

### Retained failures

An accepted project that fails to resolve on a given run (an unreachable release,
a disagreeing or unreadable APK, and so on) keeps its entry from the committed
catalog, reported as a retained failure, but only when the current policy
would render that same entry: for an APK project, using the committed
package ID; for a track-only project, using the rule's own tracker ID. Both
compare against the committed URL. A resolution failure without an entry that
can be retained fails the whole run and offers no candidate catalog. A later run retries every
failure automatically; there is no maintainer action to acknowledge or retry
one.

A run in which every project's lookup fails, for example under a GitHub API
rate limit, is not a visible failure when every project already has a
matching committed entry and its policy and display name are unchanged: every one is then
retained, so the candidate catalog reproduces the committed catalog exactly.
The proposal workflow reports its ordinary "unchanged" outcome, closing any
open proposal, and the run itself reports success. The only signal that
anything went wrong is the retained-failures list in that run's summary and
generation report; there is no separate failure indicator. A new project, or
one whose effective policy changed, has no entry to retain, so the same
outage fails that run visibly.

### Quiver discovery, skips and removals

Quiver reads every list from the configured catalog index. Missing or malformed
required lists fail the complete run. Platform metadata is advisory; it never
replaces a fresh release or APK check. Supported GitHub rows are normalized and
canonical repository aliases are collapsed, preserving row provenance. Unsupported
rows, such as GitLab repositories, are reported without GitHub requests.

For a new Quiver project, an identified repository with no permitted release or
eligible direct APK is a `noAndroid` skip. A repository metadata response of HTTP
404 or 451 is a distinct `unavailableRepositories` outcome. Transport,
authentication, rate-limit and unreadable-APK errors are resolution failures,
not evidence that a project has no Android release. Accepted entries with unchanged
policy and display name can be retained on these failures or missing artifacts.
An accepted repository returning 404 or 451 is removed, as is an accepted entry
no discovered row names. Fresh entries use the current canonical repository URL;
retained entries preserve accepted bytes and match by canonical or listed URL,
never by package ID. An alias outage that prevents either URL from matching
blocks the run visibly.

`config/quiver-projects.json` has schema version 1, optional per-repository
exceptions in `projects`, and reasoned discovery `skips`. An omitted project rule
uses stable APK discovery. Exceptions may set a port name, category, prerelease
selection or supported filename/release filters. Quiver supports APK entries only.
All selected APK manifests must be readable and agree on one package ID. Upstream
`project` names the port; the game title and upstream asset filters do not control
admission or consumer filtering. Duplicate upstream filter disagreement is a
diagnostic, not a selection rule.

A listed-URL skip is matched before any repository request. It pauses discovery
and retains a matching accepted entry byte-for-byte. A literal unsupported-row
skip may instead name `repository` and `repositorySource`. Every skip needs a
reason. Neither kind prunes apps from this source or any other source. Use the
package deny list in `config/deny.json` for permanent exclusion from both packs:
package denial applies globally, including after a repository rename. A denied
package can remain in a source candidate catalog while composition excludes it.

### Retained failures and an open proposal

Retention always compares against `main`'s committed catalog, never against
an open proposal's content. When an open proposal carries an update for a
project (a new entry, or a changed one) and a later run's lookup for that
same project fails transiently, the rebuilt candidate falls back to the
committed entry, so the proposal loses that update; if the update was the
proposal's only change, the workflow closes it. A later run that resolves
the project proposes the update again: in the still-open PR, whose branch
and body it updates, or, if the earlier PR was closed, in a new one.

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

For codm only, a `track-only` rule instead supplies a stable resource ID, rationale,
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
uv run pack generate-source quiver
```

A full local Quiver run needs a GitHub token in practice: complete repository and
release discovery exceeds GitHub's unauthenticated request allowance. Export a
read-only `GITHUB_TOKEN` in your shell before running the command; do not put it
in a policy file or command argument. `config/http.json` scopes this credential
to the configured GitHub host. The CLI permits an absent token, but a full run
then normally fails visibly at the rate limit. Automated generation supplies its
read-only job token to both sources.

Inspect `.build/source-generation/<source>/report.json`, including on unchanged
runs. On success, that directory also holds `catalog.json`, the candidate catalog;
`pack report`
remains the build and structural-verification report viewer and does not
cover source generation.

For codm, generation fails with no `catalog.json` written if the README tables are
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

DW2003 Dual Screen filters APK assets to the `DW2003-Dual-Screen-v*` family.
Since v1.4.0 each upstream release also attaches a Pocket Companion APK,
`com.digitaladventure.dw2003.remote`, a separate app for a second handheld.
Without the filter the two APKs disagree on their package ID and resolution
fails; with it the companion is reported as a filtered asset and the entry
keeps `com.digitaladventure.dw2003`. The companion is not catalogued.

## Proposal workflow

Automated source PRs contain only the selected source's accepted catalog. Generated
packs and README are checked diagnostics, not proposed files or retained artifacts;
nightly rebuilds outputs after merge. Manual policy PRs include their accepted
catalog and changed outputs under the
[manual review convention](development.md#manual-review-and-pr-contents).

The **Reviewed source catalog** Actions workflow runs daily at 04:17 UTC and can
be dispatched manually with no inputs. It runs only for `mjkoo/omnipack` on `main`.
The codm and Quiver caller jobs invoke the same reusable workflow, each under its
own non-canceling concurrency group covering the complete check-and-publish chain.
They do not wait on, count PRs from, close proposals from, or stage catalogs from
the other source. Each source runs a read-only `check` job followed by its own
write-capable `publish` job, each limited to 60 minutes.

The caller grants the reusable workflow only the ceiling needed for publication;
its check job reduces permissions to `contents: read`. No workflow grants
permissions at workflow level. Every check step, including checkout, setup,
generation, tests and build, receives only that read-only job token. The generation
step explicitly sets `GITHUB_TOKEN: ${{ github.token }}`. Checkouts never persist
credentials. The environment is synced with uv's Actions cache disabled.

The check job runs the selected source command and stages its candidate:

```sh
uv run --no-sync pack generate-source quiver
uv run --no-sync python -m scripts.source_proposal stage --source quiver
```

Use `codm` for the other source. Script commands default to codm when `--source`
is omitted; only the fixed `codm` and `quiver` descriptors are accepted, never
arbitrary catalog or branch paths. `stage` requires a successful generation report,
regular candidate/catalog files, an empty index, and a base catalog mode of
`100644`. If the candidate differs from main, it commits only that catalog on its
local `automation/<source>-catalog` branch with hooks disabled. It emits the
checked commit SHA and base revision and a Git bundle containing the commit.
Staging failure hands off nothing.

For a changed candidate, the job runs the full tests, `pack build` and `pack verify`
with that catalog in place. Its `guard` command then checks the candidate's single
base parent, source-specific path and file modes, and confirms that the regular
workspace catalog still equals the checked commit. The always-run summary reports
generation, staging, tests, build, verification and guard outcomes from the actual
step results. Only when every one of those steps succeeded does the summary also
write the escaped PR body, which includes the same validation results, so a
candidate that failed a check never has a body to publish. Failed or skipped
checks are never reported as successful.

The checked bundle and PR body are uploaded only after successful checks as
`source-handoff-<source>-<run-id>` with one-day retention. The selected generation
report is uploaded when available on success or failure as
`source-generation-report-<source>-<run-id>` with 14-day retention. Reruns replace
the same named artifacts. These artifacts contain no APKs, raw HTTP cache,
credentials, policies, pack exports or README output. A missing report after an
early failure is explicitly reported and does not imply successful validation.

The write job runs no dependency installation, generation, tests, build or
verification. It checks out the original triggering `${{ github.sha }}` afresh,
then requires its base output to equal `GITHUB_SHA` before any step receives
`GH_TOKEN`. Read-only outputs reach the publisher through environment variables,
never shell interpolation. Only this job holds `contents: write` and
`pull-requests: write`; only its publication step receives `GH_TOKEN`.

```sh
python3 -m scripts.source_proposal publish --source quiver \
  --bundle <downloaded bundle path> --body-file <downloaded body path>
```

The publisher first confirms remote main still equals the checked base. If main
advanced, publication fails without a branch or PR write. It considers only open
PRs from the selected source's branch in the canonical repository to main; fork
PRs sharing a branch name and the other source's PRs are untouched. More than one
matching PR fails before any write. An unchanged catalog needs no tests/build or
verification: closing that source's existing proposal is the only permitted write.

For a changed candidate, the bundle must identify the exact checked commit, with
one parent equal to the base and exactly the selected catalog changed at mode
`100644` on both sides. The PR body must be regular, valid UTF-8 and within 65,536
characters. The publisher compares the whole candidate tree to that source branch's
remote tree, avoiding a push when they match even if commits differ. Otherwise it
replaces that source branch with the checked commit. It then edits its existing PR
or opens one to main, titled `chore(catalog): update reviewed <source> source`.
No automatic merge, direct-main write, issue or release operation occurs.

The body links the checking workflow run, records the base SHA, catalog changes,
source diagnostics and actual validation results. Upstream strings are HTML-escaped
inside a preformatted block. Long diagnostic bodies end with an omission count;
the full summary and retained generation report remain available for review.

### Stage summary lines

On success, `stage` writes the base SHA, catalog changes, retained failures and
source diagnostics to the step summary, including when the catalog is unchanged. On failure it writes one line naming
what failed, and hands nothing off:

- `stage failed: could not read HEAD`, or
  `stage failed: HEAD is not GITHUB_SHA`;
- `stage failed: <path> is missing`, `is a symlink` or
  `is not a regular file`, for the generated candidate or
  the selected `config/catalogs/<source>.json`;
- `stage failed: could not read the generation report or candidate`, or
  `stage failed: generation did not succeed`;
- `stage failed: could not read the base catalog`,
  `stage failed: base catalog is not a regular mode 100644 file`, or
  `stage failed: index contains staged changes`;
- `stage failed: could not write the catalog`;
- `stage failed: could not commit the candidate`;
- `stage failed: HEAD is not the candidate commit`, or
  `stage failed: could not write the bundle`.

### Publish summary lines

`publish` writes one step summary line: `publish made no change`,
`publish closed PR #<n>`, `publish created PR` or `publish updated PR #<n>`
on success, or one fixed failure reason:

- `publish failed`: `CHANGED`, `CANDIDATE_SHA` or `BASE_SHA` is malformed
  (the rejected value is never echoed);
- `publish failed: gh auth setup-git failed`;
- `publish failed: could not read remote main`, or
  `publish failed: main advanced`;
- `publish failed: PR list failed`, or
  `publish failed: more than one source-update PR`;
- `publish failed: hand-off rejected`: the bundle or the commit it carries
  failed a check;
- `publish failed: PR body rejected`;
- `publish failed: could not read remote branch`;
- `publish failed: branch push failed`;
- `publish failed: PR close failed`, `publish failed: PR edit failed` or
  `publish failed: PR create failed`.

The error output of a failing `git` or `gh` command goes to the job log,
never to the step summary. Either command's failure reason goes to both, so
`gh run view --log-failed` names the cause without opening the summary. Only
failure reasons are logged, and they are fixed text: the success report, which
carries upstream URLs and messages, stays in the step summary and the PR body.

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

A PR that this workflow opens is created with the job's own token, so the
project's `pull_request` CI does not run on it by itself: GitHub creates those
runs but holds them until a maintainer approves them. The PR body links the
workflow run whose test, build and verification steps validated its
content. If repository rules require `pull_request` checks before merging, a
maintainer with write access can start them with **Approve workflows to run**
in the PR's merge box. A `pull_request` run that the Actions list shows as
failed with no jobs was never started and is not a verdict on the PR's
content.

Creating or editing a PR through the job token also requires the
repository's **Allow GitHub Actions to create and approve pull requests**
setting (Settings > Actions > General > Workflow permissions) to be enabled;
without it, `publish`'s PR create or edit step fails. This setting is not
changed automatically by any workflow.

## Diagnostics and credentials

`check` performs no remote writes: its only token is the read-only job token
(`contents: read`) used by checkout and explicitly supplied to generation. No
step receives a write token. Only `publish` holds `contents: write` and `pull-requests: write`,
and only its one step receives `GH_TOKEN`; its checkout uses the job token
only to fetch the triggering revision, and `persist-credentials: false`
keeps it out of `.git/config`. `scripts/source_proposal.py`
serves both jobs and, like `scripts/nightly_write.py`, imports only the
standard library and the shared helpers in `scripts/workflow_support.py`,
and runs on the runner's preinstalled `python3` in the write job. Source
text, project URLs, asset names and other upstream-derived strings are
treated as data: credentials, downloaded APKs and raw HTTP
caches are excluded from summaries and artifacts.

Inspect skips, unsupported rows, no-Android outcomes, unavailable repositories,
retained failures, unresolved projects, effective policy, discovery coverage,
APK/tracking observations and catalog changes even when the result is unchanged.
For Quiver these are the `skipped`, `unsupportedRows`, `noAndroid`,
`unavailableRepositories`, `retainedFailures`, `unresolved`, `effectivePolicy`,
`coverage`, `apk`, `tracking` and `changes` report fields. Successful retention or
a reasoned skip is not a fresh APK check. The run summary also records the actual
validation outcomes and explicitly marks checks skipped for unchanged candidates.

Nightly pack publication remains independent of this workflow. It reads only
the committed source catalogs on `main` and publishes
`dist/single-screen.json`, `dist/dual-screen.json` and the generated
interior of `README.md`; it never stages a catalog or policy change.
