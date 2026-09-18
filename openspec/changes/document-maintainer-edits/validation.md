# Maintainer documentation validation

Validation performed 2026-09-18 on the implementation branch. This change edits
consumer documentation only; the planning and validation records accompany it.
No live source generation, live build, release write or device access was needed.

## Baseline and editing guidance

- Full baseline: `uv run pytest --cov`, 686 passed, 93% coverage, no warnings.
  The first sandbox invocation could not use the default uv cache; a temporary
  cache then lacked network access to build dependencies. The authorized run
  with the normal cache completed successfully.
- Before the repair, extracting the composition page's overlay JSON and calling
  `parse_overlay`, `apply_overlay` and `render` raised `RenderError` because
  `additionalSettings` was a string. After repair the same path rendered
  `versionDetection: false` while preserving an existing
  `includePrereleases: true` setting. This exercised the actual example, not a
  separately reconstructed patch.
- The composition page's complete policy and denial examples passed
  `parse_composition_policy` and `parse_exclusions`; the policy contained one
  candidate rule and one pin. The development page's extracted extra passed
  `sources.extras.fetch` with both variants eligible, and adding `dualScreen:
  true` limited eligibility to dual. Field names and original-selector mapping
  were checked against `composition_policy.py`, `sources/common.py` and the
  schema-3 report producer. Catalog category fallback and sorting were checked
  against `catalog.generate_catalog`.
- Manual path review: an ordinary overlay edit skips generation, builds, uses
  the pack/README diff against the PR base rather than the id-only report delta,
  then verifies and includes changed outputs. A codm policy edit generates,
  reviews that invocation's successful report and catalog, explicitly copies
  the candidate, and joins that same build/review path. A successful no-op
  requires intended report evidence or an expected inert edit: denial removal
  without stale exclusion, or the intended selection for a pin or rule.
- Conflict review: regenerate packs/catalog-region bytes; hand-merge only README
  prose outside markers. For a codm catalog conflict, use main as the base for
  fresh generation, reinspection and acceptance, then build. No instruction
  calls the automated staging script for manual acceptance.
- Compared `.github/workflows/ci.yml`, `.github/workflows/source-catalog.yml`
  and `scripts/source_proposal.py`: CI verifies committed packs offline; the
  source check job additionally builds; the proposal allowlist is only the codm
  catalog. Generated packs are neither proposal content nor uploaded artifacts.
- `pack --help` and `pack generate-source --help` confirmed the command surface.
- `just check-links`: 553 total links, 332 unique, 52 checked OK, zero errors
  (remote links excluded by the existing offline command).

## Publication and curation wording

- Compared curation and publishing wording with `scripts/nightly_write.py`
  `run_release`, `_upload` and `_edit`, and the rolling-pack-release spec:
  served digests are inspected before choosing unchanged/repair/advance;
  repair uploads without an edit; advance uploads then edits; neither branch
  performs a post-upload readback. The stable URLs can expose mixed or missing
  assets and the publishing page owns the raw-main fallback explanation.
- Curation now has a single-line non-atomic visibility note and a publishing
  link. Device acceptance remains explicitly separate. Rollback retains only
  restoring extras/overlay and rebuilding, with no release timing assertion.
- Ludashi review: composition owns deferred migration and retained selection
  and source-version policy; curation owns the current APK filter and older
  release fallback. Neither passage credits a past change; identity uncertainty
  and migration/device precautions remain.
- `just check-links`: 555 total, 333 unique, 54 checked OK, zero errors.
  Publication and policy fragment targets were also checked against headings;
  the offline link checker does not establish remote-link availability.
- `git diff --check`: passed.
