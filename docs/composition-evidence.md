# Composition implementation evidence

The implementation and committed configuration enforce device-aware family
selection across source ingestion, composition, build reporting, and offline
verification. Focused tests cover strict policy parsing, corrected and historical
identity projection, source eligibility and preference, pin-first selection,
exclusions, family coverage, build-bound overlays, report transitions, exact-byte
fingerprints, and publication failure behavior.

The maintained source build rendered 88 single-screen and 107 dual-screen apps.
The full output comparison and exact SHA-256 values are recorded in
[composition migration validation](composition-validation.md). The selected CTR,
OpenMW, Super Metroid, and Dusklight families retain one winner per target with
the documented identity or project transitions.

Validation on 2026-09-09 produced these outcomes:

- `UV_CACHE_DIR=/private/tmp/omnipack-uv-cache just check-all` passed all checks,
  including 727 tests with 92% coverage and offline verification.
- `UV_CACHE_DIR=/private/tmp/omnipack-uv-cache uv run pack verify` passed with
  verifier 0.4.0 and no errors, warnings, or entry findings.
- Authenticated `uv run pack verify --live` passed for all 195 rendered entries
  with no errors or warnings.
- `openspec validate --specs` and strict change validation passed after the four
  capability deltas were merged into the main specifications.

Android device acceptance remains outstanding because `adb devices -l` found no
connected device. Import, re-import, installation, signature compatibility, and
app-data continuity have not been established. The final implementation review
and task-evidence audit also remain pending before archive.
