# Validation record: generalize-curation-specs

Base commit: `9b5e84e` (main). Baseline suite on the change branch before any
edit: 793 passed.

## 1.1 Coverage audit

Each per-app fact the deltas retire, where reviewed configuration holds it,
and, for a composed outcome, the check that protects it. "Guard" means the
curated single-screen guard in `tests/test_port_curation.py`
(`test_committed_configuration_selects_each_curated_extra_in_single`), whose
designated set is recorded under 1.2. No committed family has a single pin, so
no designated family is excluded by one; every curated extra eligible for
single is checked by the guard.

### pack-curation: "Cinderbox is included in both packs"

| Fact | Configuration | Outcome check |
|---|---|---|
| URL, package id, name, category, installable, prereleases excluded, standard version detection, no date or extraction rule | `config/extras.json` (`com.game.cinderbox`) | `tests/test_curation.py::test_cinderbox_retains_release_selection_settings` asserts the rendered values |
| Present in single | same | Guard (family `package:com.game.cinderbox`) |
| Present in dual | same | Composition's coverage check fails the build when a single family has no dual selection; the guard composes the committed configuration, so it fails too |

### pack-curation: "Numeric app versions are selected without release labels"

| Fact | Configuration | Outcome check |
|---|---|---|
| BanjoRecomp and SymphonyRecomp dotted numeric extraction | `config/overlay.json` (`com.aure.banjorecomp`, `com.blacklabelhq.sotn`) | `tests/test_curation.py::test_policies_preserve_existing_entries_and_settings` (`NUMERIC_IDS`) |
| Both Cemu variants use the tag, not the title | `config/overlay.json` (two `info.cemu.cemu` records) | same test; it also asserts URL and variant membership are unchanged |
| RPCSX keeps its complete tag | No overlay record targets `net.rpcsx`, so its upstream settings pass through unchanged | Not a composed outcome; the absence of a record is the configuration |
| Structural verification never evaluates version extraction | Generic rule stated in pack-verification | n/a |

### pack-curation: "Source-version tracking preserves build identity"

| Fact | Configuration | Outcome check |
|---|---|---|
| `versionDetection: false` for `com.ctrnative` (both repositories), `com.dishii.soh`, `org.citron.citron_emu`, `org.vita3k.emulator`, `xendroid.compose`, `com.winlator.ludashi`, `com.winlator.cmod`, `xyz.blacksheep.mjolnir` | `config/overlay.json` | `tests/test_curation.py::test_policies_preserve_existing_entries_and_settings` (`SOURCE_IDS`); `tests/test_reconciliation_curation.py::test_full_reconciliation_survives_repeated_catalog_refresh` for both CTR repositories after repeated refreshes |
| Limits of source-version tracking | Kept in "Curation evidence states its limits" | Documentation duty, reviewed |

### pack-curation: "Curated store and established ports are present in both variants"

| Fact | Configuration | Outcome check |
|---|---|---|
| Aurora Store, idTech4A++, VCMI, Julius, Xash3D URLs, ids, categories, GitLab source, APK filters, architecture and version settings | `config/extras.json` | `tests/test_port_curation.py::test_curated_ports_are_present_once_with_maintained_policy` |
| One effective entry per variant when an upstream repeats the project; single by source precedence, dual by pin | Dual pins in `config/composition.json` | `tests/test_port_curation.py::test_composition_pins_keep_extras_when_dual_preferred_duplicates_appear` |
| Each is its family's single-screen winner | `config/extras.json`; no single pin | Guard (the five `package:` families) |
| Game-data documentation | `docs/curation.md` "Port setup" | Folded into "Curation evidence states its limits"; reviewed |

### pack-curation: "Xash3D tracks the continuous Android asset"

| Fact | Configuration | Outcome check |
|---|---|---|
| Release title, prereleases, APK filter, asset-date version, version detection off, latest-tag verification off, fallback | `config/extras.json` (`su.xash.engine.test`) | `tests/test_port_curation.py::test_curated_ports_are_present_once_with_maintained_policy` |
| Rolling-channel note | Entry `about` in `config/extras.json`; `docs/curation.md` | Documentation duty, reviewed |

### pack-curation: "Hollow Knight entries have recognizable presentation"

| Fact | Configuration | Outcome check |
|---|---|---|
| Names and PC Ports category | `config/overlay.json` (`igawa6.dualsouls`, `com.jakobkhansen.silksong`) | `tests/test_port_curation.py::test_hollow_knight_overlay_preserves_dual_identity_and_adds_setup` |
| Package ids, repositories, dual-only, no single entries | Committed codm2000 catalog, targeted by the overlay records | `tests/test_port_curation.py::test_hollow_knight_source_composition_preserves_dual_only_catalog`; a catalog dropping them fails the build on a stale overlay |
| Setup documentation, including the Android 13 restriction | `docs/curation.md` "Port setup"; entry `about` via overlay | Folded into "Curation evidence states its limits"; reviewed |

### pack-curation: "Reviewed installed applications use verified identities and maintained sources"

| Fact | Configuration | Outcome check |
|---|---|---|
| The sixteen identity corrections, exactly, and none for `com.winlator.ludashi` | `packageId` rules in `config/composition.json` | `tests/test_reconciliation_curation.py::test_reconciliation_evidence_is_real_and_configuration_is_complete` (exact set against recorded evidence) |
| Corrected ids present after repeated refreshes, OpenMW-DS and Dusklight dual only | same | `test_full_reconciliation_survives_repeated_catalog_refresh` |
| Official Ghostship wins both packs, legacy Ghostship denied | `config/extras.json`, `app:ghostship` rules and dual pin in `config/composition.json`, `com.ghostship.android` in `config/deny.json` | Single: Guard (`app:ghostship`); both: `test_full_reconciliation_survives_repeated_catalog_refresh`; dual: the pin |
| Gen1Recomp from its canonical repository | `config/extras.json`, `app:gen1recomp` rules and dual pin | Single: Guard (`app:gen1recomp`); both: `test_full_reconciliation_survives_repeated_catalog_refresh` |
| Simon CTR single, igawa6 CTR dual, both `com.ctrnative` | `app:ctr` rules in `config/composition.json` | `test_full_reconciliation_survives_repeated_catalog_refresh` |
| Retired Super Metroid ids denied, ordinary RetroArch in both packs | `config/deny.json`; `487343354` correction | `test_full_reconciliation_survives_repeated_catalog_refresh` |
| Dated acceptance criterion and installed-app comparison scenario | None | Dropped: a finished change's acceptance criterion, and a comparison no code implements |
| Documentation of tracking-only versus binary changes, no device claims | `docs/source-reconciliation.md` | Folded into "Curation evidence states its limits"; reviewed |

### pack-curation: "MetroidArch preserves a separate dual-screen Super Metroid selection"

| Fact | Configuration | Outcome check |
|---|---|---|
| Dual-screen build, URL, package, APK filter, version detection off, no fallback, no prereleases or ZIPs | `config/extras.json` (`dualScreen: true`) | `test_full_reconciliation_survives_repeated_catalog_refresh` asserts the rendered settings |
| Super Metroid family and dual pin | `config/composition.json` | Same test: dual selects it from extras, single has no Super Metroid entry |
| Retired catalog ids denied, no URL denial | `config/deny.json` | Same test |
| Evidence, shared-directory and ADB configuration documentation | `docs/metroidarch.md` | Folded into "Curation evidence states its limits" (user action beyond installing); reviewed |

### pack-curation: "The upstream pack tracker is excluded" (replaced)

| Fact | Configuration | Outcome check |
|---|---|---|
| RJNY tracker `904332840` excluded from both packs and the README catalog after refreshes | `config/deny.json` | `tests/test_curation.py::test_upstream_pack_tracker_stays_excluded_after_refresh` |
| Migration guidance for users who imported the tracker | `docs/curation.md` still carries it | Duty dropped as a finished transition |

Upstream catalogs checked for other pack trackers: the captured BBoi34
standard and dual catalogs have no track-only entries. The captured RJNY
catalog has four: `476086958` (Adreno-Tools-Drivers), `994078275` (Mr. Purple
Turnip Drivers), `767644078` (ES-DE Custom Systems) and `904332840`
(Obtainium Emulation Pack). Only the last is RJNY's own pack tracker, and it is
denied. The codm2000 catalog's only track-only entry is Kanto Gear, a mod
tracker, not a pack tracker. The generic exclusion therefore holds as
committed.

### pack-curation: "Curation regression checks protect exported configuration" (replaced)

| Fact | Configuration | Outcome check |
|---|---|---|
| Refresh survival of maintained overrides | `config/overlay.json` | `test_policies_preserve_existing_entries_and_settings`, `test_full_reconciliation_survives_repeated_catalog_refresh` |
| Curated single-screen guard | Derived from `config/extras.json` and single pins | Guard, rewritten in 1.2 |
| Retired live verifier scenario | None | Dropped as a finished transition |

### pack-curation: "Curation evidence states its limits" (modified)

The Shipwright example (`com.waterdish.shipwright` to `com.dishii.soh`) is a
`packageId` rule in `config/composition.json` and part of the exact set checked
by `test_reconciliation_evidence_is_real_and_configuration_is_complete`. The
retired-automation sentence is dropped as a finished transition, which the user
accepted at convergence.

### readme-source-generation

| Fact | Configuration | Outcome check |
|---|---|---|
| Prerelease discovery for EmuLnk, Showdown-DS, Heimdall; Kanto Gear track-only | `config/codm-projects.json` | Configured values; generic rules tested in `tests/test_source_generation*.py` |
| Showdown and Heimdall APK filename filters and prerelease-suffix extraction; Heimdall excludes debug-latest | `config/codm-projects.json` | Configured values |
| `fallbackToOlderReleases` true for Heimdall, false for Showdown and EmuLnk | `config/codm-projects.json` | `tests/test_source_generation_fixtures.py::test_reviewed_policy_sets_fallback_for_named_projects` (reads reviewed policy, not the catalog) |
| Heimdall strict resolution under consumer fallback | Generic behavior | `tests/test_source_generation_boundaries.py::test_failed_apk_resolution_membership_and_fallback` |
| Kanto Gear resource id, name, URL, stable tags, manual installation guidance | `config/codm-projects.json` (`github.com/averageconsumer/kanto-gear`); `docs/source-generation.md` | `tests/test_source_generation_boundaries.py::test_kanto_settings_manual_guidance_and_cli_tracker` (fixture rule) |
| Kanto dual-only while Gen1Recomp stays in both packs | Kanto has no candidate rule, so its family is `package:1845280017`, not `app:gen1recomp`; Gen1Recomp's dual pin in `config/composition.json` | codm2000 dual-only eligibility: rewritten fixture test from 2.1; Gen1Recomp single: Guard; dual: the pin |

### source-ingestion

| Fact | Configuration | Outcome check |
|---|---|---|
| EmuLnk's dual RJNY entry suppresses its codm2000 entry | Upstream record and codm2000 catalog; not curated | Generic suppression: rewritten fixture test from 2.1 |
| Showdown-DS and Heimdall admitted to dual with prerelease settings | `config/codm-projects.json`; committed catalog | Generic admission: rewritten fixture test from 2.1 |
| Kanto keeps its identity and does not replace its host | `config/codm-projects.json`; committed catalog | Generic tracking: rewritten fixture test from 2.1 |

### pack-cli

| Fact | Configuration | Outcome check |
|---|---|---|
| Kanto needs no APK resolution | `config/codm-projects.json` | `tests/test_source_generation.py::test_track_only_generation_writes_current_candidate_without_apk_state`, `test_kanto_settings_manual_guidance_and_cli_tracker` |

### pack-composition

| Fact | Configuration | Outcome check |
|---|---|---|
| Zelda 3, Minish Cap and Harvest Moon 64 standard and dual builds share a package id | `packageId` rules in `config/composition.json` | Illustration only: no committed denial names these ids. The generic rule is tested by `tests/test_composition.py::test_denied_shared_package_removes_a_family_with_no_other_build` |

Result: every retired fact maps to reviewed configuration, to an outcome check,
or to a documentation duty, or it is recorded above as dropped with its
reason.

## 1.2 Derived single-screen set

`designated_single_winners` over the committed `config/extras.json` and
`config/composition.json` (no single pins committed):

| Family | Expected winner (effective id, normalized URL) | Pinned |
|---|---|---|
| `app:gen1recomp` | `com.theboisclub.pokemonred`, `github.com/bryanthaboi/gen1recomp` | dual |
| `app:ghostship` | `dev.net64.ghostship`, `github.com/harbourmasters/ghostship` | dual |
| `package:809443320` | `809443320`, `github.com/mjkoo/omnipack` | none |
| `package:com.aurora.store` | `com.aurora.store`, `gitlab.com/AuroraOSS/AuroraStore` | dual |
| `package:com.game.cinderbox` | `com.game.cinderbox`, `github.com/ekyso/cinderbox` | none |
| `package:com.github.bvschaik.julius` | `com.github.bvschaik.julius`, `github.com/bvschaik/julius` | dual |
| `package:com.karin.idTech4Amm` | `com.karin.idTech4Amm`, `github.com/glkarin/com.n0n3m4.diii4a` | dual |
| `package:is.xyz.vcmi` | `is.xyz.vcmi`, `github.com/vcmi/vcmi` | dual |
| `package:su.xash.engine.test` | `su.xash.engine.test`, `github.com/fwgs/xash3d-fwgs` | dual |

MetroidArch is a dual-screen build and is not in the set. Every entry wins its
family's single-screen selection as committed: the guard passes. Cinderbox and
the omnipack tracker are the designated extras that no pin names; the denial
test composes successfully under each one's denial and reports exactly that
family. With an in-memory candidate rule giving either extra `packageId`
`com.example.corrected`, the derived family is `package:com.example.corrected`,
or the rule's `family` when it sets one, and the guard still passes. Red check:
replacing the derivation with one that ignores candidate rules makes all four
correction cases fail.

## 1.3 Composed outcomes without a check

None. Every composed outcome in 1.1 is checked by an existing test, the
rewritten guard, the rewritten codm2000 fixture test, or a composition check
that the build performs.

## 1.4 Removed requirement names

Searched `openspec/specs/`, `docs/`, `tests/`, `config/`, `README.md`,
`AGENTS.md`, and also `src/`, `scripts/` and `.github/`, for all fifteen names.
Each appears exactly once, as its own heading in its own spec file.

## 2.1 codm2000 fixture test

`test_committed_codm_entries_keep_their_source_semantics_in_composition` is
replaced by `test_codm_catalog_entries_keep_their_source_semantics_in_composition`
in `tests/test_source_generation_fixtures.py`. It composes a three-entry fixture
catalog with the frozen captured higher sources, under the frozen pre-migration
composition policy and denials with their codm2000 selectors removed and no
overlay, since those target entries the fixture does not carry. It compares
every family selection with a composition over an empty codm2000 catalog.

| Scenario | Fixture entry | Assertion |
|---|---|---|
| Dual coverage suppresses a local catalog candidate | `com.example.covered`, at the URL of a dual-eligible captured higher-source candidate | Ingestion drops it; every family selection, including what each considered, equals the empty-catalog composition's |
| Newly resolved prerelease apps are admitted | `com.example.prerelease` with prerelease and APK filter settings | Dual selects it from codm2000 with its original id and settings; single has no entry |
| A tracking resource keeps its identity | Track-only `1234567890` extending a captured app eligible for both packs | Dual keeps its id, track-only flag and description; single has no entry; the host family's selection in both packs is unchanged |

The test names no entry of `config/catalogs/codm.json`, and it passes. Red
checks: it fails when ingestion stops suppressing dual-covered entries, when
codm2000 entries become eligible for both packs, and when ingestion drops a
prerelease setting.

## 2.2 Tests that read the committed codm2000 catalog

Catalog validation, as pack-curation defines it, checks five things: the catalog
is an object with an apps list, entry ids are unique, normalized project URLs
are unique, ids and flags suit each entry's kind, and the bytes are the
canonical rendering of the entries. Ingestion checks the first two. Source
generation checks unique ids and normalized URLs in the committed catalog it
reads, unique ids in its candidate, and renders the candidate canonically.
Composition does not load the catalog.

| Test | Can fail only where |
|---|---|
| `test_committed_catalog_entries_have_unique_ids_and_urls` (committed and varied catalog) | Catalog validation: unique ids and unique normalized URLs. The only check of the staged file's normalized URLs; assertions unchanged |
| `test_committed_catalog_entries_have_kind_appropriate_ids_and_flags` (both) | Catalog validation: kind-appropriate ids and flags. The only check of the staged file's kinds; assertions unchanged |
| `test_committed_catalog_bytes_are_the_canonical_rendering_of_its_entries` | Catalog validation: canonical bytes. The only check of the staged file's bytes; assertions unchanged |
| `test_a_pretty_printed_catalog_is_not_canonical` | An indented rendering never equals the compact canonical one, so it fails only on a document that is not an object with an apps list, which ingestion rejects |
| `test_committed_catalog_composes_with_frozen_captured_sources_without_errors` (both) | Composition with the committed configuration. The varied catalog now removes only an entry composition does not depend on and adds a synthetic APK under an unused id and URL (see below) |
| `test_committed_catalog_leaves_the_single_screen_pack_unchanged` | Composition: codm2000 entries are dual-only, so single differs only if composition fails |
| `tests/test_port_curation.py` guard tests (`test_committed_configuration_selects_each_curated_extra_in_single`, the correction and denial tests) | Composition: they compare only designated families' single-screen winners, which a dual-only codm2000 entry cannot take |
| `test_hollow_knight_source_composition_preserves_dual_only_catalog` | Build: it reads only the two entries overlay records target, so dropping one or changing its id or normalized URL fails the build on a stale overlay. Its asserted names, category and setup text come from those overlay records. Its URL assertion now compares normalized URLs (see below) |

The other tests that mention the catalog path (`tests/test_source_generation.py`,
`tests/test_source_generation_boundaries.py`, `tests/test_cli.py`,
`tests/test_sources.py`) write their own catalogs under a temporary directory,
and `tests/test_publication_workflows.py` only asserts a workflow command
string. The tests compose with the frozen captured RJNY and BBoi34 records;
the source workflow composes with live ones.

Two tests could fail on a catalog that the build and catalog validation accept.
Both were fixed at the user's direction:

- `_catalog_with_one_project_added_and_one_removed` removed whichever entry
  sorted last. A valid proposal whose sort-last entry a composition rule or
  overlay targets, or which supplies a family's only dual-screen build, would
  fail both tests that compose the variant. It now removes the last entry that no
  codm2000 rule, pin or overlay record targets and whose package id no captured
  higher-source candidate or identity correction carries, removing nothing
  when none qualifies. Its template falls back to minimal APK settings, and
  the added project takes an id and URL the catalog does not use. The
  composes test derives the added ids by comparison with the committed
  catalog. Red/green: a valid 23-entry catalog ending at `igawa6.dualsouls`
  composes with the committed configuration. The old helper removed
  `igawa6.dualsouls` and the composes test failed with a stale-overlay
  `CompositionError`. The new helper removed `com.kalenjohnson.chronoduo`
  and the test passed.
- The Hollow Knight test asserted exact URL strings. A proposal that only
  changes a URL's case still matches the overlays and builds, but failed the
  test. Red/green: with both Hollow Knight URLs case-changed, the catalog
  composes with the committed configuration. The old assertion failed; the
  normalized comparison passes.

Candidate catalog run, from the committed catalog as of commit `2ed9be9`:

- Removed `com.exojosh.minecraftsecondscreen` and `com.darkaxt.dualdex`, which
  no composition selector, identity correction, overlay record, denial, extra,
  reviewed project rule or captured higher-source candidate references.
- Re-resolved `com.enrpau.dualscreendex` as `com.enrpau.dualscreendex.rebuilt`.
- Added an APK entry `com.example.candidate.added` and a track-only entry
  `9876543210`.
- Rendered with `_render_catalog`: an object with an apps list, canonical, with
  unique ids, unique normalized URLs and kind-appropriate ids and flags.

With the candidate in place, and the committed `dist/` and `README.md`, as in
the source workflow:

- The unique-ids-and-URLs, kind and canonical-bytes tests passed (5 passed).
- The full suite passed (793 passed).
- `uv run pack build` exited 0, and `uv run pack verify` exited 0. The three
  candidate ids appeared only in `dist/dual-screen.json`. The build's other
  changes to `dist/` came from live upstream records.

The catalog, `dist/` and `README.md` were then restored from copies saved before
the run. `config/catalogs/codm.json` is byte-identical to its copy, and
`config/`, `dist/` and `README.md` match HEAD. The Hollow Knight URL change came
after this run; it only relaxes an assertion on entries the candidate did not
touch.

## 2.3 Track-only wording

`effective_settings` now ends every track-only description with "Obtainium
only tracks release notifications; acknowledgement does not install the
resource or detect its installed version." The Kanto Gear entry
(`1845280017`) in `config/catalogs/codm.json` was rewritten by rendering its
committed rule through `effective_settings` and re-rendering the catalog with
`_render_catalog`.

- Kanto Gear is the only track-only rule in `config/codm-projects.json`.
  Rendering it through `effective_settings` yields settings the committed entry
  carries with identical values, `about` included. The full entry that
  `_entry` renders for the rule's tracker ID and the committed URL equals the
  committed entry after both pass through `_rendered_entry`, and `_retained`
  returns true for it.
- `tests/test_source_generation_boundaries.py::test_kanto_settings_manual_guidance_and_cli_tracker`,
  which asserts "acknowledgement does not install", passes, and so does the
  canonical-bytes test.
- Compared with the catalog before the task, every other entry is unchanged.
  In the Kanto Gear entry only the `about` setting differs, and a word diff of
  the file shows exactly `mod` replaced by `resource`.

`dist/` was not edited.

## 3.1 pack-curation Purpose

Rewritten directly in `openspec/specs/pack-curation/spec.md`: "Defines how
curated app decisions are recorded, protected and documented, plus the pack's
own notification tracker and the exclusion of upstream pack trackers."
`openspec validate --specs --strict`: 10 passed, 0 failed.

## 4.1 Retired names in the delta specs

A search of all five delta specs for the retired app and project names
(Cinderbox, BanjoRecomp, SymphonyRecomp, Cemu, RPCSX, Shipwright, Vita3K,
Aurora, idTech4A, VCMI, Julius, Xash, Hollow Knight, Silksong, Dual Souls,
MetroidArch, Super Metroid, RetroArch, Ghostship, Gen1Recomp, EmuLnk, Showdown,
Heimdall, Kanto, Zelda, Minish, Harvest Moon, CTR, OpenMW, Dusklight and the
other corrected apps), for `904332840` and `1845280017`, and for `com.` and
`github.com/`, finds matches only inside `## REMOVED Requirements` sections.
