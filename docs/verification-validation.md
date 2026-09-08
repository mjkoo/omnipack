# Verification validation

## Current contract and request budget

Routine `pack verify --live` now checks metadata and effective versions without
requesting download bodies. `--live --probe-assets` retains comprehensive bounded
reachability diagnostics. Offline verification remains the ordinary CI gate.
The observations below used verifier 0.1.0, when `--live` also probed assets; they
are historical evidence, not a claim that the current implementation was run
against all upstreams again.

The historical committed pair had 194 entries. At that observation, excluding
unsupported GitHub settings left 92 distinct supported GitHub repository URLs.
That earlier budget was about one release-list request per supported repository,
plus tags fallback and HTML traversal requests. Latest-enabled entries now also
participate, with one latest request before each release list; see the dated
validation below. Different variant settings reuse metadata responses.
The first comprehensive observation made 173 probes for 96 distinct reported
asset URLs; routine metadata verification eliminates all those probes. Explicit
diagnostics deduplicate identical probe requests within their invocation.
Redirects and bounded retries can increase actual wire request counts.

A two-second per-host interval limits bursts; configured authentication avoids
the 60-request unauthenticated GitHub hourly pool. Conditional revalidation saves
transfer, and authenticated 304 responses do not consume GitHub's primary quota.
See [GitHub's request guidance](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api).
The client suppresses a host after rate limiting rather than repeatedly failing
requests for later entries. Cached bodies require fresh revalidation; no old
verification pass or asset probe is accepted as current evidence.

The command fixture has the same repository in both variants: metadata-only
verification sends one release request and zero asset requests; explicit
diagnostics send that one release request plus one shared asset probe. Both
variants retain their own results. Separate fixtures change variant settings
while retaining one shared metadata fetch, and preserve failures without
repeating requests.

These limits are tested with controlled responses and injected time, without
repeating a full live pull solely to validate code changes. Metadata success does
not prove unchanged downloads remain reachable. Future publishing can use actual
asset downloads as evidence when it already needs them.

## Latest-release compatibility validation - 2026-09-08

Verifier identity `0.3.0` supports the committed packs' active `verifyLatestTag`
settings. Compatibility classification finds no currently active unsupported
settings across either pack. Report schema remains `1`, and reports recorded
with `0.2.2` or any other earlier verifier identity display as stale.

Controlled resolver fixtures prove exact tag-or-name identity matching, retention
of list metadata, supplementation outside the first 100 list records, promotion
after both supported sort modes, and continued filtering and version processing.
Latest lookup failures, including 404 and malformed responses, stop before the
corresponding list request. Track-only fallback requests `tags/latest` before its
tag list and retains the release inspection count. A selected record's version
or date failure does not trigger that fallback.

CLI fixtures exercise the real live client with controlled transports: latest
responses and failures are shared across variants, differing settings retain
independent selections, and reports with `inspected_count` 101 and `window_limit`
100 round-trip through the report reader. No routine asset requests occur.
Latest-enabled release resolution costs one latest and one list lookup per
repository before reuse; tags fallback adds its latest and list lookups.
Latest responses have invocation-local reuse only. Persistent conditional caching
remains restricted to eligible release/tag lists with `per_page=100`.

The initial focused resolver, compatibility, live client, CLI integration, and
report checks passed all 234 tests. `just check-all` passed with 572 tests and 91%
coverage, including lock, formatting, lint, types, dependency audit, Python
builds, offline pack validation, workflow checks, Nix formatting, and native
flake checks. Nix emitted its expected dirty-tree and omitted-incompatible-system
notices; test output had no warnings. SHA-256 comparison before and after checks
confirmed all 11 distribution and configuration files, including the package-id
cache, were byte-for-byte unchanged.

After review, controlled fixtures distinguish date order from API order after a
latest mismatch and compare the actual shared decoded metadata before and after
resolution. Both targeted regression mutations failed as expected. Removing
redundant cases and adding the focused shared-object check yielded 232 passing
focused tests and 570 passing tests in `just check-all`, with 91% coverage. The
full checks and all 11 protected input hash comparisons passed again.

This is fixture validation, not a fresh live upstream health observation. It
removes the known compatibility rejection recorded below without asserting that
those sources now resolve or that their downloads remain reachable. Historical
observations and their original publishing blockers remain preserved below.

## Earlier implementation checks

`just check-all` passed at implementation commit `866975a`: 503 tests, 91%
coverage, offline validation of both committed packs, format/lint/type and lock
checks, dependency audit, Python distribution builds, workflow checks, Nix
formatting and native flake checks. That run used verifier identity `0.2.0`; report schema
remains `1` with distinct `offline`, `live` and `live-probe` modes.

Verifier identity `0.2.1` additionally preserves bounded server cooldowns after
retry exhaustion and rejects ambiguous leading closing brackets in regex
character classes. Reports from `0.2.0` are stale under this identity.

Verifier identity `0.2.2` preserves configured non-secret HTML headers during
asset probes, with separate probe caching for different header values. Build
failure reports also retain a successful offline verdict when a later stage
fails. Earlier verifier identities are stale under this identity.

The fixtures prove request reuse, zero routine asset requests, authenticated
conditional revalidation, pacing through redirects and retries, host suppression,
no repeated permanent failures, and bounded redirect/final response reads.
Malformed configuration and reports fail with actionable diagnostics. Historical
live observations remain below; the changed request policy was verified with
controlled transports, without another comprehensive upstream pull.

Distribution/configuration/package-id-cache and build-report bytes still match
the pre-validation snapshots. Expected check notices are limited to Nix omitting
nonnative systems and zizmor using its normal offline mode.

## Refreshed observation after diagnostic and schema fixes

`uv run pack verify --live` completed from 2026-09-07T21:52:00.700360+00:00 to 2026-09-07T21:53:26.175669+00:00
using implementation commit `af8cd3e`, verifier `0.1.0`, baseline `1.6.14`,
and verification schema `1`. The input fingerprints below are unchanged.
All 194 entries were checked; the complete run exited 1. Every resulting error
and warning was inspected. Protected distribution, configuration, cache, and
build-report bytes still match the pre-validation snapshots.

| Variant | Entries | Passed | Errors | Warnings | Download probes |
| --- | ---: | ---: | ---: | ---: | ---: |
| single | 87 | 68 | 19 | 10 | 67 |
| dual | 107 | 68 | 39 | 9 | 67 |

The 58 errors comprise the same 13 active `verifyLatestTag` compatibility errors
listed below and 45 `github-request-failed` metadata failures. No download
probe failed. The metadata failures are network-stage failures, not proof of
bad local configuration or missing upstream releases. They remain publishing
blockers, and previous successful observations were not reused.

After this run, a quota check using the same configured client returned a
60-request core limit with one request remaining. A representative failed source
then returned HTTP 200 with zero remaining and a quota reset timestamp of
`2026-09-07T22:11:50+00:00`. This is consistent with quota pressure, but the
recorded generic metadata error does not establish that every failure had the
same cause. The diagnostic request did not rerun or replace the full observation.

| Entry with metadata failure | Variants |
| --- | --- |
| `767644078` | single, dual |
| `904332840` | single, dual |
| `994078275` | single, dual |
| `app.nanostack.pixelguide` | single, dual |
| `com.andreyvelsk.skyrimwebmonitor` | dual |
| `com.aure.clustertune` | single, dual |
| `com.balatro.dualscreen` | dual |
| `com.chimeragaming.pokemonzmap` | dual |
| `com.ctrnative` | dual |
| `com.cylonid.nativealpha` | dual |
| `com.emulnk` | dual |
| `com.enrpau.dualscreendex` | dual |
| `com.esde.companion` | dual |
| `com.exojosh.minecraftsecondscreen` | dual |
| `com.igawa6.dusklight` | dual |
| `com.jakobkhansen.silksong` | dual |
| `com.joshdaniels.openmwds` | dual |
| `com.kei.pulse` | single, dual |
| `com.moonbench.bifrost` | single, dual |
| `com.pokeemerald.dualscreen` | dual |
| `com.producdevity.emureadylite` | single, dual |
| `com.quantumsoul.esde_android` | single, dual |
| `com.raofflineproxy` | single, dual |
| `com.stormpanda.megingiard` | dual |
| `com.thor.mph` | dual |
| `de.langerhans.odintools` | single, dual |
| `igawa6.dualsouls` | dual |
| `info.cemu.cemu` | dual |
| `it.ottaviomiele.chd` | single, dual |
| `org.pkforge.app` | dual |
| `pup.app.mimir` | single, dual |
| `xyz.blacksheep.mjolnir` | dual |

The 19 non-blocking numeric-shape warnings have the same values and explanations
as the initial warning table below, excluding dual-screen `info.cemu.cemu` and
`xyz.blacksheep.mjolnir`: those two entries failed metadata acquisition in this
run and therefore had no successful version to lint. A reduced warning count
does not imply those versions were repaired.

`just check-all` passed after these corrections: 419 tests, 91% coverage, offline
validation, and all repository checks. Ordinary CI remains offline. The source
and reachability limits below still apply to every successful record.


## Initial live observation

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
