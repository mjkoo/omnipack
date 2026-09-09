# Curation observations

Release metadata and selected APK manifests were retrieved on 2026-09-09 UTC.
`releases.json` retains resolver inputs from the first eight public releases
per repository, with each release's primary URL. `manifests.json` records
range-retrieved AndroidManifest.xml package, versionName and versionCode for
each selected asset, identified by its primary download URL.
`baseline-apps.json` captures the affected entries from the pre-curation packs.

The configured Symphony, CTR, Shipwright and Ludashi identities disagree with
the manifests: respectively `com.blacklabelhq.sotn`, `com.ctrnative`,
`com.dishii.soh` and `com.winlator.vanilla`. These remain unresolved.
Ludashi's unchanged APK filter selects `bionic-vanilla.apk` from `v3.1.h`;
the newer `v4.0` release uses different names and is skipped.

XenDroid advanced from `XenDroid-0b11201` to `XenDroid-c4f6863` during
observation. Both manifests preserve the expected package and corresponding
hash versionName. This supports the unchanged source-tracking policy.

The Cinderbox regression deliberately moves an observed dependency prerelease
into the future and gives it an APK candidate, so exclusion is tested even
when date ordering and asset availability would otherwise select it.
The release-history test clears prerelease status when isolating historical
version extraction; the preservation test uses the original selection settings.
