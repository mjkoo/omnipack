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
the committed-catalog rename changes only the title. Independent review approved
commit `ab55847`: all three ingestion tasks evidenced, no findings. The reviewer
checked implementing modules, existing coverage and scenario-name preservation.

## Composition

`tests/test_composition.py` and `tests/test_composition_policy.py`: **91 passed**.
The first test draft assumed an extra `composition.` diagnostic prefix; inspecting
the real diagnostic corrected that test expectation. The delta requires the
selector and invalid origin, which the existing diagnostic supplies, so no delta
or source correction was needed.

- `test_selector_origin_must_belong_to_its_source_before_matching` checks both
  candidate rules and pins directly at policy parsing, before candidate matching.
- `test_overlay_unknown_field_identifies_record_and_field` checks record position
  and field. `test_overlay_blank_or_nonstring_key_identifies_field_without_value`
  checks empty, whitespace, numeric and null values in each key. Exact expected
  messages also prove the invalid value is omitted.
- `test_overlay_hostless_url_identifies_record_field_and_value` checks that the
  nonempty invalid URL is included in this diagnostic.
- Existing `test_dual_falls_back_to_source_precedence_among_several_baseline_builds`
  covers the carried fallback rule, and
  `test_build_ingestion_failure_leaves_existing_outputs_untouched` covers the
  distinct failed-source outcome.

Temporary mutations and results: removing source/origin membership checking fails
both selector cases; allowing unknown overlay fields fails its case; bypassing
id validation fails all four id cases; bypassing URL validation fails all four
URL cases; removing the hostless URL value from its diagnostic fails that case.
Every mutation was restored before the next one.

A search of `src/`, tests, README and `docs/` found no dependency on the retired
composition requirement. Inspection of composition, build and verification found
no post-composition app release lookup. `docs/verification.md` describes the
separate nightly publication boundary and remains true. The carried fallback
scenario occurs once in the composition delta, under union and precedence, with
its original name and text. Main specs still hold the pre-sync version at this
point. Independent review approved commit `079dd59`, all three tasks evidenced,
no findings. A mistaken pair of module filenames in the initial review report
was corrected by a focused reread of `merge.py`, `cli.py`, `build.py`, `verify.py`
and `offline.py`; the no-lookup conclusion was confirmed.

## Generation

The generation contract, source-generation and boundary test modules passed:
**127 passed** on unchanged source. No delta correction was needed. The corrected
prerelease scenario describes list resolution with no stable-latest request and
contains no 404 claim.

| Restated behavior | Evidence |
| --- | --- |
| Exactly one selected-endpoint lookup, including transport retry | `test_generation_looks_up_only_the_rule_selected_release_endpoint`: stable, prerelease and title-filter modes, each with and without an incomplete-body retry; real HTTP client and APK manifest parsing, exact release-request lists |
| Distinct bounded-list failures | `test_release_scan_bound_is_visible`: 100 drafts vs 101 otherwise permitted releases, exact distinct diagnostics and one bounded-list request |
| Track-only APK-only settings rejected before HTTP | `test_track_only_apk_settings_fail_before_network_with_project_and_setting`: all three prohibited keys, including empty settings that would otherwise be defaults |
| Track-only prerelease and fallback settings exported | `test_track_only_release_settings_are_accepted_and_exported`: both settings accepted, endpoint selected correctly and generated entry retains the enabled value |
| Accepted catalog shape, id uniqueness and normalized project uniqueness | `test_accepted_catalog_malformed_shape_fails_generation`, `test_accepted_catalog_repeated_id_names_both_projects`, `test_accepted_catalog_duplicate_normalized_project_fails_generation` |
| Policy schema, unsupported/invalid settings, normalization and duplicate keys | Existing `test_policy_rejects_invalid_documents`, `test_policy_normalizes_keys_and_field_order`, `test_invalid_rule_fields_and_combinations`, `test_duplicate_json_policy_keys_fail_before_discovery`, `test_duplicate_policy_keys_and_inactive_rules` |
| Portable regex and group selectors | Existing `test_version_capture_references_fail_before_discovery`, `test_version_capture_references_preserve_supported_selectors`, `test_unicode_sensitive_regex_escapes_fail_before_discovery`, `test_explicit_regex_classes_and_literal_backslashes_remain_supported` |
| Project-table boundary, normalized deduplication, malformed/empty rejection | Existing parser tests plus `test_duplicate_order_and_nested_paths` and `test_malformed_second_table_cannot_propose_removal` |
| Deterministic catalog, identities, defaults and source changes | Existing `test_unchanged_inputs_reproduce_the_committed_catalog_byte_for_byte`, `test_every_invocation_resolves_every_project_afresh`, `test_readme_additions_and_removals_are_reported`, `test_cross_project_collisions`, fixture catalog-composition tests |
| Inputs and policy never rewritten | Existing `test_failed_invocation_rejects_stale_candidates_and_preserves_tracked_inputs`, `test_cli_real_generation_preserves_inputs_and_cleans_failed_candidates` |
| Strict release selection, publication metadata, drafts, title/tag matching and ID tie break | Existing `test_release_list_excludes_drafts_and_selects_newest_matching_title`, `test_latest_requires_published_stable_release`, `test_equal_publication_time_uses_numeric_id`, `test_title_filter_uses_search_and_trimmed_tag_fallback`, `test_invalid_host_release_identifier` |
| All eligible APKs, filters, agreement, bounded extraction, no execution and no older-release retry | Existing package-ID tests, `test_apk_filter_and_all_eligible_agreement`, `test_heimdall_newest_matching_release_never_searches_older_apk`, `test_failed_apk_resolution_membership_and_fallback` |
| Host-scoped credentials | Existing `test_fresh_resolution_sends_the_api_credential_only_to_the_api_host` and source HTTP credential/redirect tests |

Temporary mutations, all restored: choosing the opposite endpoint fails all six
endpoint cases; adding another release lookup fails all six; disabling transport
retries fails the three retry cases; replacing the no-permitted diagnostic fails
that bounded case; bypassing the page-size bound fails the oversized case;
allowing APK-only tracker settings fails all three cases; dropping configured
settings fails the prerelease-export case, while forcing fallback off separately
fails the fallback-export case; bypassing normalized-project uniqueness fails
its accepted-catalog case; changing the malformed diagnostic fails all four shape
cases; bypassing accepted-ID uniqueness fails the repeated-ID case.

The first draft of one mutation used a source substring that was absent and made
no edit; it was replaced with the actual settings-copy statement before running.
Surviving generation scenario names are unchanged. Independent review is pending.
