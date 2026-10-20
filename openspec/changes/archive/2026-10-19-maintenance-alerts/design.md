# Design

## Context

See proposal.md for motivation. Two scheduled workflows run unattended:

- `nightly.yml`: a read-only `prepare` job (`scripts/nightly.py prepare`,
  which builds, verifies and commits a candidate and reports the failing stage
  by name in its step summary) and a `publish` job holding `contents: write`
  (`scripts/nightly_write.py push` and `release`, stdlib only, on the
  runner's `python3`). The workflow is serialized by the workflow-level
  `omnipack-nightly-publisher` group.
- `source-catalog.yml`: one call of the reusable `source-maintenance.yml` per
  generated source (codm, Quiver), each in its own concurrency group, plus the
  read-only `live-check` job in group `omnipack-live-check`.
  `source-maintenance.yml` has a read-only `check` job (generate, stage, tests,
  build, verify, guard, then `scripts/source_proposal.py summarize`) and a
  `publish` job holding `contents: write` and `pull-requests: write`.

`pack build` makes no network requests, so a nightly `prepare` failure means
`main` is broken or the runner failed. The build report already lists
`staleExclusions` (stale denials), `uncategorizedFamilies` and
`staleCategoryAssignments`. Quiver's skipped listings are routine screening
(about 200 projects for "latest release lists no APK asset").

`scripts/source_proposal.py` already renders upstream-derived text
HTML-escaped inside `<pre>` within a character budget, summarizing overflow as
"and N more", for the run summary and the PR body (`PR_BODY_LIMIT = 65536`).
`scripts/workflow_support.py` holds the shared stdlib helpers, including the
`GhRunner` protocol the publish scripts use for `gh` calls.

## Goals / Non-Goals

**Goals:**

- One reconcile implementation shared by every alert job.
- The credential split already used for publication: no job holds both
  upstream-derived data and a write token beyond what it holds today.
- Issues are the only state; the workflows stay stateless.

**Non-Goals:**

- Debouncing repeated failures.
- Alerting on PR-triggered CI, whose failures show on the PR.
- Handling duplicate issues for one key beyond a deterministic choice.

## Decisions

**A findings file per producing job, reconciled by a separate alert job.**
Each producing job writes `.build/alerts/findings.json` and uploads it as
`alert-findings-<owner>-${{ github.run_id }}`, with `<owner>` built from
`inputs.source` in the reusable workflow, so no two producers in one run share
an artifact name and an `overwrite: true` upload never replaces another
owner's file; an alert job holding only `issues: write` downloads each of its
producers' artifacts by that name and reconciles them. The
alternatives were putting the reconcile step in the existing publish jobs and
a central alerts workflow. The publish jobs `need` the check jobs, so they
would have to run on failure, they hold contents write access, and live-check
has no write job. A central workflow would read other runs' artifacts through
the API and could reconcile against a stale run. A per-workflow alert job
keeps credentials separate and reconciles exactly the run it belongs to.

The file holds `owner`, `scope` (key prefixes the run re-checked),
`unchecked` (keys under those prefixes it did not re-check) and `findings`,
each `{key, title, details}` with `details` a list of raw detail lines;
producers never escape or wrap them, because the alert job is the escaping
authority. `owner` is one of
`nightly-prepare`, `nightly-publish`, `codm-check`, `codm-publish`,
`quiver-check`, `quiver-publish` and `live-check`, unique across workflows, so
codm and Quiver, which call the same reusable jobs, never share a key.

**Keys are owner, stage and subject; scope decides what may close.** One
issue per finding, keyed so a changing error message stays one issue. Each
owner owns the key prefixes in the table and nothing else. Its early-failure
key is `run` under its first prefix (`nightly/prepare/run`,
`nightly/publish/run`, `<source>/check/run`, `<source>/publish/run`,
`live-check/run`), in scope whenever the producer's result is `success`,
`failure` or `cancelled`. Every other key is in scope only when the stage or step it names
actually ran:

| Owner | Prefix | Keys | In scope when |
|---|---|---|---|
| `nightly-prepare` | `nightly/prepare/` | `nightly/prepare/<stage>`, stage one of `checkout`, `build`, `allowlist`, `readme-boundary`, `commit`, `verify`, `drift-after-verify`, `bundle` | the stage ran, as listed in the `stages` step output preparation writes: a no-op success lists neither `commit` nor `bundle`, a failure lists the stages it started up to and including the failing one, a failure removing stale reports lists only `build` and not `checkout`, and nothing is in scope when the prepare step did not run |
| `nightly-prepare` | `build/` | `build/uncategorized/<family>`, `build/stale-denial/<url>`, `build/stale-category/<key>` | `.build/report.json` exists with `status: success`; a failed report's listed items are still raised, but its empty lists close nothing, because the baseline records them empty when the checks did not run |
| `nightly-publish` | `nightly/publish/` | `nightly/publish/push`, `nightly/publish/release` | that step's `outcome` is `ok` or `failed`; `main-advanced` or a skipped step leaves the key out of scope |
| `<source>-check` | `<source>/check/` | `<source>/check/<generation\|stage\|tests\|build\|verify\|guard>` | the step's outcome is `success` or `failure`; tests, build, verify and guard also count as re-checked when they were skipped because generation and staging succeeded with an unchanged candidate, so a stale check failure closes |
| `<source>-publish` | `<source>/publish/` | `<source>/publish/proposal` | the publish step's `outcome` is `ok` or `failed`, with the same `main-advanced` exception |
| `live-check` | `live-check/` | `live-check/read` (the packs could not be read) | the `pack check-live` step's outcome is `success` or `failure` |
| `live-check` | `live-check/` | `live-check/gone/<url>` (HTTP 404 or 410), `live-check/status/<url>` (another non-retried error status) | the report has `status: success`; both keys of a URL the budget left unchecked, or whose inconclusive entry recorded no status (a retried status after retries, a timeout, a connection failure), are listed in `unchecked`; a URL no longer in the packs therefore closes |

Splitting the URL keys by class keeps a muted 403 from hiding a later 404 or
410 for the same project, while one key per class still keeps one issue when a
403 becomes a 401. Scoping by what ran is what keeps a `prepare` failure from
closing a release issue, and a failed generation from closing a verification
issue. An inconclusive entry without a status is no evidence that a problem
cleared, so it closes nothing.

Keys use letters, digits and `/:._~%+-`. Stage names map to the fixed slugs
above (`README boundary` becomes `readme-boundary`). Subjects (a normalized
URL, a family, a category key) are percent-encoded after normalization: each
UTF-8 byte of a character outside letters, digits and `/:._~+-`, `%` itself
included, becomes `%XX`. So `https://dolphin-emu.org/download/?ref=btn` keys
as `live-check/gone/https://dolphin-emu.org/download/%3Fref%3Dbtn`, and one
subject always yields one key. Titles and bodies carry the subject unencoded.

**Emitters live in `scripts/alerts.py`, not in the producers.**
`alerts.py emit <owner>` runs under `if: always()` as each producing job's
last step but the findings upload, and builds the file from what the job
already has: the preparation stage, the build report, the publish outcomes,
the source step results `summarize` receives, `.build/live-check/report.json`,
and `job.status` through `env`. When `job.status` is `failure` and no stage or
step finding, and no `main-advanced` outcome, accounts for it (setup-uv or
`uv sync --locked` failing, a base guard or hand-off download failing before
the publish step, a report or hand-off upload failing), the emitter raises
the owner's early-failure finding itself. Because it runs after those steps, a failure
the stages do not model never yields a valid, silent file. The emitter is the
authority on how its job ended: when `job.status` is `cancelled`, as after a
`timeout-minutes` stop, it writes only the owner's early-failure finding, with
empty `scope` and `unchecked`, whatever partial reports the job left, so
reconcile never takes stage, step or URL scope from an interrupted run whatever
result GitHub reports for the job. The emit and findings-upload
steps carry `continue-on-error: true`, so an alerting defect never changes a
producer's verdict or keeps nightly `publish` from running; the alert job sees
the resulting missing or invalid file instead. Putting the
emitters inside `omnipack` or the existing scripts would spread alert
knowledge through packages that have no other reason to know about issues.
`scripts/alerts.py` runs in the alert job's sparse `scripts/` checkout and in
emit steps that may follow a failed `setup-uv` or `uv sync --locked`, so, like
the publish scripts, it imports only the standard library and the `scripts`
package and runs on the runner's `python3` 3.12. It never imports
`scripts.nightly`, which imports `omnipack`; it keeps its own literal table
from each preparation stage name to its slug, and a test outside the 3.12 run
keeps that table's keys equal to the `PrepareStage` values other than
`complete`. It joins the existing 3.12 guards: the py312 per-file target
version in `pyproject.toml`, the module list of the stdlib import-boundary
test in `tests/test_write_side_runtime.py`, and the `check-py312` recipe in
the `justfile`.

Producer changes are limited to exposing data the emitters cannot otherwise
read without parsing text:

- `scripts/nightly.py prepare` writes the failing stage to a step output on
  failure as well as on success, and a `stages` step output listing every
  stage it started, in order; the emitter maps each listed stage name to
  its slug through its own table and scopes exactly the listed stages. Removing stale reports is
  part of `build`, so its failure lists `build` alone.
- `scripts/nightly_write.py push` and `release` and
  `scripts/source_proposal.py publish` write an `outcome` step output of `ok`,
  `main-advanced` or `failed` beside their fixed summary lines. The name
  `main-advanced` keeps it distinct from the existing release status
  `advanced`, which means a new revision was published. The mapping is
  explicit: release statuses `unchanged`, `repaired` and `advanced` give `ok`;
  push status `published` gives `ok`; publish statuses `closed`, `unchanged`
  and `published` give `ok`; a `ReleaseFailure("main advanced")`, or a push or
  publish failure refused because main advanced, gives `main-advanced`; push
  status `detach-failed` gives `failed`, since the push step exits non-zero;
  every other failure gives `failed`.
- `src/omnipack/live_check.py` records `status` on an inconclusive entry only
  when it came from `HttpStatusError` other than 404 or 410 (a status the
  client does not retry), so a 403 is distinguishable from a 429 after
  retries, which arrives as `TransientHttpError` and, like a timeout or a
  connection failure, lands in `unchecked`.

**The escaped, budgeted renderer moves into `workflow_support.py`.** The run
summary, the PR body and finding bodies all need the same escaping and "and N
more" budget; moving `_render_report`'s core avoids a second copy. Reconcile,
not the producer, renders each finding's raw detail lines through it, so a
body can carry no markup a producer wrote, whatever the producer read. The
alternative, importing `source_proposal` from `alerts`, would couple the alert
script to one producer.

**Alert jobs.**

- `nightly.yml`: `alert`, needs `prepare` and `publish`, under the existing
  workflow-level group.
- `source-maintenance.yml`: `alert`, needs `check` and `publish`, under the
  per-source group on each call, so codm and Quiver reconcile independently.
  A called workflow's jobs cannot exceed the caller job's grant, so the `codm`
  and `quiver` jobs in `source-catalog.yml` add `issues: write`, commented as
  used only by the called alert job; `check` and `publish` keep declaring
  their own narrower sets without it.
- `source-catalog.yml`: `alert-live-check`, needs `live-check`, in its own
  non-canceling group `omnipack-live-check-alerts`.

Each runs under `if: always()` combined with the canonical-repository and
`main` guard, holds `permissions: issues: write` only, checks out only
`scripts/` (sparse) with `persist-credentials: false`, runs no `setup-uv`,
and runs `python3 -m scripts.alerts reconcile`. Its findings download
carries `continue-on-error: true`, since `actions/download-artifact` fails on
a missing artifact and a producer that died before uploading must still reach
reconcile as a missing file. Producer results (`needs.<job>.result`) reach it
through `env`. `GH_TOKEN` is passed only to the reconcile step.

**Reconcile.** For each expected producer whose result is `success` or
`failure`: a missing file, or a file that fails validation, raises
that owner's early-failure finding and contributes no other findings or
scope. A producer whose result is `cancelled` raises that owner's
early-failure finding and contributes no other findings or scope, whatever
file it left, exactly as a failed producer with no usable file does. A
producer stopped by its `timeout-minutes` therefore raises that finding and
contributes no other findings or scope whether its result reads `cancelled` or
`failure`: a `failure` result arrives either with no file, or with the file the
emit step wrote on seeing `job.status` `cancelled`, which holds only the
early-failure finding and empty scope. No assumption is made about which
result GitHub reports for a timeout. An owner's manual cancellation raises the
finding too, which is accepted. A producer with any other result, such as
`skipped` for nightly `publish` after `prepare` fails, contributes nothing.
Validation checks `owner`, that every
key and scope entry starts with a prefix the owner owns, the key character set
above (which cannot form `-->`) and a length cap, one-line titles under 256
characters, and that `details` is a list of strings; details are never
rejected for their length, since rendering bounds them. Reconcile then builds each
body itself: the key marker `<!-- omnipack-alert-key: <key> -->` as the first
line, the detail lines HTML-escaped inside `<pre>` by the shared renderer with
the budget left after the marker and run line, so a body always fits 65,536
characters, and the run line. Then:

1. Ensure the `omnipack-alert` label exists, idempotently: create it, and
   treat GitHub's response that the label already exists as success, since
   alert jobs in different concurrency groups can race to create it.
2. List every labelled issue, open and closed, through paginated `gh api`,
   and read each key only from the body's first line, which must be exactly
   one key marker with a valid key; markers anywhere else, including inside
   escaped details, are ignored. Issues without a valid first-line marker are
   ignored. Several issues for one key use the lowest-numbered one.
3. For each finding: create when absent; edit an open issue only when its
   title or finding body changed; reopen and update one closed as completed;
   leave one closed as not planned. The body ends with a run line naming the
   run that opened, reopened or last changed the issue; edit detection
   compares title and body without that line, so a persisting finding with
   unchanged details gets no edit at all and keeps its title, details and run
   line.
4. For each key in the merged scope, not in `unchecked`, and not raised: close
   its open issue as completed with the comment "Not seen in run <url>". When
   its issue is closed as not planned, reopen it and close it as completed
   with the comment "Cleared in run <url>", since GitHub's REST "Update an
   issue" ignores `state_reason` unless the state changes. A mute thus lasts
   one occurrence: a recurrence reopens the issue through the closed as
   completed path, and a run that did not re-check the key leaves the mute in
   place.

Creates and reopens precede closes. Any `gh` failure fails the job with a
fixed reason in the step summary and the command's stderr in the log, as the
publish scripts do.

## Risks / Trade-offs

- [The alert job fails or issues are disabled] -> The red run is the only
  trace. Documented as the residual risk in `docs/alerts.md`.
- [A runner flake opens and the next clean run closes an issue] -> Two
  notifications per flake, accepted to keep the workflows stateless; "main
  advanced", the one routinely self-healing failure, raises nothing.
- [A host that blocks bots keeps a 403 finding open] -> The owner closes it as
  not planned; it stays muted until a run sees the URL answer, and a 404 or
  410 opens its own issue meanwhile.
- [A host alternates between a 403 and a 429 or a timeout] -> The inconclusive
  runs leave the 403 issue as it is rather than closing and reopening it.
- [Findings files are written next to upstream-derived data] -> Treated as
  untrusted: validated, never interpolated, keys restricted to a safe
  character set, raw details escaped by reconcile itself inside `<pre>`, and
  an issue's key read only from its body's first line.
- [A manual re-run of an older run's alert job after a newer run reconciled]
  -> It can close, reopen or clear the mute of an issue from stale findings;
  the next scheduled run corrects it, and a cleared mute must be re-muted by
  hand. Accepted rather than guarded. Scheduled runs cannot cause this,
  because each alert job is serialized in a non-canceling group. Documented
  in `docs/alerts.md`.
- [A first run opens several issues at once] -> Expected: one per currently
  uncategorized family.

## Migration Plan

Merge, then whichever alert job runs first creates the label, and the first
nightly run opens issues for the current build warnings. Rollback: delete the alert jobs and emit steps; open
issues stop updating and can be closed by hand.
