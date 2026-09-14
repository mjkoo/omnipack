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
