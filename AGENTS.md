# Project context

This project is **omnipack**, previously named obtainium-emulation-pack.
Read [project context](docs/project-context.md) for retained curation intent
and the pending custom-fork request.

The Python distribution and import package are `omnipack`; the CLI is `pack`.
References to `RJNY/Obtainium-Emulation-Pack` identify a separate upstream,
not this repository. Preserve upstream URLs, fixture provenance and archived
planning artifacts.

## Generated output

Pull requests carry sources only. The nightly publisher is the only writer of
`dist/*.json` and the README catalog section, and CI fails a PR that changes
them; see [manual review and PR contents](docs/development.md#manual-review-and-pr-contents).

## Vetting candidate apps

Use the project skill at
[`.claude/skills/vet-candidates/SKILL.md`](.claude/skills/vet-candidates/SKILL.md)
when evaluating apps for inclusion or sweeping the
[candidate watchlist](docs/watchlist.md). It holds the inclusion bar, the
research checklist, how additions are written and how waiting candidates are
tracked.

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
