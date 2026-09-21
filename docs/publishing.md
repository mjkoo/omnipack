# Nightly publishing

The **Nightly publishing** workflow is scheduled daily at 3:00 AM Eastern
(`America/New_York`, so it follows daylight saving time) and can also be
dispatched manually with no inputs. Both paths run only for `mjkoo/omnipack`
on `main`; a dispatch from another ref, or a run in a fork, does not publish.
One `omnipack-nightly-publisher` concurrency group serializes runs without
canceling one already in progress. The workflow runs two jobs in sequence,
each limited to 60 minutes, so a run can take about 120 minutes end to end.
Scheduling is best effort: GitHub does not guarantee an exact start time or
execution of every queued trigger.

## Two-job flow and credential split

The workflow has two jobs, `prepare` and `publish`, so that nothing which
builds, generates or handles upstream data ever shares a job, a workspace or
the write credential with the steps that push to `main` or write the release.

**`prepare`** holds `permissions: contents: read` and no step in it sets
`GH_TOKEN` or otherwise receives a token beyond that read-only job token. It
checks out `${{ github.sha }}` with `persist-credentials: false`, sets up uv
with its GitHub Actions cache disabled, so that nothing this job writes can be
restored into a later run, syncs the locked project environment, and runs:

```sh
uv run --no-sync python -m scripts.nightly prepare
```

`prepare`:

- removes any `.build/report.json` and `.build/verify.json` left in the
  workspace by an earlier run, so the diagnostics upload carries only this
  run's reports;
- requires `HEAD` to equal `GITHUB_SHA` and the checkout to be clean;
- runs `pack build`;
- rejects any tracked change outside `dist/single-screen.json`,
  `dist/dual-screen.json` and `README.md`, and rejects any of those three that
  is missing, a symlink, not a regular file, or executable;
- requires the README's generated-catalog markers and everything outside them
  to match the checked-out base revision byte for byte;
- when any of the three files changed, commits them locally as
  `github-actions[bot]` with hooks disabled, with the subject
  `chore(dist): nightly rebuild <UTC date>` (the date as `YYYY-MM-DD`) and a
  body naming the workflow run's URL and the base SHA;
- runs `pack verify`;
- requires the checkout to be clean again afterward;
- when it committed, confirms `HEAD` is that commit and writes a
  `git bundle create <dir>/candidate.bundle <base>..HEAD`.

It writes `changed`, `sha` and `base` as job outputs, and its step summary
line is `no-op at <sha>`, `prepared <sha>`, or the name of the stage that
failed: `checkout`, `build`, `allowlist`, `README boundary`, `commit`,
`verify`, `drift after verify` or `bundle`. `pack build` and `pack verify` write their
own output to the job log.

**`publish`** needs `prepare`, holds `permissions: contents: write`, and runs
no `setup-uv` and no `uv sync`. It checks out `${{ github.sha }}` shallowly
with `persist-credentials: false`, then runs a guard step,
`test "$BASE_SHA" = "$GITHUB_SHA"` with `BASE_SHA` mapped from
`needs.prepare.outputs.base`, before any step that receives `GH_TOKEN`. The
checkout uses the job token only to fetch that revision, and
`persist-credentials: false` keeps it out of `.git/config`. Only the push and
release steps set `GH_TOKEN: ${{ github.token }}`:

```sh
python3 -m scripts.nightly_write push --bundle <downloaded bundle path>
python3 -m scripts.nightly_write release
```

The push step runs only when `prepare` produced a change; the release step
has no `if` condition, so Actions' implicit success gate runs it whenever
`prepare` succeeded and the push step either succeeded or was skipped.

### Bundle hand-off

When `prepare` committed a candidate, it uploads the bundle as
`nightly-handoff-<run-id>` with one-day retention; the upload fails if the
bundle is missing. `publish` downloads that
same artifact, with a SHA-pinned `actions/download-artifact`, only when
`changed` is `true`. The bundle carries only the candidate commit, its trees
and its changed blobs; it never carries the checked-out worktree or the
project environment. `push` verifies the bundle, fetches its `HEAD`, and
requires the fetched commit to equal `sha`, its only parent to equal `base`,
and every changed path to be one of the three allowed files at mode `100644`
on both sides, all before doing anything else.

### The write job's runtime

`publish` installs nothing from the project. `scripts/nightly_write.py`, and
`scripts/workflow_support.py`, which holds the helpers it shares with the
source proposal workflow, import only the standard library and each other,
and run on the runner's preinstalled `python3`, which is 3.12 on
`ubuntu-latest` even though the project otherwise requires Python 3.14. Each
module starts with `from __future__ import annotations` so that no
annotation is evaluated at import time, and `pyproject.toml` pins their ruff
target to `py312`. `just check-py312` runs the tests of the write jobs'
scripts (`tests/test_nightly_write.py`, `tests/test_source_proposal.py` and
`tests/test_workflow_support.py`) under a real CPython 3.12, without the
project environment, since ruff alone cannot catch a 3.13-or-later
standard-library API or an annotation-evaluation difference. Locally it
uses `python312` from the `nixpkgs` this repository's flake pins; CI's
`check` job runs `just check-py312 /usr/bin/python3` against the runner's
own interpreter.

Every git command the write job's scripts run adds `-c core.hooksPath=/dev/null`,
even though the write job's checkout is fresh and runs no project code before
those scripts, as a defense against a future checkout option or runner image
that installs a hook.

## Permissions and direct-push prerequisites

The workflow grants no permissions at workflow level; `prepare` holds
`contents: read` and `publish` holds `contents: write`. `publish` pushes with
the ordinary job token (`${{ github.token }}`), handed to `git` through
`gh auth setup-git`, so there is no personal access token and no automatic
change to repository settings.

Before relying on nightly publishing, confirm that:

- Actions is enabled for the repository, and organizational policy permits
  the job token permissions and the pinned actions the workflow uses.
- The workflow file is on the default branch.
- `main`'s branch protections and rulesets permit a direct push from the
  Actions job token. Required pull requests, required signed commits, or
  required status checks on `main` will reject the nightly push.
- Artifact retention policy permits the 14-day diagnostics retention and the
  one-day bundle retention.
- The `continuous` tag and prerelease are either absent and ready for the
  bootstrap below, or already an owned, published, mutable prerelease.

## One-time rolling release bootstrap

Before the first nightly release synchronization, a maintainer creates the
`continuous` prerelease by hand:

```sh
gh release create continuous --prerelease --title "omnipack revision 0" \
  --notes-file <file>
```

where `<file>` holds:

```
<!-- omnipack:rolling-pack -->

Initial pack publication is pending; JSON assets are not yet published.
```

The seed carries the ownership marker and no digest record. Routine
publishing never creates or replaces this seed; it only checks it. The
release must stay a published, mutable prerelease: not a draft, not
immutable, and its title must keep matching `omnipack revision <N>`. The
first successful synchronization replaces the seed's body outright with the
canonical body below and advances the title from revision 0 to revision 1.

## Release digest record and served-asset check

After a successful main push, or a verified no-op, the release step reads
`dist/single-screen.json` and `dist/dual-screen.json` at `HEAD`, hashes them
with SHA-256, and requires `git ls-remote origin refs/heads/main` to still
report `HEAD` before writing anything. It then reads the release with
`gh release view continuous --json name,body,assets,isDraft,isPrerelease,isImmutable`
and requires the ownership marker `<!-- omnipack:rolling-pack -->`, a title
matching `omnipack revision <N>`, `isDraft` false, `isPrerelease` true and
`isImmutable` false.

It compares two things against the freshly hashed pair: the digest record
line in the release body,

```
<!-- omnipack:digests single-screen.json=<sha256> dual-screen.json=<sha256> commit=<sha> -->
```

and the `digest` GitHub reports for each served asset. A missing asset, or an
asset with no reported digest, counts as a mismatch.

- When the record and both served digests already match the pair, it writes
  nothing and summarizes `unchanged at revision N`.
- When the record matches but a served digest does not, it re-uploads both
  assets with `gh release upload continuous ... --clobber` and makes no edit,
  so the title revision does not advance; it summarizes
  `repaired at revision N`.
- Otherwise (the record differs, or there is none) it uploads both assets and
  then makes one `gh release edit continuous --title "omnipack revision N+1"
  --notes-file <file>` whose body is the canonical template below, replacing
  the previous body outright; it summarizes `revision N+1`.

The canonical body, written on every edit:

```
<!-- omnipack:rolling-pack -->

Download the current pack pair directly from the stable URLs:
- https://github.com/mjkoo/omnipack/releases/download/continuous/single-screen.json
- https://github.com/mjkoo/omnipack/releases/download/continuous/dual-screen.json

<!-- omnipack:digests single-screen.json=<sha256> dual-screen.json=<sha256> commit=<sha> -->
```

The stable download URLs serve whatever the most recent upload left in place.
During publication an asset can be missing or the pair can be mixed across
revisions. Use the [raw-main download links](curation.md#tracking-omnipack-itself)
as the fallback until a later run completes or repairs the pair.

## Failure and rerun behavior

A failed `prepare` publishes nothing: `publish` never runs its push or
release steps unless `prepare` succeeded. Within `publish`, the base guard
step fails before anything else if the checked-out revision is not the one
`prepare` built.

**Ambiguous push.** `push` treats a rejected or erroring `git push` the same
way regardless of whether the push actually reached `main`: it summarizes
`push failed for <sha>` and exits nonzero, without inspecting remote history
to decide whether the commit landed. If the commit did land, the next run's
`prepare` finds no difference from `main` (a no-op), and the release step
still synchronizes the release from that already-published pair; recovery
therefore lags by at most one run rather than needing a retry.

**Checkout after a landed push.** If the push succeeds but checking out the
pushed commit afterward fails, `push` summarizes `published <sha>`, because
the commit is on `main`, and still exits nonzero, so the release step does
not run on the old checkout. The next run synchronizes the release.

**Served-asset repair.** A run whose record matches but whose served assets
do not (for example, one asset was replaced or deleted by hand, or an
earlier upload was interrupted after only one asset succeeded) re-uploads
both assets without advancing the revision, as described above.

**Main has moved past the run's base.** Before writing anything, `push`
requires `git ls-remote origin refs/heads/main` to report the run's base SHA,
and `release` requires it to report `HEAD` (the pushed commit, or the base
for a no-op). Either check failing means a push landed on `main` after this
run's `prepare` checked out its revision. That push may be another run's, or
this run's own: a write job re-run after its push landed finds `main` at its
candidate, not its base. In either case the write
job fails without writing anything: `push` summarizes
`push failed for <sha>: main advanced`, and `release` summarizes
`release failed: main advanced` with no bootstrap guidance. Re-running that
same failed job reuses the same stale checkout and stale `prepare` outputs,
so it fails the same way again; a new workflow dispatch is what builds and
verifies the newer `main` and lets that newer run publish or synchronize it.
A rerun therefore never publishes an older pair over a newer one, and never
moves the release backward.

**Release prerequisites missing.** A missing release, a missing or duplicated
ownership marker, a malformed title, a draft, a release that is not a
prerelease, or an immutable release fails the release step with
`release failed: <reason>` plus the bootstrap guidance above, without any
release write. The release counts as missing only when `gh release view`
reports `release not found`; any other failure to read it, such as an API
error, fails with `release failed: could not read release` and no bootstrap
guidance. A failed release step never undoes a successful `main` push;
the pushed commit stays on `main`.

## Step summary lines

Each summary line has one owner, so a run's Actions summary shows at most one
line each from `prepare`, `push` and `release`:

- `prepare`: `no-op at <sha>`, `prepared <sha>`, or the failing stage name.
- `push`: `published <sha>`, `push failed for <sha>`, or
  `push failed for <sha>: main advanced`. `published <sha>` on a failed step
  means the push landed but the checkout after it failed.
- `release`: `unchanged at revision N`, `repaired at revision N`,
  `revision N+1`, or `release failed: <reason>` (with bootstrap guidance when
  the release itself is the problem).

## Diagnostics

`prepare` always uploads `.build/report.json` and `.build/verify.json` as
`nightly-diagnostics-<run-id>`, with 14-day retention, whether or not the run
succeeded; a missing file is ignored rather than failing the upload. When it
committed a candidate, it also uploads the bundle as
`nightly-handoff-<run-id>` with one-day retention. Both uploads replace an
artifact of the same name, so **Re-run all jobs**, which keeps the run ID,
does not fail on a name an earlier attempt already used. Actions' own step
status, logs and these artifacts are the record of a run; there is no
separate issue-tracking or notification mechanism. A failing `git` or `gh`
command writes its error output to the job log, never to the step summary.

## Rollback

Disable **Nightly publishing** in Actions to stop new scheduled and manual
runs; this does not cancel a run already in progress, which must be inspected
separately. The raw `dist/` links on `main` keep serving whatever was last
published. Reverting already-published content is a separate maintainer
decision: restoring older JSON through the workflow is a new publication and
receives a new, higher revision, not a rollback of the shared one. Do not
delete the `continuous` release or the omnipack tracking entry as an implicit
rollback; if a tracker is intentionally retired, users must remove its
Obtainium entry by hand, since removing it from a later import does not
guarantee on-device deletion.

See [reviewed codm source generation](source-generation.md) for the separate
workflow that proposes changes to the committed codm source catalog; nightly
publishing never writes that catalog or any other configuration.
