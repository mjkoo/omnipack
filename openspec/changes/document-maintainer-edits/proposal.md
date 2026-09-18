## Why

Maintainers can find composition semantics but lack a short path from an intended app edit to a reviewable PR. Some durable documentation also describes retired publication behavior or an obsolete change context, which obscures what a successful check actually proves.

## What Changes

- Add common-edit recipes to `docs/development.md` for extras, reviewed codm policy and catalog acceptance, overlays, denials, identity corrections, families and pins.
- Recommend that every manual edit affecting pack contents be generated where necessary, built, reviewed and structurally verified before review, with changed pack files and the generated README included in the same PR. Explain the difference between this maintainer convention and CI's existing offline checks.
- Preserve and explain the automated source workflow's catalog-only PR contract: its generated packs are checked diagnostics, and nightly publishes outputs after merge.
- Correct tracker publication wording in `docs/curation.md` and delete its stale claim that a rollback's publication is a separate maintainer action; repair the overlay example in `docs/composition.md` and remove change-scoped Ludashi wording from it and `docs/curation.md`; correct the stable download URLs' availability claim in `docs/publishing.md`, the page that owns it; correct the report command's "current local inputs" claim in `docs/development.md`; and correct the source-workflow documentation's claim that main CI rebuilds packs.
- Retire implicit PR-content guidance, the post-upload readback claim, and duplicated or stale prose displaced by these edits. Link to existing references instead of restating their full semantics.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is documentation of existing commands and contracts plus a human review convention, without runtime or CI enforcement changes. The change declares `skip_specs: true`; no normative spec delta is needed.

## Impact

Affected files: `docs/development.md`, `docs/source-generation.md`, `docs/curation.md`, `docs/composition.md` and `docs/publishing.md`. The publishing page receives a wording repair only. Production code, configuration, workflows, pack outputs and README remain outside the implementation scope. Existing tests and parsers support example review; no new prose-only tests are planned.

Estimated additions: zero requirements, zero scenarios, zero production implementation lines and zero test lines; approximately 95-160 documentation lines, with shorter references replacing stale prose. Planning and validation records stay in this change directory. No new retries, ownership, race, diagnostic-format or evidence requirements are introduced.
