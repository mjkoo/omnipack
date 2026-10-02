## Why

Pack categories come from whichever source won selection. Today the dual pack
shows apps with no category (most codm entries and a track-only mod tracker)
and BBoi recomps tagged "Dual Screen". Corrections are scattered across
overlay patches and Quiver's own category field. The owner approved one
taxonomy, owned in owner config and applied uniformly across sources, so
categories stop depending on which source supplied a build.

## What Changes

- The categories are a fixed set, using the spellings RJNY and BBoi already
  use so imported categories merge with what users have: Emulator,
  PC Emulation, Decomps/Recomps, PC Ports, Frontend, Utilities, Streaming,
  Track Only.
- `config/composition.json` gains an optional `categories` object that maps an
  app family (`package:<id>` or `app:<name>`) to one category from the set
  other than Track Only. An unknown category fails policy loading, and so does
  any JSON object key repeated anywhere in the policy, a family key listed
  twice included, in every command that loads the policy.
- The set is defined once in code and shared with Quiver's project policy,
  which keeps accepting the same values.
- After overlays apply, each selected entry gets its categories:
  - A track-only entry gets exactly "Track Only".
  - Otherwise, a mapped family gets its mapped category.
  - Otherwise, the source's categories are kept, minus any outside the set. An
    entry left with none carries no category.
- Unmapped apps never fail the build: an upstream adding an app must not break
  the nightly. The build report lists the selected families left without a
  category in any variant, naming those variants, and any stale map keys: keys
  that set no selected entry's category, because they name no selected family
  or a family whose selected entries are all track-only.
- **BREAKING (owner config):** overlay patches can no longer set `categories`.
  The two existing category patches move into the map in the same commit that
  protects the field and starts assigning categories, and the map is then
  seeded so every selected entry resolves to a category.
- The omnipack notification tracker changes from Utilities to Track Only,
  following the track-only rule, and its reviewed configuration is updated to
  match.
- Retired:
  - category edits through the overlay;
  - "Dual Screen" and any other category outside the set reaching a pack;
  - uncategorized codm entries.

  Quiver's per-project `category` policy field stays here; only its separate
  enum is replaced by the shared set. A later change that unifies the
  generators removes the field, and the map already overrides it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-composition`:
  - A new requirement covers category assignment from the closed set and the
    family map.
  - Composition-policy loading rejects any repeated JSON object key.
  - The stage order gains category assignment after overlays.
  - The overlay protected fields gain `categories`.
- `pack-cli`: the build report records families with a selected entry left
  without a category and stale category map keys, and
  `pack report` displays both lists.
- `pack-curation`: the shared tracker's category follows the track-only rule
  instead of reviewed configuration.

## Impact

- **Code:**
  - `composition_policy.py`: parse and validate `categories` against one
    shared category enum, and become the single composition-policy decoder,
    rejecting duplicate keys through a shared hook that also replaces the
    project-policy and Quiver hooks. `pack build` and the offline gate decode
    the policy through it.
  - `quiver_source.py`: its `Category` enum is replaced by the shared members.
  - `merge.py`: assign categories after overlays.
  - `overlay.py`: add `categories` to the protected fields.
  - `report.py` / `report_model.py`: two report lists and their rendering,
    with a build report schema version bump so an older report gets the
    `pack build` regeneration diagnostic.
- **Config:** `config/composition.json` (seeded map), `config/overlay.json`
  (two category patches removed) and `config/extras.json` (tracker category
  set to Track Only). Rebuilt `dist/` and README: catalog headings
  change for the re-categorized apps.
- **Users:** after re-importing, the affected apps move to their new
  categories in Obtainium. No package IDs change.
- **Estimate:** one new requirement and a handful of modified ones, with a
  small implementation and a larger test diff.
- **Report lists and the proposal rule:**
  - Stale map keys produce no visible symptom on their own, so the report is
    their only signal.
  - Uncategorized apps do show in the README under "Other", but the report
    names the family key the map needs. Both lists stay.
