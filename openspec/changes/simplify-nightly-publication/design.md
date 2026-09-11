## Context

See [proposal.md](proposal.md) for motivation and scope. The current Actions job
checks out the repository and synchronizes dependencies, then the publisher
creates disposable checkouts and repeats setup, development checks, building
and verification for up to two attempts. Issue management and fallback commands
coordinate reporting across helper, setup, cleanup and artifact failures. Release
seed preflight currently runs before main publication.

The candidate abstraction already captures verified bytes and validates allowed
paths, README boundaries, staged bytes and commit contents. Release synchronization
already validates ownership and repairs interrupted asset replacement. These
boundaries remain valuable and are retained.

## Goals / Non-Goals

**Goals:** one revision and runtime per run; one main publication attempt;
independent main and release outcomes; visible failures through Actions; one
coherent implementation and specification update.

**Non-Goals:** replacing the structural evidence format, simplifying the release
state machine, changing source adapters or generated output, or introducing a
replacement CI polling, notification or recovery service.

## Decisions

### Use the Actions workspace directly

Select `main` explicitly in the workflow checkout before runtime setup and record
the checked-out HEAD as the base. Keep checkout credentials unpersisted. The
entrypoint validates repository/ref eligibility and a clean initial tracked tree
before building. It never switches the workspace revision. The remote comparison
near publication detects advancement since checkout; selecting a newer revision
and loading its Python code in the existing process is unnecessary.

Remove the disposable checkout factory and cleanup outcomes. A second checkout
would preserve complexity without serving another attempt. Actions owns runner
workspace disposal. Controlled tests provide their own temporary repositories.

The workflow performs locked runtime setup once. Refresh orchestration runs the
existing build and then one fresh structural verification. Delete pre-build
verification and formatting/lint/type/packaging/full-suite commands from nightly.
CI remains unchanged; do not replace duplicate checks with status polling.

### Keep candidate evidence and exact-byte boundaries

Retain current evidence freshness, selected-runtime identity and input checks,
including rejection of old evidence and mutation during verification. Keep the
candidate's captured bytes and existing file, README, staging, mode and commit
checks. Comparing bytes at staging boundaries is distinct from rerunning
structural verification. The initial clean-tree check prevents user modifications
in allowed files from being mistaken for generated changes.

Replacing the serialized authorization evidence with a direct result could be
a later simplification, but would add a separate contract change here. No
standalone verification or report-reader migration is required by this design.

### Make main publication a single attempt

Use the checked-out base, build and verify once, and compare remote main before
either committing/pushing or recognizing a no-op. Advancement fails the run.
Keep normal fast-forward push and current commit metadata. A rejected or lost
push acknowledgement gets a bounded read-only history reconciliation, including
commits followed by later main commits. Presence confirms publication, confirmed
absence fails and unreadable state is uncertain. None causes another push or
build. Use remote reads with enough history to establish ancestry; a shallow
local history alone is not evidence that the candidate is absent remotely.

Removing reconciliation would save little while needlessly delaying release
updates and reporting failure after an actual publication. Keeping the second
build attempt would conflict with the agreed rerun policy.

### Synchronize releases after the main outcome is confirmed

Remove release preflight from main eligibility. Call the existing synchronization
boundary only after confirmed publication or a verified no-op, using captured
JSON bytes and the corresponding published/base SHA. Ownership and seed checks
remain inside that release boundary. Missing seed reports bootstrap guidance;
malformed or unowned releases fail without writes. Bootstrap stays explicit.

Retain release state, stable asset names, shared numeric revision, remote digest
checks and pending-target repair. A release failure produces a failed workflow
with a successful main outcome. A later no-op can repair release assets. Failed
or uncertain main outcomes perform no release writes. Do not advertise a new
revision before both assets have passed the retained checks.

This preserves notification behavior without imposing release availability on
the primary raw-main downloads. A new release-state schema or automatic seed
creation is unnecessary.

### Report through Actions without a recovery protocol

Remove the issue reconciler and issue-only interfaces, preserving shared GitHub
transport used by releases. Remove issue permission and all automatic issue
operations. Keep the entrypoint and reporting modules small: a single run result,
available build/verification reports and a concise summary. Log and flush the
confirmed main outcome and SHA before beginning release work. When available,
also report the failing stage and separate release/pending-revision outcome.

Remove `finalize-setup`, `record-upload`, completion markers, result reload and
system-Python fallback steps. Actions step logs cover early setup or unexpected
helper failure. Best-effort summaries do not promise reconstruction after a
crash; summary-write errors remain visible failures. Existing recorded logs are
not overwritten by a generic later failure. Token redaction and treating source
text as data apply to logs as well as artifacts.

Upload only available allowlisted reports with 14-day retention, including after
a publisher failure. Configure absence of reports after an early failure as
acceptable, while actual upload errors remain failed steps. Do not mask the
publisher exit status or upload outcome through finalization code. The uploaded
run result has no upload-status claim; Actions records the eventual status.

Keeping a smaller issue recovery helper would still require external permissions
and a notification contract the maintainer no longer needs. Reconstructing a
complete result after helper failure is also unnecessary when logs suffice.

## Risks / Trade-offs

- Main advancement can delay a refresh until a manual rerun or later nightly
  invocation. This is accepted; no retry service is introduced.
- Regressions that escape CI are no longer independently caught by nightly's
  full suite. Candidate validation and publication boundaries still run.
- The release can lag a successful main update, including indefinitely until an
  absent seed is explicitly bootstrapped. Actions reports the release failure
  and the maintainer can bootstrap or repair it before rerunning.
- Asset replacement can temporarily expose missing or mixed downloads. Existing
  digest, revision and repair rules remain; no atomic-pair claim is introduced.
- Crashes may leave no summary or run-result artifact. Flushed publication logs
  and Actions step status are the accepted fallback, not a guarantee under runner
  loss. Uncertainty must never be presented as confirmed failure to publish.
- Shared transport currently overlaps issue code. Audit import/caller boundaries
  before deletion so release authentication and redirect restrictions survive.

## Migration Plan

Implement workflow, helper, specs and documentation together. Remove obsolete
helper commands and their callers in the same change; no external consumer or
compatibility wrapper is required. Existing release state and asset names stay
compatible. Existing issues are left untouched; closing them is a separate
maintainer operation. Preserve archived plans and dated validation records.

Run development checks and controlled git/release integration tests before landing.
Update current operator guidance and record that tests are not live publication
or device acceptance. Landing, dispatching the real workflow, bootstrapping and
external writes remain maintainer actions. A maintainer can disable scheduled
publication to halt future runs and inspect any active run separately. Restoring
the prior workflow requires restoring matching helper code; do not roll back
already published main content or delete the rolling release automatically.
