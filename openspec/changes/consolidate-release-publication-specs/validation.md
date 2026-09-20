# Implementation validation

## Baseline and scope

The starting implementation revision was `420785c17a2579554bbc32b584d839e3f0572c17`
on branch `consolidate-release-publication-specs`. Before edits, `just check-all`
passed, including 758 Python tests, the CPython 3.12 write-side tests, offline
pack verification, workflow linting, offline documentation links, Nix formatting
and the host flake check. The sandbox initially denied access to the existing
uv cache; rerunning with cache access passed.

The workflow linter reported its default offline mode and no findings. Nix
reported that incompatible systems were omitted; the host check passed. Neither
message represents live publication or device acceptance.

## Main specs

- `openspec validate --specs --strict`: 10 passed, 0 failed. Informational
  long-requirement notices remain; there are no validation failures.
- `openspec list --specs --json`: `rolling-pack-release` has 4 requirements;
  `nightly-publishing` has 7.
- Compared both main specs to the starting revision. The diff contains only
  the replacements, split, moves, deletions and wording edits named in the
  proposal. Both Purpose sections are unchanged.
- Compared every retained scenario block with its original bytes (excluding
  trailing block-separator whitespace): all match. The only removed scenarios
  are "Missing release seed" and "Later main no-op repairs the release".
- "Main outcome is uncertain", "Write job rerun after main advanced" and
  "The push lands but its commit cannot be established" each appear exactly
  once across the two specs, all in the release-write requirement.
- "Main advances before a no-op" and "Release fails after a confirmed push"
  remain unchanged in `nightly-publishing`.
- Literal `rg` searches for all three retired requirement names found no
  matches in `openspec/specs/`, `README.md`, `AGENTS.md`, `docs/`, `tests/`,
  `scripts/` or `src/` (exit 1).

No application tests were added: this change modifies only specs and prose.
The scenario comparison and strict spec validation directly check the edits.

## Curation guide

The initial acceptance edit added both stable JSON downloads and distinguished
controlled tests from completed device or live publication acceptance, but omitted
unchanged polling from the removed paragraph. The later review correction below
restores it and makes revision-change notification explicit. The user
authorized removing the existing final sentence linking to an archived change's
validation record. A search for `openspec/changes`, `proposal.md`, `design.md`
and `tasks.md` in the guide found no matches. Offline documentation-link
validation passed with zero errors. No device was accessed.

## Post-change checks

`just check-all` passed after the spec and documentation edits:

- Lock consistency, formatting, lint and types passed.
- 758 Python tests passed, with 94% total coverage. This includes
  `tests/test_write_side_runtime.py::test_write_side_modules_import_only_stdlib_and_scripts`,
  which recursively rejects non-standard-library imports from write-side modules.
- All 105 write-side tests passed under CPython 3.12.14.
- Offline pack verification and both workflow linters passed.
- Offline links: 552 total, 53 OK, 0 errors, 499 excluded.
- Nix formatting changed no files; the host flake check passed.

The same offline-linter and incompatible-system advisories appeared as in the
baseline. Nix also noted the dirty tree while task checkboxes were being updated;
that was documentation progress, not an input or dependency failure.

`git diff --stat main` listed 10 files: the two main specs, `docs/curation.md`,
and seven files in this change directory. An allowlist assertion over
`git diff --name-only main` passed. No changes appear under `src/`, `scripts/`,
`tests/`, `.github/`, `config/` or `dist/`. `git diff --check` passed.

## Implementation reviews

The main-spec group review approved commit `9055686`, confirming the declared
edits, scenario preservation, strict validation and retired-name search. Its
only minor note was the informational long-requirement output. The wording was
retained to preserve the planned scope; this advisory does not indicate a
validation failure or changed behavior.

The documentation group review approved commit `c9b3d59`, confirming the two
planned acceptance additions, the authorized link removal and targeted checks,
with no findings. That review missed the omitted unchanged-polling check; both
later whole-diff reviewers caught it.

## Independent sentence-map review

An independent reviewer checked all 11 rows against the synchronized main specs,
`scripts/nightly_write.py` and `.github/workflows/nightly.yml`. Its original
result was pass with no findings, but the acceptance-row verdict was incomplete:
it missed unchanged polling, as both later whole-diff reviewers identified. The
original review used local source inspection without running
publication, accessing the network or touching a device.

| Removed text or scenario | Retained governing text and implementation evidence |
| --- | --- |
| Establish the pushed commit as the local revision | Release-write requirement and its first scenario; `nightly_write.py:122-134` requires successful push and checkout of the candidate before workflow release. |
| Rejected or erroring push prohibits release | Release-write requirement and uncertain-outcome scenario; `nightly_write.py:122-124` fails the push, and workflow step success gating prevents release. |
| Main must still be at the pair's commit | Release-write requirement; `nightly_write.py:154-167` compares local HEAD with remote main before any release operation. |
| Later landed output synchronizes as a no-op | Main-push requirement defines the no-op, release-write requirement authorizes it, nightly synchronization requires it; `nightly.yml:97-110` skips only the push on an unchanged pair. |
| Six bootstrap states | "Bootstrap is explicit" owns the list; `nightly_write.py:178-207` checks missing, unowned, malformed, draft, non-prerelease and immutable states, with guidance at lines 235-237. |
| Release readiness does not block valid main | Nightly synchronization requirement; `nightly.yml:97-110` pushes before checking the release. |
| Synchronize after successful push or verified no-op | Nightly synchronization and release-write requirements; the workflow's conditional push is followed by release for either successful path. |
| Release failure does not undo or prevent main | Nightly synchronization requirement and retained scenario; release follows push, and `run_release` has no main rollback path. |
| Maintainer acceptance paragraph | Original verdict: the guide retained the device-acceptance note and added stable downloads and the controlled-test limitation. Correction: unchanged polling was missing, so that verdict did not establish complete relocation. The corrected guide includes both stable JSON downloads, import, unchanged polling, revision-change notification, acknowledgement, re-import and the controlled-test limitation. |
| Missing release seed | "First normal run has no seed" and "Unowned release conflicts with synchronization" retain valid main outcomes; missing/unowned checks fail before release writes. |
| Later main no-op repairs the release | The retained interrupted-upload, missing/unverifiable-asset and explicit-seed scenarios cover repair and first publication; `nightly_write.py:220-234` implements unchanged, repair and advance paths. |

The reviewer also confirmed all three moved scenarios remain under the
release-write requirement. The no-install restatement matches the write job's
use of preinstalled Python without dependency installation or build/test/verify
steps. The unchanged import-guard test enforces the recursive module boundary.

## Acceptance preservation correction

Both whole-diff reviewers independently found the same Important omission:
unchanged polling appeared in the removed acceptance paragraph but not in the
curation guide. They reported no other findings. The user approved restoring
that check and reconciling the artifacts. The guide now retains all six checks:
both stable JSON downloads, import, unchanged polling, revision-change
notification, acknowledgement and re-import. It also retains the limitation on
calling controlled tests completed device or live publication acceptance.
The proposal and design now name all three additions to the former guide note,
and the documentation task explicitly requires checking every retained item.
The earlier review results above remain recorded with their missed omission.

Targeted checks after the correction:

- `just check-links`: offline links passed, 552 total, 53 OK, 0 errors,
  499 excluded.
- A wording-completeness assertion compared the removed paragraph at the
  starting implementation revision against the corrected guide: all six checks
  and the controlled-test limitation are present. It also confirmed the guide
  cites no change artifact and the documentation and independent-review tasks
  remain unchecked pending re-review.
- `git diff --check`: passed.

No code or spec behavior changed, and no device or live publication was
accessed. The full suite was not rerun for this focused correction; a final
coordinator check and independent re-review remain pending.

The scoped independent re-review approved `f862740`, confirmed all six
acceptance checks plus the controlled-test limitation, and closed the sole
Important finding with no remaining findings. It confirmed the corrected
documentation task and the sentence-map acceptance row are complete.

## Completion

A fresh completion auditor confirmed all 8 checked tasks at `a8073a1`, each
with an implementing commit and concrete validation evidence. No task was
unevidenced, and no blocking finding remained.

The final `just check-all` after that audit passed with exit 0: 758 Python tests,
105 CPython 3.12 write-side tests, lock/format/lint/type checks, offline pack
verification, workflow linting, documentation links, Nix formatting and the host
flake check. Only the previously disclosed offline-linter and incompatible-system
advisories remained. The working tree was clean for that run.

Implementation is complete. The change remains active; the separate verification
and archive workflows have not run. No device or live publication acceptance is
claimed.
