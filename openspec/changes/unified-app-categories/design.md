## Context

Categories are carried through unchanged from whichever candidate wins
selection. Overlay patches can replace them per selected `(id, url)`. The
README catalog groups rows under each entry's first category, falling back to
"Other". The pack settings block derives one colour per category it sees.
The composition policy (`config/composition.json`) already owns family names
(`package:<id>` and `app:<name>`), so a map keyed by family fits there.

## Goals / Non-Goals

**Goals:**
- One place decides an app's category, keyed by family, so it survives fork
  switches and covers both packs with one line.
- Uncategorized and stale entries show up in the build report, never as a
  failed build.

**Non-Goals:**
- Quiver's `category` policy field and generator output. The map overrides
  them, and the generator unification change removes them.
- Offline verification of categories. The build guarantees the set, and
  verification checks only structure.

## Decisions

1. **Assign after overlays.** Overlays can change `trackOnly`, so the
   track-only rule must see final settings. Because overlays can no longer
   carry `categories`, nothing after this stage changes categories.
   - Alternative: assign at selection time. Rejected because it would read
     pre-overlay settings.
2. **Map in `composition.json`, not a new file or the overlay.**
   - The family names are defined in `composition.json` and validated there,
     and composition already reports stale denials the same way.
   - The overlay is keyed by `(id, url)`, so a category set there is lost on a
     fork switch.
   - A separate file would duplicate the policy's loading and fingerprinting.
3. **Source categories pass through, filtered to the set.** Most entries
   already use the set's spellings, which are RJNY's and BBoi's, so the map
   stays small. Filtering drops "Dual Screen" without
   a map entry per BBoi recomp. The seed still maps the affected families so
   they land in a real category.
4. **One mapped category, not a list.** The README groups by the first
   category, and a single value keeps the map readable. Multi-category entries
   can still come through from a source when unmapped.
5. **Track Only is reserved.** Only `trackOnly: true` entries carry it. A map
   value of Track Only is rejected, and a source tag on an installable entry is
   dropped. This keeps one rule, following the RJNY convention that every
   tracker is tagged Track Only.
   - The set is defined once in code as a `StrEnum`. Composition-policy
     validation and category assignment use it, and Quiver's project-policy
     `Category` enum, a separate enum today, is replaced by references to the
     shared members, keeping the values Quiver accepts (Decomps/Recomps and
     PC Ports) unchanged. Removing Quiver's category field itself stays with
     the generator unification change.
6. **Report shape.** The report gets two lists:
   - `uncategorizedFamilies`: families whose selected entry in some variant
     ends with an empty final category list, each naming exactly the variants
     where that happened. Single and dual pick winners independently, so the
     check is per selected entry: a family whose single-screen entry keeps a
     category but whose dual-screen entry ends with none is listed for dual
     only. A track-only entry always carries Track Only, so it is never
     uncategorized, whatever its source supplied.
   - `staleCategoryAssignments`: map keys that set no selected entry's
     category. That covers a key naming no selected family and a key whose
     family's selected entries are all track-only, since the track-only rule
     wins over the map. Assignment tracks which keys it applied; the unused
     keys are stale.

   When composition fails before category assignment runs, both lists are
   recorded empty, as stale exclusions are, and the report's recorded failure
   and stage tell the reader the check did not complete. Lists collected
   before a later failure are preserved.

   Both fields are required, so the build report schema version is bumped with
   them. A report written before the change then fails the schema check and
   `pack report` directs the user to regenerate it with `pack build`, instead
   of rejecting it as malformed. `pack report` renders both lists, using the
   same pattern as `staleExclusions`, and a report whose only non-blocking
   outcomes are these lists still displays them.
7. **One composition-policy decoder.** Today the policy is decoded three ways
   with plain `json.loads`: `pack build` through the generic source decoder
   and then `parse_composition_policy`, `pack verify` through
   `load_composition_policy`, and the offline gate through its generic
   snapshot decoder. A repeated `categories` key would silently keep the last
   occurrence. `load_composition_policy` becomes the single decoder, and
   `pack build` and the offline gate call it. It rejects duplicate object keys
   through one shared duplicate-rejecting `object_pairs_hook` helper, which
   also replaces the two hooks that exist separately today for project policy
   and Quiver policy. The deny, overlay and pack files keep their current
   decoding.
   - Alternative: a duplicate check inside `categories` parsing only.
     Rejected because by then the decoder has already dropped the duplicate.

## Seed map

The values below were read from each project's description. They are review
data and live in config, not in the specs.

| Category | Families |
|---|---|
| Decomps/Recomps | `app:ctr`, `app:pokemon-emerald`, `app:dusklight`, `package:com.aure.banjorecomp`, `package:com.dishii.zelda3`, `package:dev.picori.tmc`, `package:io.github.hm64recomp`, `package:io.github.tomba2recomp`, `package:com.thor.mph` (Metroid Prime Hunters recomp) |
| PC Ports | `app:openmw`, `package:com.balatro.dualscreen`, `package:igawa6.dualsouls`, `package:com.jakobkhansen.silksong` (the two former overlay category patches) |
| Utilities | dual-screen companions and tools: `package:app.wayfinder`, `package:com.exojosh.minecraftsecondscreen`, `package:com.mastercook777.heimdall`, `package:com.stormpanda.megingiard`, `package:com.cylonid.nativealpha`, `package:com.darkaxt.dualdex`, `package:com.enrpau.dualscreendex`, `package:com.chimeragaming.pixelnavigator`, `package:com.chimeragaming.pokemonzmap`, `package:com.andreyvelsk.skyrimwebmonitor`, `package:com.digitaladventure.dw2003`, `package:com.kalenjohnson.chronoduo`, `package:dev.zomboidds.companion`, `package:dev.adrian.showdown`, `package:org.pkforge.app` |

Kanto Gear (`1845280017`) and the omnipack tracker become Track Only through
the track-only rule. The tracker's reviewed `categories` in `config/extras.json`
is set to Track Only as well, so reviewed configuration matches what ships.

## Risks / Trade-offs

- [New upstream apps arrive uncategorized] → They render under "Other" and the
  build report names the family key to add. The nightly is never blocked.
- [A family rename, such as a new `app:` rule, orphans a map key] → It is
  reported as stale, the same way denials are.
- [Users see categories move after re-importing] → This is expected and
  one-time. Package IDs are unchanged, so no app is orphaned.

## Migration Plan

Every commit keeps `pack build`, `pack verify` and the tests green.

1. Land the shared category enum, `categories` policy parsing and the single
   composition-policy decoder. An absent map changes nothing.
2. In one commit, move category ownership to the map: assign categories after
   overlays; add `categories` to the overlay's protected fields; strip only the
   `categories` key from the two overlay records that carry it
   (`igawa6.dualsouls` and `com.jakobkhansen.silksong`, keeping their other
   patched fields such as `name` and `additionalSettings.about`); map both
   families to PC Ports; set the omnipack tracker's reviewed `categories` in
   `config/extras.json` to Track Only; and update the tracker test
   expectation. Splitting these would leave a commit where the protected-field
   check fails on the overlay or the tracker test disagrees with the build.
3. Collect uncategorized families and stale category assignments.
4. Add both report fields with the schema version bump, and render them.
5. Seed the remaining map keys, rebuild the packs and check the report's
   uncategorized list is empty. Check that no entry is added or removed and
   package ids are unchanged; that, matching entries by id, only `categories`
   changes; and that otherwise only entry order and the settings colour map
   differ. Rendering orders entries by primary category, then name, then
   package id, so a re-categorized entry is expected to move.
6. Rollback is a revert of the change, which restores the previous outputs.
