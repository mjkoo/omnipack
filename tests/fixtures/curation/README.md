# Curation observations

Release metadata and selected APK manifests were retrieved on 2026-09-09 UTC.
`releases.json` retains resolver inputs from the first eight public releases
per repository, with each release's primary URL. `manifests.json` records
range-retrieved AndroidManifest.xml package, versionName and versionCode for
each selected asset, identified by its primary download URL.
`baseline-apps.json` captures the affected entries from the pre-curation packs.
`ctr.json` records two independent 2026-09-10 CTR release and APK observations.
Each variant retains its repository, original and effective identity, full source
tag, selected asset metadata, decoded manifest values, byte size and SHA-256.
The APK identities were decoded from separately downloaded binaries, and each
download byte-matched its corresponding prior capture. The hashes identify dated
evidence and are not runtime pins or reproducible-build requirements.

The historical configured Symphony, Simon CTR, Shipwright and Ludashi identities
disagree with the manifests: respectively `com.blacklabelhq.sotn`,
`com.ctrnative`, `com.dishii.soh` and `com.winlator.vanilla`. The reconciliation
fixtures cover the maintained identity corrections; Ludashi remains outside that
scope.
Ludashi's unchanged APK filter selects `bionic-vanilla.apk` from `v3.1.h`;
the newer `v4.0` release uses different names and is skipped.

XenDroid listed `XenDroid-c4f6863` before `XenDroid-0b11201` during
observation, but its earlier published timestamp means the configured date
sort still selects `XenDroid-0b11201`. Both manifests preserve the expected package and corresponding
hash versionName. This supports the unchanged source-tracking policy.

The Cinderbox regression deliberately moves an observed dependency prerelease
into the future and gives it an APK candidate, so exclusion is tested even
when date ordering and asset availability would otherwise select it.
The release-history test clears prerelease status when isolating historical
version extraction; the preservation test uses the original selection settings.


## Android store and ports

`port-releases.json` retains the complete asset inventories and resolver-used
release fields from official metadata retrieved on 2026-09-10. Each entry
records its primary API URL and the SHA-256 of the original full response.
Aurora retains its original description with ordinary, hw and preload upload
links and empty asset links. GitHub inventories include non-Android files and
architecture-specific alternatives, preserving the exclusions under test.

`port-manifests.json` records package ids, versionName, versionCode and native
ABIs decoded from the downloaded official APKs, with SHA-256 identifying those
exact bytes. Match its source URL, release and asset name to the retained
inventory to recover the primary download URL. Aurora's inspected ordinary APK
was fetched from
<https://gitlab.com/api/v4/projects/6922885/uploads/245eec8867a47057cbc54535f73b32ee/AuroraStore-4.8.4.apk>;
the resolver uses the equivalent numeric-project upload route.
These are manifest observations, not identities inferred from filenames.

The regression resolves maintained extras against these inventories and joins
all selected candidate names to inspected manifests. idTech4A++ selects the
universal APK, excluding `_arm64` and `_armv7`, and preserves source version
`v1.1.0harmattan72` independently from manifest `1.1.0harmattan72lindaiyu`.
VCMI deliberately exports `autoApkFilterByArch: true` and the resolver returns
all three inspected ABI candidates. Selection for a particular device remains
Obtainium's responsibility; no device architecture selection, installation or
gameplay acceptance is claimed here.

Silksong setup wording was checked against the upstream README at commit
[9dc2cf03590a4211b16ba7da3c0eebfc808c9031](https://github.com/jakobkhansen/SilksongAndroid/blob/9dc2cf03590a4211b16ba7da3c0eebfc808c9031/README.md).
It specifies Android 13 only and explicitly excludes Android 15. Its retained
dual-only pack eligibility is a separate curation decision.
