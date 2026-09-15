# Implementation validation

## Baseline

At 308257e before test edits: 460 test functions, 798 cases, 12,613 test/helper Python lines and 6,145 production Python lines including scripts. The implementation-branch baseline passed all 798 tests in 40.27 seconds with coverage of both src and scripts using the C tracer and per-test contexts. Production files remain fixed for line/arc comparisons.

## Proposal review

Strict OpenSpec validation passed. Four independent profile reviews completed with no candidates or residual warnings in the first round. All reviewers used Codex; no cross-family gate ran. Existing schedule and retention requirements remain normative even though their incidental literal assertions are being retired. Curation expectations must remain independent of production selection logic.

## Repository checks

- Locked dependency validation passed (12 packages).
- Workflow lint with actionlint and zizmor passed.
- Offline documentation link check passed.
- Isolated CPython 3.12.14 publication baseline passed: 121 tests in 31.95 seconds.
- Nix formatting passed with zero changes; native flake checks passed. The flake command reports incompatible platforms as omitted, as expected for the native check.

The sandbox initially prevented the Python 3.12 dependency fetch and Nix cache writes. Reruns with the required access passed; these were tooling-access failures, not suite failures.

Implementation results, survivor ownership and final review evidence follow as batches complete.

## Assertion repair and shortlist

Affected suite: 473 passed in 28.28 seconds. Ruff and ty passed. The remaining suite collects 783 cases; the APK loop is now three separately parameterized cases.

### Repairs and transferred assertions

- Tracker checks now compose captured upstream inputs with the current extras, committed catalog, current denials, overlays and policy. The collision check inspects ingested candidate identities, and the composition check requires one identical rendered tracker per variant, all track-only settings, and no installed/latest version state.
- APK fixtures use a fixed `ZipInfo` timestamp. The agreement test has explicit success/failure outcomes for matching IDs, mixed IDs and unreadable input while retaining filtered-asset assertions.
- The source-generation preservation test no longer reads HEAD from the unrelated development repository; its name now describes input preservation and failed-candidate cleanup.
- `test_verification_only_report_is_current_then_stale` now owns the exact offline structural-mode wording.
- `test_rejected_push_logs_the_remote_error_and_keeps_it_out_of_the_summary` now also proves the rejected push leaves remote main at its base SHA.
- `test_stage_cli_reads_env_and_exit_code_and_writes_outputs` now proves the summary names the branch-creation base SHA.

### Survivor ownership for removed functions

- Mocked catalog build failure: real pipeline and output preservation remain in `test_build_runs_the_real_pipeline_with_transport_only_fixtures` and `test_failed_build_reports_exact_stage_and_preserves_outputs`.
- Tracker observed-state helper: real current-config tracker composition owns all retained assertions.
- App dataclass layout: focused source adapters own eligibility translation; `test_dual_preference_is_derived_from_dual_only_eligibility` owns derived preference behavior.
- Pretty-print helper meta-test: `test_committed_catalog_bytes_are_the_canonical_rendering_of_its_entries` owns canonical committed bytes.
- Four-source omnibus preference: focused RJNY, BBoi, codm and extras tests own their translations.
- Regroup-after-suppression: `test_codm_suppression_follows_source_dual_eligibility` owns suppression and composition-policy tests own regrouping.
- Omnibus selection reasons: the focused dual preference, pin and source-fallback tests own each reason.
- Duplicate original identity: `test_identical_candidates_collapse_but_ambiguous_identity_fails` owns the policy boundary.
- Two direct redirect-request tests: `test_urllib_redirect_selects_destination_credentials` owns real urllib redirect credential selection and stripping.
- Historical verification report: report-reader schema rejection cases own regeneration behavior.
- Structural report mode: transferred to the current/stale report case.
- Successful nightly push round trip: CLI publication, hook-disabled and prepare-to-push cases retain successful write behavior.
- Rejected nightly push: transferred remote-main preservation to the surviving logged-error case.
- Matching release digests: `test_comparison_ignores_the_recorded_commit_and_uses_digests_only` retains unchanged/no-write behavior.
- Suffix-main branch decoy: `test_ls_remote_reads_only_the_exact_ref` owns exact-ref selection.
- Source-stage Base SHA: transferred to the changed-stage success case.

### Counterexamples

- Tracker disappearance mutation: temporarily filtered the tracker from `captured_higher`. Both the candidate-identity test and composed-pack presence test raised `AssertionError`, demonstrating the checks fail when the tracker disappears. No repository file was changed by the probe.
- ZIP timestamp probe: built two byte-distinct APK ZIPs for `org.example.app` with timestamps one year apart and ran the source generator with both eligible assets. Status was `success`, demonstrating identity agreement no longer depends on ZIP byte equality. No repository file was changed by the probe.

Full suite after repairs/removals: 783 passed in 36.24 seconds. Comparing actual coverage databases with the baseline lost zero executed production lines and zero arcs (including entry/exit arcs), with zero additions.

Independent evidencing review of 00f3046..7f7ce8a approved all three implementation boxes with no findings, citing the surviving tests, counterexamples and actual coverage comparison.

## Publication workflow contracts

The 44 publication-workflow cases are now seven shared checks across both workflows. The import-boundary check remains one case. All eight pass (0.09 seconds), and Ruff/type checks pass.

- `test_publication_permissions_and_runtime_boundaries` owns permissions, checkout refs/depth/credential persistence, main/repository guards, action pinning, cache restrictions, locked setup, write-side runtime isolation and unsafe expression/status-function restrictions.
- `test_handoff_connects_checked_candidate_to_writer` owns checked-step outputs, artifact names/paths, changed/no-op gating, upload replacement behavior, diagnostics, writer environment/token placement and essential module entrypoints.
- `test_base_guard_rejects_stale_revision_before_consumption` owns guard environment and ordering before artifact/token consumption and executes both matching and mismatching SHAs.
- `test_source_candidate_validation_finishes_before_handoff` owns generate/stage/test/build/verify/catalog-guard/upload ordering and conditions.
- `test_write_side_modules_import_only_stdlib_and_scripts` follows script imports, including relative imports, without requiring future annotations or forbidding a particular import style. Real Python 3.12 execution remains the runtime compatibility check.

Retired assertions: exact cron, timeout, runner, retention, concurrency labels, display names, shell whitespace/continuations and immediate guard adjacency. The workflows and their normative requirements remain unchanged.

Temporary counterexamples on each parsed workflow: replacing the base-guard command with `true` fails the new check; the original guard passes matching and mismatching inputs. Renaming all display labels and inserting a diagnostic step after checkout still passes. No workflow file was mutated by these probes.

## Publication setup and outcomes

The shared standard-library/pytest helper replaces repeated Git setup and fake GitHub runners. Preparation and source staging success assertions now live in changed/no-op CLI cases, including bot identity, bundle/base/run metadata and disabled hooks. Shared handoff rejection is tested once with one propagation case per caller; caller path/mode rules and distinct release outcomes remain separate. The affected suite passed 135 tests in 26.59 seconds; Ruff and ty passed.

## Exact publication outcome ownership

| Outcome | Surviving test |
|---|---|
| Nightly remote main advanced | `test_advanced_main_fails_before_push_and_reports_main_advanced` |
| Nightly shared handoff rejection propagation | `test_push_propagates_handoff_rejection_before_remote_write` |
| Nightly disallowed path, empty diff, symlink and executable rejection | `test_commit_touching_disallowed_path_is_rejected`; `test_commit_changing_nothing_is_rejected`; `test_commit_replacing_allowed_file_with_symlink_is_rejected`; `test_commit_setting_executable_bit_is_rejected` |
| Nightly malformed input before Git/GitHub | `test_malformed_shas_are_rejected_before_any_fetch_or_push` |
| Nightly successful write and hook suppression | `test_write_side_repository_hooks_never_run`; `test_push_cli_reads_env_and_exit_code_and_writes_summary`; `test_real_prepare_commit_hands_off_to_push` |
| Nightly GitHub credential failure | `test_push_cli_fails_when_gh_cannot_hand_git_the_credential` |
| Nightly rejected remote push without remote advance | `test_rejected_push_logs_the_remote_error_and_keeps_it_out_of_the_summary` |
| Nightly push lands but detach fails | `test_detach_failure_after_a_landed_push_reports_published_and_fails` |
| Release unchanged by current digests despite stale commit or extra asset | `test_comparison_ignores_the_recorded_commit_and_uses_digests_only`; `test_unexpected_extra_assets_are_ignored`; `test_release_cli_exit_code_and_summary` |
| Release advances for duplicate/malformed/different record | `test_duplicate_record_lines_count_as_no_valid_record`; `test_malformed_record_line_counts_as_no_valid_record`; `test_differing_record_uploads_and_edits_with_canonical_body` |
| Release bootstrap advances to revision 1 | `test_bootstrap_seed_is_replaced_by_the_canonical_body_at_revision_1` |
| Release repairs stale, missing or partially replaced served assets without edit | `test_matching_record_with_differing_served_digest_repairs_without_edit`; `test_missing_or_absent_served_digest_repairs_without_edit`; `test_interrupted_upload_then_run_returning_to_recorded_pair_repairs` |
| Release ownership/bootstrap failures | `test_invalid_release_marker_or_title_fails_with_bootstrap_guidance`; `test_draft_non_prerelease_or_immutable_fails_with_bootstrap_guidance`; `test_release_not_found_is_missing_with_bootstrap_guidance` |
| Release local asset and repository failures | `test_symlinked_pack_file_fails_before_any_release_call`; `test_head_read_failure_fails_with_release_failed_reason`; `test_missing_pack_file_fails_with_release_failed_reason_and_no_writes` |
| Release upload/edit failure sequencing | `test_upload_failure_prevents_edit_without_bootstrap_guidance`; `test_release_cli_fails_when_the_release_edit_fails` |
| Release remote/auth/view failures | `test_remote_main_other_than_head_fails_without_bootstrap_guidance`; `test_gh_auth_failure_fails_with_specific_reason_and_no_writes`; `test_ls_remote_command_failure_fails_with_specific_reason_and_no_writes`; `test_release_view_failure_other_than_not_found_has_no_bootstrap_guidance` |
| Source unchanged closes owned PR or makes no write | `test_unchanged_closes_an_open_pr_and_makes_no_push_or_pr_write`; `test_unchanged_with_no_open_pr_makes_no_write` |
| Source changed creates or edits owned PR | `test_changed_with_no_open_pr_creates_one_from_the_body_file`; `test_changed_with_an_open_pr_edits_its_body` |
| Source branch equal/different tree behavior | `test_equal_trees_make_no_push_even_with_a_different_hand_made_commit`; `test_hand_pushed_commit_with_a_different_tree_is_overwritten`; `test_bot_branch_built_on_an_older_main_is_compared_from_a_shallow_checkout` |
| Source fork and duplicate-owned-PR selection | `test_fork_pr_sharing_the_branch_name_is_untouched_and_own_pr_is_created`; `test_fork_pr_sharing_the_branch_name_is_not_closed_when_unchanged`; `test_two_selected_same_repository_prs_fail_before_any_write`; `test_two_selected_same_repository_prs_fail_before_closing_either` |
| Source shared handoff rejection propagation | `test_publish_propagates_handoff_rejection_before_remote_write` |
| Source catalog path/symlink/executable rejection | `test_commit_changing_a_file_other_than_the_catalog_is_rejected`; `test_commit_replacing_the_catalog_with_a_symlink_is_rejected`; `test_commit_setting_the_catalogs_executable_bit_is_rejected` |
| Source main advanced, malformed inputs, body rejection and push rejection | `test_remote_main_other_than_base_fails_on_both_paths`; `test_malformed_env_values_are_rejected_before_any_fetch_or_write`; `test_unusable_pr_body_fails_before_any_push_or_pr_write`; `test_rejected_branch_push_fails_with_its_reason_and_no_pr_write` |
| Source GitHub operation failures | `test_failed_gh_operation_exits_nonzero_with_its_reason` |

## Counterexample probe

Temporarily changed `verify_handoff`'s dirty status predicate from
`if status.strip()` to `if False and status.strip()`. The focused dirty case
failed with `DID NOT RAISE HandoffRejected`, proving that the consolidated
shared test detects removal of the rejection. The line was restored, the same
case passed, and `git diff --exit-code -- scripts/workflow_support.py` confirmed
that no production mutation remained.


Full suite after publication consolidation: 738 passed in 38.01 seconds. Isolated CPython 3.12.14: 112 passed in 27.64 seconds. Actual coverage comparison with the previous batch lost zero production lines or arcs, with zero additions. A final source-publisher log assertion also passed its focused test.

### Publication review correction

The first publication review accepted fixture/handoff consolidation but found missing trigger-presence checks and universal job-security coverage. The workflow test now requires scheduled/manual triggers without fixing cron values and applies repository/main guards, action pins, cache restrictions, unsafe-expression checks and nonpublisher permission limits to every job. The preparation success test accepts either UTC date bracketing the call, avoiding midnight timing failure. Thirty affected tests, Ruff formatting/lint, full ty and diff checks passed. Twenty-four unsafe in-memory workflow mutations changed from accepted to rejected; ten safe variants (additional read-only jobs, labels and cron changes) pass. No production or workflow files changed.

Scoped re-review of 33d3b3d..6cc8b85 approved the workflow correction with no findings. Publication fixture consolidation remains approved; the batch is complete.

## Curation and catalog consolidation

Shared session fixture ingests captured upstreams with actual current extras, policy, catalog, denial and overlay inputs. Baseline-extra expectations use original source/origin/id/normalized URL and explicit single pin exemptions, independent of production policy application. Tracker identity and composed presence use this real pipeline. Manifest package observations still independently check corrections; frozen pre-migration golden exports and input hashes are untouched.

Committed catalog validation is centralized. Catalog add/remove noninterference now uses one explicit higher-source app and two explicit generated entries with empty policy; it does not freeze current catalog membership. Current catalog composability remains separately tested. Redundant refresh calls, capture-date/hash-length assertions and helper meta-tests removed.

Survivors: test_committed_configuration_selects_each_baseline_extra_in_single owns configured baseline extras; tracker identity/presence tests own actual tracker selection; test_manifest_evidence_matches_configured_corrections owns manifest mapping; test_frozen_captured_baseline_reproduces_exact_exports_and_family_winners owns historical golden bytes; test_committed_catalog_is_valid_canonical_and_composable owns current catalog shape/canonical bytes; test_catalog_addition_and_removal_leave_single_screen_selection_unchanged owns independent noninterference; source semantics test retains tracker/prerelease/source eligibility and covering candidates.

In-memory current-config probes: denying configured Cinderbox makes direct extra guard fail; removing tracker makes both identity and presence tests fail. No production or frozen fixture edits. Ruff and ty passed after the final fixture correction.

Full suite: 720 passed in 34.82 seconds. Ruff and full ty passed. Actual production execution comparison with the publication batch: zero lost or added lines and arcs.

Independent curation evidencing review of 6cc8b85..a81b845 approved both implementation boxes with no findings.

## Remaining surface

Six modules changed. 147 affected cases passed in 1.97 seconds; Ruff format/lint and full ty passed.

- Transaction restoration keeps staging/replacement failure at the second output, each with existing outputs and absent outputs; README rollback integration, temporary-file cleanup, non-default 0640 mode preservation and normal creation permissions remain. First/last generic failure positions and equivalent permission values are retired.
- Render category colors use explicit fixed expected values instead of copied hashing code. Upstream default-key parity and settings behavior remain; three implementation-size assertions are removed.
- Catalog round-trip parsed equality remains; redundant sorted serialization equality is removed.
- Adapter test retains candidate IDs and unassigned families without function-signature or Python object-identity constraints.
- Agreeing policy rules now assert corrected candidate ID/family through application, not internal projections layout. Offline family/pin correctness remains in verifier and policy behavior tests.
- HTTP retry scenarios retain successful package identification, multiple GET attempts and positive backoff without exact HEAD/GET order or sleep values. Fallback reads must be bounded and nonempty; credentials, redirects and error outcomes remain covered.

No production edits or dependencies introduced. Frozen fixture files remain unchanged.

### Verification, denial and CLI outcome ownership


| Outcome | Surviving owner |
|---|---|
| A package denial removes every eligible carrier across sources and records the separate stale denial | `test_package_denial_outcomes[all-carriers]` |
| A denied dual-only package falls back to another package in the family | `test_package_denial_outcomes[different-package-fallback]` |
| Denying all same-package standard and dual builds leaves the family empty and records all three variant removals | `test_package_denial_outcomes[empty-family]` |
| A denied candidate eligible for neither pack is matched without a removal or stale diagnosis | `test_denial_of_a_build_eligible_for_neither_pack_is_not_stale` |
| Denylist required fields and forbidden family/variant fields | `test_denylist_entries_hold_exactly_a_package_id_and_reason` |
| Same-package standard/dual selection remains independent of denial coverage | `test_shared_package_builds_split_by_kind_without_a_pin` and `test_dual_pin_keeps_a_standard_build_over_its_shared_package_dual_build` |
| A real build writes both variants, exact change records and no public report artifact | expanded `test_build_verify_and_report_sequence_records_no_findings` |
| Real ingestion, composition, offline-gate failure, transport boundaries, admissions and existing-output diffs | `test_build_runs_the_real_pipeline_with_transport_only_fixtures` |
| Verification fingerprints the exact serialized input set and persists identical evidence | `test_offline_evidence_fingerprints_exact_inputs` |
| Interruptions write no new report and preserve existing evidence | `test_interrupted_verification_does_not_replace_evidence[absent/present]` |
| Verification uses captured bytes and reports later edits as stale | `test_report_fingerprints_the_bytes_captured_before_a_later_edit`, `test_composition_only_change_makes_recorded_evidence_stale` and the README capture test |
| Build-report schema type, status, diagnostics, field set, package-change shape, record container/item shape and offline status/findings/finding shape | `test_malformed_build_report_records_are_rejected` |
| Every required build report field | `test_build_report_missing_a_field_is_rejected` |
| Nested winner and considered-candidate validation | `test_malformed_selection_records_are_rejected` |
| Bool is rejected where the build and verification schemas require an integer | the `schemaVersion=True` rows in both malformed-record matrices |
| Verification fingerprint states, digests, timestamps, completion/status consistency, finding shape and exact top-level fields | `test_malformed_verification_records_are_rejected` |
| Unsupported historical build and verification schemas | reader-boundary schema rejection tests |
| Malformed reports produce one concise CLI error without replacing bytes | `test_malformed_build_report_is_concise_cli_failure` |
| The report CLI formats finding location and performs no network or evidence write | `test_findings_display_location_and_field` |
| Offline CLI verification does not read the network or alter protected inputs, with and without a build report | `test_offline_cli_succeeds_without_network_or_protected_file_changes` |

## Rows retired or combined

- Five overlapping composition denial functions become three named matrix
  rows. The all-carriers row combines source-carrier removal, fallback selection
  and stale-denial reporting. The other rows retain the distinct dual-only
  different-package fallback and empty-family outcomes.
- The mocked build-success test is removed. Its status, two rendered outputs,
  exact per-variant change records and absence of `dist/report.json` are asserted
  by the real build/verify/report sequence.
- Two interruption functions become one two-row parameter. The absent and
  present evidence outcomes remain separate collected cases.
- The 22-row malformed build-report CLI matrix becomes 12 focused reader rows
  plus one CLI rejection. Retired values exercise the same predicates: list,
  object and null schema values collapse to the retained bool/int row; a second
  invalid status type, null offline record, a second invalid diagnostic field,
  and repeated unexpected-field/list-record containers are removed.
- The six-field missing-report matrix and four nested selection rows remain
  unchanged. Container and item validation each retain a representative row.
- The malformed verification matrix replaces two equivalent unexpected-field
  rows with one. State, digest, timestamp, completion, status, finding and
  bool/int predicates remain represented.
- Historical build schema cases now call the report reader directly. One CLI
  case owns exception-to-exit-status conversion and concise diagnostics.
- `test_verify.py` and `test_report.py` no longer copy current repository inputs
  or derive a composition document from committed configuration.
  `test_verification_integration.py` no longer rebuilds the same app/settings
  fixture. `verification_support.py` writes explicit empty serialized packs,
  empty denial/overlay/policy inputs and a matching empty README catalog. Its
  report builder is explicit and does not call the verifier writer, composer,
  renderer or catalog generator.

The six verification/composition/CLI modules collect 162 cases versus 175 before this batch.
Across the six replacements plus the new 59-line support module, the change has
204 inserted and 260 deleted lines, a net reduction of 56 lines.


The build fixture remains separate: sharing serialized verification inputs would precreate pack outputs and obscure first-build and rollback states. The independent verification helper calls no composer, renderer or catalog generator.

### Remaining-surface checks and execution changes

The six verification/composition/CLI modules passed 162 cases in 2.02 seconds. Final report-only annotation/import cleanup passed 53 cases. Ruff, formatting and ty passed. In-memory counterexamples applied to tracked survivors detected both denial of only the first matching carrier and acceptance of a malformed report container; original implementations passed before each probe. No production files were edited.

Full combined suite: 695 passed in 32.75 seconds. Execution comparison with the previous batch lost six lines and fourteen arcs, all belonging to Python 3.14 lazy annotation evaluation for `ingest_all`'s signature (sources/__init__.py lines 27-33). Their sole previous context was the explicitly retired signature-inspection assertion; function-body coverage is unchanged. One arc was added, catalog.py 105 to 107, from rendering an empty catalog with the minimal verification fixture. No schema/fault behavior branch became unexecuted.

Isolated CPython 3.12.14 publication suite: 112 passed in 23.59 seconds.

## Completion checks

Before whole-diff review, the suite contains 695 cases across 382 test functions and 35 test/support Python files. Test/support physical lines fall from 12,613 to 11,204, a reduction of 1,409 (11.2%). Production Python remains 6,145 lines; the ratio falls from 2.05:1 to 1.82:1. Support modules are included. Case count is not used as a correctness metric or a reduction target.

The complete 695-case run and isolated 112-case Python 3.12 run passed. Commit hooks passed Ruff formatting/lint, ty, conventional commit validation and text checks. Locked dependency validation, actionlint, zizmor, offline link checking, Nix formatting, native flake checks and `pack verify` passed. Zizmor reported its normal offline-audit limitation; native flake checking omitted incompatible systems. These checks were run during this change and their inputs did not change afterward.

Comparison with main confirms no changes to production source, scripts, workflows, configuration, frozen fixtures/evidence, generated packs, README, dependency files or public schemas. Only test/support code and this change's planning/validation artifacts differ. No device or external publication operation was performed.

### Final-batch review correction

The group review found a lost unique assertion in the empty-family denial case. It now checks the exact package/variant multiset: two dual removals and one single removal for shared.pkg. The ingestion test name now accurately describes preserved IDs and unassigned families. Four focused cases, Ruff formatting/lint and ty passed. Credential/redirect ownership remains in the unchanged source HTTP authorization, redirect and APK download tests; these passed in the full suite.

Scoped re-review of b7b66bb..a7f2c2f approved both final-batch corrections with no findings. The independent whole-diff correctness review also found no additional issues: the nonempty CLI pipeline's restricted transport and committed-pair offline test retain no-network assurance despite the smaller verification fixtures.

## Whole-diff review

Four independent named lenses reviewed main 308257e through b7b66bb: proportionality, idiomatic patterns, correctness, and publication security/failure modes. Review seats ran within available harness capacity, with later seats sequential when concurrent dispatch was rejected. There were no Critical findings.

Proportionality found an equivalent missing-release matrix row duplicating the named missing-release test. Publication review demonstrated that appending `|| true` to each of pytest, pack verification and catalog validation was incorrectly accepted by command-prefix matching. Both Important findings are accepted for one combined fix round. Idiomatic patterns had no findings; correctness had no additional findings beyond the independently corrected final-batch assertion transfer. Artifact convergence had no residual warnings to close.

### Whole-diff review fixes

The missing-release row is removed; the standalone test now owns failed status, exact guidance and no upload/edit. Remaining marker/title rows no longer carry a constant view-success parameter or optional fixture branch. Required workflow entrypoints, including full writer arguments, now use complete normalized-token comparisons. Labels, quoting and whitespace remain flexible.

Fifty affected cases and the runtime-boundary case passed; Ruff lint/format and full ty passed. Six independent in-memory `|| true` mutations (pytest, verification, catalog diff, nightly push, nightly release and source publication) passed the previous checks and fail the corrected checks. Both workflows still accept renamed labels and harmless whitespace. No workflow files changed.

### Final implementation measurements

At 7dce3f5, the full suite passed 694 cases in 33.79 seconds and isolated CPython 3.12.14 passed 111 publication cases in 26.47 seconds. There are 382 test functions and 35 test/support Python files, totaling 11,208 physical lines including all helpers. Relative to baseline, this removes 104 cases, 78 functions and 1,405 lines (11.1%). Production remains 6,145 lines; ratio 1.82:1. Protected files remain unchanged.

Coverage after both review corrections is identical to the prior consolidation run. Compared with the original baseline, the only lost execution remains six lazy-annotation lines and fourteen associated arcs from retired signature inspection; one empty-catalog arc is added. No production function-body line or behavior branch was lost.

Scoped re-review of a7f2c2f..7dce3f5 approved both whole-wave fixes with no findings. All group and whole-diff review findings are closed; no warnings are parked.

## Implementation rulings

- The existing request to implement the plan authorized materializing/converging missing planning artifacts and continuing into apply. This did not authorize separate verification or archive. A narrower reading would have required another instruction before implementation.
- Build setup stays separate from serialized verification setup because precreating packs would conceal first-build states. The trade-off is retaining a small amount of setup duplication.
- Loss of lazy annotation evaluation from the removed signature assertion is intentional; runtime body coverage is preserved. The suite no longer constrains that internal signature through introspection.
- Harness concurrency limits required sequencing some review seats and batching a distinct scoped correction review into the independent correctness seat. Every named lens and evidence duty still ran; the trade-off is elapsed time and shared context between those two narrow review duties.
