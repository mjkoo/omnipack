## Why

Validating a curated JSON pack currently requires maintaining a partial independent
implementation of Obtainium's source resolution and version semantics. The project
will accept structural validation and deliberate curation regressions instead of
owning that compatibility layer or introducing a Flutter runtime to reuse it.

## What Changes

- **BREAKING**: Remove `pack verify --live` and `--probe-assets`, source resolvers,
  compatibility classification, effective-version lint, and verification-only HTTP
  caching/probing. Removed flags fail explicitly rather than silently doing less.
- Retain offline serialized-output, composition, settings, and catalog checks.
  Unknown settings remain structurally acceptable without a compatibility claim.
- Gate nightly publication on fresh structural verification of candidate bytes.
  Preserve publication allowlists, exact-byte checks, and other existing recovery.
- Replace live-shaped reports with structural evidence; obsolete evidence requires
  regeneration and cannot authorize publication.
- Preserve curated export settings and regression checks for their survival across
  refreshes. Describe source-selection behavior as intended Obtainium behavior,
  not an automatic guarantee by this tool.
- Clarify tracker bootstrap and curation documentation under structural verification.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-verification`: Structural-only verification and evidence; remove all live
  resolution, probe, compatibility, and effective-version-lint requirements.
- `pack-cli`: Remove live flags and simplify displayed verification evidence.
- `nightly-publishing`: Require fresh structural verification instead of live checks.
- `pack-composition`: Replace the selected-build live verification gate with
  structural verification while preserving selection and fallback rules.
- `pack-curation`: Preserve configurations and their regression coverage without
  promising live verification of app behavior or automatic publication blocking.
- `rolling-pack-release`: Require explicit bootstrap before release synchronization,
  without using tracker metadata resolution as a verification gate.

## Impact

Affects `verify.py`, `offline.py`, `report.py`, `cli.py`, `live.py`, `live_http.py`,
`resolution/`, verification-only portions of `http.py`, publisher evidence handling,
related tests, and current operator documentation. No Flutter or Dart dependency
is introduced. Generated export content is expected to remain unchanged.

## Non-goals

Do not change source ingestion, APK package-ID discovery, composition policy,
curated app choices, release mirroring, issue management, or publication recovery.
Do not replace the removed verifier with a smaller live checker or a test-only
resolver implementation. Preserve historical evidence and archived artifacts.
