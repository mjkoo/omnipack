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
