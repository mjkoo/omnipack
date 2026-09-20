# Implementation validation

This change characterizes existing behavior. Source modules, publication scripts,
reviewed configuration and published pack bytes must remain unchanged.
The baseline is `ce8f09ca9e32ca78bbc4b0af2b5cf93c8101bc24`.

## Baseline

The full suite passed before implementation: **699 passed**. Commands use
`UV_CACHE_DIR=/private/tmp/omnipack-uv-cache` and `uv run --offline` because the
sandbox cannot write the normal uv cache. No dependencies were changed.

## Ingestion

`tests/test_sources.py` and `tests/test_urls.py`: **126 passed** against unchanged
source. No delta correction was needed.

| Contract | Executable evidence |
| --- | --- |
| Configured upstream locations and source semantics | `test_rjny_matches_both_upstream_exports`, `test_bboi_latest_release_retains_both_asset_origins`, `test_codm_loads_committed_catalog_and_suppresses_dual_coverage` |
| Latest means upstream's latest on every invocation, regardless of asset version | `test_bboi_reads_the_current_latest_release_on_every_run` updates the fake latest response from version 9 to version 1 and asserts both request sequences |
| Exactly one asset per pattern, with source and pattern diagnostic | `test_bboi_requires_exactly_one_asset_per_configured_pattern`, zero and two matches for each pattern, with no asset download |
| Invalid configured locations and failed ingestion | `test_rjny_rejects_empty_location_and_unsupported_source`, `test_codm_missing_catalog_names_source`, `test_build_ingestion_failure_leaves_existing_outputs_untouched` |
| Routine ingestion reads catalogs without README or APK discovery | The source fixtures provide only catalog and latest-release responses; `test_bboi_reads_the_current_latest_release_on_every_run` asserts all requests |
| Comparison identity, including schemes, case, suffixes and GitHub path folding | `test_normalize_project_url`, `test_normalized_urls_identify_the_same_project`, `test_project_identity_retains_non_github_query_fragment_and_every_port` |
| Normalized identity at matching boundaries | `test_codm_loads_committed_catalog_and_suppresses_dual_coverage`, composition overlay and policy tests, and generation duplicate-order and policy-key tests |
| Variant-specific identities, upstream duplicates, committed duplicate rejection | `test_rjny_applies_export_flags_and_ignores_presentation_overrides`, `test_upstream_duplicate_package_ids_survive_ingestion`, `test_codm_rejects_duplicate_ids` |
| Native GitLab acceptance precedes comparison; host/scheme case, path case/encoding and empty components | `test_gitlab_acceptance_preserves_path_case_and_encoding`, `test_explicit_gitlab_extra_precedes_url_inference_and_preserves_subgroups` |
| All GitLab boundary rejections identify entry and URL | `test_explicit_gitlab_extra_rejects_urls_outside_public_boundary`, including HTTP, wrong host, too few/many components, credentials, port, query, fragment, reserved separator and www |
| GitLab hydration and rendered native source | `test_hydration_fills_sparse_settings_in_canonical_order` and existing GitLab composition/import-link integration coverage |
| Renamed committed-source requirement retains generated identity and dual eligibility | `test_codm_loads_committed_catalog_and_suppresses_dual_coverage`, `test_codm_reports_committed_apk_and_tracker_identities`, `test_codm_suppression_follows_source_dual_eligibility` |

The maintainer's primary-manifest evidence obligation is not pipeline behavior
and has no runtime assertion. No GitLab discovery implementation was introduced.

Temporary source mutations were run independently and restored byte-for-byte:

| Mutation | Observed failure |
| --- | --- |
| Remove asset-cardinality guard | All four pattern/count cases fail their expected diagnostic |
| Remove committed duplicate-id rejection | Duplicate-id test no longer raises |
| Deduplicate upstream results by id, separately in RJNY and BBoi | Each source's retention case fails |
| Discard all non-GitHub query/fragment identity | Four non-GitHub cases fail |
| Retain GitHub query/fragment | Both GitHub cases fail |
| Discard explicit ports | All three host cases fail |
| Bypass native GitLab validation | All twelve invalid-URL cases fail |
| Reject every GitLab URL | All four accepted spelling/path cases fail |
| Lowercase the native GitLab project path | All four path-preservation cases fail |
| Keep www in comparison identity | All four acceptance/comparison cases fail |
| Drop latest-release ingestion results | Current-latest test fails |

All original scenario names in surviving ingestion requirements are retained;
the committed-catalog rename changes only the title. Independent review is pending.
