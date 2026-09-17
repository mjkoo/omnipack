# Implementation validation

Implementation branch: `reject-misplaced-extras-fields`.

## Baseline and current inputs

Before implementation, `uv run --locked pytest -q` passed all 665 tests in
29.52 seconds. The UV cache was redirected to a writable temporary directory.
Lock consistency, formatting, lint, type checking, offline `pack verify`, and
offline documentation links also passed.

The input inspection parsed all JSON under `config/`, top-level captured
`tests/fixtures/rjny-*.json` and `bboi-*.json`, reconciliation JSON fixtures,
and committed `dist/*.json`. Across 20 files, 572 app objects (objects carrying
`id`, `url`, and `name`) contained no top-level `family`, `packageId`, or
`variant`. Policy rules and selectors are not source app records.

The baseline composition used the committed configuration and the captured
reconciliation fixture through
`tests.current_config_support.current_configuration_fixture.__wrapped__()`,
then rendered each `result.apps` value with `omnipack.render.render` and encoded
UTF-8. The fixtures make no live requests.

| Pack | Bytes | Baseline SHA-256 |
| --- | ---: | --- |
| single | 102039 | `f55841cc37706d93256f67b679c9b61eaf52f9fe05f61bf285cb3d0c8626f56f` |
| dual | 129129 | `d4b0ffe433274c4c6fbb63c753daaeb9836b2593e0933aecdf90e763a22a55bd` |

After implementation, the same composition and rendering procedure produced
exactly the baseline bytes for both packs, with the same lengths and SHA-256
values above. The comparison used baseline code at `7204b97` (whose application
code is identical to branch base `341a4e8`) and implementation at `3d7856d`.
No configuration migration was needed.

## Repository checks

The unchanged workflow and Nix surfaces passed `just lint-actions`,
`just nix-fmt-check`, and `just flake-check`. Zizmor reported no findings
while announcing its default offline audit mode. Nix checked the host
`aarch64-darwin` outputs and omitted incompatible systems; it reported the
working tree as dirty during implementation. These are tool scope notices,
not test failures.

`just check-py312` passed 104 script tests under Python 3.12.14 in 23.39 seconds.
`openspec validate reject-misplaced-extras-fields --strict` passed.

## Source ingestion review

Commit `1ba38b3` implements the source guard and extras consumption. The red
focused source/CLI run had 34 expected failures and 85 passes; the green run
passed 119 tests in 2.45 seconds. Independent evidencing review approved all
three source-ingestion tasks with no findings. Evidence tests are
`test_source_record_rejects_composition_policy_fields`,
`test_rjny_excluded_record_is_not_guarded_but_neither_pack_record_is`,
`test_suppressed_codm_record_is_still_guarded`,
`test_unmodeled_fields_pass_through_upstream_and_extras`, and
`test_guarded_extras_field_fails_build_and_preserves_outputs`.

The guard is centralized, checks key presence, and selects a field
deterministically. The suppression test includes an unguarded control.
Commit hooks passed formatting, lint and type checking.

## Overlay and policy boundary review

Commit `68629fe` implements the six-field overlay boundary and removes the
shared stripping/protection constant. The focused composition, policy and
offline tests had four expected failures before implementation and passed
all 130 tests afterward in 0.12 seconds. Format, lint and type checks passed.
Independent evidencing review approved both tasks with no findings.

Evidence includes `test_nonarray_overlay_error_identifies_the_overlay`,
`test_overlay_rejects_assigning_or_deleting_identity_and_composition_fields`,
`test_overlay_patches_unmodeled_origin`,
`test_policy_correction_retains_original_identity_and_internal_fields`,
`test_denylist_entries_hold_exactly_a_package_id_and_reason`, and
`test_unknown_denial_field_is_reported`. Generic candidate-rule cases also
pass. Neither candidate-rule nor denylist parsing code changed.

## Complete implementation checks

At `3d7856d`, `just lock-check format-check lint-check typecheck test verify
check-links` passed. The full suite passed 686 tests in 30.97 seconds with
93% aggregate coverage. Offline `pack verify` succeeded. Offline links checked
542 total links, 323 unique, with 41 OK and zero errors (501 excluded).
`openspec validate reject-misplaced-extras-fields --strict` passed again.
`git diff --check` passed.

`git diff --exit-code main -- config dist .github/workflows README.md` returned
zero: configuration, committed catalogs and packs, workflows and README remain
unchanged. The input scan repeated after implementation also found no guarded
fields among the same 572 app objects. No device access or live source build
was needed for this change.

## CLI and documentation review

Commit `3d7856d` replaces retired flag/schema tests with generic coverage and
updates all four named documentation files. No production behavior changed
in this group, so the replacement tests passed the existing generic rules
without an intentional red phase. The focused CLI, report and verification
suite passed 96 tests in 0.31 seconds. Independent evidencing review approved
both tasks with no findings.

`test_unsupported_verify_argument_fails_before_verification` asserts parser
exit, no verification or HTTP call and unchanged evidence bytes.
`test_unsupported_verification_schema_requires_regeneration` asserts the
`pack verify` regeneration diagnostic for an arbitrary unsupported schema.
The redundant unsupported-schema row was removed from the corrupt-report
parameterization. The source-generation flag test was deleted without
replacement.

The source/tests/docs vocabulary sweep found no remaining targeted retired
source-record or overlay names, constants, CLI flags or verification schema
wording. Remaining matches are live internal attributes and parameters,
report and fixture keys, prose, build-report schemas, unrelated historical
app provenance, or the documented git push recovery command. The entire
Retired configuration section was removed; current rules remain in the
surrounding documentation.

## Independent final reviews

The validation group's evidencing review approved the input scan, byte comparison
and repository-check evidence in `6ed361d`, with no findings. It independently
reproduced the scan and both exact byte comparisons.

Four independent whole-diff reviewers examined `341a4e8..6ed361d`:

| Scope | Result |
| --- | --- |
| Source normalization, ingestion order and output-preserving failures | Approved, no findings |
| Idiomatic patterns and maintainability | Approved, no findings |
| Overlay and CLI public boundaries, diagnostics and documentation | Approved, no findings |
| Test discrimination and proportionality | Approved, no findings |

No fix round was needed. Review confirmed the accepted boundaries: export-excluded
RJNY records bypass normalization; neither-pack RJNY records and suppressed codm
records are guarded; invalid composition policy may fail before ingestion;
configured source locations can change without adding a per-record bypass.
The test reviewer found the ingestion matrix discriminating and proportionate,
confirmed suppression's passing control, and accepted the CLI preservation and
unsupported-argument tests. The reviewers confirmed deterministic field reporting,
ownership-only diagnostics, generic denial coverage and explicit `pack verify`
regeneration guidance. Retained source-generation failures still preserve accepted
records verbatim, with source validation occurring at build ingestion. No parked
warnings or unresolved findings remain.

A fresh independent checkbox/evidence audit examined `341a4e8..06aa49e` after
the review wave. It confirmed all nine previously checked tasks, with no
unevidenced items or critical findings, naming the implementing commit and
proving test or check for each. It explicitly confirmed that the clean wave
plus this audit completes the remaining review task's gate. No implementation
fixes or scope rulings were needed.

## Completion audit evidence

| Tasks | Implementation/evidence commit | Proof |
| --- | --- | --- |
| Source guard and source tests | `1ba38b3` | Five-path assigned/null matrix, RJNY ordering, codm suppression control, pass-through and CLI preservation tests; 119 passing focused tests |
| Overlay and generic policy boundaries | `68629fe` | Six-field assigned/null matrix, origin patch control, non-array shape and generic policy/denial tests; 130 passing focused tests |
| CLI and documentation cleanup | `3d7856d` | Unsupported argument and arbitrary schema tests; 96 passing focused tests; four updated docs and zero offline link errors |
| Current inputs and repository checks | `6ed361d` | 572-record scan, exact pack bytes, 686-test full suite and repository checks |
| Independent final reviews | `06aa49e` | Four clean whole-diff reviews and independently reproduced input/byte checks |

The change remains active on `reject-misplaced-extras-fields`. Separate OpenSpec
verification and archive workflows have not been run. No push or merge occurred.

After the audit, the required final full-suite run passed all 686 tests in
29.00 seconds. Offline `pack verify` and strict artifact validation passed again.
No implementation changes followed the audit.
