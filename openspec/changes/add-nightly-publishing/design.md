## Context

See proposal.md for motivation. `pack build` fetches sources, updates the
package-id cache, writes `.build/report.json`, and replaces the output pair
after offline validation. `pack verify --live` separately records fresh
metadata-only evidence in `.build/verify.json`. Its errors block success;
warnings do not. Ordinary CI checks committed output offline. Neither command
currently publishes to GitHub.

## Goals / Non-Goals

**Goals:** Make publication a small orchestration layer around those commands,
with explicit terminal outcomes and deterministic tests of remote failures.
Preserve main when build or verification fails, including cache-only changes.

**Non-Goals:** Change resolver semantics, repair upstream entries automatically,
probe downloads on a schedule, add a public CLI command, persist failed-run
package-id work remotely, or introduce release/PR publication.

## Decisions

### Workflow and helper boundary

Add `.github/workflows/nightly.yml` and a repository helper under `scripts/`
with injected process and GitHub boundaries for tests. YAML owns triggers,
tool setup, credentials, timeouts, concurrency, and diagnostic upload. The
helper owns refresh attempts, publication decisions, and issue reconciliation.
This keeps race/error behavior testable without embedding substantial shell
logic in YAML or expanding the public `pack` CLI.

Use a daily schedule at 06:23 UTC and `workflow_dispatch`, without user-supplied
source refs or verification options. Both operate only in the canonical
repository on main; dispatches from other refs and fork copies skip before
write-capable work. Use one repository-wide publisher concurrency group with
`cancel-in-progress: false`, and a 60-minute job timeout. Queued runs need not
all execute; an executing run is not deliberately superseded.

Match existing pinned actions and uv/Python setup. Sync from the lockfile and
run the existing offline Python checks, build, and pack verification on each
selected main revision before the live refresh. Do not depend on a later
push-triggered CI run to validate the automation commit. GitHub documents that
events produced by `GITHUB_TOKEN` generally do not start new workflows; the
relevant consequence here is that the bot's push will not run ordinary push CI.
See [workflow trigger guidance](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
Scheduled execution also depends on the workflow existing on the default
branch; see [trigger troubleshooting](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows).

### Fresh candidates and exact publication scope

Start each attempt in a clean disposable checkout of the observed main SHA.
Run `uv run --no-sync pack build` followed, only on success, by
`uv run --no-sync pack verify --live`. Retain current build soft-failure and
verifier warning policies. No `--probe-assets` invocation is added; generated
package-id discovery can still read APK data as part of building.

Require complete successful live evidence for the candidate's current inputs
and current verifier identity. Run evidence validation in the selected attempt's
locked Python environment, importing that revision's verifier identity, input
paths, and report schema rather than the initial workflow checkout's runtime.
Snapshot the publishable bytes after verification
and check they remain unchanged before staging. Reject unexpected tracked
changes, missing outputs, or symlink replacements. Stage only
`dist/single-screen.json`, `dist/dual-screen.json`, and
`config/package-ids.json`, then assert the staged path set and content match
the verified candidate. Recheck the full tracked-change allowlist when staging
finishes. Compare candidate bytes directly with base blobs and preserve base
file modes in the index, so executable-bit changes cannot create a commit or
drift into a byte-changing commit. Reports and transient metadata caches stay uncommitted.

If any allowed file changed, create one conventional commit with subject
`chore(dist): nightly rebuild YYYY-MM-DD` using the UTC publication date,
bot identity, and a body identifying the workflow run and base SHA. Cache-only
changes warrant a commit because they preserve resolution work. If none changed,
record a successful no-op after confirming the observed main is still current.

### Main advancement and push outcomes

Use only a normal fast-forward push to main. Fetch main before publishing;
if it differs from the attempt's base, discard that candidate and start one
fresh attempt on the new SHA, including tool sync, checks, build and live
verification. Do not cherry-pick or rebase generated output. A second main
advancement exhausts the two-attempt budget and becomes a reported failure.

A rejected or ambiguous push requires a remote read. If the intended commit
is on remote main's history, publication succeeded, even if a maintainer has
since advanced main. Otherwise, an advanced main can consume the remaining
fresh-attempt budget. A rejection with unchanged main, or inability to determine
the remote result, fails without force-pushing. No-op attempts also check main
again before being treated as successful. There is no claim of preventing a
maintainer from updating main immediately after that observation.

Disposable attempt directories allow discarding candidates without touching a
developer checkout. Preserve reports outside those directories before retrying.
Record disposable-checkout cleanup errors separately from the terminal
publication result. Cleanup failure must retain confirmed publication SHAs and
captured reports, and fail the workflow even if a push already succeeded.
Confirmed publication or a verified no-op still authorizes issue recovery;
cleanup failure remains independently visible in the result and summary.

### Authentication and repository settings

Use `GITHUB_TOKEN` for authenticated metadata and GitHub operations, with job
permissions `contents: write` and `issues: write`. Keep checkout credential
persistence disabled and expose push credentials only to the push operation,
without writing them into remote URLs or diagnostic files. No PAT, new Python
runtime dependency, repository setting changes, or ruleset bypass is added.

Direct publication depends on the repository allowing that token to push main.
Document this prerequisite; a permissions or branch-rule rejection is a visible
publication failure. The implementation must verify the current official
workflow/token semantics and reuse pinned tooling conventions.

### One failure issue and recovery

Identify the owned issue by an exact hidden body marker
`<!-- obtainium-pack:nightly-publishing -->` and the GitHub Actions bot author,
not by title alone. Use title `Nightly build failing`. Search all pages of
repository issues, excluding PRs, across open and closed states. Reuse the
lowest-numbered matching issue, reopening it on recurrence; if none exists,
create it. If multiple owned issues exist, update the canonical one and close
the other open owned duplicates. Never edit an unmarked user issue.

On a handled setup, check, build, verify, or publication failure, replace the
owned issue body with a bounded summary: failing stage, run URL, attempt/base
SHA, whether publication is confirmed, and diagnostic links. Use structured
API bodies or body files; upstream text is data, never shell code. Repeated
failures update the body rather than appending comments. Before retrying an
ambiguous issue creation, requery ownership to avoid blind duplicate creation.

After confirmed publication or a verified no-op, update and close existing
open owned issues with recovery evidence. Do not create an issue for success.
Issue maintenance failure makes the workflow fail and appears in the summary;
it never rolls back a successful push. A later successful run retries recovery.
Hard cancellation or runner loss may prevent finalization; Actions remains the
fallback record, and no issue-delivery guarantee is made for those cases.

### Diagnostics and validation

Retain per-attempt build and verification JSON plus an orchestration result
containing stage outcomes, base and published SHAs, timestamps, and run URL.
Upload the explicit diagnostic allowlist with 14-day retention on handled
success and failure, and render a concise Actions summary. Never upload the
entire workspace, downloaded APKs, credential values, or raw HTTP caches.
Missing reports after early failures are recorded as unavailable. Retained offline
verification reports are labeled separately from live evidence. Replace JSON
files atomically so a failed rewrite leaves the prior complete publication
result available to fallback finalization. Fallback retains missing-report markers
and carries the triggering helper failure into the workflow status independently
of confirmed publication and issue recovery. Upload
failure is visible as a failed workflow step, without reversing publication;
the summary and logs remain fallback evidence.

Use controlled process/API responses for orchestration and temporary local Git
repositories for fast-forward, concurrent-update, staged-content, and ambiguous
push cases. Tests must never push to the real repository or create real issues.
Run actionlint, zizmor, the focused tests, and `just check-all`. A real manual
dispatch is a separate operational action after landing, not an implementation
test that silently publishes changes.

## Risks / Trade-offs

- All-entry metadata gating can block refreshes during upstream outages.
  Preserve published files, report the failing stage, and retry on a later run.
- Metadata success does not prove asset reachability or APK validity. Keep
  explicit asset probes available for manual troubleshooting.
- A busy main can exhaust the retry budget. Bound upstream traffic and let the
  next scheduled/manual run retry instead of looping indefinitely.
- Token restrictions can prevent pushes or issue updates. Document prerequisites
  and retain independent workflow evidence without weakening repository rules.
- An interrupted runner cannot reliably finalize diagnostics or issues. Report
  this operational limit and use later runs for recovery.

## Migration Plan

No data migration is needed. Land the workflow, helper, tests, and documentation
together after review. Confirm repository write/issue prerequisites before the
first operational dispatch. Record that run's publication or no-op outcome and
metadata-only verification mode without claiming asset health. Disable the
workflow to roll back automation; existing raw distribution URLs keep working.
Any rollback of published content is a separate maintainer decision.
