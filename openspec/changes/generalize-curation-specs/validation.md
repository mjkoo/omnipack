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
| Setup documentation of user-supplied game files and Silksong's on-device build | `docs/curation.md` "Port setup"; entry `about` via overlay | Folded into "Curation evidence states its limits" (user action beyond installing); reviewed |
| Second-screen features and Silksong's Android 13 restriction | Entry `about` via `config/overlay.json`; `docs/curation.md` "Port setup" | Documentation duty dropped: a feature description and a platform limit are not user action beyond installing. The overlay `about` text keeps both, and `test_hollow_knight_overlay_preserves_dual_identity_and_adds_setup` and `test_hollow_knight_source_composition_preserves_dual_only_catalog` assert the Android 13 restriction; `docs/curation.md` still carries it |

### pack-curation: "Reviewed installed applications use verified identities and maintained sources"

| Fact | Configuration | Outcome check |
|---|---|---|
| The identity corrections the recorded evidence lists | `packageId` rules in `config/composition.json` | `tests/test_reconciliation_curation.py::test_reconciliation_evidence_is_real_and_configuration_is_complete` checks that the evidence lists the corrections the recorded observations back, sixteen of them, and that every rule matching each one has exactly that `packageId`. It does not check that the configuration carries no others: the configuration also carries a seventeenth correction, legacy Ghostship `com.izzy2lost.ghostship` to `com.ghostship.android`, which predates this change and which the evidence fixture does not list. Three corrections have two selectors each, so the seventeen span twenty rules |
| No correction for `com.winlator.ludashi` | No `packageId` rule names it in `config/composition.json` | Configured value; no test asserts the absence. `tests/test_curation.py::test_ludashi_allows_its_manifest_package_to_differ` checks its `allowIdChange` setting |
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
| ARM64 core limitation, debuggable build, inherited HTTP updater defaults and known widescreen limitations | `docs/metroidarch.md`; the entry `about` in `config/extras.json` names the ARM64 target | Documentation duty dropped: platform limits are not user action beyond installing. `docs/metroidarch.md` still carries all four |

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

`designated_single_winners` takes each extra's family and effective id from
composition's own code: it applies the policy's extras candidate rules to the
extras alone with `apply_composition_policy`, then drops any family a single pin
selects for. Over the committed `config/extras.json` and
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
family's single-screen selection as committed: the guard passes.

The tests around the guard:

- `test_designated_single_set_is_derived_from_extras_and_single_pins` runs over
  two synthetic extras and a synthetic policy, naming no committed extra. The
  extra with no rule is designated as `package:<id>` with winner (id,
  normalized URL), and a candidate rule with an `app:` family puts the other in
  that family. Dual pins for both keep both designated, single pins for both
  remove both, and `dualScreen: true` removes that extra.
- `test_curated_single_guard_fails_when_a_designated_extra_is_denied` is
  parametrized over every designated family of the committed configuration,
  with the family as the test id: nine cases. Each drops, in its own copy of
  the policy, every pin whose projected package id is the extra's effective id,
  then adds a package denial of that id. Only single pins affect designation, so
  the family stays designated. Composition succeeds in all nine, and the guard
  reports exactly that family. The set is empty only when no curated extra is
  eligible for single.
- `test_designated_family_follows_a_package_id_correction` appends one
  synthetic extra, eligible for both packs, to the committed extras, so it never
  depends on a committed rule correcting an id. A candidate rule gives it
  `packageId` `com.example.corrected`, alone or with `family` `app:corrected`.
  The derived family is `package:com.example.corrected` or `app:corrected`,
  the uncorrected family is absent, the winner carries the corrected id, and
  the guard reports no mismatch with the synthetic extra present.

Red checks, each replacing `designated_single_winners` in a throwaway script:

- excluding a family when any pin names it, whatever the variant, fails the
  derived-set test;
- a derivation that ignores candidate rules and names each extra
  `package:<id>` fails both correction cases;
- unmutated, each of the nine denials makes the guard report exactly its own
  family: `app:gen1recomp`, `app:ghostship`, `package:809443320`,
  `package:com.aurora.store`, `package:com.game.cinderbox`,
  `package:com.github.bvschaik.julius`, `package:com.karin.idTech4Amm`,
  `package:is.xyz.vcmi` and `package:su.xash.engine.test`.

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
every family selection with a composition over an empty codm2000 catalog; that
one equality covers the covering project's and the tracked host's selections
in both packs, so no separate host check remains. The host is the first family,
by name, with a single-screen selection in the empty-catalog composition, which
a captured higher source provides. That pick and the covering candidate's are
`min()` choices made only for determinism; which ones are chosen is
immaterial. Fixture entries carry the constant author `example`.

| Scenario | Fixture entry | Assertion |
|---|---|---|
| Dual coverage suppresses a local catalog candidate | `com.example.covered`, at the URL of a dual-eligible captured higher-source candidate | Ingestion drops it; every family selection, including what each considered, equals the empty-catalog composition's |
| Newly resolved prerelease apps are admitted | `com.example.prerelease` with prerelease and APK filter settings | Dual selects it from codm2000 with its original id and settings; single has no entry |
| A tracking resource keeps its identity | Track-only `1234567890` extending a captured app eligible for both packs | Dual keeps its id, track-only flag and description; single has no entry; the all-selections equality keeps the host family's selections in both packs unchanged |

The test names no entry of `config/catalogs/codm.json`, and it passes. Red
checks, rerun after the host check was folded into the all-selections
equality: it fails when ingestion stops suppressing dual-covered entries, when
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

Composition in this rule means composition over the suite's captured upstream
records, as the spec now says at the user's direction. A catalog whose
composition depends on upstream records newer than the captures, such as an
overlay target only a live upstream supplies, is outside the guarantee.

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
  higher-source candidate or identity correction carries. When none
  qualifies it skips the variant with a stated reason, rather than silently
  testing only an addition. It reads the captured higher sources directly and
  builds its used id and URL sets once. Its template falls back to minimal APK
  settings, and the added project takes an id and URL the catalog does not
  use. The composes test derives the added ids by comparison with the
  committed catalog. Skip check, in a throwaway script: unpatched, the helper
  removes one entry; with every committed entry's package id carried by a
  higher candidate, it skips. Red/green: a valid 23-entry catalog ending at `igawa6.dualsouls`
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
  `9876543210`. The task asks only for removals and a re-resolution; the
  additions cover the requirement's scenario for proposals that add projects.
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

`dist/` and `README.md` were not edited, so both still carry the old wording
until the nightly rebuild: `dist/dual-screen.json` in the Kanto Gear entry's
`about`, and `README.md` in the Kanto Gear import link, where the text is
URL-encoded. The rebuild regenerates the README catalog from the built packs.

## 3.1 pack-curation Purpose

Rewritten directly in `openspec/specs/pack-curation/spec.md`: "Defines how
curated app decisions are recorded, protected and documented, plus the pack's
own notification tracker and the exclusion of upstream pack trackers."
`openspec validate --specs --strict`: 10 passed, 0 failed.

## 3.2 Setup notes for curated extras

Each `config/extras.json` entry's upstream README was read on 2026-09-14 from
the repository its `url` names; for VCMI, also the Android installation guide
its README links. The notes restate upstream documentation, and none claims
device validation. The Hollow Knight entries are upstream entries that overlays
touch, not curated extras; their existing notes stay.

| Entry | Upstream documents beyond installing | `docs/curation.md` "Port setup" |
|---|---|---|
| MetroidArch (Super Metroid) | A Japan/USA Super Metroid ROM with a given CRC32, loaded uncompressed; the Online Updater's Update Assets and Update Core Info Files; separately downloaded BPS and BSO files for widescreen | Added a note pointing to `docs/metroidarch.md`, which already describes these steps and the directory configuration |
| Cinderbox | A legitimate copy of Stardew Valley; no game assets are included | Added |
| Ghostship | The user's own US or JP Super Mario 64 `.z64` ROM, chosen in the app | Added |
| Pokémon Red/Blue Recomp | A legally obtained canonical US Pokémon Game Boy ROM (`.gb` or `.gbc`, listed with checksums), chosen on first boot | Added |
| Aurora Store | A login on first open, with a Google Play account or anonymously; anonymous login limits some features | Added to its existing note |
| idTech4A++ | PC game data for a supported id Tech game in the game's data folder; for Prey, an optional config-file edit to bind keys | Already described |
| VCMI | Heroes of Might and Magic III: Shadow of Death or Complete data (`Data`, `Maps`, `Mp3`), imported through the VCMI Launcher | Already described |
| Julius | The original Caesar III files | Already described |
| Xash3D FWGS | Half-Life's `valve` directory, copied to a `xash` folder in internal storage | Already described |
| omnipack updates | Its upstream is this repository: acknowledge a notification, then download and re-import the pack | Already described in "Tracking omnipack itself" |

The section's intro now says that the entries listed need user action beyond
installing them and that each note restates upstream documentation rather than
recording device validation. `nix develop -c lychee --offline docs/ README.md`:
0 errors.

## Line counts

| File | Before (`9b5e84e`) | After |
|---|---|---|
| `tests/test_port_curation.py` | 308 | 450 |
| `tests/test_source_generation_fixtures.py` | 315 | 456 |
| All of `tests/*.py` | 12316 | 12599 |

The proposal estimated a net test change near zero. The actual growth, 283
lines, comes from the guard's derivation and its synthetic derived-set,
correction and denial tests, from the fixture test comparing selections with an
empty-catalog composition, and from the two fixes to catalog-reading tests
found during the catalog audit. The suite count rises from 793 to 798: the
guard's seven dual-screen mutation cases became one derived-set test, two
correction cases and nine denial cases.

Main specs change only when the deltas are applied at archive. Applying them
with `openspec archive` in a scratch copy of `openspec/` succeeded (7 added,
2 modified, 15 removed), and `openspec validate --specs --strict` passed on
the result:

| Spec | Before | After archive |
|---|---|---|
| `pack-curation` | 346 | 127 |
| `readme-source-generation` | 490 | 483 |
| `source-ingestion` | 459 | 455 |
| `pack-cli` | 294 | 294 |
| `pack-composition` | 432 | 431 |

## Follow-ups

Outside this change's scope, recorded for later work:

- Per-app names remain in main-spec requirements this change's deltas do not
  touch. In source-ingestion, "Every entry carries a supported source type"
  has an Aurora Store GitLab scenario, "Public GitLab entries retain native
  source identity" has "Aurora extra reaches both exports", and "RJNY export
  flags select entries per variant" illustrates "Entry kept out of dual by
  upstream" with the captured Cemu entries. In pack-curation, "Both packs
  include one shared omnipack notification tracker" says "the RJNY tracker
  exclusion SHALL remain in force".
- No code stops a candidate rule from placing a track-only codm2000 entry in
  its host app's family, where it would compete with the host for the
  dual-screen selection. Making `apply_composition_policy` reject such a rule
  is a production change outside this change.

## 4.1 Retired names in the delta specs

A search of all five delta specs for the retired app and project names
(Cinderbox, BanjoRecomp, SymphonyRecomp, Cemu, RPCSX, Shipwright, Vita3K,
Aurora, idTech4A, VCMI, Julius, Xash, Hollow Knight, Silksong, Dual Souls,
MetroidArch, Super Metroid, RetroArch, Ghostship, Gen1Recomp, EmuLnk, Showdown,
Heimdall, Kanto, Zelda, Minish, Harvest Moon, CTR, OpenMW, Dusklight and the
other corrected apps), for `904332840` and `1845280017`, and for `com.` and
`github.com/`, finds matches only inside `## REMOVED Requirements` sections.
