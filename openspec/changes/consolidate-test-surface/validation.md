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
| Release ownership/bootstrap failures | `test_missing_release_marker_or_title_fails_with_bootstrap_guidance`; `test_draft_non_prerelease_or_immutable_fails_with_bootstrap_guidance`; `test_release_not_found_is_missing_with_bootstrap_guidance` |
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
