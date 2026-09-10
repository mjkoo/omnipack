# Nightly publishing

The **Nightly publishing** workflow runs daily at **06:23 UTC** and offers
manual dispatch without inputs. Both paths run only in
`mjkoo/omnipack` on `main`. Dispatches from another ref and
fork copies skip the write-capable job. One shared publisher concurrency group
serializes runs without canceling an executing publisher. Each job has a
60-minute timeout. Scheduling is best effort: exact start time and execution
of every queued trigger are not guaranteed.

## Refresh and publication

Each attempt uses a disposable checkout of the observed remote main revision.
It synchronizes the locked Python environment, checks formatting, lint, types,
Python packaging, tests, and committed packs offline, then runs:

```sh
uv run --no-sync pack build
uv run --no-sync pack verify --live
```

The live gate requires complete, successful, fresh evidence matching the
candidate inputs and verifier identity. Evidence validation runs in each
selected revision's locked runtime, including its identity, input paths, and
report schema. Existing warnings and generated-source
soft failures retain their current policy. Metadata verification does not
probe download assets. Building can still download APK data for package-id
discovery. For explicit asset troubleshooting, use
`uv run pack verify --live --probe-assets`; this is not a scheduled operation.

The only publishable paths are:

- `dist/single-screen.json`
- `dist/dual-screen.json`
- `README.md` (generated catalog interior only)
- `config/package-ids.json`

README must contain exactly one valid standalone catalog marker pair. Its prefix
and suffix, including both marker lines, must match the selected base revision
byte-for-byte. Candidate capture and final staged validation both enforce this
boundary, so successful standalone verification cannot authorize handwritten
README changes.

The publisher checks verified bytes against the staged content and resulting
commit. Missing files, symlink replacements, unrelated tracked modifications,
and changed verified bytes reject the candidate. Any changed allowed bytes,
including a cache-only or catalog-only change, produce one bot commit with subject
`chore(dist): nightly rebuild YYYY-MM-DD`. The date is UTC; the body identifies
the run URL and base SHA. Reports and transient caches stay out of commits.
A byte-identical refresh is a successful no-op and creates no commit, including
file-mode-only changes. Byte changes preserve the base file modes. The full
tracked-change allowlist is rechecked when staging finishes.

Publication uses a normal fast-forward push to main. Before either pushing or
recognizing a no-op, the publisher rechecks main. If main advanced, it discards
the candidate and performs one complete fresh attempt at the new revision.
A second advancement fails the run. It never rebases generated output,
cherry-picks a stale candidate, or force-pushes.

A rejected or ambiguous push is reconciled by reading remote history. If the
intended commit is in main's history, publication is confirmed even if a later
commit has followed it. Otherwise, an advanced main can consume the remaining
attempt; an unchanged rejection fails. An unreadable remote result is reported
as **uncertain**, without another blind push or a claim of non-publication.

## Permissions and repository prerequisites

The workflow uses `GITHUB_TOKEN` with job-scoped `contents: write` and
`issues: write`. Checkout credential persistence is disabled. Push credentials
are supplied only to the push process, and issue requests use authorization
headers. No PAT, automatic repository-setting changes, or ruleset bypass is
provided.

Before enabling operational publication, a maintainer must confirm that:

- Actions and repository issues are enabled, and organizational policy permits
  the requested token permissions and pinned actions.
- The workflow is on the default branch, and main is the intended published
  branch.
- Main's branch protections and rulesets permit the intended direct token push.
  Required pull requests, signed commits, or status checks may reject it.
- Artifact policy permits 14-day retention.

A token-authored push does not trigger ordinary push CI, so the checks before
publication are required. These platform behaviors were checked against
GitHub's [workflow-trigger documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)
and [protected-branch documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
Scheduling also requires the workflow on the default branch; GitHub documents
schedule delays and dropped queued jobs in its
[event reference](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Failure and recovery

Handled setup, check, build, verification, and publication failures maintain
one issue titled **Nightly build failing**. Ownership requires both
`github-actions[bot]` authorship and the exact body marker
`<!-- obtainium-pack:nightly-publishing -->`. A matching title alone is not
ownership. This legacy marker stays stable across the omnipack rename so
existing issues remain discoverable. Discovery includes all pages of open and closed issues and excludes
pull requests. The lowest-numbered owned issue is reused and reopened on
recurrence; other open owned duplicates are closed. Repeated failures replace
the body rather than adding comments. Ambiguous creation triggers rediscovery
before any further action.

Confirmed publication or a verified no-op updates and closes existing open
owned issues with recovery evidence. Success never creates an issue. Issue
maintenance failure fails the workflow without undoing a confirmed push; a
later successful run retries closure. A failed refresh does not publish its
locally updated package-id cache.

Disposable-checkout cleanup failures fail the workflow. Diagnostics retain the
confirmed publication outcome, published SHA, and per-attempt reports separately
from cleanup errors. Confirmed publication or a verified no-op still triggers
issue recovery even when cleanup fails.

## Diagnostics

The Actions summary distinguishes publication, no-op, failure, uncertainty,
cleanup, issue maintenance, and upload outcomes. It includes run, base, and published
identifiers where available. Early failures explicitly identify unavailable
reports. Issue bodies are bounded to 4,000 characters and summaries to 16,000.

The `nightly-publishing-<run-id>` artifact retains redacted orchestration JSON
and each attempt's build and verification JSON for 14 days. The file allowlist
excludes APKs, raw HTTP caches, credentials, and unrelated files. Reports from
discarded attempts are retained separately. Artifact upload happens before its
final outcome is known, so consult the final Actions summary and step status
for the upload outcome; the uploaded result initially records it as pending.
Upload failure fails the workflow without rolling back publication.

Diagnostic JSON files are replaced atomically. If a later write fails, fallback
finalization can reload the last complete result and preserve a confirmed
publication and its SHA. Fallback keeps the triggering helper failure visible in
the workflow status and preserves unavailable-report markers. A retained offline verification report is labeled
offline; the summary and orchestration result identify live evidence as
unavailable until a live report exists.

System Python can finalize handled uv/Python setup failures. Hard cancellation
or runner loss may prevent finalization or issue delivery; Actions remains the
fallback record. No successful verification or publication is inferred from
an interrupted run.

## Post-landing operational acceptance

This is a **future maintainer operation**, not an implementation test already
performed. It can push to main and maintain a real issue.

1. Check the repository prerequisites above after landing the workflow.
2. In Actions, select **Nightly publishing**, choose **Run workflow**, explicitly
   select **main**, and dispatch it.
3. Inspect the summary and retained reports. Confirm fresh attempt/base IDs,
   complete successful `live` evidence, and metadata-only verification mode.
4. Confirm either the published SHA in main's history with only allowed paths,
   or a verified no-op. A failed or uncertain result is not acceptance; inspect
   its failing stage and remote history before deciding what to do next.
5. If an owned failure issue was already open, confirm that recovery evidence
   was recorded and the issue closed. Do not manufacture a live failure merely
   to test issue creation.
6. Record the run URL, base/published SHA or no-op, verification mode, and issue
   outcome in the maintainer's operational record.

## Rollback

Disable **Nightly publishing** in Actions to stop new scheduled publication.
Inspect any already-running publisher separately; disabling the workflow does
not establish that an in-flight push was canceled. The existing raw dist URLs
continue serving main. Reverting published content is a separate maintainer
decision, not an automatic rollback performed by the helper.

See [publishing validation](publishing-validation.md) for implementation checks
and the distinction between controlled tests and operational acceptance.
