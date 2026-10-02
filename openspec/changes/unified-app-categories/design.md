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
   stays small: about 26 families today. Filtering drops "Dual Screen" without
   a map entry per BBoi recomp. The seed still maps the affected families so
   they land in a real category.
4. **One mapped category, not a list.** The README groups by the first
   category, and a single value keeps the map readable. Multi-category entries
   can still come through from a source when unmapped.
5. **Track Only is reserved.** Only `trackOnly: true` entries carry it. A map
   value of Track Only is rejected, and a source tag on an installable entry is
   dropped. This keeps one rule, following the RJNY convention that every
   tracker is tagged Track Only.
6. **Report shape.** The report gets two lists:
   - `uncategorizedFamilies`: selected families left with no category, with
     the variants that select them.
   - `staleCategoryAssignments`: map keys naming no selected family.

   `pack report` renders both, using the same pattern as `staleExclusions`.

## Seed map

The values below were read from each project's description. They are review
data and live in config, not in the specs.

| Category | Families |
|---|---|
| Decomps/Recomps | `app:ctr`, `app:pokemon-emerald`, `app:dusklight`, `package:com.aure.banjorecomp`, `package:com.dishii.zelda3`, `package:dev.picori.tmc`, `package:io.github.hm64recomp`, `package:io.github.tomba2recomp`, `package:com.thor.mph` (Metroid Prime Hunters recomp) |
| PC Ports | `app:openmw`, `package:com.balatro.dualscreen`, `package:igawa6.dualsouls`, `package:com.jakobkhansen.silksong` (the two former overlay category patches) |
| Utilities | dual-screen companions and tools: `package:app.wayfinder`, `package:com.exojosh.minecraftsecondscreen`, `package:com.mastercook777.heimdall`, `package:com.stormpanda.megingiard`, `package:com.cylonid.nativealpha`, `package:com.darkaxt.dualdex`, `package:com.enrpau.dualscreendex`, `package:com.chimeragaming.pixelnavigator`, `package:com.chimeragaming.pokemonzmap`, `package:com.andreyvelsk.skyrimwebmonitor`, `package:com.digitaladventure.dw2003`, `package:com.kalenjohnson.chronoduo`, `package:dev.zomboidds.companion`, `package:dev.adrian.showdown`, `package:org.pkforge.app` |

Kanto Gear (`1845280017`) and the omnipack tracker become Track Only through
the track-only rule.

## Risks / Trade-offs

- [New upstream apps arrive uncategorized] → They render under "Other" and the
  build report names the family key to add. The nightly is never blocked.
- [A family rename, such as a new `app:` rule, orphans a map key] → It is
  reported as stale, the same way denials are.
- [Users see categories move after re-importing] → This is expected and
  one-time. Package IDs are unchanged, so no app is orphaned.

## Migration Plan

1. Land the code, then the seeded map. Remove the two overlay category patches
   in the same commit, because the protected-field check would otherwise fail
   the build.
2. Rebuild the packs and check the report's uncategorized list is empty and
   that the only pack diffs are categories and the settings colour map.
3. Rollback is a revert of the change, which restores the previous outputs.
