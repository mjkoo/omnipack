# Verification validation

## Live observation

`uv run pack verify --live` completed from 2026-09-07T21:39:55.835165+00:00 to 2026-09-07T21:41:10.379334+00:00.
Verifier version: `0.1.0`. Obtainium compatibility baseline: `1.6.14`.
Verification schema: `1`. Implementation observed: commit `9208468`.

The command completed and exited 1 because unsupported active settings are errors.
Every error and warning was inspected. No distribution, configuration, package-id
cache, or build-report bytes changed during offline and live verification.

| Variant | Entries | Passed | Errors | Warnings | Download probes |
| --- | ---: | ---: | ---: | ---: | ---: |
| single | 87 | 81 | 6 | 10 | 77 |
| dual | 107 | 100 | 7 | 11 | 96 |

All 173 performed download probes succeeded. Eight track-only variant entries
required no probe. All fourteen HTML variant entries resolved successfully.
There were no metadata network failures, download failures, or malformed local
configuration findings in this observation. Successful reachability does not
establish APK identity, signatures, installation, or device compatibility.

## Publishing blockers

All 13 errors have stage `resolution` and code `unsupported-setting`: the active
`verifyLatestTag` setting is outside the declared compatibility boundary.
These entries were rejected before a source request. They are not evidence that
the corresponding upstreams are unavailable.

| Entry id | Affected variants |
| --- | --- |
| `com.armsx2` | single, dual |
| `com.github.catfriend1.syncthingfork` | single, dual |
| `com.neogamelab.neostation` | single, dual |
| `gamehub.lite` | single, dual |
| `io.navivani.swiff` | single, dual |
| `jr.brian.home` | dual |
| `org.vita3k.emulator` | single, dual |

These errors block future nightly publishing. Resolving them requires a separate,
deliberate compatibility extension or reviewed configuration change. Verification
has not disabled settings, repaired overlays, or relaxed its guarantee.
Any network failure in a later observation is also a publishing blocker until
investigated; this observation is not a promise of continuing upstream health.

## Warning review

All 21 warnings have code `github-version-format`. They are non-blocking because
source resolution and reachability succeeded. The table groups identical
variant findings; Cemu has different configured sources/titles per variant.

| Entry id | Variants | Effective version | Origin |
| --- | --- | --- | --- |
| `com.aure.banjorecomp` | single, dual | `android-v0.1.1` | tag |
| `com.sergiomanzur.sotnrecomp` | single, dual | `android-v0.10.1b` | tag |
| `com.simon358.ctrnative` | single, dual | `Android-Build4` | tag |
| `com.waterdish.shipwright` | single, dual | `v9.0.2P2` | tag |
| `com.winlator.cmod` | single, dual | `cmod_v13.1` | tag |
| `com.winlator.ludashi` | single, dual | `v3.1.h` | tag |
| `info.cemu.cemu` | dual | `CEMU Android v0.5.2: Graphic Packs Custom Root Fix` | title |
| `info.cemu.cemu` | single | `Cemu 0.5` | title |
| `net.rpcsx` | single, dual | `v20250425` | tag |
| `org.citron.citron_emu` | single, dual | `2026-04-27` | tag |
| `xendroid.compose` | single, dual | `XenDroid-0b11201` | tag |
| `xyz.blacksheep.mjolnir` | dual | `v0.2.7a-hotfix` | tag |

The prefixed tags and descriptive titles do not match the anchored numeric
shape. Date-like tags have no dot-separated numeric components. Values such as
`v9.0.2P2`, `v3.1.h`, and `v0.2.7a-hotfix` have nonnumeric components or suffixes
outside the heuristic. These findings do not prove an Android versionName
mismatch. No title or regex exemption was applied, and no warning caused the
nonzero exit. Per-entry configuration decisions remain separate work.

## Exact input fingerprints

SHA-256 hashes cover the checked bytes, excluding environment credential values.

| Input | SHA-256 |
| --- | --- |
| `dist/single-screen.json` | `87942ea73ac15119780e5dcf5d9810e9ee641aa340d3218c41e28066ad7a4f63` |
| `dist/dual-screen.json` | `bc428c6005465d59deb5c08986a575947d5f1c5c4078fcd3d34bebe8171a313c` |
| `config/deny.json` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| `config/overlay.json` | `ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356` |
| `config/overlay.dual.json` | `ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356` |
| `config/settings.json` | `ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356` |
| `config/http.json` | `c82f5ae80567692d2ccefcbef9ac11f995d379f20187dda04e583b8120e80929` |

## Repository validation

`just check-all` passed with 377 tests, offline validation of both committed
variants, lock/lint/format/type checks, dependency audit, Python distribution
builds, actionlint, zizmor, Nix formatting, and native Nix flake checks.
The fixture suite exercises all seven HTML configurations, GitHub release/tag
patterns, track-only behavior, metadata transport, bounded probes, and existing
ingestion/cache/publication behavior.

Zizmor used its normal offline mode. Nix checked the native system and omitted
incompatible systems; it reported the expected uncommitted-tree notice during
validation. Ordinary CI performs offline verification without upstream builds
or live checks.
