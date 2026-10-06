# Reviewed source generation

Normal pack builds consume committed Obtainium documents, without fetching
source discovery lists or APKs. Generation is a separate operation that writes
candidate catalogs and reports for review. It never changes the committed
catalogs, packs, README or git history itself.

| Source | Upstream input | Accepted catalog | Candidate and report directory | Proposal branch |
| --- | --- | --- | --- | --- |
| `codm` | codm README Project tables | `config/catalogs/codm.json` | `.build/source-generation/codm/` | `automation/codm-catalog` |
| `quiver` | Quiver catalog index, its lists and its release asset-name file | `config/catalogs/quiver.json` | `.build/source-generation/quiver/` | `automation/quiver-catalog` |

## Stateless generation

Generation reads only what each upstream publishes, through the same plain,
credential-free HTTP client the build uses, plus the committed catalog. It
never queries a repository host, downloads an APK or inspects a manifest:
Obtainium decides what a listed link can track. Generation keeps no state
between runs and has no forced-refresh mode; every run re-reads its inputs and
renders the candidate from scratch. Redirects are followed as the client
follows them.

## Inputs

The `codm` and `quiver` sources in `config/sources.json` each name their
upstream input and their committed `catalog`.

codm reads the README at `readme_url` and takes every `http` or `https` link
inside its Project tables, whatever host it points to. Links outside a Project
table or inside a code block are ignored, and so is a badge image inside a
link. A link no project URL can be formed from, such as one with an invalid
port, is reported and skipped. Project tables follow GitHub Markdown table
syntax: outer pipes are optional, delimiter cells need only one hyphen, and a
table runs until a blank line, a heading or a code block. A missing or
malformed Project table fails the run, even beside a valid one, because a
partial read would propose removing the projects of the table it could not
read.

Quiver reads the index at `index_url`, every list the index references and the
release asset-name file the index names by `platformMetadataUrl`. Every one of
those locations must sit within the index's own host and directory, or the
index is malformed. In each row, an absent `repositorySource` means GitHub, and
forge names match without regard to case: `github` forms
`https://github.com/<repository>`, where the repository is exactly an owner and
a name, and `gitlab` forms `https://gitlab.com/<repository>`, with one or more
namespaces and a project. A row naming another forge, or with a missing or
invalid repository, is reported and skipped.

## Screening

Where an upstream publishes release asset names, generation screens new
projects with them. Quiver's asset-name file lists each repository's latest
release assets: a project the committed catalog does not hold is admitted only
when that list includes an asset ending in `.apk`, compared without regard to
case. A committed project the upstream still lists is always kept, whatever its
latest release holds, because Obtainium falls back to older releases. A project
missing from the file or without an APK asset is reported and skipped.

codm publishes no asset names, so its links are not screened. A link Obtainium
cannot use, such as a Google Play, Modrinth or Nexus Mods page, ships until the
owner denies its URL in `config/deny.json`. A denial applies to every source
listing that URL; a denied project can remain in a source candidate catalog
while composition excludes it.

## Rendered entries

Generation renders one minimal entry per normalized project URL, independent
of listing order, as a canonical catalog:

- For a URL the committed catalog already holds, the committed entry's id and
  URL are kept verbatim, so composition rules, pins and installed apps that
  know it keep working.
- Otherwise the URL is the reduced project URL (a GitHub deep link becomes the
  repository root, while a link on any other host keeps its path; when several
  listings collapse to one URL, the smallest in code point order wins), and the id is an Obtainium placeholder: the first
  twelve hex characters of the SHA-256 of the normalized URL. Obtainium
  replaces it with the APK's package id on first install.
- `overrideSource` is GitHub for a github.com repository and GitLab for a
  gitlab.com project; any other URL, a gitlab.com link into a project's `/-/`
  routes included, leaves it unset, and Obtainium detects the source.
- The name is the listing's name with trailing emoji and other symbols trimmed
  (punctuation, `+` and currency signs are kept), or the last URL path segment,
  or the host for a URL without a path, when no listing names it. When listings give several names, the first in
  case-insensitive order wins.
- The author is the first path segment for a URL with an `overrideSource`, and
  empty otherwise.
- Entries carry no categories and no settings; the build fills in the source
  type's defaults.

Per-app names and settings for generated entries are
[overlay](composition.md#denials-and-patches) records in `config/overlay.json`,
and categories are keys in the composition
[category map](composition.md#categories). An overlay patches the selected
entry at its URL whichever source wins, so a catalog refresh never discards
them. Examples:

- Showdown and Heimdall include prereleases, filter APK names and extract
  versions; Heimdall also filters release titles.
- Melee PC includes prereleases.
- DW2003 Dual Screen filters APK assets to the `DW2003-Dual-Screen-v*`
  family. Each upstream release also attaches a Pocket Companion APK, a
  separate app for a second handheld that is not catalogued.
- Silent Hill Decomp excludes its `_OLD` APK assets, and LEGO Island
  Portable selects `app-release.apk`.
- Kanto Gear is track-only. Obtainium reports its releases but cannot install
  the Lua mod or detect its installed version. Install or update Kanto through
  official [Gen1Recomp](https://github.com/bryanthaboi/gen1recomp) using its
  Mod Index or ZIP import. Gen1Recomp remains the Android host in both packs.

A repository renamed upstream yields a removal of the old URL and a new
placeholder-id entry at the new one. A family rule, an overlay `id` patch or a
denial handles it.

Composition fails when an overlay record has no selected entry at its URL
(`overlay has no selected target`). A catalog-only proposal that removes a
project an overlay record patches, when no other source serves its URL,
therefore fails its checks; remove the overlay record on main first, then
rerun the proposal.

## Generate and inspect a candidate

Run from the repository root:

```sh
uv run pack generate-source codm
uv run pack generate-source quiver
```

Neither source needs a credential. Inspect
`.build/source-generation/<source>/report.json`, including on unchanged runs.
It records the run's status and source, every input read, with the SHA-256 of
its bytes once read, any error, and every skipped listing with its reason; on
success it also records `changes`, the added, removed and changed-in-place
entries by catalog URL. On success the directory also holds `catalog.json`, the
candidate catalog. `pack report` remains the build and structural-verification
report viewer and does not cover source generation.

A run fails only when the source configuration is missing or malformed, when
an input is unreadable or malformed, when the committed catalog is unreadable or
malformed (including two entries at one normalized URL, which the error names
with their ids, and a repeated id), or when the candidate would keep no entry.
A missing committed catalog holds nothing, so every entry gets a placeholder
id.
A failed run writes only its report: no candidate survives from it or from an
earlier run.

## Proposal workflow

Automated source PRs contain only the selected source's accepted catalog. Generated
packs and README are checked diagnostics, not proposed files or retained artifacts;
nightly rebuilds outputs after merge. Manual catalog PRs include their accepted
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
generation, tests and build, has only that read-only job token available, and
the generation step receives no token at all. Checkouts never persist
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
credentials, pack exports or README output. A missing report after an
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

The body links the checking workflow run, records the base SHA, and lists the
added, removed and changed catalog URLs, the skipped listings and the actual
validation results. Upstream strings are HTML-escaped inside a preformatted
block. When the catalog's bytes changed but no entry was added, removed or
changed, the block says `Catalog bytes changed without entry changes`. Long
diagnostic bodies end with an omission count; the uploaded generation report
remains available for review.

### Stage summary lines

On success, `stage` writes the base SHA and the report's Added, Removed,
Changed and Skipped lists to the step summary, including when the catalog is
unchanged. On failure it writes one line naming what failed, and hands nothing
off:

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
(`contents: read`) used by checkout; generation reads only public upstream
inputs and receives no token. No step receives a write token. Only `publish`
holds `contents: write` and `pull-requests: write`, and only its one step
receives `GH_TOKEN`; its checkout uses the job token only to fetch the
triggering revision, and `persist-credentials: false` keeps it out of
`.git/config`. `scripts/source_proposal.py` serves both jobs and, like
`scripts/nightly_write.py`, imports only the standard library and the shared
helpers in `scripts/workflow_support.py`, and runs on the runner's preinstalled
`python3` in the write job. Source text, project URLs, asset names and other
upstream-derived strings are treated as data: credentials, downloaded APKs and
raw HTTP caches are excluded from summaries and artifacts.

The run summary lists Added, Removed, Changed and Skipped, one line per
skipped listing giving its JSON description and then the reason, and for a
failed generation an `Error:` line with the report's error. Like the PR body,
it ends with an omission count when it would exceed GitHub's step summary
limit, and the stage summary calls out a byte-only catalog change. Inspect the
skipped listings and catalog changes even when the result is unchanged. The
run summary also records the actual validation outcomes and explicitly marks
checks skipped for unchanged candidates.

Nightly pack publication remains independent of this workflow. It reads only
the committed source catalogs on `main` and publishes
`dist/single-screen.json`, `dist/dual-screen.json` and the generated
interior of `README.md`; it never stages a catalog change.
