## Context

The approved investigation establishes APK package identities and source reputation.
The previous change remains open solely for operational acceptance; this is a
separate curation change. The clean baseline is 958 passing tests on main.

This change depends on `curate-ports-and-track-pack`. Its effective specification
baseline is the main specs with that predecessor's deltas applied, including native
public GitLab resolution against bounded Obtainium v1.6.15 behavior alongside the
existing GitHub/HTML v1.6.14 baseline. GitHub ZIP selection extends that combined
boundary while preserving the predecessor's GitLab scope and guarantees.

## Goals / Non-Goals

Goals: durable corrections across upstream refreshes, reviewed source choices,
truthful verification boundaries, and a concrete installed-device change list.
Non-goals: automatic device changes, save/controller migration, publication,
reproducible-build gates, continuous security monitoring, and auditing all apps.

## Decisions

Use existing composition packageId corrections, matching original source/origin/id/URL,
so upstream snapshots remain authentic and corrections survive refreshes. Apply each
relevant standard/dual candidate; retain previous identities in history, update
post-selection overlay IDs, and test collision behavior through real composition.
Use extras for official Ghostship and canonical Gen1Recomp, with family pins for both
targets so future upstream duplicates cannot replace the maintained source.
Gen1Recomp retains the existing reviewed settings, changing its URL to the same
repository's canonical name. Retain all other source settings unless stated below.

Retained identities:

| Project | Original catalog ID | Required APK ID |
|---|---|---|
| https://github.com/sergiomanzur/SymphonyRecomp | `com.sergiomanzur.sotnrecomp` | `com.blacklabelhq.sotn` |
| https://github.com/Carlox33/The-Simpsons-Hit-and-Run-Android | `com.carlox33.hitandrun` | `com.c4rlox.simpsons` |
| https://github.com/Waterdish/Shipwright-Android | `com.waterdish.shipwright` | `com.dishii.soh` |
| https://github.com/samyost1/zelda3-android | `com.samyost1.zelda3android` | `com.dishii.zelda3` |
| https://github.com/izzy2lost/SpaghettiKart | `com.izzy2lost.spaghettikart` | `com.izzy.kart` |
| https://github.com/izzy2lost/perfect_dark | `com.izzy2lost.perfectdark` | `com.perfectdark.port` |
| https://buildbot.libretro.com/stable | `487343354` | `com.retroarch.aarch64` |
| https://github.com/izzy2lost/Starship | `com.izzy2lost.starship` | `com.starship.android` |
| https://github.com/bryanthaboi/pokemon-gen1-recomp-project | `com.bryanthaboi.pokemonredblue` | `com.theboisclub.pokemonred` |
| https://github.com/linkzenic/2ship2harkinian-Android | `org.linkzenic.twoship` | `com.twoshipfork.mm` |
| https://github.com/samyost1/tmc-android | `com.samyost1.tmcandroid` | `dev.picori.tmc` |
| https://github.com/igawa6/dusklight | `com.igawa6.dusklight` | `dev.twilitrealm.dusk` |
| https://github.com/igawa6/HarvestMoon64Recomp | `com.igawa6.harvestmoon64` | `io.github.hm64recomp` |
| https://github.com/Matteo842/CrashBandicoot-Launcher | `com.matteo842.crashbandicoot` | `io.github.matteo842.crashlauncher.runtime` |
| https://github.com/Josh-Daniels/OpenMW-DS | `com.joshdaniels.openmwds` | `org.openmw.ds` |
| https://github.com/simon358/ctr-native-android (single-screen) | `com.simon358.ctrnative` | `com.ctrnative` |
| https://github.com/igawa6/ctr-native-android (dual-screen) | `com.ctrnative` (unchanged) | `com.ctrnative` |

Exclude all candidates for the Super Metroid family in both targets. Do not add
MetroidArch. Map old and new Ghostship to app:ghostship; deny the legacy effective
package com.ghostship.android and select HarbourMasters/Ghostship with package
 dev.net64.ghostship in both targets. The existing source's old ID also stays in
history. Use includeZips=true, apkFilterRegEx matching only the Android ZIP,
zippedApkFilterRegEx matching Ghostship.apk, stable releases, no architecture
filter on the archive name, and source-version tracking because APK versionCode
and release tagging may differ.

Preserve https://github.com/simon358/ctr-native-android for single-screen and
https://github.com/igawa6/ctr-native-android for dual-screen, both with effective
package `com.ctrnative`. Scope the Simon correction from `com.simon358.ctrnative`
to its repository; igawa6 already has catalog ID `com.ctrnative` and needs no ID
mapping. Preserve both original catalog IDs in provenance. During implementation,
verify each repository's selected APK manifest independently and retain dated
identity evidence for both before accepting the reconciled outputs. Apply the
existing `com.ctrnative` source-version policy with `versionDetection: false` to
both choices and verify the rendered settings for each variant after repeated
catalog refreshes. Describe the signer mismatch as requiring fresh installation,
not a source error; a planning edit is not manifest or device verification.

GitHub ZIP support is metadata selection only: include .zip alongside .apk when
includeZips=true and apply the existing outer filename regex. Validate the inner
APK regex before HTTP and classify it as on-device extraction behavior. Do not
claim inspection of archive members during normal live metadata verification.
HTML/GitLab archive settings remain unsupported. Preserve existing fallback,
release-date, and track-only semantics; artifact probes check the outer download.
Record the inspected official Ghostship ZIP, member, package and SHA-256 as dated
fixture evidence, not as a runtime hash pin or an allowlist that forbids future
releases. Malformed regexes fail before HTTP. No archive decompression is added.

Reputation plus basic provenance/manifest/signature checks is the accepted curation
standard. Keep OpenMW-DS and the explicitly unofficial Symphony beta; absence of
independent builds or debug-named certificates alone does not exclude them. Keep
known technical limitations visible without calling them malware findings.

## Risks / Trade-offs

- Existing tracking IDs may remain after an ordinary re-import. Document fresh
  Obtainium tracking import for the current test; do not promise automatic cleanup.
- ZIP contents are not checked by metadata verification. Dated manual member
  inspection and on-device acceptance are separate evidence.
- Fork signatures can differ despite package equality. The user accepts fresh
  installs and has waived save preservation; uninstall still requires a later action.
- Canonical URL and package corrections change selectors. Test full builds and
  retain history, rather than editing generated outputs alone.

## Migration Plan

Regenerate single/dual outputs and README locally, run offline and fresh live
verification, and produce a local comparison against the captured installed-only
export and package list. Distinguish metadata-only changes, updates, fork/package
switches, and removals. Leave branch in place without push or device operations.
Rollback is restoring the preceding configuration and generated pair; no device
state is changed by this work.
