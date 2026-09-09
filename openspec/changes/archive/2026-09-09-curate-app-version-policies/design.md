## Context

See proposal.md for motivation. The existing extras, merge-patch overlays and
live verifier support almost all required behavior. The common overlay applies
to both variants, while absent targets in one variant are permitted when the
package exists in the other. No separate dual overlay is needed for the selected
policies: Cemu's same setting change selects each variant's own tag.

A metadata-only live run completed on 2026-09-09 UTC with no errors and 23
version-shape warnings across 12 package ids. Separate release-APK manifest
inspection established the observations below. These are point-in-time evidence,
not guarantees about future upstream releases or installed-device behavior.

Obtainium's pinned [version service](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/providers/source_provider.dart)
accepts single-component numeric formats; its
[installed-version reconciliation](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/providers/apps_provider_lifecycle.dart)
can match a numeric installed version against a substring of a descriptive
source version. Consequently, a lint warning alone does not establish re-import
thrash. Conversely, a release suffix can distinguish builds even when an APK
reuses its numeric versionName.

## Goals / Non-Goals

**Goals:** Use the existing configuration mechanisms, preserve source build
identity where numeric extraction loses information, and keep the lint heuristic
honest about integer versions. Make the chosen policies reproducible in fixtures.

**Non-Goals:** Reimplement Obtainium reconciliation, infer per-device installed
state, normalize every possible upstream version grammar, or repair package
identity through version settings.

## Decisions

### Numeric extraction and tag selection

Use `versionExtractionRegEx: [0-9]+(?:\.[0-9]+)+` and
`matchGroupToUse: 0` for BanjoRecomp and SymphonyRecomp. Their inspected release
histories use Android/beta labels around numeric app versions; the current APKs
contain `0.1.1` and `0.10.1`. The pattern also matches those already-extracted
versions when Obtainium compares recorded values. It fails if no dotted version
exists. Preserve prerelease selection, APK filters and other source settings.
Symphony's four observed release tags produce distinct versions `0.9`, `0.9.1`,
`0.10`, and `0.10.1`. This policy treats its trailing `b` as a beta channel label;
a future stable/beta pair sharing one numeric version requires revisiting it.

Set `releaseTitleAsVersion: false` on `info.cemu.cemu` in the common overlay.
The observed single and dual tags `0.5` and `0.5.2` equal their APK versionNames.
A title regex would add unnecessary dependence on changing prose. Leave RPCSX
unchanged: `v20250425` reconciles with the observed APK version `20250425`.

### Preserve source versions when APK versions are insufficient

Set only `versionDetection: false` for the eight source-tracked ids in the
curation spec. This is Obtainium's standard installed-version detection switch;
it does not disable source polling or installation. Keep raw selected release
versions so future tag changes remain distinguishable. No new date-version
setting, track-only flag or notification exemption is added.

| Configured package id | Source version observed | APK versionName | Reason |
| --- | --- | --- | --- |
| `com.simon358.ctrnative` | `Android-Build4` | `1.0` | Build sequence differs from APK version |
| `com.waterdish.shipwright` | `v9.0.2P2` | `9.0.2` | P1 and P2 must remain different builds |
| `org.citron.citron_emu` | `2026-04-27` | `0237a9b88` | Date tag differs from commit hash |
| `org.vita3k.emulator` | `4093` | `0.2.1` | Frequent build tags differ from app version |
| `xendroid.compose` | `XenDroid-0b11201` | `0b11201` | Commit hashes are not numeric versions |
| `com.winlator.ludashi` | `v3.1.h` | `3.1` | Hotfix marker carries release identity |
| `com.winlator.cmod` | `cmod_v13.1` | `Cmod-v13.1` | Neither label is a strict installed numeric format |
| `xyz.blacksheep.mjolnir` | `v0.2.7a-hotfix` | `0.2.7a` | Letter and hotfix suffixes identify builds |

Primary release histories: [CTR](https://github.com/Simon358/ctr-native-android/releases),
[Shipwright](https://github.com/Waterdish/Shipwright-Android/releases),
[Citron](https://github.com/citron-neo/emulator/releases),
[Vita3K](https://github.com/Vita3K/Vita3K-builds/releases),
[XenDroid](https://github.com/rfandango/XenDroid/releases),
[Ludashi](https://github.com/StevenMXZ/Winlator-Ludashi/releases),
[Cmod](https://github.com/coffincolors/winlator/releases), and
[Mjolnir](https://github.com/blacksheepmvp/mjolnir/releases).

Reducing these to a shared numeric base can hide new builds. Date overrides
would unnecessarily replace already-changing source identifiers. Explicit
source tracking makes the existing fallback policy deliberate, but preserves
Obtainium's re-import limitation and cannot detect overwritten assets under an
unchanged tag.

### Correct only the integer false positive in lint

Extend the full-string heuristic to accept optional `v`/`V` followed by a bare
unsigned integer, alongside the existing dotted form. Keep suffix support on
the dotted form only. Simply making the dot group optional would accidentally
accept `2026-04-27` as an integer with a suffix, so date-shaped values must remain
negative fixtures. No APK equality claim or full Obtainium grammar is added.

Change verifier identity from `0.3.0` to `0.3.1` because classification changes.
Keep report schema `1` and the Obtainium `1.6.14` compatibility baseline. Prior
identity evidence must be displayed as stale. Vita3K's `4093` can be a valid lint
shape while still requiring source tracking because its APK version differs.

### Add Cinderbox as an explicit extra

Add one complete extra for `https://github.com/Ekyso/Cinderbox`, package
`com.game.cinderbox`, name `Cinderbox`, author `Ekyso`, category `PC Ports`, and
explicit membership in both variants. Use the existing source defaults with
prereleases excluded, standard detection enabled, and release tags as versions.
Do not overlay this new entry merely to restate its own settings.

The [0.8.1 release](https://github.com/Ekyso/Cinderbox/releases/tag/0.8.1)
contains `Cinderbox-v0.8.1.apk`; its inspected manifest reports versionName
`0.8.1`, versionCode `113`, and the stated package id. No placeholder cache entry
or release pin is needed. Excluding prereleases keeps build-dependency releases
out of selection.

### Keep identity defects visible and separate

The selected APK manifests disagree with four current configured ids:

| Configured id | APK id |
| --- | --- |
| `com.sergiomanzur.sotnrecomp` | `com.blacklabelhq.sotn` |
| `com.simon358.ctrnative` | `com.ctrnative` |
| `com.waterdish.shipwright` | `com.dishii.soh` |
| `com.winlator.ludashi` | `com.winlator.vanilla` |

Document these in `docs/curation.md` with asset URLs and observation dates.
Identity changes require migration and collision analysis, particularly because
`com.ctrnative` already appears in the dual pack from another project. Do not
change ids, sources or selected APKs as part of this work. Ludashi's observed
selection also falls back to `v3.1.h` although release `v4.0` exists; its APK names
changed. Record this selection limitation without altering its filter here.

## Risks / Trade-offs

- Source tracking can show a one-time update after re-import, and installing
  externally may not update the recorded source version. Document this rather
  than promising zero update prompts.
- Numeric extraction can collapse an unforeseen future suffix-only release.
  Capture observed histories, assert distinct selected versions, and document
  the beta-label assumption. Do not claim that live lint can detect a collision.
- A warning-free metadata result does not repair the four identity mismatches.
  Acceptance must report those separately and avoid per-device success claims.
- Upstreams can change between discovery and implementation. Revalidate selected
  releases and manifest facts when preparing final configuration; a contradiction
  requires revising the policy before publication.

## Migration Plan

During implementation, add focused configuration and classification fixtures,
apply the extras and common overlay, rebuild both packs, and run offline and
metadata-only live verification. Expected fixture-baseline output adds Cinderbox
once per variant and removes all 23 recorded format warnings through the stated
policies. Fresh unrelated upstream changes must be reviewed separately rather
than forcing historical app counts or masking new findings.

Run the repository's required checks. Record exact generated-file hashes and
verification observations in durable validation documentation. Exercise import
and re-import on an available test device; if unavailable, record device
acceptance as outstanding rather than treating metadata checks as a substitute.
Consumers receive these policies on their next import. Rollback restores the
prior curated configuration and rebuilds; reverting GitHub publication is a
separate maintainer operation.
