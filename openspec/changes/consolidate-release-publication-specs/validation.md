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

The acceptance note now covers both stable JSON downloads and distinguishes
controlled tests from completed device or live publication acceptance. The user
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

The documentation group review approved commit `c9b3d59`, confirming both
acceptance statements, the authorized link removal and targeted checks, with
no findings.
