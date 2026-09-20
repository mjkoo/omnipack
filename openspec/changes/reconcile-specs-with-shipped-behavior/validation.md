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
Surviving generation scenario names are unchanged. Independent review approved
commit `75eaa74`, all three tasks evidenced, no findings.

## Curation and main-spec synchronization

The curation, port-curation, tracker and source-generation fixture modules pass:
**20 passed**. Existing tracker tests already assert identity, release-title
pattern, version extraction, release selection and background notifications,
and the exact rendered key set. No tracker assertion was missing.

Before removing tracker data from main normative text, each of these independent
configuration mutations made the tracker suite fail at its assertion, with no
setup errors: id, name, repository URL, categories, release-title regex,
prerelease admission, fallback, extraction regex, match group, release-title
versioning, latest-tag verification, sort method, asset-date versioning,
release-date versioning, version detection, track-only mode, background-update
exemption, notification suppression, and adding `installedVersion`. The original
`config/extras.json` bytes were restored after each of the nineteen runs.

`test_committed_configuration_selects_each_baseline_extra_in_single` already
computed coverage from reviewed extras and single-pin exemptions. Its diagnostic
now names the missing families using the real composition policy projection.
A probe composed the current candidates with an additional denial of the
unpinned tracker, successfully produced both variants, and ran that check: it
failed naming `package:809443320`, proving the regression check catches an
omission that composition accepts. No configuration mutation remains.

`test_maintained_version_override_survives_refreshed_source_settings` now changes
all ingested candidates' version-detection setting, composes and renders them,
and asserts every reviewed disabling override still wins. Temporarily bypassing
overlay application makes this test fail; source bytes were restored.

The existing `test_committed_catalog_is_valid_canonical_and_composable` guards
both suite-owned validity rules. Direct probes against the same assertion block
confirmed failure for a track-only nonnumeric id, enabled version detection,
enabled ZIP inclusion, enabled architecture filtering, an invalid APK package
id, and an APK entry switched to track-only. Appending a newline to the catalog
also fails canonical byte equality; its original bytes were restored. These are
suite obligations, not additional pipeline guarantees.

The catalog-stage audit confirms `codm.fetch` rejects malformed documents and
repeated ids, whereas generation's `_load_catalog` rejects malformed documents,
repeated ids and repeated normalized projects. No ingestion adapter checks
normalized-project uniqueness. The direct accepted-catalog tests added with the
generation coverage evidence the distinction. No pipeline stage checks the
committed catalog's kind-specific ids/settings or its canonical file bytes.

The four main specs were synchronized through the separate sync workflow:
12 modified requirements, 1 retired requirement and 1 title-only rename.
The deltas add 13 new scenarios, relocate 1 unchanged scenario, and rewrite 5
in place. All surviving scenario names and all untouched requirement blocks
are preserved. Both main-spec and change strict validation pass. The initial
merge helper rejected its overly broad heading regex before writing any spec;
a line-bounded heading parser completed the merge.

Searches across other main specs, README and `docs/` found no contradictory
restatement requiring an edit. Consumer-facing names and tracker instructions
in README and `docs/curation.md` correctly describe current configuration;
removing per-app values from normative requirements does not remove consumer
instructions. The nightly verification/publication boundary remains valid.
The synchronized curation text names no test file, fixture or assertion recipe.
The retired requirement is absent from main composition, and the fallback
scenario now occurs once under union and precedence. Independent review approved
commit `cda98ba`, all three tasks evidenced, no findings. A separate block-by-block
comparison confirmed every untouched requirement is unchanged and every modified
requirement matches its delta.

## Whole-change checks

Captured upstream records were composed with committed configuration in two
separate Python processes, one importing source extracted from the branch base
`ce8f09ca9e32ca78bbc4b0af2b5cf93c8101bc24`, the other importing the implementation
checkout. Both used the existing current-configuration fixture and real renderer.
Import paths were checked to ensure each process used its own source tree.
The resulting bytes were compared directly, not merely by digest:

| Variant | Bytes | SHA-256, identical before and after |
| --- | ---: | --- |
| single | 100927 | `e367488d7c67ad6eb3d07395f5b60b111147859d292e0050c4d1eab61d0534a5` |
| dual | 128017 | `bdc5a9645d42d81ce3256f971af342a75120622d1c3414914c4cd9c50ea9df47` |

The branch diff leaves `src/`, `scripts/`, `config/`, committed exports, and
README unchanged. These captured-input renders are deliberately distinct from
the committed exports, which reflect a different upstream snapshot.

Checks after implementation:

- Full suite with coverage: **756 passed**, 94% source coverage, no test warnings.
- Python 3.12 publication-script suite: **105 passed**.
- Locked dependency check, Ruff formatting and lint, and ty: passed.
- Offline `pack verify`: complete, success, no errors for the committed pair.
- Actionlint and Zizmor: no findings. Zizmor reports its default offline mode;
  network-dependent audits are outside that invocation.
- Offline documentation links: 553 links, 332 unique, 54 checked successfully,
  499 excluded, zero errors.
- Nix formatting: no changes. Flake checks: passed on aarch64-darwin; the command
  reports incompatible platforms omitted, as expected on this host.
- Strict OpenSpec validation: the active change and all 10 main specs passed.
  Main-spec length notices are informational, not validation failures.

The initial combined invocation of the optional-argument Python 3.12 recipe
mistook the following recipe name for an interpreter; separate invocations
passed. Nix's cache required execution outside the filesystem sandbox, and the
approved rerun completed all remaining checks without modifying project files.

Independent group review approved the byte-preservation and repository-check
evidence in commit `4ea6725`. The whole-diff wave and its fix are recorded below;
the final checkbox audit is the remaining gate.

## Whole-diff review fix

The review found two redundant GitHub query and fragment cases in
`test_project_identity_retains_non_github_query_fragment_and_every_port`.
Those cases were removed; the matrix retains all seven distinct non-GitHub
query/fragment and all-host port cases and asserts that each changes identity.
The existing exact-output assertions in `test_normalize_project_url` remain
unchanged and continue to cover GitHub query and fragment removal.

To verify that coverage after the removal, a temporary mutation made
`normalize_project_url` retain GitHub queries and fragments. Running the existing
`test_normalize_project_url` produced **3 assertion failures and 7 passes**:
the query-only, fragment-only, and combined query/fragment inputs each failed
their expected canonical output. There were no collection or setup errors.
The source file was restored in a `finally` block and checked byte-for-byte
against its original contents. No production source change remains.

The focused URL suite passed all **20 tests**. After source restoration, the
full suite passed **754 tests** without test warnings; the earlier **756-test**
coverage run above is historical evidence from before the two duplicate cases
were removed. The new full-suite invocation did not collect coverage.
Repository-wide Ruff lint, Ruff formatting, and ty checks passed.
The fix changes only URL tests and this validation record. Independent scoped
review of `4ea6725..d61a402` approved the fix with no findings. The completion
audit is the remaining gate.


## Independent whole-diff review

Four reviewers examined `ce8f09c..4ea6725` with separate lenses:

- Specification correctness: approved, no findings. All four main-spec merges
  preserve surviving scenario names and stage ownership.
- Public failure boundaries and meaningful tests: approved, no findings. Tests
  exercise real pipeline code and distinguish the documented failure modes.
- Idiomatic patterns: approved, no findings. Tests reuse established fixtures,
  keep session inputs immutable, and contain no planning-identifier leakage.
- Proportionality: found only the two redundant GitHub matrix cases. The single
  fix commit `d61a402` removed them, and its scoped re-review approved the fix.

Every residual convergence note was closed explicitly: the tracker guard is on
the branch base; scenario accounting is 13 new, 1 relocated and 5 rewritten;
characterization tasks use temporary mutations; the maintainer's manifest-evidence
obligation is not a runtime check; GitLab empty components are documented; HTTP
and too-short paths are covered. Previously accepted findings about ports,
transport retries, catalog validity, GitLab host spelling and overlay diagnostic
contents now agree with the shipped behavior. Later explanatory-clause errors
about scheme comparison and duplicate overlay-target ownership are absent.

The one review ruling was to accept removal of two redundant assertions because
existing exact-output assertions discriminate the same GitHub behavior more
strongly. The cost if that judgment were wrong would be reduced regression
coverage; a new mutation check confirmed that the retained assertions fail for
both query and fragment preservation.
