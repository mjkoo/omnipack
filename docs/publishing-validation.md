# Publishing implementation validation

Controlled validation was performed on 2026-09-08 on macOS aarch64 with Python
3.14.7 and uv 0.12.5. This record describes local implementation checks, not a
successful live nightly refresh or a GitHub Actions dispatch.

## Commands and results

| Check | Result |
| --- | --- |
| Focused `tests/test_nightly_*.py` suite | 67 passed |
| `just check-all` | Passed, including all 637 Python tests |
| `actionlint .github/workflows/nightly.yml` | Passed with actionlint 1.7.12 |
| `zizmor --persona pedantic .github/workflows/nightly.yml` | No findings with zizmor 1.30.0 |
| Runtime-independent entrypoint and reporting syntax | Python 3.10 grammar accepted |
| Distribution and configuration integrity | SHA-256 comparison unchanged for every file; no Git diff |

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
| Publication and retry races | `test_publishes_one_allowlisted_commit_with_metadata`, `test_main_advancement_discards_candidate_and_runs_fresh_attempt`, `test_lost_push_ack_is_reconciled_by_remote_ancestry` |
| Issue ownership and recovery | `test_failure_discovers_every_page_and_normalizes_owned_issues`, `test_ambiguous_create_rediscovers_before_any_retry`, `test_published_result_survives_issue_failure_and_later_success_retries_closure` |
| Redaction and artifact selection | `test_diagnostics_are_per_attempt_redacted_and_identify_missing_reports`, `test_artifact_selection_is_an_explicit_regular_file_allowlist` |
| Workflow boundary | `test_system_python_module_entrypoint_does_not_import_project_runtime`, `test_helper_fallback_reloads_confirmed_outcome_instead_of_resetting_it`, `test_upload_outcome_updates_persistent_result_and_summary` |

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
acceptance run is claimed here. See [publishing](publishing.md) for that
procedure, permissions, diagnostic limitations, and rollback.

Official GitHub documentation was checked for
[token-authored push triggers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow),
[direct-push restrictions](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches),
and [artifact retention](https://github.com/actions/upload-artifact/tree/v7#retention-period).
The upload action's release tag was resolved to its immutable Git commit before
pinning the workflow. No repository permission or branch-rule setting was
changed as part of verification.
