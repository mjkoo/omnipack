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

Each run selects main once in the Actions checkout and captures that HEAD as its
base. It rejects initial tracked modifications and uses that workspace throughout.
The workflow synchronizes the locked Python environment once, then the publisher
runs:

```sh
uv run --no-sync pack build
uv run --no-sync pack verify
```

The structural gate requires complete, successful, fresh evidence matching the
candidate inputs and verifier identity. Evidence validation runs in the selected
revision's locked runtime, including its identity, input paths, and report schema. Development CI owns formatting,
lint, types, packaging and the full suite; nightly does not repeat those checks
or verify committed packs before building. Existing warnings and generated-source
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
recognizing a no-op, the publisher rechecks main. If main advanced, the run fails
without another build or push. Rerun manually or wait for the next scheduled run
to build the newer revision. It never rebases generated output, cherry-picks a
stale candidate, retries the push, or force-pushes.

A rejected or ambiguous push is reconciled by reading remote history. If the
intended commit is in main's history, publication is confirmed even if a later
commit has followed it. Confirmed absence fails the run. An unreadable remote
result is reported as **uncertain**, without another blind push or a claim of non-publication.

After confirmed main publication or a verified no-op, the run synchronizes `single-screen.json` and `dual-screen.json` to the owned prerelease
at tag `continuous`. The release title is `omnipack revision N`. Both variants
share that revision, and only a change to either JSON increments it. README-only
and package-id-cache-only changes do not advertise a pack update. The stable
release downloads are:

- <https://github.com/mjkoo/omnipack/releases/download/continuous/single-screen.json>
- <https://github.com/mjkoo/omnipack/releases/download/continuous/dual-screen.json>

Synchronization records a pending target, replaces only changed assets, verifies
both downloaded asset digests, then promotes the release title and completed
state. A failed or uncertain main publication performs no release writes. A
release failure preserves the independently confirmed main SHA and fails the run.
Seed readiness gates only this release stage; valid main output can publish even
when the seed is missing, malformed or unowned.

## Permissions and repository prerequisites

The workflow uses `GITHUB_TOKEN` with job-scoped `contents: write` for main and
release publication. Checkout credential persistence is disabled. Push credentials
are supplied only to the push process, and release requests use authorization
headers. No PAT, automatic repository-setting changes, or ruleset bypass is
provided.

Before enabling operational publication, a maintainer must confirm that:

- Actions is enabled, and organizational policy permits
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
release discovery after confirmed main publication or a verified no-op. A missing,
malformed or unowned seed fails release synchronization without release writes;
main remains independently successful. Structural verification never queries the
seed and can pass before bootstrap. Synchronization retains ownership and digest
checks. After explicit bootstrap, a later freshly verified main no-op can publish
the first asset pair at revision one.

A token-authored push does not trigger ordinary push CI. Development CI checks
code changes before landing; nightly checks the generated candidate and its exact
publication bytes. There is no CI-status polling gate. These platform behaviors
were checked against
GitHub's [workflow-trigger documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)
and [protected-branch documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
Scheduling also requires the workflow on the default branch; GitHub documents
schedule delays and dropped queued jobs in its
[event reference](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Failure and recovery

Use Actions step status, logs, summaries and available reports to investigate a
failed run. Main confirmation and its SHA are logged and flushed before release
work starts. A release or reporting failure cannot erase that earlier confirmation.
A failed refresh does not publish its locally updated package-id cache.

Automation no longer creates, updates or closes issues. Existing issues are left
untouched; any migration is a separate maintainer operation. Historical records
retain the legacy ownership marker `<!-- obtainium-pack:nightly-publishing -->`.
Actions owns workspace disposal.

Release diagnostics report completed and pending revisions separately from the
main publication result. If an interruption occurs while replacing assets, the
old completed revision stays advertised even though manual downloaders can see a
missing asset or a mixed pair. A later run rediscovers and repairs the owned
release from a freshly verified pair without duplicating a revision. Permission,
immutability, ownership, or protection failures remain visible and are not
worked around by changing repository settings.

## Diagnostics

The concise Actions summary and run result distinguish main publication, no-op,
failure or uncertainty from release synchronization. They include available run,
base, candidate and confirmed published identifiers, the failing stage, and
completed or pending release revisions. Verification evidence is structural and
offline; missing reports do not establish verification success.

The `nightly-publishing-<run-id>` artifact offers available redacted
`run-result.json`, `build-report.json` and `verify-report.json` for 14 days,
after either success or failure. Its
explicit file allowlist excludes APKs, raw HTTP caches, credentials and unrelated
files. Diagnostics treat source text as data and redact credential values.
Actions step status is the authority for artifact upload; the captured run result
does not claim an upload outcome. Actual upload errors fail the step. Missing
reports after early setup or helper failure are acceptable.

Summary writes are best effort, and a write error remains a visible failure.
Setup failures and unexpected helper failures may leave only Actions status and
logs. There are no fallback-finalization commands, completion markers or result
reload recovery. Hard cancellation or runner loss may prevent even those logs
from arriving; an interrupted run never establishes successful publication.

## Post-landing operational acceptance

This is a **future maintainer operation**, not an implementation test already
performed. It can push to main and modify the real rolling release.

1. Check the repository prerequisites above after landing the workflow.
2. In Actions, select **Nightly publishing**, choose **Run workflow**, explicitly
   select **main**, and dispatch it.
3. Inspect the summary and retained reports. Confirm the selected base and run
   identifiers, complete successful candidate evidence, and structural/offline
   verification mode.
4. Confirm either the published SHA in main's history with only allowed paths,
   or a verified no-op. A failed or uncertain result is not acceptance; inspect
   its failing stage and remote history before deciding what to do next.
5. Confirm release synchronization separately, including both stable JSON downloads
   and the shared completed revision. If it failed, retain the main confirmation,
   resolve the reported release prerequisite, and rerun with fresh verification.
6. Check Obtainium import, unchanged polling, revision-change notification,
   acknowledgement and re-import on devices.
7. Record the run URL, base/published SHA or no-op, structural verification result,
   release revision/outcome, diagnostic upload status and device observations in
   the maintainer's operational record.

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

See [nightly publication validation](nightly-publication-validation.md) for current
implementation checks
and the distinction between controlled tests and operational acceptance.
