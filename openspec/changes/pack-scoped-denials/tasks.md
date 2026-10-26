# Tasks

## 1. Build kind replaces pack eligibility

- [ ] 1.1 Replace `App.eligibility` and `dual_preferred` with a `dual_screen` kind in `src/omnipack/model.py`, and the generated-catalog `eligibility` in `src/omnipack/source_registry.py`; verify `tests/test_model.py` and `tests/test_source_registry.py` pass with the new field
- [ ] 1.2 Set the kind in each source: RJNY dual-export-only is a dual-screen build, any other kept entry a baseline build, and an entry in neither export is dropped; BBoi by asset; extras by `dualScreen`; codm and Quiver from the registry. Verify with synthetic tests in `tests/test_sources.py` covering each RJNY flag combination, a BBoi dual asset with no standard counterpart, and extras with and without `dualScreen`
- [ ] 1.3 Check the committed composition policy for any rule or pin whose selector matches an RJNY entry in neither export against the live RJNY catalog, and remove any such selector; verify `uv run pack build` reports no unmatched selector

## 2. Pack-scoped denials and symmetric selection

- [ ] 2.1 Parse an optional `packs` field on denylist entries (nonempty list of distinct `single`/`dual`, absent meaning both) in `src/omnipack/merge.py`, reject other values with the entry identified, and carry the variants on each exclusion and removal record; verify with tests in `tests/test_composition.py` for each invalid form and for an existing denial without `packs`
- [ ] 2.2 Apply each denial only to its variants: families form over candidates denied in fewer than all variants, and selection skips a candidate in the variants it is denied in; verify with tests that a single-scoped denial keeps a dual-only family out of single only, and that a candidate denied in one pack keeps its explicit family
- [ ] 2.3 Make selection symmetric (single prefers baseline builds, dual dual-screen builds, each falling back to the other kind), with single reporting source precedence and dual its existing reasons; verify with tests for a dual-only family selected in both packs, single preferring a lower-precedence baseline build over an extras dual-screen build, and the selection reasons
- [ ] 2.4 Validate pins against denials in the pin's variant and delete the ineligibility branches; verify with tests that a pin fails when a denial removes its candidate from its variant and stays valid when the denial names only the other pack
- [ ] 2.5 Remove the single-only coverage record (`_single_only_families`, `SingleOnlyFamily`, the report field) and the eligible-for-neither denial case; verify the removed tests are gone and `uv run pytest tests/test_composition.py` passes
- [ ] 2.6 Add a test that a baseline original and a dual-screen fork at different URLs sharing a package id are both selected in both packs and recorded as repeated ids, and that a family rule resolves it; verify it passes

## 3. Verification, report and alerts

- [ ] 3.1 In `src/omnipack/offline.py`, check denied URLs only in the variants each denial applies to and delete the single-only coverage pass and finding; verify with `tests/test_offline.py` cases for an entry in a variant its denial does not name and for a single-only family recording no finding
- [ ] 3.2 Advance the build report schema in `src/omnipack/report.py`: drop `singleOnlyFamilies`, record each removal's variants, and display them in `pack report`; verify with `tests/test_report.py` and `tests/test_cli.py`
- [ ] 3.3 Map each `repeatedIds` item to a `build/repeated-id/<variant>/<package id>` finding in `scripts/alerts.py`, with details naming the variant, package id and each entry's family and project URL; verify with `tests/test_alerts.py`
- [ ] 3.4 Update `docs/composition.md` (build kinds, denials with `packs`, selection, removal of single-only coverage), `docs/alerts.md` (the repeated-id alert) and `docs/development.md` (report fields); verify no doc still describes pack eligibility or single-only coverage with `git grep -n -i "single-only\|eligib" docs`

## 4. Migration and curation workflow

- [ ] 4.1 Add the 15 single-scoped denials to `config/deny.json` (Heimdall, Megingiard, Wayfinder, ZomboidDS, Minecraft Second Screen, Stardew-Thor-DS, Eden Duo Companions, Eden Duo, ChronoDuo, Showdown!, MetroidArch, HuntersRecomp, Pixel Navigator, GBA Duo, GBA DS), each with its reason; verify `uv run pack verify` passes
- [ ] 4.2 Update the arrival-triage section of `.claude/skills/vet-candidates/SKILL.md` and the denial guidance in section 3: for a family with no baseline build, decide whether it belongs in single and add a single-scoped denial if not; verify the skill text describes the `packs` field
- [ ] 4.3 Run `uv run pack build` and compare against main's packs: the dual-screen pack is unchanged, single gains exactly the 18 expected families, and the report lists no repeated package id and no stale denial; then discard the rebuilt `dist/` and `README.md` with `git restore`
- [ ] 4.4 Run `uv run pytest` and `uv run pack verify`, and confirm both pass

## Workflow follow-up

- At archive, update the source-ingestion Purpose, which names eligibility among what ingestion owns.
