## 1. Policy

- [ ] 1.1 Parse an optional `categories` object in the composition policy: keys must be `package:` or `app:` family names, and values one category from the closed set other than Track Only. Verify with policy tests covering a valid map, an unknown category, Track Only, a non-string value and a malformed key, each failing with the key identified.

## 2. Assignment

- [ ] 2.1 Add `categories` to the overlay's protected patch fields. Verify with an overlay test that a patch carrying `categories` (including null) fails naming the selector and field.
- [ ] 2.2 Assign categories after overlays, in every variant: track-only entries get Track Only, mapped families get their value, and other entries keep source categories filtered to the set without Track Only. Verify with composition tests for each scenario in the pack-composition delta, asserting on each entry's final category list, including an unmapped track-only entry with no source categories that carries exactly Track Only.
- [ ] 2.3 Collect uncategorized families, deciding per selected entry from its final category list after assignment and recording exactly the variants whose entry ended empty, and map keys that name no selected family, without failing the build. Verify with composition tests for both lists, including that an unmapped track-only entry with no source categories is not listed and that a family whose single-screen entry keeps a category while its dual-screen entry ends with none is listed for the dual variant only.

## 3. Report

- [ ] 3.1 Record `uncategorizedFamilies` (each family with its variants) and `staleCategoryAssignments` in the build report, bumping the build report schema version together with the two new fields, and render both lists in `pack report`. Verify with report and CLI tests, including that a failed build before composition still writes a valid report, that a report at the previous schema version produces the `pack build` regeneration diagnostic, and that a report whose only non-blocking outcomes are category lists displays them.

## 4. Configuration and outputs

- [ ] 4.1 Seed `config/composition.json` `categories` from the design's seed map, and remove the two overlay `categories` patches in the same commit. Verify that `uv run pack build` succeeds and the report's uncategorized list is empty.
- [ ] 4.2 Rebuild `dist/` and README. Verify that no entry is added or removed, package ids are unchanged, per entry matched by id only `categories` changes, and otherwise only entry order and the settings colour map differ (rendering orders by primary category, so re-categorized entries may move), and that `uv run pack verify` passes.
- [ ] 4.3 Update current-config tests and fixtures whose expected categories changed (for example the omnipack tracker now Track Only). Verify `just check-all` passes.

## 5. Docs and review

- [ ] 5.1 Document the taxonomy, the map and the resolution order in `docs/composition.md`. Replace the overlay category guidance in `docs/development.md` and `docs/curation.md` with the map. Verify the docs link check passes in `just check-all`.
- [ ] 5.2 Review the branch for correctness, completeness and idiomatic code, and fix the findings. Verify with a final `just check-all` and `openspec validate unified-app-categories --strict`.
