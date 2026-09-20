# Implementation validation

Implementation is in progress. This record covers local implementation checks;
the separate OpenSpec verification and archive workflows have not run.

## Baseline

At `0b852ce`, `just test` passed 758 tests in 26.94 seconds with 94% total
coverage under CPython 3.14.7. The uv cache was redirected to a writable temporary
directory because the sandbox does not permit writing the normal user cache.

The captured-input comparison uses `current_configuration_fixture` from
`tests/current_config_support.py`: committed configuration and codm2000 catalog,
with the repository's captured RJNY and BBoi34 records. Before implementation,
rendering produced:

| Variant | Bytes | SHA-256 |
| --- | ---: | --- |
| single | 100927 | `e367488d7c67ad6eb3d07395f5b60b111147859d292e0050c4d1eab61d0534a5` |
| dual | 128017 | `bdc5a9645d42d81ce3256f971af342a75120622d1c3414914c4cd9c50ea9df47` |

## Deliberately left alone

The retained-failure diagnostic character cap, the unchanged-tree PR-body edit,
and the workflow timeout and retention values remain outside this change. A
write-job rerun after its candidate hand-off expires fails in the workflow's
download step before either publication script; that workflow-only outcome has
no new script test.

Findings derived from unavailable inputs remain as before. This change removes
only false missing-input reports for unreadable inputs and the README's duplicate
unreadable report; it does not suppress independent or dependent composition
findings.

## Ingestion characterization

Commit `c3ac383` adds the ingestion coverage below. The focused source suite
passed 112 tests and `just test` passed 766 tests with 94% coverage. Independent
evidencing review approved the group without findings; `0816ca1` records its
completed checkboxes.

| Task | Test | Scenario evidence |
| --- | --- | --- |
| 1.1 | `test_non_rjny_catalog_metadata_is_dropped_but_unmodeled_fields_render` | Catalog metadata is removed while unrelated fields survive rendering |
| 1.2 | `test_codm_declared_source_type_wins_and_omitted_type_is_derived` | Declared codm2000 HTML wins over URL inference; an omitted type derives GitHub |
| 1.3 | `test_upstream_record_without_declared_source_type_is_rejected` | RJNY and BBoi34 reject missing source declarations |
| 1.4 | `test_empty_configured_location_names_source` | Empty BBoi34 and codm2000 locations identify the source |
| 1.5 | `test_build_keeps_tracking_resource_beside_the_app_it_extends` | A build retains the resource identity and settings beside the extended app |
| 1.6 | Independent evidencing review | Each test maps to its requirement; the empty-location scenario is retained baseline text rather than a modified delta |

## Implementation rulings

- The staging summary promises that staging failed and gives its reason. It does
  not name the internal stage. `StageOutcome.summary` returns
  `stage failed: HEAD is not GITHUB_SHA` for a failed snapshot stage carrying
  that reason. The task and delta wording were corrected under the design's
  characterization rule; the script behavior is unchanged. If this reading is
  wrong, the internal stage remains absent from the summary.
- The cleanup instruction permits rejection tests naming the retired report
  fields and status. They protect the new format; they do not retain support
  for an incomplete report. Removing them would weaken migration coverage.
- The ingestion empty-location test maps to its retained baseline scenario.
  Requiring a delta copy would duplicate unchanged text without improving
  coverage.

## Composition characterization

Commit `d2a0d19` adds the composition coverage; `1132878` strengthens the denial
test after review. The three focused files passed 104 tests, the strengthened
test passed its focused rerun, and `just test` passed 774 tests with 94% coverage.
Ruff and ty passed after the fix. `d8563b6` records completed checkboxes.

| Task | Test | Scenario evidence |
| --- | --- | --- |
| 2.1 | `test_selector_url_must_be_normalizable_before_candidate_matching` | Candidate and pin selectors reject hostless, whitespace and invalid-port URLs during configuration parsing |
| 2.2 | `test_denial_of_a_build_eligible_for_neither_pack_is_not_stale` | The candidate remains in its family, without denied markers, exclusions or stale exclusions |
| 2.3 | `test_dual_falls_back_to_source_precedence_among_several_baseline_builds`; `test_pin_reason_is_reported_when_pin_selects_among_baseline_builds` | Dual fallback, single source precedence and explicit pin reasons |
| 2.4 | `test_committed_configuration_selects_each_baseline_extra_in_single`; `test_denied_designated_extra_fails_single_winner_guard_with_family` | The guard passes committed configuration and fails with the affected family after a package denial |
| 2.5 | Independent review and scoped re-review | Initial Important finding: empty-output assertions did not prove that the never-eligible candidate was preserved. The strengthened test does; re-review approved without new findings |

## Generation characterization

Commit `05b8bf0` adds generation coverage and corrects the staging-summary delta;
`9b1dc91` strengthens the retained-failure test after review. The two focused
files passed 143 tests, the strengthened test passed its focused rerun, and
`just test` passed 782 tests with 94% coverage. Ruff and ty passed.
`ad955c9` records completed checkboxes.

| Task | Test | Scenario evidence |
| --- | --- | --- |
| 3.1 | `test_generated_apk_entry_preserves_consumer_fallback_setting` | Both configured fallback values survive rendering when the newest matching release resolves |
| 3.2 | `test_generated_tracking_entry_preserves_release_title_filter` | A track-only entry accepts and exports its title filter |
| 3.3 | `test_reject_nonportable_regex`; `test_unicode_sensitive_regex_escapes_fail_before_discovery`; `test_track_only_rule_requires_a_nonempty_rationale`; `test_tracker_instruction_requires_named_canonical_host` | Rejected regex classes, rationale and installation-path requirements |
| 3.4 | `test_stage_summary_reports_failure_reason_or_successful_base_revision` | Failed staging reports failure and reason; successful staging reports its base revision |
| 3.5 | `test_retained_failure_reproducing_main_closes_open_proposal` | Retained baseline scenario "A retained failure reverts a proposed update"; actual staging output drives publication |
| 3.6 | Independent review and scoped re-review | Initial Important finding: a hard-coded publish input failed to establish the stage-to-publish path. The test now passes `StageOutcome.changed`, `sha` and `base_sha`; re-review approved without new findings |

## Publication characterization

Commit `e85932a` adds
`test_rerun_after_own_push_fails_as_main_advanced_through_cli` for task 4.1. It
lands the candidate on the local test remote, then checks direct and entry-point
failure, the "main advanced" summary and unchanged remote main. The focused
publication suite passed 42 tests; `just test` passed 783 tests in 29.46 seconds
with 94% coverage.

For task 4.2, independent review found the new test over-specified the summary
format. The first fix (`90aacf3`) changed the wrong assertion; the scoped review
caught it. The final correction (`c8497bd`) restores the existing test and
narrows only the new test's two assertions to the promised phrase. Coordinator
inspection of the net diff and two passing focused tests resolved that mechanical
finding under the review-round cap. `f510587` records completion. If this ruling
is wrong, a harmless formatting difference could pass; the required diagnostic
and failing outcome remain asserted.

## Report changes

The initial focused regression run produced seven expected failures and four
passes: legacy completion-state acceptance (two cases), obsolete schema
acceptance, the `Complete:` display line, and double reports for unreadable
single-pack, denylist and README inputs. Missing-input and missing-timestamp
characterization already passed. After the implementation, all 133 focused
report, verification and offline tests passed. Null and timezone-naive
completion timestamps are rejected by the malformed-record parameterization;
absent completion timestamps are rejected by the exact-shape check.

| Task | Evidence |
| --- | --- |
| 5.1 | `test_removed_verification_state_is_rejected`, `test_previous_verification_schema_requires_regeneration`, `test_verification_display_has_no_completion_flag`: observed expected failures before implementation |
| 5.2 | Verification schema 4 writer and exact-shape reader; removed incomplete-state display test; malformed completion-timestamp and missing-timestamp tests remain enforced |
| 5.3 | `test_unreadable_input_is_reported_once_without_being_called_missing` fails for a pack, configuration file and README before the fix and passes after it; `test_genuinely_missing_input_remains_reported_as_missing` preserves the missing case |
| 5.4 | `test_absent_unpinned_losing_candidate_cannot_be_assessed_offline`; `test_interrupted_verification_does_not_replace_evidence` calls `main(["verify"])`, interrupts inside validation, and compares prior report bytes |
| 5.5 | `pack --help` displays "print available build and verification reports" |
| 5.6 | `docs/verification.md` describes standalone schema 4 without a completion field and retains build schema 3; `just check-links`: 552 links, 332 unique, 53 checked, zero errors |
| 5.7 | The pre-existing local schema 3 verification report failed with the `pack verify` regeneration diagnostic. After `pack verify`, `pack report` exited zero with `Evidence: current`, no regeneration diagnostic and no `Complete:` line |

Ruff and ty passed. The build report's schema constant and documented version
remain 3. The unreadable-input change is confined to `verify.py`; the pure offline
validator's API and derived composition findings stay unchanged.

The first full run after the report fix passed 795 tests and exposed one existing
README test that required the retired duplicate catalog error. That test now
asserts the single `input_unreadable` code for an unreadable README and
`catalog_invalid` for its missing, malformed and stale cases. Its six focused
catalog tests pass.

The corrected full run passed 796 tests in 25.72 seconds with 94% total coverage;
`verify.py` has 100% coverage. No production build-schema change was made.

Commit `cb42f10` implements tasks 5.1-5.7. A further isolated mutation check
removed only the unconditional completion-timestamp guard from a temporary copy
of the current package. The malformed-record suite then failed exactly its
invalid-string, null and timezone-naive `completedAt` cases (3 failed, 11 passed),
proving that the preserved tests detect the parked regression. The checkout was
not mutated. The absent-field case remains protected by exact report-shape
validation.

Task 5.8: independent evidencing review approved `cb42f10` with no findings.
It confirmed all task-to-code/test mappings, completion-timestamp enforcement,
the preserved derived findings, verification schema 4, unchanged build schema 3
throughout the documentation, and only intentional rejection tests referencing
the retired report state.

## Main-spec synchronization

Commit `edd890f` implements tasks 6.1-6.5. Commit `5ca19e6` records task 6.6's
independent evidencing review, approved with no findings.

| Task | Evidence |
| --- | --- |
| 6.1 | Seven selected deltas synchronized without archiving; `openspec validate --specs --strict` passes 10/10; `openspec list --specs --json` totals 70 requirements |
| 6.2 | Purposes updated for family composition, source identity and request credentials, publication/catalog/release handling, and source-generation CLI coverage |
| 6.3 | Shared HTTP helper has an antecedent; stale-exclusion vocabulary is consistent; the overlay scenario names the patch field; heading separation and the three specified prose rewraps are applied |
| 6.4 | Eight scenario titles now describe their bodies; modified requirements use identical titles in delta and main spec; both strict validations pass |
| 6.5 | Grep over main specs, the active change, README, docs, source and tests found old names only in required rename metadata and the task edit list, with no stale normative reference |
| 6.6 | Independent comparison: all 24 modified blocks match after trimming boundary whitespace, and all 15 quoted cross-capability pointers resolve to exact requirement titles |

The parked selector-URL concern is resolved by stating normalization, a readable
host, a valid numeric port when present and no whitespace in both delta and main
spec. The existing scenario now includes invalid ports, supported by the earlier
candidate-rule and pin tests. No selector acceptance behavior changed.

The proposal's spec findings are covered by the synchronized requirements:
source metadata/type handling and composition pointers; single owners for
selection, exclusion and eligibility; curation outcome guards; generation
regex/settings/tracking/summary wording; publication-attempt and rerun outcomes;
and report freshness/display ownership. Retired change-era sentences,
duplicated statements, stale titles, purposes and formatting are corrected in
the same spec commit. The report-state and diagnostic findings are covered by
the implementation evidence above. The intentionally untested diagnostic and
workflow values remain listed under "Deliberately left alone."

## Final validation before the whole-branch review

Task 7.1: `just check-all` exited zero. The first sandboxed attempt passed the
796-test suite and offline verification but could not access the Nix daemon for
the Python 3.12 check. Re-running with daemon access completed all checks:

- Locked dependency check, formatting, lint and types passed.
- CPython 3.14.7: 796 tests passed in 25.41 seconds, total coverage 94%.
- Offline `pack verify` passed.
- CPython 3.12.14 write-side checks: 108 tests passed in 18.45 seconds.
- Actionlint and zizmor passed; zizmor reported no findings.
- Offline documentation links: 552 total, 332 unique, 53 checked, zero errors.
- Nix formatting changed zero files; flake evaluation passed for the local
  `aarch64-darwin` system. Nix emitted its expected notice that incompatible
  systems were omitted; no cross-platform flake build is claimed.

Task 7.2: rendering the same captured-input configuration after implementation
produced bytes identical to the baseline, not merely equivalent JSON. Single
remains 100927 bytes with SHA-256
`e367488d7c67ad6eb3d07395f5b60b111147859d292e0050c4d1eab61d0534a5`;
dual remains 128017 bytes with SHA-256
`bdc5a9645d42d81ce3256f971af342a75120622d1c3414914c4cd9c50ea9df47`.
