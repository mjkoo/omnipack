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
- `test_changed_candidate_writes_bundle_and_body_with_run_url_and_base_sha` now proves the summary names the branch-creation base SHA.

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
