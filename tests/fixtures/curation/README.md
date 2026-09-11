# Curation observations

`baseline-apps.json` captures the affected entries from the pre-curation packs.
The curation regression applies the maintained overlays and identity
corrections to them and checks that only the intended settings change.

`ctr.json` records two independent 2026-09-10 CTR release and APK observations.
Each variant retains its repository, original and effective identity, full source
tag, selected asset metadata, decoded manifest values, byte size and SHA-256.
The APK identities were decoded from separately downloaded binaries, and each
download byte-matched its corresponding prior capture. The hashes identify dated
evidence and are not runtime pins or reproducible-build requirements.

`reconciliation.json` records the bounded identity map and the official
Ghostship ZIP and member observation used by the reconciliation curation tests.

The historical configured Symphony, Simon CTR, Shipwright and Ludashi identities
disagreed with their APK manifests: respectively `com.blacklabelhq.sotn`,
`com.ctrnative`, `com.dishii.soh` and `com.winlator.vanilla`. The reconciliation
fixtures cover the maintained identity corrections. Ludashi instead keeps its
configured identity and allows the ID change. When observed on 2026-09-09, its
unchanged APK filter selected `bionic-vanilla.apk` from `v3.1.h`; the newer
`v4.0` release used different names and was skipped.

## Ports

Silksong setup wording was checked against the upstream README at commit
[9dc2cf03590a4211b16ba7da3c0eebfc808c9031](https://github.com/jakobkhansen/SilksongAndroid/blob/9dc2cf03590a4211b16ba7da3c0eebfc808c9031/README.md).
It specifies Android 13 only and explicitly excludes Android 15. Its retained
dual-only pack eligibility is a separate curation decision.
