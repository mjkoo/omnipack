# Maintained app curation

## Pack tracking entries

The RJNY/Obtainium-Emulation-Pack tracking entry (`904332840`) is excluded from
both exports through `config/deny.json`. RJNY remains an app catalog source,
and its attribution and fixture provenance are retained. This exclusion survives
upstream refreshes and removes the tracker from the individual app catalog too.

If you imported an older pack, manually remove that tracking entry in Obtainium
if it remains after re-import. Removing the tracker does not remove the emulator
apps it accompanied. Export exclusion does not guarantee deletion on a device.

### Tracking omnipack itself

Both packs include the same track-only GitHub entry, **omnipack updates**
(`809443320`). It follows the numeric title of the owned `continuous` prerelease.
Publishing a changed verified pair uploads both JSON assets before editing the
shared revision and digest record. Served digests are checked before deciding
to leave, repair or advance the release; repair uploads both assets without
advancing the revision. There is no post-upload readback. A notification means
the collection may have changed for either variant, not which pack changed.

After an update notification, acknowledge the tracker update in Obtainium,
download the appropriate pack, and import it again through **Settings >
Import/export > Obtainium import**. Re-importing applies current app definitions;
the tracker cannot synchronize them automatically. Keep using the same variant
unless you are intentionally changing device type.

Raw-main downloads remain the ordinary consumer links:

- [single-screen JSON](https://raw.githubusercontent.com/mjkoo/omnipack/main/dist/single-screen.json)
- [dual-screen JSON](https://raw.githubusercontent.com/mjkoo/omnipack/main/dist/dual-screen.json)

The rolling release also exposes stable asset links:

- [single-screen release asset](https://github.com/mjkoo/omnipack/releases/download/continuous/single-screen.json)
- [dual-screen release asset](https://github.com/mjkoo/omnipack/releases/download/continuous/dual-screen.json)

Release asset replacement is non-atomic; see [publication visibility and recovery](publishing.md#release-digest-record-and-served-asset-check).

Offline verification validates the complete pair, including this tracker, without
querying releases. After confirmed main publication or a verified no-op, release
synchronization requires an owned release seed. A missing seed fails that release
stage with bootstrap guidance while preserving the successful main outcome.
Omitting the tracker is not a valid way to satisfy either contract. Device import,
unchanged polling, revision-change notification, acknowledgement, and re-import
behavior still require separate device acceptance. Acceptance also covers both
stable JSON downloads. Controlled tests are not completed device or live
publication acceptance.

## Port setup

The entries below need user action beyond installing them. Each note restates
what the upstream project documents; it is not a device validation record.

- **Aurora Store** selects the ordinary GitLab APK rather than hardware-specific
  or preload variants. On first open it asks the user to log in, with a Google
  Play account or anonymously; an anonymous login leaves some features
  unavailable.
- **Cinderbox** requires a user-supplied legitimate copy of Stardew Valley; the
  project distributes no game assets.
- **Ghostship** requires a user-supplied US or JP Super Mario 64 ROM (`.z64`),
  chosen in the app.
- **Pokémon Red/Blue Recomp** requires a user-supplied canonical US Pokémon Game
  Boy ROM (`.gb` or `.gbc`), chosen in the app. The upstream README lists the
  accepted ROMs and their checksums.
- **MetroidArch (Super Metroid)** requires a user-supplied, uncompressed Super
  Metroid ROM, the app's own asset and core-info updates, and separate writable
  directories. The [MetroidArch setup guide](metroidarch.md) describes each
  step.
- **idTech4A++** requires user-supplied data for a supported id Tech game.
- **VCMI** requires user-supplied Heroes of Might and Magic III data and lets
  Obtainium select the APK matching the device architecture.
- **Julius** requires user-supplied Caesar III data.
- **Xash3D FWGS** requires user-supplied Half-Life data. It follows the rolling
  continuous-master Android build; temporary absence of that build is an update
  failure rather than permission to select another channel.
- **Hollow Knight: Dual Souls** requires user-supplied Hollow Knight files.
- **Hollow Knight: Silksong** requires user-supplied Linux game files and builds
  on-device. Its upstream setup currently documents Android 13 only and says
  Android 15 is unsupported.

## Version-policy observations

Release metadata and APK manifests were revalidated on 2026-09-09 UTC.
These dated observations support configuration choices. Current structural
verification does not repeat metadata resolution or APK inspection, or establish
installation, re-import, signature or device behavior. The policies below describe
intended Obtainium behavior; regression tests protect exported configuration.

## Policies

Cinderbox is an explicit extra in both variants, named Cinderbox, by Ekyso,
in PC Ports. It uses numeric release tags and standard detection, excludes
prereleases (including build-dependency releases), and is installable. The
observed 0.8.1 APK has versionCode 113. No release pin or extraction is used.

BanjoRecomp and SymphonyRecomp extract `[0-9]+(?:\.[0-9]+)+`, group `0`,
from release tags. Obtainium evaluates this extraction; a missing match does
not block structural pack verification or nightly publication. Symphony's observed tags yield distinct 0.9, 0.9.1, 0.10 and
0.10.1 versions. This treats trailing `b` as a channel label; a future
stable/beta pair sharing a numeric version requires revisiting the policy.
Cemu uses each variant's own release tag (0.5 single, 0.5.2 dual), retaining
its source URL and asset selection. RPCSX retains v20250425 unchanged.

CTR, Shipwright, Citron, Vita3K, XenDroid, Ludashi, Cmod and Mjolnir explicitly
set only `versionDetection: false`. Their complete source versions remain
intact. Source polling, installation, background checks and notifications
remain enabled; this does not turn them into track-only entries.
Shipwright's v9.0.2, v9.0.2P1 and v9.0.2P2 must remain distinguishable even
though the inspected APK reports 9.0.2. Vita3K's build number is distinct
from its APK version. Date tags, commit hashes, hotfix markers and Cmod's
labels likewise require preserving source identity.

## Manifest evidence

Each link identifies the inspected primary APK asset. Configured ids, observed
source versions and manifest values are also retained in the
[regression evidence](../tests/fixtures/curation/README.md).

| Configured id | Source version | APK package | APK versionName | APK versionCode | Primary asset |
| --- | --- | --- | --- | --- | --- |
| `com.aure.banjorecomp` | `android-v0.1.1` | `com.aure.banjorecomp` | `0.1.1` | 101 | [APK](https://github.com/AurelioB/BanjoRecomp-Android/releases/download/android-v0.1.1/BanjoRecompiled-v0.1.1-Android-ARM64.apk) |
| `com.sergiomanzur.sotnrecomp` | `android-v0.10.1b` | `com.blacklabelhq.sotn` | `0.10.1` | 12 | [APK](https://github.com/sergiomanzur/SymphonyRecomp/releases/download/android-v0.10.1b/SymphonyRecomp-Android-Beta-0.10.1.apk) |
| `com.simon358.ctrnative` | `Android-Build4` | `com.ctrnative` | `1.0` | 1 | [APK](https://github.com/Simon358/ctr-native-android/releases/download/Android-Build4/CTR-native-android.26.07.2026.apk) |
| `com.waterdish.shipwright` | `v9.0.2P2` | `com.dishii.soh` | `9.0.2` | 8 | [APK](https://github.com/Waterdish/Shipwright-Android/releases/download/v9.0.2P2/soh.apk) |
| `info.cemu.cemu` | `Cemu 0.5` | `info.cemu.cemu` | `0.5` | 1 | [APK](https://github.com/SSimco/Cemu/releases/download/0.5/Cemu-0.5.apk) |
| `org.citron.citron_emu` | `2026-04-27` | `org.citron.citron_emu` | `0237a9b88` | 1 | [APK](https://github.com/citron-neo/emulator/releases/download/2026-04-27/app-mainline-release.apk) |
| `org.citron.citron_emu` | `2026-04-27` | `org.citron.citron_emu` | `0237a9b88` | 1 | [APK](https://github.com/citron-neo/emulator/releases/download/2026-04-27/Citron-28560-Android-8.Elite-Lyb.apk) |
| `net.rpcsx` | `v20250425` | `net.rpcsx` | `20250425` | 1 | [APK](https://github.com/RPCSX/rpcsx-ui-android/releases/download/v20250425/rpcsx-release.apk) |
| `org.vita3k.emulator` | `4093` | `org.vita3k.emulator` | `0.2.1` | 21 | [APK](https://github.com/Vita3K/Vita3K-builds/releases/download/4093/vita3k-4093-257464af-android.apk) |
| `xendroid.compose` | `XenDroid-0b11201` | `xendroid.compose` | `0b11201` | 1 | [APK](https://github.com/rfandango/XenDroid/releases/download/XenDroid-0b11201/XenDroid_Release_0b11201.apk) |
| `com.winlator.ludashi` | `v3.1.h` | `com.winlator.vanilla` | `3.1` | 20 | [APK](https://github.com/StevenMXZ/Winlator-Ludashi/releases/download/v3.1.h/bionic-vanilla.apk) |
| `com.winlator.cmod` | `cmod_v13.1` | `com.winlator.cmod` | `Cmod-v13.1` | 20 | [APK](https://github.com/coffincolors/winlator/releases/download/cmod_v13.1/Winlator-Cmod-v13.1.1.apk) |
| `info.cemu.cemu` | `CEMU Android v0.5.2: Graphic Packs Custom Root Fix` | `info.cemu.cemu` | `0.5.2` | 52 | [APK](https://github.com/SapphireRhodonite/Cemu/releases/download/0.5.2/Cemu.DualScreen.0.5.2.apk) |
| `xyz.blacksheep.mjolnir` | `v0.2.7a-hotfix` | `xyz.blacksheep.mjolnir` | `0.2.7a` | 20 | [APK](https://github.com/blacksheepmvp/mjolnir/releases/download/v0.2.7a-hotfix/Mjolnir-v0.2.7a-hotfix.apk) |
| `com.game.cinderbox` | `0.8.1` | `com.game.cinderbox` | `0.8.1` | 113 | [APK](https://github.com/Ekyso/Cinderbox/releases/download/0.8.1/Cinderbox-v0.8.1.apk) |
| `xendroid.compose` | `XenDroid-c4f6863` | `xendroid.compose` | `c4f6863` | 1 | [APK](https://github.com/rfandango/XenDroid/releases/download/XenDroid-c4f6863/XenDroid_Release_c4f6863.apk) |

## Unresolved identity and selection findings

CTR retains the manifest-backed `com.ctrnative` identity and variant-specific
sources. The later [installed-source reconciliation](source-reconciliation.md)
corrects Symphony and Shipwright plus the other reviewed installed identities,
replaces Ghostship with its official Android release, and removes retired Super
Metroid. Its reputation-plus-basic-vetting policy retains Symphony and OpenMW-DS.
An identity correction does not itself require replacing an installed APK.

Ludashi (`com.winlator.ludashi`) remains outside that bounded reconciliation.
Its inspected APK declares `com.winlator.vanilla`; the configured identity is
still unresolved. Structural verification cannot repair that mismatch or
establish successful device acceptance.

[Ludashi releases](https://github.com/StevenMXZ/Winlator-Ludashi/releases)
include v4.0, but the existing APK filter still selects bionic-vanilla.apk from
v3.1.h through the older-release fallback. The newer release uses renamed
assets and is not selected by that filter.

[XenDroid releases](https://github.com/rfandango/XenDroid/releases) exposed
XenDroid-c4f6863 during refresh; its inspected manifest has the matching hash
and unchanged package identity. Its published timestamp (2026-08-14 11:11 UTC)
is earlier than 0b11201 (16:33 UTC), so date sorting still selects 0b11201.
Both observations are recorded.

## Limits and maintenance

The [pinned installed-version reconciliation](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/providers/apps_provider_lifecycle.dart)
can reconcile descriptive versions with numeric installed versions. A format
warning alone therefore does not prove re-import thrash. Source tracking can
still show a one-time update after re-import; external installation may not
update Obtainium's recorded source version. Replacing an asset under an unchanged
source version is not detectable through source-version comparison.

Generic whole-pack live resolution, effective-version format lint and
upstream-health publication gating are retired. The explicit codm source
generator still resolves reviewed APK projects before their catalog changes are
accepted; normal builds consume that committed catalog. Structural checks retain
setting types without evaluating patterns, versions or release availability.
Investigate changed source behavior in Obtainium and record new observations
with their dates and provenance.

Policies take effect on the next import. Rollback restores the previous extras
and overlay and rebuilds both files.
