# Nightly publication validation

Validation date: 2026-09-11, macOS aarch64, Python 3.14.7 and uv 0.12.5.
These are local development checks and controlled publication tests. They do not
establish live GitHub publication or Obtainium device acceptance.

## Results

`just check-all` passed: lock validation, Ruff formatting and lint, Ty, dependency
audit, Python sdist/wheel builds, all 594 tests, structural pack verification,
workflow lint, Nix formatting and native flake checks. The suite took 23.57 seconds
with 92% package coverage. The dependency audit found no known vulnerabilities or
adverse project statuses in 10 packages.

Zizmor reported no findings in its default offline mode; online-only audits were
not run. Nix reported the expected working-tree notice and omitted incompatible
systems. Its aarch64-darwin checks passed; this is not Linux validation.

The focused publication, reporting, workflow and retained release suites passed
106 tests. Strict change validation and all nine main-spec validations passed
after synchronizing the two capability deltas.

## Behavioral evidence

| Boundary | Evidence |
| --- | --- |
| Selected workspace and clean tracked tree | `test_uses_selected_workspace_head_without_another_checkout`, `test_rejects_initial_tracked_changes_before_refresh` in [Git tests](../tests/test_nightly_git.py) |
| Build, then fresh structural verification | `test_refresh_runs_build_then_candidate_structural_verification`, `test_failed_gate_stops_without_candidate`, `test_bad_structural_evidence_rejects_candidate` in [candidate tests](../tests/test_nightly_publish.py) |
| Verified bytes and allowlisted commits | Retained candidate tests cover symlinks, README boundaries, staging mutations, file modes, cache/catalog-only output and no-op; `test_publication_uses_byte_changes_without_mode_drift` checks real commit trees |
| One main attempt and ambiguous pushes | Git tests cover advancement before push/no-op, rejected push races, lost acknowledgements, remote uncertainty and full ancestry from shallow history |
| Independent release readiness | `test_seed_discovery_fails_release_after_main_publication` covers missing, malformed and unowned seeds; failure/uncertainty tests prohibit release writes |
| Repair after a later fresh no-op | `test_failed_release_is_repaired_by_later_fresh_noop_without_extra_revision` uses the real synchronizer, a controlled release remote and two fresh runs; main advances once and release repair completes revision one |
| Confirmation survives reporting failure | `test_confirmed_main_log_is_flushed_before_release_and_survives_reporting_failure` uses an actual local push, checks flush before release work, and injects a later helper failure |
| Redaction and diagnostics | [Reporting tests](../tests/test_nightly_reporting.py) check available reports, regular-file allowlisting, JSON log encoding, redaction and summary escaping |
| Actions failures and permissions | [Workflow tests](../tests/test_nightly_workflow.py) check repository/ref guards, early setup failure, summary/helper errors and the upload contract: always run, accept missing files, retain 14 days, and expose upload errors |
| Release state and transport | Retained [release tests](../tests/test_nightly_release.py) cover bootstrap, ownership, digest/revision state, asset repair, bounded requests and authentication/redirect restrictions |

Artifact-upload behavior is checked against the committed workflow configuration;
no real Actions upload was performed. The result artifact records known main and
release outcomes without claiming the subsequent upload or overall workflow result.
Actions step status remains authoritative for those outcomes.

## Preservation and reduction

All 717 captured baseline files matched their SHA-256 hashes after implementation.
This includes exports, curation configuration, fixtures, existing archived plans,
dated validation evidence and protected review records. New review records are
retained separately. No fixture exports or curation policy changed.

Python physical lines changed from 7,467 to 6,786 across `src/` and `scripts/`, and
from 10,836 to 9,976 under `tests/`: reductions of 681 implementation lines and
860 test lines. The suite changed from 628 to 594 tests as retired issue,
retry and fallback guarantees were removed and related tests consolidated.
These are measured reductions, not a quota.

The active publishing, verification and development guides were checked for valid
relative links, plain hyphens, and consistency with one workspace, one attempt,
CI-owned code checks, Actions diagnostics and independent main/release outcomes.
Historical records retain the retired behavior and legacy issue ownership marker.

All Git publication tests used temporary local repositories, and release responses
were controlled. No main push to GitHub, release write, workflow dispatch, issue
migration or repository-setting change was performed. Follow
[publishing](publishing.md) for the separate maintainer acceptance procedure.
