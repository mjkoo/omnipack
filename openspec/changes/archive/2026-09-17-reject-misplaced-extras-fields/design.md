## Context

omnipack merges Obtainium JSON sources with precedence. Four sources feed composition through one shared normalization function, `sources/common.normalize_record`: the RJNY catalog, the BBoi34 standard and dual assets, the committed codm2000 catalog and the hand-written extras. Each source decides eligibility natively before normalization: RJNY from its `meta` export flags, BBoi34 from the asset a record comes from, codm2000 as dual-screen builds, and extras from `dualScreen`, which is the only omnipack extension read from any source record.

Composition policy in `config/composition.json` owns app families (`family`), package identity corrections (`packageId`) and per-pack selection (pins with `variant`). No code reads those names from a source record, yet ingestion handles them inconsistently: `family` is stripped because it is in `model.COMPOSITION_ONLY_FIELDS`, and `packageId` and `variant` pass through into published records without effect.

The rest of `COMPOSITION_ONLY_FIELDS` (`variants`, `dualPreferred`, `dual_preferred`, `eligible`, `eligibility`, `origin`, `originalId`, `original_id`, `provenance`) and the overlay-only names `selectionReason` and `selection_reason` are not read from a source record or an overlay patch. `origin` remains live as a composition-policy selector field, an internal `App` attribute and a build report key, and original identity as internal `App` attributes and report keys, none of which this change touches. The extras adapter additionally keeps `_RETIRED_FIELDS` to reject `variants` and `dualPreferred` as unknown fields, and `overlay.parse_overlay` has a special error for a legacy id-keyed overlay object. Specs mirror this dead vocabulary: candidate-rule `eligible`/`dualPreferred`, denylist family or variant selectors, the retired `pack verify` flags `--live` and `--probe-assets`, the retired `pack generate-source codm` flag `--force`, and named or "old" retired verification report schemas. Neither command has code for those flags; argument parsing already rejects unknown flags. `pack report` already rejects any verification report schema other than the current one.

The current `config/extras.json`, `config/overlay.json`, committed codm2000 catalog, committed packs and captured upstream fixtures (`tests/fixtures/rjny-*.json`, `tests/fixtures/bboi-*.json`, 212 entries) carry none of these names at the top level, except `dualScreen` in extras.

## Goals / Non-Goals

**Goals:**

- Treat every source record as a plain Obtainium app object, with extras `dualScreen` as the only extension.
- Fail loudly, once, in shared normalization when a source record carries composition-policy vocabulary.
- Delete retired names, tombstone lists and obsolete-shape errors from code, tests, specs and docs, keeping generic unknown-field, unknown-argument and schema-mismatch rules.
- Keep rendered packs byte-identical for current inputs.

**Non-Goals:**

- A complete Obtainium schema, typo detection or recursive settings validation.
- Changing modeled-field handling, including RJNY `meta`, which normalization continues to consume for every source.
- Changing `dualScreen` semantics, composition selection, internal `App` attributes or build report keys.

## Decisions

### One uniform guard in shared normalization

`normalize_record` rejects a record whose top-level keys include `family`, `packageId` or `variant`, by key presence, so null values fail too. The `SourceError` names the source and the entry label the function already computes, names the offending field, and carries one fixed explanation that the field cannot come from a source record and that composition policy in `config/composition.json` owns app families, package identities and per-pack selection. Reporting one offending field is sufficient. Every source reaches this function, so no adapter repeats the check.

The explanation states ownership only; it does not direct or imply a correction through composition policy. No per-record override or allowlist is added.

Every record a source normalizes is validated and guarded, including a committed codm2000 record later suppressed by higher-precedence dual coverage, since validation must not depend on live upstream coverage; an RJNY entry marked as excluded from export is dropped before normalization and is not. Output for current inputs is unchanged.

### Delete stripping and the composition-only list

Remove `COMPOSITION_ONLY_FIELDS` from the modeled set in `normalize_record` and drop its import from `sources/common.py`. The constant itself stays in `model.py` until the overlay stops importing it, and is deleted together with the overlay's switch to an explicit protected set, so no step leaves an importer of a deleted name. The modeled set returns to the Obtainium fields normalization consumes (`id`, `url`, `name`, `overrideSource`, `categories`, `additionalSettings`) plus RJNY `meta`. Every other unmodeled field passes through unchanged on every source.

Because `dualScreen` is no longer stripped globally, the extras adapter must consume it so it never reaches that extra's Obtainium app record, for example by removing it from the entry it passes to normalization. An upstream or codm2000 record carrying `dualScreen` has no extension meaning and passes through like any other unmodeled field; no current input carries one.

Delete `_RETIRED_FIELDS` and its check from `sources/extras.py`. A retired name on an extras entry is now an ordinary unmodeled pass-through field.

### Overlay protected fields are an explicit six-name set

`parse_overlay` protects exactly `id`, `url`, `overrideSource`, `family`, `packageId` and `variant`, written as one literal set without importing a model constant, and rejects any of them with any value including null. The dead names `selectionReason` and `selection_reason` and the imported composition-only names leave the protected set, so a patch may assign or delete them, and `dualScreen`, like any other key. Such a key then renders as an unknown Obtainium field with no composition effect, which offline verification already accepts. Protecting `family`, `packageId` and `variant` keeps overlays aligned with the ingestion guard: composition-policy vocabulary is owned by `config/composition.json` wherever it appears.

The overlay is the last importer of `COMPOSITION_ONLY_FIELDS` once normalization stops using it, so the same step that switches `parse_overlay` to the literal set deletes the constant from `model.py`.

The non-array overlay error drops its legacy guidance and states only the expected array shape with the overlay identified.

### Spec cleanups state generic rules only

- Candidate rules: keep that eligibility and dual preference come only from the build's source, and state that a field other than `match`, `rationale`, `packageId` and `family` fails as an unknown field with the rule and field identified. Code already enforces this generically.
- Denylist: keep that any field other than `id` and `reason` fails with the entry identified, without naming family or variant selectors.
- `pack verify`: delete the retired flag sentence and state that an unsupported argument fails argument parsing with nonzero exit before verification runs, which argument parsing already does and which preserves existing evidence.
- `pack generate-source codm`: delete the retired flag sentence and its scenario without a replacement, since the requirement already states that every invocation resolves every project and a generic unsupported-argument rule adds nothing the command needs to promise.
- Verification evidence and `pack report`: a report with any schema other than the current one, or an unsupported verification report schema, requires regeneration with `pack verify`, without naming retired or old schemas.

A modified requirement must carry every scenario its current version has, so the extras ingestion, composition policy, package denial, verify command and source generation command requirements, whose scenarios name retired vocabulary, are removed and re-added under new names with their remaining text unchanged. The build-kind requirement is modified only to point at the renamed denial requirement. Retired names appear only in the removal reasons and migrations; the resulting main specs name none of them.

### Tests follow the same rule

Delete tests that assert retired names, retired flags or retired schemas by name: the extras retired-field rejection test, the extras test expecting composition names to be stripped, the legacy overlay object test, retired names in the overlay protected-field parameterization, retired names in the candidate-rule unknown-field and rendered-record assertions, the retired verify flag test, and the `pack generate-source codm --force` rejection test in `tests/test_cli.py`. Replace them where coverage would otherwise be lost: a non-array overlay shape error, overlay protection of exactly the six names including null, a generic candidate-rule and denylist unknown field, and a generic unsupported `pack verify` argument that leaves prior evidence intact. Add guard tests for every ingestion path through shared normalization (RJNY, the BBoi34 standard and dual assets, the committed codm2000 catalog, and extras), including null presence and the source, entry and field in the error, cases showing that a guarded field fails on a committed codm2000 record suppressed by dual coverage but not on an RJNY entry excluded from export, and a pass-through test showing a formerly stripped field such as `origin`, and an upstream `dualScreen`, survive unchanged to the rendered record. Keep the existing `dualScreen` eligibility test and assert that `dualScreen` does not reach the rendered record.

## Risks / Trade-offs

- A live upstream record carrying `family`, `packageId` or `variant` blocks nightly publication: the build fails visibly while the configured source serves it, with no per-record override added.
- A live upstream record carrying a formerly stripped name such as `origin` now publishes it unchanged: it is an ordinary unknown Obtainium field with no composition effect, the same treatment as every other unmodeled field.
- An overlay may now set a formerly protected dead name, including `dualScreen`, into a published record: it has no composition effect and is an explicit maintainer edit.
- Existing extras or overlays that relied on stripping or protection would change behavior: current configuration carries none of these names, confirmed by byte comparison.

## Migration Plan

No configuration migration is expected. Confirm that no current configuration file, captured upstream fixture, committed codm2000 catalog or committed pack carries a guarded name at the top level, and compose current configuration with identical captured sources at the branch base and after implementation to compare rendered bytes. Implement on an isolated branch with behavior and delta specs together, and run the full suite and repository checks. Rollback reverts the code, tests and deltas; there is no external migration.
