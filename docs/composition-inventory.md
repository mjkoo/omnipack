# Device-aware composition inventory

This inventory records the migration baseline captured from commit
`9a33d26fd0b5eb22ad0f2a0ba52ee59ac9eac565`. It is evidence for maintained
composition rules, not a claim about signature compatibility, installed data,
or successful device migration. The exact 88-entry single-screen and 111-entry
dual-screen imports, along with representative candidate origins, are retained
under [`tests/fixtures/composition-baseline`](../tests/fixtures/composition-baseline/README.md).

## Standard and dual build decisions

| App | Standard candidate | Dual candidate | Family decision | Policy consequence |
| --- | --- | --- | --- | --- |
| Cemu | [`SSimco/Cemu`](https://github.com/SSimco/Cemu), `info.cemu.cemu` | [`sapphirerhodonite/cemu`](https://github.com/sapphirerhodonite/cemu), `info.cemu.cemu` | One Cemu family. The repositories are target-specific alternatives. | Keep the standard repository for single and prefer the dual repository for dual. No package correction is needed; both inspected manifests declare `info.cemu.cemu`. |
| Banjo-Kazooie Recomp | BBoi standard asset, `com.aure.banjorecomp` | BBoi dual asset, `com.aure.banjorecomp` | One default package family. | Retain both source records. Select the standard record for single and the dual-preferred record for dual. |
| Harvest Moon 64 Recomp | BBoi standard asset, `com.igawa6.harvestmoon64` | BBoi dual asset, `com.igawa6.harvestmoon64` | One default package family. | Retain both source records. Select the standard record for single and the dual-preferred record for dual. |
| Zelda: A Link to the Past | BBoi standard asset, `com.samyost1.zelda3android` | BBoi dual asset, `com.samyost1.zelda3android` | One default package family. | Retain both records even though their original id and URL are equal. Origin distinguishes the assets; the dual record remains dual-preferred. |
| Zelda: The Minish Cap | BBoi standard asset, `com.samyost1.tmcandroid` | BBoi dual asset, `com.samyost1.tmcandroid` | One default package family. | Retain both source records. Select the standard record for single and the dual-preferred record for dual. |
| Crash Team Racing | [`Simon358/ctr-native-android`](https://github.com/Simon358/ctr-native-android), configured as `com.simon358.ctrnative` | [`igawa6/ctr-native-android`](https://github.com/igawa6/ctr-native-android), rendered as `com.ctrnative`, plus the Simon candidate | Unresolved. Repository names and a shared manifest package do not establish whether these forks are one logical app family. | Do not group or exclude either candidate without a maintainer decision. Correcting the Simon identity creates an output package collision in dual, so the initial policy must also make an explicit selection or exclusion decision. |

The Winlator repositories remain separate families: `brunodev85/winlator`,
`coffincolors/winlator`, and `StevenMXZ/Winlator-Ludashi` are unrelated
maintained forks for composition purposes. A common upstream does not justify
grouping them. The same rule applies to other forks unless a row above or a
future evidence update explicitly associates them.

## Manifest evidence and correction scope

The primary APK observations are stored in
[`tests/fixtures/curation/manifests.json`](../tests/fixtures/curation/manifests.json)
and summarized in [maintained app version policies](curation.md#manifest-evidence).
Only a correction necessary to implement an evidenced family decision belongs
in the initial composition policy. Other mismatches remain observations; this
change does not turn them into identity migrations.

| Repository | Original configured id | Effective manifest id | Evidence | Migration status |
| --- | --- | --- | --- | --- |
| `sergiomanzur/SymphonyRecomp` | `com.sergiomanzur.sotnrecomp` | `com.blacklabelhq.sotn` | Primary `android-v0.10.1b` APK | Outstanding observation. Preserve the configured identity; no selected-family decision currently requires a correction. |
| `Simon358/ctr-native-android` | `com.simon358.ctrnative` | `com.ctrnative` | Primary `Android-Build4` APK | A correction is necessary if this candidate participates in the CTR selection decision. The resulting collision with the igawa6 dual entry requires the unresolved family/selection decision above. |
| `Waterdish/Shipwright-Android` | `com.waterdish.shipwright` | `com.dishii.soh` | Primary `v9.0.2P2` APK | Outstanding observation. Preserve the configured identity; no selected-family decision currently requires a correction. |
| `StevenMXZ/Winlator-Ludashi` | `com.winlator.ludashi` | `com.winlator.vanilla` | Primary `v3.1.h` `bionic-vanilla.apk` | Outstanding observation. Preserve the configured identity, selected release, APK filter, and source-version policy. Identity and flavor migration are deferred. |

## Preserved Ludashi selection

Ludashi stays on the `v3.1.h` release and `bionic-vanilla.apk`. Its APK filter
remains `bionic-vanilla`, `versionDetection` remains false, and source release
tracking remains enabled. Release v4.0 has renamed assets and states that it
does not install as an update over the previous build. Selecting it needs a
separate flavor, identity, and device-migration decision.

## Open acceptance issues

- Decide whether the Simon and igawa6 CTR repositories are one family or
  independent families, then encode the corresponding pin or exclusion needed
  to avoid the evidenced `com.ctrnative` collision.
- Validate import, re-import, installation, signatures, and app-data migration
  on an Android device. Manifest inspection alone cannot settle those points.
- Revisit the three non-CTR identity mismatches only if a future selected-family
  decision or device evidence makes a correction necessary.
