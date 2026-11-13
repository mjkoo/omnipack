# Design

## Context

Three scheduled or chained workflows touch the packs each day: **Reviewed
source catalog** on a fixed 04:17 UTC cron, **Nightly publishing** at 03:00
America/New_York (07:00 or 08:00 UTC across daylight saving), and **Release
archive**, which a `workflow_run` trigger starts when each nightly completes.
The live check job and its alert job live in the source catalog workflow. They
share nothing with the per-source jobs except the schedule. See proposal.md for
why the schedule is wrong.

## Goals / Non-Goals

**Goals:**

- The live check reads the packs a nightly just published, with no lag that
  depends on cron arithmetic or daylight saving.
- The live check and alert jobs move unchanged, so their tests and alert keys
  carry over as they are.

**Non-Goals:**

- Changing what `pack check-live` checks, how it reports, or how findings
  reconcile.
- Rebalancing API usage between the live check and the release archive.

## Decisions

### A `workflow_run` trigger on Nightly publishing, in a workflow of its own

A new **Live project check** workflow holds the two jobs unchanged, triggered
by `workflow_run` (Nightly publishing, `completed`, branch `main`) and
`workflow_dispatch`. Its checkout pins `ref: ${{ github.sha }}`, which for
`workflow_run` is the latest `main` commit when the trigger fires. That is
after the nightly's push. Today's Release archive run checked out the nightly
commit this way. The `dangerous-triggers` zizmor finding is ignored inline,
with the same reasoning as Release archive: the jobs check out `main`, consume
no artifact from the triggering run and hold only read or issue access.

Alternatives considered:

- **Move the cron to after the nightly.** The nightly's UTC time shifts with
  daylight saving and its duration varies. A fixed offset either races the
  push or reintroduces a lag, and it breaks silently when the nightly
  schedule changes.
- **A job inside the nightly workflow, after `publish`.** This would tie the
  check's permissions and concurrency to the publisher's, and a failing check
  would turn the publisher's run red. The project already keeps follow-on work
  in its own workflow, as Release archive does.
- **Chain after Release archive.** The archive runs up to five and a half
  hours, which brings the lag back.

### Run whatever the nightly's outcome

The trigger fires on every completion. If the nightly fails, the check reads
the packs already on `main`, so a failed or skipped nightly never costs a day
of coverage. Filtering on `conclusion == 'success'` would have given up that
coverage and saved nothing.

### The source catalog workflow keeps its schedule

Proposal PRs need the owner to merge them, so their timing relative to the
nightly does not matter. 04:17 UTC still has them ready by the owner's
morning.

### Documentation moves next to nightly publishing

The "Live project check" section lived in `docs/source-generation.md` only
because the job shared that workflow. It moves to `docs/publishing.md`, after
the release archive pointer, and the links in `docs/development.md` and
`docs/alerts.md` follow it.

## Risks / Trade-offs

- [The live check and Release archive start together and share the repository
  `GITHUB_TOKEN` API quota] → Both use well under half the hourly quota at
  current pack size. A rate-limited health lookup reads as health inconclusive,
  which raises no finding, so the cost of hitting the limit is lost health
  coverage for that run, never a false alert. A residual-risk note in
  `docs/alerts.md` records this.
- [No live check runs when the nightly does not run at all, for example when
  scheduled workflows are disabled] → The nightly's own failure and its alerts
  surface that first. Manual dispatch remains.
- [The first run after merge comes only after the next nightly] → Accepted.
  Manual dispatch covers an urgent check.

## Migration Plan

Merging deploys it, because `workflow_run` workflows run from the default
branch. The source catalog's next scheduled run no longer includes the live
check, and the next nightly starts the first live check. Open live-check issues
carry over, because keys and reconciliation are unchanged. Rollback is a revert.
