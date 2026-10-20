# Proposal

## Why

The owner does not see GitHub Actions failed-run notifications, so every
unattended problem in omnipack goes unnoticed: a nightly stage or release
failure, a source whose generation, checks or publish fail (which withholds
its PR every day), a project `pack check-live` finds gone, and build warnings
that fail nothing (stale denials, uncategorized families, stale category
keys). GitHub issues do reach the owner. The main specs currently forbid
issues in both scheduled workflows, so routing alerts there reverses that
decision rather than filling a gap.

## What Changes

- Each actionable unattended problem becomes a **finding** with a stable key
  (owning job, unique per source, stage, and a subject such as a URL or family
  where there is one, encoded to a safe character set). Each finding has one GitHub issue labelled `omnipack-alert`, which a
  run opens, updates while the finding persists, and closes when a later run
  re-checks and no longer sees it. A key is re-checked only when the stage or
  step it names actually ran.
- Closing an issue as "not planned" mutes that occurrence of its finding: a
  run that sees the finding clear closes the issue as completed, so a
  recurrence reopens it. Closing as "completed" while it persists reopens it.
- Findings are raised for: nightly preparation stage failures, nightly push
  and release failures, each source's generation, staging, check and publish
  failures, live-check runs that cannot read the packs, live-check URLs that
  answer 404 or 410, separately those ending in any other error status the
  HTTP client does not retry, and each
  item in the build report's stale denials, uncategorized families and stale
  category assignments.
- A push or publish refused because `main` advanced past the run's base never
  raises a finding: the next scheduled run resolves it.
- Routine outcomes raise nothing: skipped listings (screening working as
  designed) and transient live-check outcomes (retried statuses, timeouts,
  connection failures, URLs left unchecked by the time budget), which also
  close nothing.
- Each producing job writes a findings file; a separate alert job per
  workflow, holding only issue-write permission, validates it and reconciles
  issues. No job gains both upstream-derived data and a write token; the
  source catalog's calling jobs grant issue access for the called alert job
  only.
- Run verdicts do not change: jobs stay red or green exactly as today, even
  when emitting or uploading findings fails.
- `pack check-live`'s report records the HTTP status on inconclusive entries
  that came from a non-retried error status.
- Retires the "no failure issues / no issue operations" rules in
  `nightly-publishing` and `source-generation`, and the docs sentence that
  there is no issue-tracking or notification mechanism.

Estimate: 1 new capability with 3 requirements and about 25 scenarios; 7
modified requirements across 3 capabilities, adding about 5 scenarios; about
450 implementation lines (the alert script, emitters, a shared renderer moved
from the source proposal script, workflow jobs, the live-check status field);
about 600 test lines.

Visible failure plus a rerun does not suffice here: the visible failure is
exactly the channel that does not reach the owner. Duplicate-issue handling
and label bootstrapping are left to design, not specified.

## Capabilities

### New Capabilities

- `maintenance-alerts`: findings, their keys and owners, the issue lifecycle
  and mute, findings-file validation and the alert job's credential scope.

### Modified Capabilities

- `nightly-publishing`: drops the issue ban; release and setup failures raise
  findings; an alert job joins the workflow.
- `source-generation`: drops both issue bans; scopes the unchanged-candidate
  and duplicate-PR write limits to branch and PR writes; per-source alert
  jobs; the live-check job raises findings and gains an alert job.
- `pack-cli`: the check-live report records the status of inconclusive
  entries that came from a non-retried error status.

## Impact

- Code: new `scripts/alerts.py`; `scripts/workflow_support.py` gains the
  escaped, budgeted renderer moved from `scripts/source_proposal.py`;
  `scripts/nightly.py`, `scripts/nightly_write.py` and
  `scripts/source_proposal.py` expose machine-readable stage and publish
  outcomes; `src/omnipack/live_check.py` adds the inconclusive status.
- Workflows: alert jobs in `nightly.yml`, `source-maintenance.yml` and
  `source-catalog.yml`; producing jobs gain an emit step and an upload.
- Permissions: alert jobs hold `issues: write` only; the `codm` and `quiver`
  calling jobs in `source-catalog.yml` add `issues: write` for them.
- Docs: new `docs/alerts.md`; `docs/publishing.md` and
  `docs/source-generation.md` updated.
- First run: the label is created and one issue opens per currently
  uncategorized family.
