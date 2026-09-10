# Nightly publishing

The **Nightly publishing** workflow is scheduled daily at **3:00 AM Eastern**
(`America/New_York`), following daylight saving time, and offers
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
uv run --no-sync pack verify
```

The structural gate requires complete, successful, fresh evidence matching the
candidate inputs and verifier identity. Evidence validation runs in each
selected revision's locked runtime, including its identity, input paths, and
report schema. Existing warnings and generated-source
soft failures retain their current policy. Verification makes no network requests.
Building retains source fetching and APK package-ID discovery. A structurally
invalid selected build blocks publication without choosing another project.
Unavailable app release metadata after a successful build does not add a
publication gate or trigger reselection.

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

After confirmed main publication or a verified no-op, the same attempt
synchronizes `single-screen.json` and `dual-screen.json` to the owned prerelease
at tag `continuous`. The release title is `omnipack revision N`. Both variants
share that revision, and only a change to either JSON increments it. README-only
and package-id-cache-only changes do not advertise a pack update. The stable
release downloads are:

- <https://github.com/mjkoo/omnipack/releases/download/continuous/single-screen.json>
- <https://github.com/mjkoo/omnipack/releases/download/continuous/dual-screen.json>

Synchronization records a pending target, replaces only changed assets, verifies
both downloaded asset digests, then promotes the release title and completed
state. A failed or uncertain main publication performs no release writes. A
release failure preserves the independently confirmed main SHA, fails the run,
and keeps the owned failure issue open.

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
- The `continuous` tag and prerelease are either absent, ready for the explicit
  bootstrap below, or already owned by omnipack. A conflicting tag, unowned or
  malformed release, immutable release, or inadequate release permission blocks
  synchronization. Automation does not change protections or repository settings.

### One-time rolling release bootstrap

Bootstrap is an explicit, write-capable maintainer operation. Run it only after
reviewing the repository and tag state and authorizing creation of the real seed:

```sh
GITHUB_REPOSITORY=mjkoo/omnipack \
GITHUB_TOKEN="<maintainer token>" \
uv run --no-sync python -m scripts.nightly bootstrap-release
```

The command targets `main` and creates the owned `continuous` prerelease at
revision zero with no assets. It refuses a conflicting tag, malformed or unowned
release, or immutable release, and safely reports an existing valid seed. The
token needs permission to read and create releases and tags in the canonical
repository; branch or tag protections can still reject the operation. Routine
publishing never invokes bootstrap. It checks seed existence and ownership using
release discovery before main publication; a missing or unowned seed blocks main
and release writes. Structural verification never queries the seed and can pass
before bootstrap. Synchronization rediscovers ownership and retains digest checks.

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

Release diagnostics report completed and pending revisions separately from the
main publication result. If an interruption occurs while replacing assets, the
old completed revision stays advertised even though manual downloaders can see a
missing asset or a mixed pair. A later run rediscovers and repairs the owned
release from a freshly verified pair without duplicating a revision. Permission,
immutability, ownership, or protection failures remain visible and are not
worked around by changing repository settings.

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
the workflow status and preserves unavailable-report markers. Retained pre-build
verification is labeled as pre-build evidence. Candidate structural/offline
evidence is unavailable until the post-build verification runs; the two phases
are distinguished even though both use offline mode.

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
   complete successful candidate evidence, and structural/offline verification mode.
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

Do not delete the tracker or rolling release as an implicit rollback. First stop
new nightly runs and inspect any in-flight run. Restoring older JSON through the
publisher is a new content publication and receives a higher shared revision.
If the tracker is intentionally retired, users must remove its Obtainium entry
manually; removing it from a later import does not guarantee device deletion.

See [publishing validation](publishing-validation.md) for implementation checks
and the distinction between controlled tests and operational acceptance.
