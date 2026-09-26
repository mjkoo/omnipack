# Quiver initial admission validation

Observation date: 2026-09-26.

## Method and discovery

Refreshed the [Quiver index](https://raw.githubusercontent.com/tgeorgiadis/quiver-community-app-catalog/main/index.json) and all four referenced lists. The snapshot contained 232 rows, 229 literal repository names and 223 supported GitHub repository names. Every supported repository was freshly identified through the GitHub API and its latest stable release checked. Twenty-three projects exposed direct APKs. The ninth original lead, Melee, had no stable release; an explicit prerelease review selected v0.2.2-beta. All nine original leads were accounted for. Platform metadata did not decide Android eligibility.

Downloaded 29 APKs across these 24 projects. Inspected manifests and native-library ABIs with Android SDK build-tools 37.0.0 aapt2; verified signatures using apksigner with OpenJDK 21.0.11. All 29 APKs passed signature verification and selected assets within each project agreed on package identity. APKs were not executed. No device, ADB server, installation or gameplay check was performed.

The acceptance standard is documented maintainer lineage, credible community use and basic source/APK inspection. Project release history and public source establish lineage; captured release download counts below are limited corroboration of distribution, not proof of successful play. Experimental status, AI assistance and a debug certificate subject alone are not rejection reasons. This is not a malware audit or reproducible-build attestation.

Six unsupported GitLab rows were reported without GitHub requests: `sonicdcer/DNZHRecomp`, `sonicdcer/MarioKart64Recomp`, `sonicdcer/Starfox64Recomp`, `bighead.0/ladxhd_updated`, `sonicdcer/ExtremeGRecomp` and `ethan4love/psx-recomp-port`. They are unsupported discovery rows, not rejected Android apps. The 199 remaining supported projects had no eligible Android release under the reviewed policy. No lookup remained unresolved and no repository returned a conclusive 404/451 absence in this observation.

Three canonical projects had differing upstream release filters: `FluffyQuack/ReXGlue-Exit`, `mstan/FireRedLeafGreenRecomp` and `mstan/RubySapphireRecomp`. None had an eligible direct Android APK at review time. Their rows were preserved as provenance and collapsed per repository; upstream filters did not silently select a game. A future multi-package APK release will require a reviewed filter or fail visibly under the one-package-per-project rule.

## Candidate evidence and dispositions

| Project | Inspected release | Package ID | Distribution observations | Disposition |
| --- | --- | --- | --- | --- |
| [999sian/melee-pc](https://github.com/999sian/melee-pc) | [v0.2.2-beta](https://github.com/999sian/melee-pc/releases/tag/v0.2.2-beta) | `dev.melee.game` | 382 stars; 16 forks; 360 selected-release APK downloads | Admit beta by explicit prerelease rule; decompilation/aurora lineage, public beta use; arm64/Vulkan and separate updater disclosed |
| [999sian/tmc](https://github.com/999sian/tmc) | [v0.9.3](https://github.com/999sian/tmc/releases/tag/v0.9.3) | `dev.picori.tmc` | 434 stars; 19 forks; 1425 selected-release APK downloads | Admit lower-ranked duplicate; preserve Picori single and samyost1 dual |
| [alondero/aerogauge-recomp](https://github.com/alondero/aerogauge-recomp) | [v0.5.0](https://github.com/alondero/aerogauge-recomp/releases/tag/v0.5.0) | `io.github.alondero.aerogaugerecomp` | 33 stars; 0 forks; 42 selected-release APK downloads | Admit experimental port; clear source/release lineage, limited Android uptake and testing disclosed |
| [alondero/automobililamborghini-recomp](https://github.com/alondero/automobililamborghini-recomp) | [v0.7.2](https://github.com/alondero/automobililamborghini-recomp/releases/tag/v0.7.2) | `io.github.alondero.lamborghinirecomp` | 38 stars; 2 forks; 45 selected-release APK downloads | Admit experimental port; documented ROM/Android build and published source, save caveats disclosed |
| [birabittoh/EternalSonataReprise](https://github.com/birabittoh/EternalSonataReprise) | [v1.2.4](https://github.com/birabittoh/EternalSonataReprise/releases/tag/v1.2.4) | `com.birabittoh.eternalsonata` | 101 stars; 3 forks; 86 selected-release APK downloads | Admit experimental ReXGlue port; Android release history and community issues; separate updater disclosed |
| [bryanthaboi/pokemon-gen1-recomp-project](https://github.com/bryanthaboi/gen1recomp) | [v0.3.20](https://github.com/bryanthaboi/gen1recomp/releases/tag/v0.3.20) | `com.theboisclub.pokemonred` | 3779 stars; 329 forks; 1434 selected-release APK downloads | Admit canonical duplicate; preserve reviewed Gen1Recomp extra |
| [bvschaik/julius](https://github.com/bvschaik/julius) | [v1.8.0](https://github.com/bvschaik/julius/releases/tag/v1.8.0) | `com.github.bvschaik.julius` | 3385 stars; 442 forks; 1888 selected-release APK downloads | Admit duplicate; preserve reviewed Julius extra |
| [chrissotraidis/kartpad](https://github.com/chrissotraidis/kartpad) | [v0.5.2](https://github.com/chrissotraidis/kartpad/releases/tag/v0.5.2) | `dev.kartpad.android` | 589 stars; 34 forks; 490 selected-release APK downloads | Admit lower-ranked duplicate of live BBoi; correct BBoi package ID from inspected APK, retain its settings; WiiCompiled lineage and limited physical testing disclosed |
| [doukutsu-rs/doukutsu-rs](https://github.com/doukutsu-rs/doukutsu-rs) | [1.0.0](https://github.com/doukutsu-rs/doukutsu-rs/releases/tag/1.0.0) | `io.github.doukutsu_rs` | 1298 stars; 82 forks; 751 selected-release APK downloads | Admit established Cave Story engine with original data requirement |
| [Eukaryot/sonic3air](https://github.com/Eukaryot/sonic3air) | [v26.03.28.0-stable](https://github.com/Eukaryot/sonic3air/releases/tag/v26.03.28.0-stable) | `org.eukaryot.sonic3air` | 641 stars; 164 forks; 174144 selected-release APK downloads | Admit official stable Android release; established project and substantial distribution |
| [isledecomp/isle-portable](https://github.com/isledecomp/isle-portable) | [continuous](https://github.com/isledecomp/isle-portable/releases/tag/continuous) | `org.legoisland.isle` | 1049 stars; 96 forks; 14 selected-release APK downloads | Admit upstream experimental build with release-only APK filter; developer-oriented status disclosed; does not fulfill pending owner-fork request |
| [JRickey/BattleShip](https://github.com/JRickey/BattleShip) | [v1.6](https://github.com/JRickey/BattleShip/releases/tag/v1.6) | `com.jrickey.battleship` | 445 stars; 47 forks; 4243 selected-release APK downloads | Admit duplicate; preserve reviewed BBoi source and settings |
| [kandowontu/starfox-enhanced](https://github.com/kandowontu/starfox-enhanced) | [v0.0.8](https://github.com/kandowontu/starfox-enhanced/releases/tag/v0.0.8) | `com.starfox.enhanced` | 352 stars; 18 forks; 163 selected-release APK downloads | Admit UltraStarFox-derived port with Android releases and public issue/test activity |
| [Keriew/augustus](https://github.com/Keriew/augustus) | [v4.0.0](https://github.com/Keriew/augustus/releases/tag/v4.0.0) | `com.github.Keriew.augustus` | 2092 stars; 179 forks; 1468 selected-release APK downloads | Admit established Julius extension as distinct gameplay fork and package; original data required |
| [Matteo842/CrashBandicoot-Launcher](https://github.com/Matteo842/CrashBandicoot-Launcher) | [1.9.4](https://github.com/Matteo842/CrashBandicoot-Launcher/releases/tag/1.9.4) | `io.github.matteo842.crashlauncher.runtime` | 231 stars; 8 forks; 1376 selected-release APK downloads | Admit duplicate; preserve reviewed BBoi source and settings |
| [mstan/EmeraldRecomp](https://github.com/mstan/EmeraldRecomp) | [v0.0.7](https://github.com/mstan/EmeraldRecomp/releases/tag/v0.0.7) | `com.mstan.emeraldrecomp` | 22 stars; 5 forks; 37 selected-release APK downloads | Admit early gbarecomp port; limited uptake disclosed; reviewed family preserves existing dual-screen Emerald |
| [OpenRCT2/OpenRCT2](https://github.com/OpenRCT2/OpenRCT2) | [v0.5.5](https://github.com/OpenRCT2/OpenRCT2/releases/tag/v0.5.5) | `io.openrct2` | 16262 stars; 1906 forks; 817 selected-release APK downloads | Admit official mature engine; original data and mobile UI limitations disclosed |
| [sergiomanzur/regaiden-recomp](https://github.com/sergiomanzur/regaiden-recomp) | [v0.4.1](https://github.com/sergiomanzur/regaiden-recomp/releases/tag/v0.4.1) | `com.capcom.regaiden` | 46 stars; 3 forks; 164 selected-release APK downloads | Admit known SymphonyRecomp maintainer port with Android release/issue history and exact ROM requirement |
| [Simon358/ctr-native-android](https://github.com/Simon358/ctr-native-android) | [Android-Build4](https://github.com/Simon358/ctr-native-android/releases/tag/Android-Build4) | `com.ctrnative` | 35 stars; 3 forks; 6259 selected-release APK downloads | Admit duplicate; preserve Simon single and igawa6 dual without signer change |
| [SlickAmogus/silent-hill-decomp](https://github.com/SlickAmogus/silent-hill-decomp) | [crossplatform-beta](https://github.com/SlickAmogus/silent-hill-decomp/releases/tag/crossplatform-beta) | `com.silenthill.port` | 590 stars; 34 forks; 2156 selected-release APK downloads | Admit lower-ranked duplicate of live BBoi; correct BBoi package ID, retain settings; Quiver candidate omits _OLD APK; beta/nightly channel disclosed |
| [SSunnKing/Open-Nectar---Pikmin-Native-PC-Port](https://github.com/SSunnKing/Open-Nectar---Pikmin-Native-PC-Mobile-Port) | [0.8.5](https://github.com/SSunnKing/Open-Nectar---Pikmin-Native-PC-Mobile-Port/releases/tag/0.8.5) | `org.opennectar` | 167 stars; 10 forks; 429 selected-release APK downloads | Admit canonical renamed project; documented projectPiki lineage and Android release history |
| [TeamGDB/Yakumo](https://github.com/TeamGDB/Yakumo) | [v0.6.0-alpha.4](https://github.com/TeamGDB/Yakumo/releases/tag/v0.6.0-alpha.4) | `io.github.teamgdb.yakumo` | 260 stars; 8 forks; 2770 selected-release APK downloads | Admit alpha with documented source lineage and substantial APK distribution; limited physical-device coverage disclosed |
| [TwilitRealm/dusklight](https://github.com/TwilitRealm/dusklight) | [v2.0.2](https://github.com/TwilitRealm/dusklight/releases/tag/v2.0.2) | `dev.twilitrealm.dusk` | 5539 stars; 408 forks; 6412 selected-release APK downloads | Admit duplicate; preserve existing single and dual family winners |
| [vcmi/vcmi](https://github.com/vcmi/vcmi) | [1.7.5](https://github.com/vcmi/vcmi/releases/tag/1.7.5) | `is.xyz.vcmi` | 5885 stars; 698 forks; 4568 selected-release APK downloads | Admit duplicate; preserve reviewed VCMI extra and architecture settings |

## Admission and composition decisions

Every initial Android candidate is admitted to the source catalog. There are no rejected Android candidates and therefore no new global package denials or discovery skips. Existing package denials continue to apply to every source. Automated composition tests cover a denied package resurfacing under a renamed Quiver repository in both packs.

Eight reviewed exceptions select Melee prereleases, omit Silent Hill's `_OLD.apk`, select LEGO Island's `app-release.apk`, and categorize Augustus, OpenRCT2, Julius, doukutsu-rs and VCMI as PC Ports. These rules are exceptions, not a project allowlist. Subsequent upstream additions are still discovered by default.

The inspected LEGO Island debug and release APKs share an identity but use different signing keys. Selecting only the release artifact avoids alternating between incompatible keys. BattleShip's two architecture assets and VCMI's three architecture assets share their respective package IDs and signing keys. All 29 assets were inspected, including the two deliberately omitted debug/obsolete assets; 28 matched the GitHub API's published SHA-256 digest and the older Augustus asset supplied no digest.

The existing higher-ranked sources win whole on package overlap. Live BBoi entries for KartPad (`com.chrissotraidis.kartpad`) and Silent Hill (`com.slickamogus.silenthill`) carried IDs that differ from the inspected APK manifests. Reviewed composition corrections set their effective IDs to `dev.kartpad.android` and `com.silenthill.port`; all other fields remain unchanged. These live rows were newer than the captured reconciliation fixtures, so dedicated tests inject their exact selectors and verify the corrected identities and retained settings. The explicit Emerald family relates two reviewed implementations of the same original game, not an inferred title match: [EmeraldRecomp](https://github.com/mstan/EmeraldRecomp) supplies the single-screen baseline, while [pokeemerald-dualscreen](https://github.com/Goldoire/pokeemerald-dualscreen) remains the preferred dual-screen app. Their IDs differ. Augustus remains separate from Julius because its gameplay extensions are a distinct curated choice.

[Setup guidance](../../../docs/quiver-ports.md) records the user-data requirements and material maturity/update-channel limits. [Source reconciliation](../../../docs/source-reconciliation.md) retains earlier fork and signer decisions. The owner's requested custom LEGO Island fork still needs its actual URL; adding upstream does not resolve that separate request.

## APK observations

All hashes are SHA-256 of the downloaded bytes. Signing fingerprints identify the inspected APK, not future releases or compatibility with an installed app. Full SDK-range signature verification succeeded for each asset. Some v1 signatures warn that META-INF build metadata is not protected by that signature; modern v2/v3 verification also succeeded where recorded.

### 999sian/melee-pc / Melee-Android-arm64.apk

- Asset: [Melee-Android-arm64.apk](https://github.com/999sian/melee-pc/releases/download/v0.2.2-beta/Melee-Android-arm64.apk)
- APK SHA-256: `b6ff2cac76b88a321ab0627db9c8b3c7c5b472c8c33fac47ce71aee8aed5881d`
- Manifest: `package: name='dev.melee.game' versionCode='12' versionName='v0.2.2-beta' platformBuildVersionName='14' platformBuildVersionCode='34' compileSdkVersion='34' compileSdkVersionCodename='14'`
- SDK: minSdkVersion:'26'; targetSdkVersion:'34'. ABI: native-code: 'arm64-v8a'.
- Signer: CN=melee-pc, OU=999sian, O=melee-pc, C=US; SHA-256: `8533e4a3b1e04d564bae9e9de3213bfc568e00e17390e72b7939e1087a4af51f`. Verification passed; debuggable: False.
- Permissions: `android.permission.VIBRATE`, `android.permission.READ_EXTERNAL_STORAGE`, `android.permission.WRITE_EXTERNAL_STORAGE`, `android.permission.MANAGE_EXTERNAL_STORAGE`, `android.permission.INTERNET`, `android.permission.ACCESS_NETWORK_STATE`, `android.permission.ACCESS_WIFI_STATE`, `android.permission.CHANGE_WIFI_MULTICAST_STATE`.

### 999sian/tmc / tmc-multi-android-v0.9.3.apk

- Asset: [tmc-multi-android-v0.9.3.apk](https://github.com/999sian/tmc/releases/download/v0.9.3/tmc-multi-android-v0.9.3.apk)
- APK SHA-256: `dbb1b8f8c0239a21df438e615d14d9fe7d7e5985e1a2ef4c7c35d128fd5c2702`
- Manifest: `package: name='dev.picori.tmc' versionCode='90300' versionName='0.9.3' platformBuildVersionName='14' platformBuildVersionCode='34' compileSdkVersion='34' compileSdkVersionCodename='14'`
- SDK: minSdkVersion:'21'; targetSdkVersion:'34'. ABI: native-code: 'arm64-v8a' 'x86_64'.
- Signer: CN=Project Picori, OU=TMC PC Port, O=999sian; SHA-256: `0982f3b7135a317d7185140fe35e805ab7f070aba930662161e1679771088458`. Verification passed; debuggable: False.
- Permissions: `android.permission.VIBRATE`.

### Eukaryot/sonic3air / sonic3air_game.apk

- Asset: [sonic3air_game.apk](https://github.com/Eukaryot/sonic3air/releases/download/v26.03.28.0-stable/sonic3air_game.apk)
- APK SHA-256: `915fbf525efadfff06ed27923f8aead490ff29723b87445fbf172e1a4b476838`
- Manifest: `package: name='org.eukaryot.sonic3air' versionCode='1' versionName='26.03.28.0' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'`
- SDK: minSdkVersion:'23'; targetSdkVersion:'29'. ABI: native-code: 'arm64-v8a' 'armeabi-v7a' 'x86' 'x86_64'.
- Signer: CN=Eukaryot; SHA-256: `340b403e3078f04fbd27f242eeebe9ccbe5bbd2137509f6b318ac38eba4a2aea`. Verification passed; debuggable: False.
- Permissions: `android.permission.WRITE_EXTERNAL_STORAGE`, `android.permission.BLUETOOTH`, `android.permission.VIBRATE`, `android.permission.INTERNET`, `android.permission.READ_EXTERNAL_STORAGE`.

### JRickey/BattleShip / BattleShip-android-armeabi-v7a.apk

- Asset: [BattleShip-android-armeabi-v7a.apk](https://github.com/JRickey/BattleShip/releases/download/v1.6/BattleShip-android-armeabi-v7a.apk)
- APK SHA-256: `21d9965ed694af5142edade56e094dc8e125f6819a60b2913b09646d4099ebe1`
- Manifest: `package: name='com.jrickey.battleship' versionCode='1' versionName='0.1.0-spike' platformBuildVersionName='14' platformBuildVersionCode='34' compileSdkVersion='34' compileSdkVersionCodename='14'`
- SDK: minSdkVersion:'24'; targetSdkVersion:'34'. ABI: native-code: 'armeabi-v7a'.
- Signer: CN=BattleShip, O=JRickey, C=US; SHA-256: `fcf996399e5f2e81e88d2070515cb0424a3e355e7bd6ca0775a16d2d4ffafa2e`. Verification passed; debuggable: False.
- Permissions: `android.permission.VIBRATE`, `com.jrickey.battleship.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`.

### JRickey/BattleShip / BattleShip-android.apk

- Asset: [BattleShip-android.apk](https://github.com/JRickey/BattleShip/releases/download/v1.6/BattleShip-android.apk)
- APK SHA-256: `310f2ff55454faf6b8cfb9a3088beba3ef98cefb75b92c7b6bc8183a108648b8`
- Manifest: `package: name='com.jrickey.battleship' versionCode='1' versionName='0.1.0-spike' platformBuildVersionName='14' platformBuildVersionCode='34' compileSdkVersion='34' compileSdkVersionCodename='14'`
- SDK: minSdkVersion:'24'; targetSdkVersion:'34'. ABI: native-code: 'arm64-v8a'.
- Signer: CN=BattleShip, O=JRickey, C=US; SHA-256: `fcf996399e5f2e81e88d2070515cb0424a3e355e7bd6ca0775a16d2d4ffafa2e`. Verification passed; debuggable: False.
- Permissions: `android.permission.VIBRATE`, `com.jrickey.battleship.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`.

### Keriew/augustus / augustus-4.0.0-android.apk

- Asset: [augustus-4.0.0-android.apk](https://github.com/Keriew/augustus/releases/download/v4.0.0/augustus-4.0.0-android.apk)
- APK SHA-256: `934b6580b7e4d1063c95bbb11c642f7bde3839076e5594f14e68729f0ea8b8d2`
- Manifest: `package: name='com.github.Keriew.augustus' versionCode='40000000' versionName='4.0.0' platformBuildVersionName='13' platformBuildVersionCode='33' compileSdkVersion='33' compileSdkVersionCodename='13'`
- SDK: minSdkVersion:'21'; targetSdkVersion:'33'. ABI: native-code: 'arm64-v8a' 'armeabi-v7a' 'x86' 'x86_64'.
- Signer: CN=Augustus Dev Team, OU=IT, O=Augustus, C=PL; SHA-256: `b8b8895dfad50947593c1ca3423aa53cdb6b62958c0f31d395157bd75cb7c326`. Verification passed; debuggable: False.
- Permissions: `com.github.Keriew.augustus.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`.

### Matteo842/CrashBandicoot-Launcher / CrashBandicoot-1.9.4.apk

- Asset: [CrashBandicoot-1.9.4.apk](https://github.com/Matteo842/CrashBandicoot-Launcher/releases/download/1.9.4/CrashBandicoot-1.9.4.apk)
- APK SHA-256: `0020f780e9b911b3f41ed075512c3033ddbfcf30070cce2790900251aece70c5`
- Manifest: `package: name='io.github.matteo842.crashlauncher.runtime' versionCode='14' versionName='1.9.4' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'`
- SDK: minSdkVersion:'26'; targetSdkVersion:'36'. ABI: native-code: 'arm64-v8a' 'x86_64'.
- Signer: CN=Crash Bandicoot Recompiled, OU=Unofficial fan project, O=CrashBandicoot-Launcher, C=IT; SHA-256: `4879193db383c0dace44aabb71486a9a197d6475633ebda6cc9073cd53df79e6`. Verification passed; debuggable: False.
- Permissions: `android.permission.READ_EXTERNAL_STORAGE`, `android.permission.WRITE_EXTERNAL_STORAGE`, `android.permission.MANAGE_EXTERNAL_STORAGE`, `android.permission.BLUETOOTH`, `android.permission.VIBRATE`.

### OpenRCT2/OpenRCT2 / OpenRCT2-v0.5.5-android.apk

- Asset: [OpenRCT2-v0.5.5-android.apk](https://github.com/OpenRCT2/OpenRCT2/releases/download/v0.5.5/OpenRCT2-v0.5.5-android.apk)
- APK SHA-256: `8dcabe11c87a5ea8de00a7e083ee3f54bd37239def6cb6f14d2b192492707111`
- Manifest: `package: name='io.openrct2' versionCode='25' versionName='0.5.5' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'`
- SDK: minSdkVersion:'24'; targetSdkVersion:'36'. ABI: native-code: 'arm64-v8a' 'armeabi-v7a' 'x86_64'.
- Signer: CN=OpenRCT2 Team, OU=Development, O=OpenRCT2 Team; SHA-256: `f22b57042c6d4114b40ce559216ac049cdae9b34b830f7b0f018bca090ef99a9`. Verification passed; debuggable: False.
- Permissions: `android.permission.ACCESS_NETWORK_STATE`, `android.permission.INTERNET`, `android.permission.MANAGE_EXTERNAL_STORAGE`, `android.permission.READ_EXTERNAL_STORAGE`, `android.permission.WRITE_EXTERNAL_STORAGE`, `io.openrct2.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`.

### SSunnKing/Open-Nectar---Pikmin-Native-PC-Port / open_nectar_0.8.5.apk

- Asset: [open_nectar_0.8.5.apk](https://github.com/SSunnKing/Open-Nectar---Pikmin-Native-PC-Mobile-Port/releases/download/0.8.5/open_nectar_0.8.5.apk)
- APK SHA-256: `eb42d9b9b420cb56783236d10dad49af489d12832d1f3cd222fc7f061eb4c665`
- Manifest: `package: name='org.opennectar' versionCode='6' versionName='0.8.5' platformBuildVersionName='15' platformBuildVersionCode='35' compileSdkVersion='35' compileSdkVersionCodename='15'`
- SDK: minSdkVersion:'29'; targetSdkVersion:'35'. ABI: native-code: 'arm64-v8a'.
- Signer: CN=Open Nectar, O=Open Nectar; SHA-256: `9099adffdb003d9d03f6eecb24879f989625a72cb62be5f042bc49925c88b1ed`. Verification passed; debuggable: False.
- Permissions: `android.permission.VIBRATE`.

### Simon358/ctr-native-android / CTR-native-android.26.07.2026.apk

- Asset: [CTR-native-android.26.07.2026.apk](https://github.com/Simon358/ctr-native-android/releases/download/Android-Build4/CTR-native-android.26.07.2026.apk)
- APK SHA-256: `a14cb6fc5d39bedeff2c1c5479a50aeba6ade022428d5ac9196dcd50cc79ca38`
- Manifest: `package: name='com.ctrnative' versionCode='1' versionName='1.0' platformBuildVersionName='14' platformBuildVersionCode='34' compileSdkVersion='34' compileSdkVersionCodename='14'`
- SDK: minSdkVersion:'21'; targetSdkVersion:'34'. ABI: native-code: 'armeabi-v7a' 'x86'.
- Signer: C=US, O=Android, CN=Android Debug; SHA-256: `b7aebffee316cff627cdbb40f25f64fdebfa9b8de95d43e15bbcf40e0ea2c52c`. Verification passed; debuggable: True.
- Permissions: `android.permission.VIBRATE`, `android.permission.INTERNET`, `android.permission.READ_EXTERNAL_STORAGE`, `android.permission.WRITE_EXTERNAL_STORAGE`, `android.permission.MANAGE_EXTERNAL_STORAGE`, `com.ctrnative.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`.

### SlickAmogus/silent-hill-decomp / SHAndroid_091826_OLD.apk

- Asset: [SHAndroid_091826_OLD.apk](https://github.com/SlickAmogus/silent-hill-decomp/releases/download/crossplatform-beta/SHAndroid_091826_OLD.apk)
- APK SHA-256: `e94c62bdb582651f6476efd1e5c3b5e7626d443c75ab0afa8d8c1547b3bcccd3`
- Manifest: `package: name='com.silenthill.port' versionCode='1' versionName='0.1-android' platformBuildVersionName='14' platformBuildVersionCode='34' compileSdkVersion='34' compileSdkVersionCodename='14'`
- SDK: minSdkVersion:'21'; targetSdkVersion:'34'. ABI: native-code: 'arm64-v8a' 'armeabi-v7a'.
- Signer: C=US, O=Android, CN=Android Debug; SHA-256: `2a3786e1b2ae8065ff744d6b44dfc059a49110942711b643fad454cadb428abe`. Verification passed; debuggable: True.
- Permissions: `android.permission.INTERNET`, `android.permission.READ_EXTERNAL_STORAGE`, `android.permission.MANAGE_EXTERNAL_STORAGE`.

### SlickAmogus/silent-hill-decomp / SHAndroid_092226.apk

- Asset: [SHAndroid_092226.apk](https://github.com/SlickAmogus/silent-hill-decomp/releases/download/crossplatform-beta/SHAndroid_092226.apk)
- APK SHA-256: `54a5126f09703e64868a37226957b2f17057070ae52fc035a66730888dcb436e`
- Manifest: `package: name='com.silenthill.port' versionCode='1' versionName='0.1-android' platformBuildVersionName='14' platformBuildVersionCode='34' compileSdkVersion='34' compileSdkVersionCodename='14'`
- SDK: minSdkVersion:'21'; targetSdkVersion:'34'. ABI: native-code: 'arm64-v8a' 'armeabi-v7a'.
- Signer: C=US, O=Android, CN=Android Debug; SHA-256: `2a3786e1b2ae8065ff744d6b44dfc059a49110942711b643fad454cadb428abe`. Verification passed; debuggable: True.
- Permissions: `android.permission.INTERNET`, `android.permission.READ_EXTERNAL_STORAGE`, `android.permission.MANAGE_EXTERNAL_STORAGE`.

### TeamGDB/Yakumo / yakumo-0.6.0-alpha.4-android-arm64.apk

- Asset: [yakumo-0.6.0-alpha.4-android-arm64.apk](https://github.com/TeamGDB/Yakumo/releases/download/v0.6.0-alpha.4/yakumo-0.6.0-alpha.4-android-arm64.apk)
- APK SHA-256: `75be7bcba3a406266df2984885a5c7fc1fc143a25c2ccd1ccbb318f4933de2e7`
- Manifest: `package: name='io.github.teamgdb.yakumo' versionCode='291' versionName='0.6.0-alpha.4' platformBuildVersionName='15' platformBuildVersionCode='35' compileSdkVersion='35' compileSdkVersionCodename='15'`
- SDK: minSdkVersion:'29'; targetSdkVersion:'35'. ABI: native-code: 'arm64-v8a'.
- Signer: CN=Yakumo test build; SHA-256: `1ca2f27cfbcd9ea7d875a8ca002f57866037b19f43aaf449ce87739aee868570`. Verification passed; debuggable: False.
- Permissions: `android.permission.INTERNET`, `android.permission.ACCESS_NETWORK_STATE`, `android.permission.ACCESS_WIFI_STATE`, `android.permission.CHANGE_WIFI_MULTICAST_STATE`.

### TwilitRealm/dusklight / Dusklight-v2.0.2-android-arm64.apk

- Asset: [Dusklight-v2.0.2-android-arm64.apk](https://github.com/TwilitRealm/dusklight/releases/download/v2.0.2/Dusklight-v2.0.2-android-arm64.apk)
- APK SHA-256: `cef2144fdc344fb189a7ef363f3d8fa2246015504dbf7caea2ea05011fe881c1`
- Manifest: `package: name='dev.twilitrealm.dusk' versionCode='20002000' versionName='2.0.2' platformBuildVersionName='17' platformBuildVersionCode='37' compileSdkVersion='37' compileSdkVersionCodename='17'`
- SDK: minSdkVersion:'28'; targetSdkVersion:'36'. ABI: native-code: 'arm64-v8a'.
- Signer: CN=Dusk, OU=Release, O=Twilit Realm, L=Unknown, ST=Unknown, C=US; SHA-256: `aa162c0df5ae18b0e72e2b16e29768bd28eaf60ef8bb09d0d486df7dd2b99702`. Verification passed; debuggable: False.
- Permissions: `android.permission.VIBRATE`, `android.permission.INTERNET`, `android.permission.MANAGE_EXTERNAL_STORAGE`.

### alondero/aerogauge-recomp / aerogauge-recomp-android-arm64.apk

- Asset: [aerogauge-recomp-android-arm64.apk](https://github.com/alondero/aerogauge-recomp/releases/download/v0.5.0/aerogauge-recomp-android-arm64.apk)
- APK SHA-256: `b5f45d9c5c18ac96b14d73b58d88c7706255a60eecaa8fa8552d66a7dfcf19d8`
- Manifest: `package: name='io.github.alondero.aerogaugerecomp' versionCode='5000' versionName='0.5.0' platformBuildVersionName='15' platformBuildVersionCode='35' compileSdkVersion='35' compileSdkVersionCodename='15'`
- SDK: minSdkVersion:'28'; targetSdkVersion:'35'. ABI: native-code: 'arm64-v8a'.
- Signer: CN=AeroGauge Recompiled; SHA-256: `246877d1f65a3aea672ea35fc0fc4b9e5bcdc00fb6a8c165c54a2d078ff33128`. Verification passed; debuggable: False.
- Permissions: `android.permission.VIBRATE`, `android.permission.BLUETOOTH`, `android.permission.BLUETOOTH_CONNECT`, `android.permission.BLUETOOTH_SCAN`.

### alondero/automobililamborghini-recomp / lamborghini-recomp-android-arm64.apk

- Asset: [lamborghini-recomp-android-arm64.apk](https://github.com/alondero/automobililamborghini-recomp/releases/download/v0.7.2/lamborghini-recomp-android-arm64.apk)
- APK SHA-256: `4629e8373678a5e6f807415e80b4baf52ab89d4091dba12f861cf6c5da2f1b06`
- Manifest: `package: name='io.github.alondero.lamborghinirecomp' versionCode='5000' versionName='0.5.0' platformBuildVersionName='15' platformBuildVersionCode='35' compileSdkVersion='35' compileSdkVersionCodename='15'`
- SDK: minSdkVersion:'26'; targetSdkVersion:'35'. ABI: native-code: 'arm64-v8a'.
- Signer: CN=Lamborghini Recompiled; SHA-256: `c94eef8e19d4e4ed9004221db3fc59de4e8ccba8e0ecd091a4105e4a7e67f23c`. Verification passed; debuggable: False.
- Permissions: `android.permission.VIBRATE`.

### birabittoh/EternalSonataReprise / eternalsonata-v1.2.4-android-arm64.apk

- Asset: [eternalsonata-v1.2.4-android-arm64.apk](https://github.com/birabittoh/EternalSonataReprise/releases/download/v1.2.4/eternalsonata-v1.2.4-android-arm64.apk)
- APK SHA-256: `e316fd3c954c9b685f8ddaa9c9d29afb33f728bf2205415ef0806588c0ee7f3d`
- Manifest: `package: name='com.birabittoh.eternalsonata' versionCode='1002004' versionName='1.2.4' platformBuildVersionName='15' platformBuildVersionCode='35' compileSdkVersion='35' compileSdkVersionCodename='15'`
- SDK: minSdkVersion:'28'; targetSdkVersion:'35'. ABI: native-code: 'arm64-v8a'.
- Signer: CN=Eternal Sonata Reprise Sideload, OU=EternalSonataReprise, O=birabittoh, C=IT; SHA-256: `9f89ebf7c45d832f049db0883aabe691db7f84e63e98d461d65d072498e0ff29`. Verification passed; debuggable: False.
- Permissions: `android.permission.INTERNET`, `android.permission.REQUEST_INSTALL_PACKAGES`, `android.permission.READ_EXTERNAL_STORAGE`, `com.birabittoh.eternalsonata.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`.

### bryanthaboi/pokemon-gen1-recomp-project / gen1recomp-0.3.20-android.apk

- Asset: [gen1recomp-0.3.20-android.apk](https://github.com/bryanthaboi/gen1recomp/releases/download/v0.3.20/gen1recomp-0.3.20-android.apk)
- APK SHA-256: `47911b0f361c776b526cdf07e4cc575be98d0ae0be1b45d697578d1039d3d7ce`
- Manifest: `package: name='com.theboisclub.pokemonred' versionCode='3020' versionName='0.3.20' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'`
- SDK: minSdkVersion:'19'; targetSdkVersion:'36'. ABI: native-code: 'arm64-v8a' 'armeabi-v7a'.
- Signer: C=US, O=Android, CN=Android Debug; SHA-256: `533ca935ab53dd87a1575dc53e744fdda8c8b68ede803d97d764ee4f3f01fa27`. Verification passed; debuggable: False.
- Permissions: `android.permission.VIBRATE`, `android.permission.BLUETOOTH`, `android.permission.INTERNET`, `android.permission.REQUEST_INSTALL_PACKAGES`, `android.permission.ACTIVITY_RECOGNITION`, `com.theboisclub.pokemonred.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`.

### bvschaik/julius / julius-1.8.0-android.apk

- Asset: [julius-1.8.0-android.apk](https://github.com/bvschaik/julius/releases/download/v1.8.0/julius-1.8.0-android.apk)
- APK SHA-256: `f5a0226e458da9f75efa4f704c0e654ed3ea764c468079b90c39cdf5d4856adb`
- Manifest: `package: name='com.github.bvschaik.julius' versionCode='10800000' versionName='1.8.0' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'`
- SDK: minSdkVersion:'21'; targetSdkVersion:'36'. ABI: native-code: 'arm64-v8a' 'armeabi-v7a' 'x86' 'x86_64'.
- Signer: CN=Julius Team, OU=Bvschaik, O=Github, L=Rome, ST=Latium, C=NL; SHA-256: `a8b8e44c70e47f1e8e1d2fcaf7a263a0d9c5ef3baa2d8869bdac1f22444cc24b`. Verification passed; debuggable: False.
- Permissions: `com.github.bvschaik.julius.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`.

### chrissotraidis/kartpad / KartPad-v0.5.2-arm64.apk

- Asset: [KartPad-v0.5.2-arm64.apk](https://github.com/chrissotraidis/kartpad/releases/download/v0.5.2/KartPad-v0.5.2-arm64.apk)
- APK SHA-256: `31b0cc95b4fda088920313e148babec486d38a198e042bf05f029fdaad2ba925`
- Manifest: `package: name='dev.kartpad.android' versionCode='230' versionName='0.5.2' platformBuildVersionName='16' platformBuildVersionCode='36' compileSdkVersion='36' compileSdkVersionCodename='16'`
- SDK: minSdkVersion:'28'; targetSdkVersion:'36'. ABI: native-code: 'arm64-v8a'.
- Signer: CN=KartPad Community Release; SHA-256: `c1dbe0a0d72d830a5779476b346a750d0a37515adef992cad2f3863058f7f2f2`. Verification passed; debuggable: False.
- Permissions: `android.permission.INTERNET`, `android.permission.ACCESS_NETWORK_STATE`, `android.permission.FOREGROUND_SERVICE`, `android.permission.FOREGROUND_SERVICE_DATA_SYNC`, `android.permission.POST_NOTIFICATIONS`, `android.permission.WAKE_LOCK`, `android.permission.RECEIVE_BOOT_COMPLETED`, `dev.kartpad.android.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`.

### doukutsu-rs/doukutsu-rs / doukutsu-rs_android_1.0.0.universal.apk

- Asset: [doukutsu-rs_android_1.0.0.universal.apk](https://github.com/doukutsu-rs/doukutsu-rs/releases/download/1.0.0/doukutsu-rs_android_1.0.0.universal.apk)
- APK SHA-256: `fae4e1629c81a911a01677d2979ed53e03b86cad18b08b0ce4d7287f9affe275`
- Manifest: `package: name='io.github.doukutsu_rs' versionCode='3' versionName='1.0.0' platformBuildVersionName='15' platformBuildVersionCode='35' compileSdkVersion='35' compileSdkVersionCodename='15'`
- SDK: minSdkVersion:'24'; targetSdkVersion:'35'. ABI: native-code: 'arm64-v8a' 'armeabi-v7a' 'x86' 'x86_64'.
- Signer: CN=doukutsu-rs; SHA-256: `bc7859f61854dd990d11e98b0a6f41b1ebd6f0aaa29bb5df7ee62da0b8a0923e`. Verification passed; debuggable: False.
- Permissions: `android.permission.INTERNET`, `android.permission.ACCESS_NETWORK_STATE`, `io.github.doukutsu_rs.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`.

### isledecomp/isle-portable / app-debug.apk

- Asset: [app-debug.apk](https://github.com/isledecomp/isle-portable/releases/download/continuous/app-debug.apk)
- APK SHA-256: `df4d3daa1498bf965eccb756f1a28fc3cd23a33083e655f1ca1be62f5ee02cca`
- Manifest: `package: name='org.legoisland.isle' versionCode='1' versionName='1.0' platformBuildVersionName='15' platformBuildVersionCode='35' compileSdkVersion='35' compileSdkVersionCodename='15'`
- SDK: minSdkVersion:'21'; targetSdkVersion:'35'. ABI: native-code: 'arm64-v8a' 'armeabi-v7a' 'x86' 'x86_64'.
- Signer: C=US, O=Android, CN=Android Debug; SHA-256: `b837fb67163cebd05de2635823b974b2e689d695e20a4fa624f5a99d42dc9b39`. Verification passed; debuggable: True.
- Permissions: `android.permission.VIBRATE`.

### isledecomp/isle-portable / app-release.apk

- Asset: [app-release.apk](https://github.com/isledecomp/isle-portable/releases/download/continuous/app-release.apk)
- APK SHA-256: `7f81a9d9e936b0c0d4eb965822ab68dac9e5e579bd813b6e19c2b311b4889502`
- Manifest: `package: name='org.legoisland.isle' versionCode='1' versionName='1.0' platformBuildVersionName='15' platformBuildVersionCode='35' compileSdkVersion='35' compileSdkVersionCodename='15'`
- SDK: minSdkVersion:'21'; targetSdkVersion:'35'. ABI: native-code: 'arm64-v8a' 'armeabi-v7a' 'x86' 'x86_64'.
- Signer: CN=LEGO Island Portable, O=isledecomp, L=Unknown, ST=Unknown, C=US; SHA-256: `b9f45609a2d397c3f04b997c3057dd72094fd2e8fae8ab58f0c71d36ad6bf7f5`. Verification passed; debuggable: False.
- Permissions: `android.permission.VIBRATE`.

### kandowontu/starfox-enhanced / StarFoxEnhanced-0.0.8-android-arm64.apk

- Asset: [StarFoxEnhanced-0.0.8-android-arm64.apk](https://github.com/kandowontu/starfox-enhanced/releases/download/v0.0.8/StarFoxEnhanced-0.0.8-android-arm64.apk)
- APK SHA-256: `e2889ada210a9dd3d4c5d51e295be4119a5dd0a992f7b91d8718506ea7908fd8`
- Manifest: `package: name='com.starfox.enhanced' versionCode='13' versionName='0.0.8' platformBuildVersionName='15' platformBuildVersionCode='35' compileSdkVersion='35' compileSdkVersionCodename='15'`
- SDK: minSdkVersion:'26'; targetSdkVersion:'35'. ABI: native-code: 'arm64-v8a'.
- Signer: CN=Star Fox Enhanced; SHA-256: `50bcb41f7a02c2e9bb0f68a74b1f6e14f7317fedc69d2c6fd70a165f87800fc0`. Verification passed; debuggable: True.
- Permissions: `android.permission.VIBRATE`.

### mstan/EmeraldRecomp / EmeraldRecomp-android-arm64-v0.0.7.apk

- Asset: [EmeraldRecomp-android-arm64-v0.0.7.apk](https://github.com/mstan/EmeraldRecomp/releases/download/v0.0.7/EmeraldRecomp-android-arm64-v0.0.7.apk)
- APK SHA-256: `12b87b5824edc2b9de3c7445ad8db05476169ed2149fcf85f84417e23e659702`
- Manifest: `package: name='com.mstan.emeraldrecomp' versionCode='7' versionName='0.0.7' platformBuildVersionName='15' platformBuildVersionCode='35' compileSdkVersion='35' compileSdkVersionCodename='15'`
- SDK: minSdkVersion:'28'; targetSdkVersion:'35'. ABI: native-code: 'arm64-v8a'.
- Signer: CN=EmeraldRecomp, OU=gbarecomp, O=mstan; SHA-256: `60ebc7960ab60fe14c7d319f7623aefa801b9cec8b75466ff03468e2bdb9fa41`. Verification passed; debuggable: False.
- Permissions: `android.permission.VIBRATE`.

### sergiomanzur/regaiden-recomp / Resident_Evil_Gaiden_Recomp_v0.4.1_Android.apk

- Asset: [Resident_Evil_Gaiden_Recomp_v0.4.1_Android.apk](https://github.com/sergiomanzur/regaiden-recomp/releases/download/v0.4.1/Resident_Evil_Gaiden_Recomp_v0.4.1_Android.apk)
- APK SHA-256: `d548911a14505b5dad4369d64b6abb4baa833a44841101efde572efde2a708d6`
- Manifest: `package: name='com.capcom.regaiden' versionCode='5' versionName='0.4.1' platformBuildVersionName='14' platformBuildVersionCode='34' compileSdkVersion='34' compileSdkVersionCodename='14'`
- SDK: minSdkVersion:'24'; targetSdkVersion:'34'. ABI: native-code: 'arm64-v8a'.
- Signer: C=US, O=Android, CN=Android Debug; SHA-256: `4259e5033f3128b6cce50ba4fe9f43d966af9add3ddcc4d2e9fdc5baff390fa0`. Verification passed; debuggable: True.
- Permissions: `android.permission.READ_EXTERNAL_STORAGE`, `android.permission.WRITE_EXTERNAL_STORAGE`, `android.permission.MANAGE_EXTERNAL_STORAGE`, `android.permission.VIBRATE`.

### vcmi/vcmi / VCMI-Android-arm64-v8a.apk

- Asset: [VCMI-Android-arm64-v8a.apk](https://github.com/vcmi/vcmi/releases/download/1.7.5/VCMI-Android-arm64-v8a.apk)
- APK SHA-256: `81738076e58c18b050d9b5f46b3dc1455e40afc112292ee439681572f633cbec`
- Manifest: `package: name='is.xyz.vcmi' versionCode='1770' versionName='1.7.5' platformBuildVersionName='15' platformBuildVersionCode='35' compileSdkVersion='35' compileSdkVersionCodename='15'`
- SDK: minSdkVersion:'21'; targetSdkVersion:'35'. ABI: native-code: 'arm64-v8a'.
- Signer: CN=Unknown, OU=Unknown, O=Unknown, L=Unknown, ST=Unknown, C=Unknown; SHA-256: `26207925962ccd73f53be4c4999cf253328531419f2586ae25104a3189867044`. Verification passed; debuggable: False.
- Permissions: `android.permission.INTERNET`, `android.permission.VIBRATE`, `android.permission.ACCESS_NETWORK_STATE`, `is.xyz.vcmi.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`.

### vcmi/vcmi / VCMI-Android-armeabi-v7a.apk

- Asset: [VCMI-Android-armeabi-v7a.apk](https://github.com/vcmi/vcmi/releases/download/1.7.5/VCMI-Android-armeabi-v7a.apk)
- APK SHA-256: `7ccec9f182fa23f86cf12942dec32dfbaacfbf749a039d635ac24cd0b392cf6f`
- Manifest: `package: name='is.xyz.vcmi' versionCode='1769' versionName='1.7.5' platformBuildVersionName='15' platformBuildVersionCode='35' compileSdkVersion='35' compileSdkVersionCodename='15'`
- SDK: minSdkVersion:'21'; targetSdkVersion:'35'. ABI: native-code: 'armeabi-v7a'.
- Signer: CN=Unknown, OU=Unknown, O=Unknown, L=Unknown, ST=Unknown, C=Unknown; SHA-256: `26207925962ccd73f53be4c4999cf253328531419f2586ae25104a3189867044`. Verification passed; debuggable: False.
- Permissions: `android.permission.INTERNET`, `android.permission.VIBRATE`, `android.permission.ACCESS_NETWORK_STATE`, `is.xyz.vcmi.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`.

### vcmi/vcmi / VCMI-Android-x86_64.apk

- Asset: [VCMI-Android-x86_64.apk](https://github.com/vcmi/vcmi/releases/download/1.7.5/VCMI-Android-x86_64.apk)
- APK SHA-256: `f789e99dd9c1ada463583302753c18935dfab0a070e357985c14eef3920537cb`
- Manifest: `package: name='is.xyz.vcmi' versionCode='1771' versionName='1.7.5' platformBuildVersionName='15' platformBuildVersionCode='35' compileSdkVersion='35' compileSdkVersionCodename='15'`
- SDK: minSdkVersion:'21'; targetSdkVersion:'35'. ABI: native-code: 'x86_64'.
- Signer: CN=Unknown, OU=Unknown, O=Unknown, L=Unknown, ST=Unknown, C=Unknown; SHA-256: `26207925962ccd73f53be4c4999cf253328531419f2586ae25104a3189867044`. Verification passed; debuggable: False.
- Permissions: `android.permission.INTERNET`, `android.permission.VIBRATE`, `android.permission.ACCESS_NETWORK_STATE`, `is.xyz.vcmi.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`.

## Captured discovery fingerprints

| Input | SHA-256 |
| --- | --- |
| index.json (captured JSON, indented normalization) | `3f19c636c6f3caf490baee6fcb4e4cdbe4bc5ed414eb49afc71c1ec06f922075` |
| Nintendo.json (captured JSON, indented normalization) | `21571cdabca603f1cf830bc3ab6207fce9a2ffde150b9ffcea045653917b19ec` |
| PlayStation.json (captured JSON, indented normalization) | `dee76a70ce913de11e98073bb8097512a736cf166d28c952d6ac56245d2711b0` |
| Xbox.json (captured JSON, indented normalization) | `b715f60957b6bc7739cafb88dd3c3611e708c86a95a3387074dc645df310f346` |
| OtherPlatforms.json (captured JSON, indented normalization) | `bf828a991e1619bdfb396aeb9cdeec62e16dbbf6536a856fe32f7a1c41f5172a` |

## Implementation checks

- Live `generate_quiver` invocation, the generator used by `pack generate-source quiver`: success with the reviewed policy; 24 resolved APK projects, 199 no-Android outcomes, six unsupported rows, no unresolved failures, no stale accepted-entry retentions. All candidate identities matched the independently inspected APKs before acceptance, and all 24 generated release IDs matched the reviewed release records.
- `pack build`: success against live RJNY/BBoi and committed codm/Quiver catalogs. Produced 110 single-screen and 134 dual-screen entries. Build performs no Quiver discovery or APK requests; adapter and ordinary-build tests enforce that boundary.
- `pack verify`: success, offline structural validation of both rendered exports.
- Focused Quiver discovery/generation/ingestion tests: 79 passed with the accepted catalog.
- Formatting, Ruff lint, Ty, locked dependency check, offline documentation links, Nix formatting and native-platform flake evaluation passed.
- Publisher/workflow regressions: 136 passed; Python 3.12 compatibility: 126 passed using the pinned Nix pytest runner without the project environment. The usual uv ephemeral environment did not expose pytest, so the equivalent pinned interpreter/pytest environment was used.
- `actionlint` and `zizmor --persona pedantic .github/workflows`: passed. Local disposable Git remotes exercised publication; no real proposal or remote write occurred.
- Initial full-suite run: 955 passed and one old exact-family-roster assertion failed after valid Quiver additions. The assertion was revised to account for every surviving candidate and preserve recorded family relationships without freezing source membership. Focused admission/reconciliation tests then passed (8 tests).
- Full integration suite after the roster correction: 956 passed. Per-group evidencing reviews passed for discovery, generation, ingestion, initial admission and automation. Final whole-diff reviews, completion audit and post-audit full-suite result are recorded below when complete.

## Export comparison

A live build without Quiver produced 96 single-screen and 121 dual-screen entries. Every existing main entry and setting was identical; current RJNY added SleepManager (`com.med.sleepmanager`, [source](https://github.com/Baggio94/SleepManager)) to both. This unrelated addition is ordinary upstream refresh, not Quiver discovery.

The final build adds 14 Quiver baseline apps to single and 13 to dual. Emerald appears as the new single baseline while the existing Goldoire dual build remains. Both variants also replace the two outdated BBoi IDs for KartPad and Silent Hill with their inspected manifest IDs. Comparing complete entry objects showed those two corrections change only `id`; every other existing entry and setting is unchanged. No other app was removed.

The new baseline apps are AeroGauge, Automobili Lamborghini, Eternal Sonata Reprise, Resident Evil Gaiden, Augustus, Star Fox Enhanced, Melee PC, doukutsu-rs, Yakumo, OpenRCT2, Sonic 3 A.I.R., LEGO Island Portable and Open Nectar in both variants, plus EmeraldRecomp in single. KartPad and Silent Hill were already present through BBoi and therefore are source overlaps rather than new user-visible apps.

A separate captured-source comparison isolates code changes from live upstream drift. Before initial admission, all 91 single and 116 dual captured entries remained identical. Current configuration tests compare composition with and without Quiver dynamically, preserve higher-ranked selections and settings, and cover the reviewed ID corrections using representative live BBoi selectors absent from the older capture. Catalog membership is not frozen by a second roster assertion.

## Whole-change implementation review

Four independent review lenses covered correctness, automation/concurrency,
idiomatic implementation, and test proportionality. The fix round addressed
malformed optional metadata URLs aborting discovery, overlap assertions that
blocked otherwise valid Quiver catalog removals, and a skip/rename test whose
setup did not exercise generation. The replacement scenario generates and
loads the renamed candidate, then proves the global denial removes it from
both variants. Retention prose was narrowed to the actual URL matching rule.

After these fixes, 89 focused Quiver tests and the full suite passed: **961 tests,
94% coverage**. Formatting, lint, typing and whitespace checks also passed.
The optional transport-interface cleanup is deferred: the production HTTP client
enforces confinement before redirects; any future custom adapter must preserve
that behavior rather than relying only on post-response URL validation.

The independent scoped fix review approved the fixes with no unresolved blocking
finding. The fresh completion audit confirmed all 17 previously checked tasks
with commit and test or process evidence, performed the final audit task, and
found no unevidenced item. All 18 implementation tasks are complete.

After the audit, the full suite passed again: **961 tests in 29.90 seconds,
94% coverage**. Offline `pack verify` and whitespace checks passed again. The
50 changed paths contain no scratch evidence, APK binaries, credentials or
device artifacts. The change remains active on `add-quiver-source`; separate
OpenSpec verification and archive were not invoked.
