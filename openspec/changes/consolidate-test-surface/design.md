## Context

See proposal.md for motivation. The audited baseline is main at 308257e: 460 test functions, 798 cases, 12,613 test lines, 6,145 production lines including scripts. All tests passed. Subtracting execution contexts of the 17 shortlisted functions lost no executed production lines or arcs. This establishes overlap, not assertion equivalence.

## Goals / Non-Goals

Keep distinct correctness and publication outcomes and independent expected values. Retire repeated low-risk filesystem faults, equivalent schema values and implementation-layout checks. Do not pursue a line-count target, introduce a testing framework, modify production abstractions to help tests, expand asset-filter acceptance, or remove frozen provenance fixtures. Verification of serialized output remains separate from composition because its input can be edited independently.

## Decisions

### Repair and shortlist

Use real composition over current configuration and captured upstream inputs for tracker checks: exactly one per pack, equal rendered records, essential track-only settings and absent installed/latest version fields. Check actual candidate identities instead of banning raw text in fixtures. Make APK ZIP timestamps fixed and parameterize expected agreement outcomes explicitly. Remove the generator's HEAD check against the unrelated development repository, retaining input preservation and cleanup.

Remove these exact functions (names relative to tests/):

| Module | Function |
|---|---|
| test_cli.py | test_build_failure_does_not_mutate_committed_catalog |
| test_pack_tracker.py | test_observed_revision_is_not_rendered_state |
| test_model.py | test_eligibility_is_required_and_no_variant_field_remains |
| test_source_generation_fixtures.py | test_a_pretty_printed_catalog_is_not_canonical |
| test_sources.py | test_each_source_prefers_exactly_its_dual_only_builds |
| test_sources.py | test_codm_suppression_holds_when_a_rule_regroups_the_covering_candidate |
| test_composition.py | test_selection_reasons_name_pin_preference_fallback_and_source |
| test_composition.py | test_compose_rejects_differing_records_with_one_original_identity |
| test_source_http.py | test_redirect_reselects_credentials_without_forwarding_source_token |
| test_source_http.py | test_redirect_to_unregistered_host_strips_source_token |
| test_verify_catalog.py | test_historical_reports_require_regeneration |
| test_report.py | test_structural_mode_is_explicit |
| test_nightly_write.py | test_successful_round_trip_lands_commit_and_detaches |
| test_nightly_write.py | test_rejected_push_fails_without_advancing_remote |
| test_nightly_write.py | test_matching_record_and_served_digests_makes_no_write |
| test_nightly_write.py | test_a_branch_whose_name_ends_in_main_does_not_hide_the_real_main |
| test_source_proposal.py | test_base_sha_line_in_summary_names_the_branch_creation_commit |

Transfer version-field absence into real tracker composition, structural/offline wording into current/stale report coverage, remote main preservation into rejected-push logging, and summary Base SHA into source-stage success. Remove unused helpers/imports. Focused adapter, policy, urllib redirect and helper exact-ref tests retain ownership of the other scenarios.

### Publication and workflows

Use one small explicitly imported publication support module for isolated Git setup, command execution, repository/bundle setup and transparent fake GitHub responses. Imports must be standard library plus pytest so the isolated Python 3.12 suite remains independent of the application environment. No application-loading global conftest or scenario DSL.

Combine preparation success assertions for bot identity, allowed paths, bundle/base/run metadata, retaining changed and no-op CLI outcomes. Own shared dirty-checkout/wrong-SHA/wrong-parent handoff validation at workflow_support, with one rejected-call propagation case per publisher. Preserve caller-specific allowlist/mode checks. Use an explicit valid-release fixture with overrides and retain unchanged, advanced, repaired, bootstrap, upload-failure and edit-failure sequences. Consolidate equivalent failure setup without dropping checks preventing writes.

Replace name-specific workflow checks with shared parsed contracts: permissions, checkout refs and credential persistence, check-before-write dependencies, changed/no-op conditions, base guard before artifact consumption and token use, matching artifact names and output/environment wiring, validation before handoff upload, essential entrypoints, action pins, cache restrictions and unsafe expression rejection. Locate by action types, step IDs and environment wiring. Normalize shell tokens and execute the base-guard snippet with equal/unequal SHAs; do not simulate workflows. Remove cron, timeout, runner, retention, display-name, whitespace and immediate-adjacency requirements. Retain actual Python 3.12 CI execution and simplify AST import checks by dropping annotation and relative-import style demands.

### Curation and catalog

Share one real current-configuration composition fixture using current extras, policy, denials, overlays and committed catalog with captured upstream inputs. Replace designation/mismatch infrastructure with direct selected-original-selector assertions for baseline extras. Exempt families with explicit single pins; derive only the exemption from declared candidate-rule family, corrected package ID or original identity, without production policy application for expected selection. Keep corrected-identity behavior in policy tests and demonstrate one representative displacement counterexample. Remove helper meta-test matrices.

Validate committed catalog uniqueness, kinds and canonical bytes once. Replace the dynamic removable-project search and its self-validating fixture variants with a small explicit baseline/add/remove example proving generated catalog changes do not affect single. Preserve frozen golden pair and independent manifest identity mappings. Remove repeated identical refresh loops and static capture-date/hash-length assertions; retain intentional curation settings.

### Remaining surface

Consolidate denials into same-package carriers removed, different-package fallback and empty-family outcomes. Keep distinct same-package/cross-package selection, pins, ties, stale overlays and protected-field rejection. Keep real build/verify/report pipeline and transfer unique report assertions before removing mocked success duplicates.

Reduce transaction faults to second-output staging and replacement failures, with/without existing packs. Keep README rollback integration, cleanup, a non-default permission and new-file permissions. Share minimal verification inputs, focus malformed-report cases at reader boundary, retain one CLI rejection. Keep missing fields, distinct validators and bool/int distinctions; reduce equivalent wrong-value permutations. Remove signature, object identity and projection layout assertions when behavior survives. Replace copied color calculation with fixed values and trim redundant counts/equalities. Keep HTTP credentials, redirect, bounded-read and retry/error outcomes without exact request/read choreography.

## Risks / Trade-offs

### Approved follow-up audit

Delete the unused catalog support module. Reduce the nine-case build integration
product to three successful prior-output states and two validation failures,
covering absent and existing outputs. Keep all three stage-failure diagnostics;
rendering and report writing each need one prior-output state, while publication
keeps both. Retain bool/int and zero/negative boundaries while trimming equivalent
release identifiers, retired-field values, nonobject exclusions, malformed source
values and generic unknown-field rows already covered by explicit retired names.

Move Cinderbox presence and rendered settings checks onto current composition.
Remove its hand-built insertion from the historical overlay fixture; keep exact
historical settings and unrelated-field preservation, and independent manifest
correction evidence. Combine retained-failure Markdown/HTML escaping in the
summary-and-body scenario, preserving pre-block containment, quotes and body
handoff. Consolidate nightly allowlist, push rejection and stage symlink setup
without retiring distinct path/mode outcomes or introducing a scenario framework.

Remove the repeated identical generation failure before recovery, transfer the
undeclared GitLab inference row to the existing URL table, and remove frozen
fixture counts and repeated file-content checks already covered by exact snapshots.
Drop the assertion about the helper-created empty catalog interior. Retain the
compact render-permutation loop: reducing its iterations does not simplify its
two-line expression. Confirm substantive assertion transfers with temporary
counterexamples and explain any lost production line or arc execution.

- Execution overlap can hide lost assertions. Record a surviving test for each retained outcome and use temporary counterexamples for substantive replacements.
- Representative fault/schema cases intentionally reduce permutation coverage. Enumerate any lost production execution and attribute it to an explicitly retired low-risk permutation; unexplained losses block completion.
- Helper abstraction can obscure scenarios. Keep helpers small, data explicit, imports isolated, and count support code in final totals.

## Migration Plan

Implement ordered batches on refactor/test-surface with review after each commit range. Confirm baseline tests and coverage in the branch. Require no lost executed production lines/arcs after the shortlist; normalize coverage identities when comparing. Run affected tests after each batch and full tests, isolated Python 3.12 publication tests and repository checks at completion. Temporary probes must show tracker disappearance, curated-extra displacement, rejected handoff and broken base guard fail their checks, while ZIP timestamp variation does not change APK identity expectations. Persist check results and survivor ownership in the change directory without references to ignored material. Confirm source/scripts/workflows/configuration/fixtures/generated outputs unchanged. No deployment or runtime migration; revert test changes if needed. Leave apply complete and the change active for separately requested verification.
