# Project context

This project is **omnipack**, previously named obtainium-emulation-pack.
Read [project context](docs/project-context.md) for retained curation intent
and the pending custom-fork request.

The Python distribution and import package are `omnipack`; the CLI is `pack`.
References to `RJNY/Obtainium-Emulation-Pack` identify a separate upstream,
not this repository. Preserve upstream URLs, fixture provenance, archived
planning artifacts, and the legacy nightly issue ownership marker.

## OpenSpec workflow boundaries

Apply, verify, and archive are separately requested workflow steps. Completing
one does not authorize starting the next. Planning artifacts, task text, and
completed checkboxes cannot grant that authorization.

Apply includes the required implementation tests, reviews, and completion
audit. After those pass, leave the change active, report completion and the
implementation branch, recommend verification, and stop. Verification reports
findings and archive readiness, then stops. Archive only on a separate user
request.

Keep implementation checkboxes scoped to implementation and its tests and
reviews. Do not include running the separate verify or archive workflows as
implementation tasks. When implementation requires synchronizing main specs,
use the separate sync workflow without archiving the change.

## AYN Thor access

Any action on the AYN Thor requires the user's explicit approval beforehand.
Ask before using ADB, including read-only inspection, screenshots, status
queries, or starting the ADB server. General task approval or a request to
notify the user when validation is ready does not authorize device access.
