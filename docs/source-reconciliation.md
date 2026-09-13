# Reviewed game sources and installed identities

Observation date: 2026-09-10 UTC. This review covers 17 installed package-ID
conflicts and the installed CTR source change. It is not a security audit of the
entire catalog.

## Acceptance standard

For community game ports, documented maintainer lineage, credible community use,
and basic source/APK vetting are sufficient for inclusion. Independent binary
reproduction is not required. An unofficial fork, AI-assisted development, or an
Android Debug certificate subject does not by itself establish maliciousness.
These observations also do not certify an app as safe.

The review checked repository lineage and release history, community references,
selected asset hashes, APK manifest identities, permissions, SDK/ABI metadata,
and signing certificates. All 19 inspected candidates for the original 18-app
scope verified with Android's signing tools for the captured Android 13 device.
All 18 GitHub APK asset digests agreed with the downloaded bytes. The remaining
candidate was RetroArch from its official buildbot. Sixteen apps had a candidate
byte-identical to the installed APK; CTR and OpenMW-DS differed. For Simpsons,
that comparison applies to the NTSC asset, not the alternate PAL asset.
No full code audit, malware-free certification, or reproducible-build claim is
made. Source reputation supports the inclusion decision but cannot eliminate
unknown-code or future publisher-compromise risk.

## Source decisions

- **SymphonyRecomp stays.** This is sergiomanzur's unofficial, experimental fork
  of BlackLabelHQ/SymphonyRecomp. Its README disclaims upstream endorsement.
  Community testing corroborates a working Android port while reporting beta
  bugs. The selected APK matches the installed bytes. The previous suggestion
  to withhold it for stronger binary provenance is superseded by the accepted
  reputation standard.
- **OpenMW-DS stays.** Josh-Daniels' second-screen UI provides useful functionality
  and has community corroboration. The selected v1.2.1 APK uses the same signing
  certificate as installed v1.1.0. Native libraries supplied precompiled in the
  source tree remain an acknowledged evidence limit, not an inclusion blocker.
- **Ghostship moves to HarbourMasters.** Its official 3.0.0 release adds Android
  support based on Waterdish's work. Both packs select the Android ZIP, with
  `Ghostship.apk` as the on-device member filter. The legacy izzy2lost entry is
  excluded even if upstream catalogs continue to supply it.
- **CTR keeps its variant choices.** Single-screen uses Simon358; dual-screen uses
  igawa6. The installed Simon build and selected igawa6 build share package ID
  `com.ctrnative` but use different signing keys without a rotation lineage.
  Switching that device to the dual choice requires a fresh installation. Both
  entries disable APK version detection and retain their complete source versions:
  Simon `Android-Build4` and igawa6 `v0.1.0`.
- **MetroidArch replaces the retired Super Metroid port in dual.** The successor
  provides a real second-screen companion interface and passes the accepted
  reputation/basic-vetting standard. Normal RetroArch remains in both packs.
  The two reviewed retired catalog IDs remain excluded. MetroidArch uses a new
  package and needs separate writable-directory setup; see [setup and vetting](metroidarch.md).
- **Gen1Recomp uses its canonical repository.** The old
  `bryanthaboi/pokemon-gen1-recomp-project` URL redirects to
  `bryanthaboi/gen1recomp`. This is a repository rename, not a publisher switch.
  Its launcher can also fetch executable `.love` updates outside Obtainium's APK
  update path; that same-project secondary channel is part of the accepted trust
  boundary.

The remaining reviewed sources stay as listed below. Community links corroborate
use and reputation; they are not endorsements by the original game publishers.

| App | Maintained repository or download source | Community or primary corroboration |
| --- | --- | --- |
| Castlevania: Symphony of the Night Recomp | [Source](https://github.com/sergiomanzur/SymphonyRecomp) | [Reference](https://www.reddit.com/r/decomps/comments/1vpez8w/sotn_recomp_for_android/) |
| Simpsons Hit and Run | [Source](https://github.com/Carlox33/The-Simpsons-Hit-and-Run-Android) | [Reference](https://www.reddit.com/r/retroid/comments/1toi2ii/simpsons_hit_run_android_port_works/) |
| ctr-native-android | [Source](https://github.com/igawa6/ctr-native-android) | [Reference](https://www.reddit.com/r/AndroidNativePorts/comments/1vbx7xf/crash_team_racing_android_port/) |
| Zelda: Ocarina of Time (Shipwright) | [Source](https://github.com/Waterdish/Shipwright-Android) | [Reference](https://www.reddit.com/r/SBCGaming/comments/1tlanti/created_a_list_of_unofficial_android_ports/) |
| Zelda: A Link to the Past DS | [Source](https://github.com/samyost1/zelda3-android) | [Reference](https://www.reddit.com/r/AynThor/comments/1us1t54/zelda_a_link_to_the_past_dual_screen_mod/) |
| Super Mario 64 (Ghostship) | [Source](https://github.com/HarbourMasters/Ghostship/releases/tag/3.0.0) | [Reference](https://www.reddit.com/r/EmulationOnAndroid/comments/1ufaooy/super_mario_64_port_crash_on_android/) |
| Mario Kart 64 (SpaghettiKart) | [Source](https://github.com/izzy2lost/SpaghettiKart) | [Reference](https://www.resetera.com/threads/retro-portables-are-neat.299129/page-483) |
| Perfect Dark Recomp | [Source](https://github.com/izzy2lost/perfect_dark) | [Reference](https://www.resetera.com/threads/retro-portables-are-neat.299129/page-483) |
| MetroidArch (Super Metroid) | [Source](https://github.com/Raekwon1603/RetroArch) | [Reference](https://www.reddit.com/r/AynThor/comments/1w4gdlg/metroidarch_super_metroid_dual_screen/) |
| RetroArch (AArch64) | [Source](https://buildbot.libretro.com/stable) | [Reference](https://www.retroarch.com/?page=platforms) |
| Star Fox 64 (Starship) | [Source](https://github.com/izzy2lost/Starship) | [Reference](https://www.resetera.com/threads/retro-portables-are-neat.299129/page-483) |
| Pokémon Red/Blue Recomp | [Source](https://github.com/bryanthaboi/gen1recomp) | [Reference](https://www.reddit.com/r/EmulationOniOS/comments/1vi5hqu/gen1recompsideloaded/) |
| Zelda: Majora's Mask (2 Ship) | [Source](https://github.com/linkzenic/2ship2harkinian-Android) | [Reference](https://www.reddit.com/r/EmulationOnAndroid/comments/1twd9mo/2ship2harkinian_on_android_update/) |
| Zelda: The Minish Cap | [Source](https://github.com/samyost1/tmc-android) | [Reference](https://www.reddit.com/r/AynThor/comments/1v7lp7x/the_legend_of_zelda_minish_cap_dualscreen_mod_for/) |
| Zelda: Twilight Princess (Dusklight DS) | [Source](https://github.com/igawa6/dusklight) | [Reference](https://www.reddit.com/r/AynThor/comments/1uzyarp/initial_release_dusklight_dualscreen_fork_for/) |
| Harvest Moon 64 Recomp | [Source](https://github.com/igawa6/HarvestMoon64Recomp) | [Reference](https://www.reddit.com/r/AynThor/comments/1vkvnek/back_again_with_more_dual_screen_projects_with/) |
| Crash Bandicoot | [Source](https://github.com/Matteo842/CrashBandicoot-Launcher) | [Reference](https://www.reddit.com/r/decomps/comments/1v714me/update_on_cb1_launcher/) |
| Elder Scrolls 3 Morrowind (OpenMW-DS) | [Source](https://github.com/Josh-Daniels/OpenMW-DS) | [Reference](https://www.reddit.com/r/Morrowind/comments/1v19jye/follow_up_from_my_post_last_week_openmwds_is/) |

## Identity corrections that survive catalog refresh

These are corrections to Obtainium's configured tracking ID. They name the
package already present inside the inspected APK; they do not rename an Android
installation or require reinstalling an identical APK. Composition rules match
original source provenance and preserve that original catalog identity in build
reports. Package/family uniqueness is enforced after correction.

| App | Original catalog ID | Verified APK ID |
| --- | --- | --- |
| Castlevania: Symphony of the Night Recomp | `com.sergiomanzur.sotnrecomp` | `com.blacklabelhq.sotn` |
| Simpsons Hit and Run | `com.carlox33.hitandrun` | `com.c4rlox.simpsons` |
| Zelda: Ocarina of Time (Shipwright) | `com.waterdish.shipwright` | `com.dishii.soh` |
| Zelda: A Link to the Past DS | `com.samyost1.zelda3android` | `com.dishii.zelda3` |
| Mario Kart 64 (SpaghettiKart) | `com.izzy2lost.spaghettikart` | `com.izzy.kart` |
| Perfect Dark Recomp | `com.izzy2lost.perfectdark` | `com.perfectdark.port` |
| RetroArch (AArch64) | `487343354` | `com.retroarch.aarch64` |
| Star Fox 64 (Starship) | `com.izzy2lost.starship` | `com.starship.android` |
| Pokémon Red/Blue Recomp | `com.bryanthaboi.pokemonredblue` | `com.theboisclub.pokemonred` |
| Zelda: Majora's Mask (2 Ship) | `org.linkzenic.twoship` | `com.twoshipfork.mm` |
| Zelda: The Minish Cap | `com.samyost1.tmcandroid` | `dev.picori.tmc` |
| Zelda: Twilight Princess (Dusklight DS) | `com.igawa6.dusklight` | `dev.twilitrealm.dusk` |
| Harvest Moon 64 Recomp | `com.igawa6.harvestmoon64` | `io.github.hm64recomp` |
| Crash Bandicoot | `com.matteo842.crashbandicoot` | `io.github.matteo842.crashlauncher.runtime` |
| Elder Scrolls 3 Morrowind (OpenMW-DS) | `com.joshdaniels.openmwds` | `org.openmw.ds` |
| Crash Team Racing (Simon single-screen) | `com.simon358.ctrnative` | `com.ctrnative` |

## CTR release and manifest evidence

The two CTR identities were checked from separate APKs on 2026-09-10 UTC. The
Simon `Android-Build4` release, published 2026-07-26, selected
`CTR-native-android.26.07.2026.apk` from
<https://github.com/Simon358/ctr-native-android/releases/download/Android-Build4/CTR-native-android.26.07.2026.apk>.
Its 6,912,189 bytes have SHA-256
`a14cb6fc5d39bedeff2c1c5479a50aeba6ade022428d5ac9196dcd50cc79ca38`.
The manifest declares package `com.ctrnative`, versionName `1.0`, and versionCode
`1`. The downloaded release asset is byte-identical to the captured installed APK.

The igawa6 `v0.1.0` release, published 2026-08-30, selected
`ctrds-0.1.0-release.apk` from
<https://github.com/igawa6/ctr-native-android/releases/download/v0.1.0/ctrds-0.1.0-release.apk>.
Its 8,003,024 bytes have SHA-256
`e8ba77a2f0ef0a3ac464c02d734b7d1bad856fa13098a7a97a13cabd80ebb7df`.
Its independently decoded manifest also declares package `com.ctrnative`, with
versionName `0.1.0` and versionCode `1`. The downloaded release is byte-identical
to the separately captured igawa6 APK.

These hashes record the inspected releases; they do not pin future releases.
Metadata resolution does not substitute for APK inspection, and neither check
establishes installation, update, save migration, or controller behavior on a
device. Source-version tracking preserves the full tags while leaving update
checks and notifications enabled. It cannot rule out a one-time update prompt
after re-import or detect an asset replacement whose source tag stays unchanged.

Ghostship is a separate replacement: the retired catalog ID
`com.izzy2lost.ghostship` referred to installed package `com.ghostship.android`.
The official replacement is `dev.net64.ghostship`, so Android treats it as a
separate app. The old package can coexist until manually removed. The official
ZIP SHA-256 is
`f33904ab87c7a99c2465fc244baa43ebdf09d433ef60f63e2b1f8be77b5eafde`;
its inspected `Ghostship.apk` SHA-256 is
`4560cfba9eac305c856c9f255517fdf740fb455886d69fd2f3a786b1c74f6dad`.
That member declares versionName `3.0.0`, versionCode `2`, minimum SDK `24`,
ARM64 and ARMv7 support, and certificate SHA-256
`00785240a0c0db6c54e115c11b4e0ea71540ccce41c39f2ec5c3f8fb86d9485a`.
Its signature verifies; the certificate subject is Android Debug. This is an
observation about the selected official release, not a claim about future assets.

## What changes on an existing device

| Change | Existing package | Effect |
| --- | --- | --- |
| CTR Simon to igawa6 dual | `com.ctrnative` | Different signer; uninstall the existing app before installing the dual build |
| Official Ghostship | `com.ghostship.android` to `dev.net64.ghostship` | New package; install separately and remove the old app if no longer wanted |
| OpenMW-DS v1.1.0 to v1.2.1 | `org.openmw.ds` | Same signer and higher versionCode; ordinary update is possible, fresh install optional |
| Super Metroid successor | `com.raekwon.supermetroid` to `com.metroidarch.app.aarch64` | Dual pack adds MetroidArch as a separate install; old app remains until manually removed; isolate writable directories |
| Other retained identity corrections | IDs listed above | Correct tracking definitions; no reinstall is implied |
| Gen1Recomp URL rename | `com.theboisclub.pokemonred` | Canonical source URL; same inspected APK |

Re-import is not a deletion or synchronization protocol. Removing an entry from
an export does not uninstall its Android package or necessarily remove its
existing Obtainium tracking record. Clearing Obtainium and importing the new
pack is a separate device test. Save and controller migration are intentionally
outside this update; no device writes were performed while preparing it.

## Why incorrect identities and old choices were present

Most mismatches originated in the BBoi/codm2000 source catalogs or generated
catalog identities. The pack previously validated metadata and version syntax
without checking those selected APK manifests. Some known mismatches, including
Symphony and Shipwright, were explicitly deferred during version-policy work.
The dual preference correctly selected igawa6 CTR, a dual-screen build from the
codm catalog, but that choice did not establish signing continuity with an
existing Simon installation. These are limits in our curation and acceptance process as well as
upstream metadata quality, not evidence that the conflict resolver randomly
chose the wrong repository.

Maintained provenance-aware corrections, explicit official-source pins, and
package denials now preserve the decisions through refreshes. The bounded
review does not correct unrelated known catalog issues such as Winlator-Ludashi.
See [curation](curation.md) for that remaining identity/asset selection caveat and
[verification](verification.md) for the runtime check's limits.

The [captured regression evidence](../tests/fixtures/reconciliation/README.md)
retains source inputs and selected manifest observations. See
[validation results](../openspec/changes/archive/2026-09-10-reconcile-installed-apps/source-reconciliation-validation.md) for generated hashes
and the dated live-resolution observations from that validation run.
