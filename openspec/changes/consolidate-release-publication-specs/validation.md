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
