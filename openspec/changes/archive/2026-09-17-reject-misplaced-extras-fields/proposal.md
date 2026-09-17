## Why

omnipack is a pipeline that merges Obtainium JSON sources with precedence, and every source should be treated uniformly. Retired field names, synonyms, tombstone lists and special errors for obsolete shapes are dead code: they are deleted, not guarded. The pipeline keeps only the minimum extension its layered functionality needs.

Today the code does not follow that principle. Shared normalization silently strips a list of current and retired composition names from every source record, the extras adapter rejects two retired names as unknown fields, the overlay protects a longer list of names that nothing reads, and an obsolete id-keyed overlay shape has its own error. Meanwhile the names that composition policy actually uses are handled inconsistently: `family` is silently stripped from a source record, while `packageId` and `variant` pass through into published records without effect, so a maintainer can believe a grouping, identity or selection edit took effect when it did not.

The only omnipack extension read from a source record is the extras `dualScreen` build-kind field. Upstream pack membership is native to each upstream: RJNY export metadata and the BBoi34 release asset a record comes from. `family`, `packageId` and `variant` are the vocabulary of composition policy in `config/composition.json` (candidate rules and pins), and no code reads them from a source record.

## What Changes

- **BREAKING**: every source record ingestion normalizes, from RJNY, BBoi34, the committed codm2000 catalog and extras, that carries a top-level `family`, `packageId` or `variant` fails ingestion regardless of value, including null, with an error naming the source, the entry and the field, stating that the field cannot come from a source record and that composition policy in `config/composition.json` owns app families, package identities and per-pack selection. The error does not direct the correction to composition policy. The build fails visibly while the configured source serves such a record, with no per-record override added.
- **BREAKING**: no other field is reserved or stripped from a source record. Delete the shared composition-only field list and its stripping, so every other unmodeled field passes through unchanged on every source. `dualScreen` remains extras-only and consumed by the extras adapter, so an extras entry's `dualScreen` still never reaches that entry's Obtainium app record.
- Delete the extras retired-field rejection and the special error for an obsolete id-keyed overlay object; a non-array overlay fails as an ordinary shape error.
- **BREAKING**: overlay protected patch fields become exactly `id`, `url`, `overrideSource`, `family`, `packageId` and `variant`. Names that nothing reads are no longer protected and may be patched like any other key.
- Remove retired-name wording from specs, tests and docs: candidate-rule `eligible`/`dualPreferred`, denylist family or variant selectors, the retired `pack verify` flags `--live` and `--probe-assets`, the retired `pack generate-source codm` flag `--force`, and named or old retired verification report schemas in verification evidence and `pack report`. The generic unknown-field, unknown-argument and schema-mismatch rules stay.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `source-ingestion`: add one uniform guard rejecting `family`, `packageId` and `variant` on every source record, with pass-through for every other unmodeled field; replace the extras ingestion requirement with one that drops the retired-field rule and scenario.
- `pack-composition`: state the overlay protected patch fields explicitly and drop the obsolete overlay shape error; replace the composition-policy and denylist requirements with ones that state unknown-field rejection without retired names, and update the one cross-reference to the renamed denylist requirement.
- `pack-cli`: replace the verify command requirement with one that drops the retired `pack verify` flags and keeps generic rejection of unsupported arguments; replace the source generation command requirement with one that drops the retired `--force` flag and its scenario; state that `pack report` directs any unsupported verification report schema to `pack verify` without calling it old.
- `pack-verification`: state that a verification report with any other schema requires regeneration, without naming retired schemas.

## Impact

Affects `src/omnipack/model.py`, `src/omnipack/sources/common.py`, `src/omnipack/sources/extras.py`, `src/omnipack/overlay.py`, tests in `tests/test_sources.py`, `tests/test_composition.py`, `tests/test_composition_policy.py`, `tests/test_verification_integration.py` and `tests/test_cli.py`, and `docs/composition.md`, `docs/development.md`, `docs/verification.md` and `docs/version-detection.md`. No dependency, workflow or configuration migration is expected: the current `config/extras.json`, `config/overlay.json`, committed codm2000 catalog, committed packs and the 212 captured upstream fixture entries carry none of the guarded names, and none of the retired names except `dualScreen` in extras. Rendered packs stay byte-identical for the current configuration and captured upstream fixtures. A future live upstream record carrying a guarded name fails the build visibly while the configured source serves it, with no per-record override added; one carrying a formerly stripped name now reaches the published record unchanged, as any other unmodeled field does.

Estimate: add one new requirement (the source record guard). Because a modified requirement cannot drop a scenario, five requirements whose scenarios name retired vocabulary are removed and re-added under new names with their other text unchanged: extras ingestion, composition policy, package denials, the verify command and the source generation command. Modify five more: the build-kind requirement's cross-reference to the renamed denylist requirement, the composition stage order, the overlay requirement, verification evidence and the report command's verification schema sentence. Add three ingestion scenarios and one overlay shape scenario, replace three retired-name scenarios with generic unknown-field and unsupported-argument scenarios, drop the extras retired-field and forced-refresh scenarios, and restate the overlay protected-field and obsolete-evidence scenarios. Implementation deletes roughly 35-45 lines and adds 10-20; tests delete roughly 60-90 lines and add 40-70. No new retry, ownership, race, diagnostic-format or evidence requirement is introduced: a visible ingestion or configuration failure suffices.
