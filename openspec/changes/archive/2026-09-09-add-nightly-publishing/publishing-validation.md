# Publishing implementation validation

Controlled validation was performed on 2026-09-08 on macOS aarch64 with Python
3.14.7 and uv 0.12.5. This record describes local implementation checks, not a
successful live nightly refresh or a GitHub Actions dispatch.

## Commands and results

| Check | Result |
| --- | --- |
| Focused `tests/test_nightly_*.py` suite with scoped `init.defaultBranch=master` | 81 passed |
| `just check-all` | Passed, including all 651 Python tests |
| `actionlint .github/workflows/nightly.yml` | Passed with actionlint 1.7.12 |
| `zizmor --persona pedantic .github/workflows/nightly.yml` | No findings with zizmor 1.30.0 |
| Runtime-independent entrypoint and reporting syntax | Python 3.10 grammar accepted |
| Distribution and configuration integrity | All 11 file SHA-256 hashes unchanged; no Git diff |

These are the final results after review fixes. The focused suite took 16.03
seconds; the Python suite in `just check-all` took 20.08 seconds. The Git default
was set only for the focused test process using `GIT_CONFIG_COUNT=1`,
`GIT_CONFIG_KEY_0=init.defaultBranch`, and `GIT_CONFIG_VALUE_0=master`; no user
Git configuration changed.

`just check-all` included lock consistency, formatting, lint, types, dependency
audit, source/wheel builds, tests, offline pack verification, workflow lint,
Nix formatting, and native Nix flake checks. Package coverage was 91%; the
coverage configuration measures the package, while the automation scripts are
exercised by their focused tests. Zizmor used offline mode and the repository's
existing suppression. Nix omitted incompatible systems and passed all native
checks. These tool notices do not establish validation on other platforms.

## Behavioral evidence

| Surface | Representative proving tests |
| --- | --- |
| Fresh gates and exact bytes | `test_refresh_orders_checks_build_and_metadata_only_verification`, `test_bad_live_evidence_rejects_candidate`, `test_candidate_rejects_staged_content_mismatch` |
| Byte-only publication and staging races | `test_candidate_ignores_mode_changes_and_preserves_base_mode`, `test_publication_uses_byte_changes_without_mode_drift`, `test_candidate_rejects_unrelated_mutation_after_capture` |
| Selected-revision verifier contracts | `test_retry_validates_evidence_with_selected_revision_runtime` |
| Publication and retry races | `test_publishes_one_allowlisted_commit_with_metadata`, `test_main_advancement_discards_candidate_and_runs_fresh_attempt`, `test_lost_push_ack_is_reconciled_by_remote_ancestry` |
| Issue ownership and recovery | `test_failure_discovers_every_page_and_normalizes_owned_issues`, `test_ambiguous_create_rediscovers_before_any_retry`, `test_published_result_survives_issue_failure_and_later_success_retries_closure` |
| Redaction and artifact selection | `test_diagnostics_are_per_attempt_redacted_and_identify_missing_reports`, `test_artifact_selection_is_an_explicit_regular_file_allowlist` |
| Cleanup after confirmed publication | `test_cleanup_failure_preserves_confirmed_publication_and_fails_workflow` |
| Workflow boundary | `test_system_python_module_entrypoint_does_not_import_project_runtime`, `test_helper_fallback_reloads_confirmed_outcome_instead_of_resetting_it`, `test_upload_outcome_updates_persistent_result_and_summary` |

The regression tests reproduced mode-only commits, executable-bit drift,
unrelated tracked mutations after capture and during staging, cleanup errors
escaping after a successful push, valid newer-revision evidence being rejected,
and Git fixtures failing under a master default before the fixes. Each passes
with the fixes. The mode cases also check actual local remote commit counts
and tree modes. The selected-revision test executes copied committed runtime
source in separate Python processes, advances verifier identity, schema, and an
input path, accepts matching evidence, and rejects each old-contract mismatch.
The cleanup test exercises the workflow entrypoint and helper fallback after a
real local push: workflow failure stays visible, confirmed SHA and both reports
survive, and the existing issue-recovery policy creates no failure issue.

Follow-up reporting regressions also reproduced an interrupted JSON rewrite
losing the confirmed publication in helper fallback, and offline evidence
being presented without identifying missing live evidence.
`test_interrupted_finalization_write_preserves_publication_for_fallback` and
`test_offline_report_is_retained_without_claiming_live_evidence` failed before
the fixes and pass after them. The former retains the SHA and both attempt
reports through fallback; the latter preserves offline diagnostic content
while identifying live evidence as unavailable.

Fallback regression coverage additionally checks that a helper failure remains
a workflow failure through successful artifact upload, without losing the
confirmed publication. `test_fallback_preserves_missing_report_markers` checks
that reloaded missing-report placeholders remain unavailable in both the
orchestration result and summary. Both assertions failed before their fixes
and pass afterward.

Process/API responses are controlled, and real Git transport tests use only
temporary local repositories. No test pushed to GitHub, created a real issue,
dispatched a workflow, changed repository settings, or changed the repository's
dist/config/package-id-cache bytes. Local check commands can update ignored
test, packaging, and offline verification output. They do not perform a live
pack build or asset probe.

## Documentation checks

The publishing guide and README were compared with the workflow and helper
constants for the schedule, repository/main guard, concurrency, timeout,
three-file commit allowlist, retry budget, issue marker/ownership, retention,
and metadata-only command. The named tests above exercise the described
behavior. Relative documentation links were checked against existing files.

The guide's acceptance procedure explicitly requires a future maintainer
dispatch on main, prerequisite checks, fresh evidence inspection, confirmed
publication/no-op, and recovery inspection when applicable. No operational
acceptance run is claimed here. See [publishing](../../../../docs/publishing.md) for that
procedure, permissions, diagnostic limitations, and rollback.

Official GitHub documentation was checked for
[token-authored push triggers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow),
[direct-push restrictions](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches),
and [artifact retention](https://github.com/actions/upload-artifact/tree/v7#retention-period).
The upload action's release tag was resolved to its immutable Git commit before
pinning the workflow. No repository permission or branch-rule setting was
changed as part of verification.
