# Implementation validation

Implementation branch: `align-publication-reporting`.

## Report diagnostics

The formatter displays all recorded candidate additions/removals, exclusions,
stale exclusions and admissions between selections and failure details. Failed
build comparisons are labelled `Candidate (not published)`; null comparisons
are unavailable. Empty categories emit nothing. The stored report validator,
writer and schema version remain unchanged.

Validation on 2026-09-19:

- Baseline: `uv run pytest --cov` passed all 691 tests (93% coverage).
- Red: `uv run pytest tests/test_report.py tests/test_cli.py -q` produced
  7 expected failures and 84 passes before the formatter change. Failures covered
  both populated build statuses, unavailable comparison, malformed exclusion,
  stale exclusion and admission elements, and command-level display.
- Green: the same focused command passed all 91 tests after the formatter change.
- `test_recorded_build_diagnostics_are_displayed_in_full` loads the existing
  schema directly and checks every entry in 40-element lists, both variants and
  both directions, success and failure wording, ordering, and unchanged bytes.
- `test_empty_and_unavailable_comparisons_are_distinct_cli_output` asserts exact
  command output and zero exit status for empty and null comparisons.
- `test_malformed_diagnostic_elements_raise_report_format_error` checks malformed
  fields in each of the three object lists. The existing malformed build-record
  test covers invalid candidate comparisons, which are mappings rather than lists.
- `test_build_then_report_displays_diagnostics_without_changing_report` runs the
  real build with fixture HTTP transport and checks all diagnostic categories and
  byte preservation. No external network or device access is needed.

The sandbox prevents use of the default uv cache; checks use
`UV_CACHE_DIR=/private/tmp/omnipack-uv-cache` without changing project configuration.

## Maintainer documentation

The development guide now directs maintainers to `pack report` for all recorded
lists, including admissions. It retains the limits of the package-id comparison
and the check that a newly denied id appears among exclusions, not stale denials.
It describes empty, unavailable and failed comparisons and no longer promises
warnings. `just check-links` passed: 553 links, 0 errors. Strict OpenSpec artifact
validation passed with `openspec validate align-publication-reporting --strict`.

Independent group review of `b9aebc0..f76a129`: approved with no findings.
The reviewer mapped all three report tasks to the implementation commit and
the named formatter, malformed-record and command integration tests above.

## Publication requirement evidence

These corrections require no changes to workflow or publication scripts:

- `scripts/nightly.py`, `PrepareOutcome.summary_line`, returns `prepared <sha>`,
  `no-op at <sha>`, or the failing stage. `_run_prepare_command` writes that line
  to the step summary. `test_prepare_cli_writes_changed_sha_and_base_for_a_candidate`
  and `test_prepare_cli_writes_changed_false_for_a_no_op` assert these summaries.
- `.github/workflows/nightly.yml` places both artifact uploads in `prepare`:
  the candidate bundle has one-day retention and diagnostics have 14-day retention
  with `always()` and missing-file ignore. `publish` depends on `prepare`, so
  neither upload follows a push. The handoff and permission tests in
  `tests/test_publication_workflows.py` inspect this job graph and artifact paths.
- `scripts/nightly_write.py`, `run_push`, pushes the verified SHA and then
  checks it out detached. Checkout failure returns `detach-failed` with
  `published <sha>`; `main` appends that summary and returns 1. The subsequent
  release step has no failure override, so it does not run after this failed
  step. `test_detach_failure_after_a_landed_push_reports_published_and_fails`
  induces a real post-push checkout failure and asserts the remote commit,
  summary and nonzero exit. The workflow test checks the release has no `if`
  override. No release command runs inside `run_push`.
- The nightly delta replaces the complete main-spec requirement "Nightly
  completion includes rolling release synchronization". Its opening now
  conditions the post-push synchronization promise on establishing the pushed
  commit locally. The remaining main-spec references describe successful
  publication, verified-byte eligibility, or release-failure scenarios; none
  separately promises an unconditional post-push release write. The rolling
  release delta owns the explicit failure and later verified no-op repair rule.

### Split preservation

The removed "Actions records publication outcomes" requirement distributes its
rules as follows. The reporting replacement retains step/log failure records;
main and release outcomes; push failures and release reasons/bootstrap guidance;
report existence, 14-day retention and structural scope; no issue maintenance or
issue permission; visible diagnostics failures; and exclusion of credentials,
raw caches and APKs with source text treated as data. Its corrections add the
prepared outcome, qualify release reporting by whether the stage ran, and
separate pre-push upload failures from post-push summary failures.

The credential replacement retains empty workflow permissions, write-job-only
contents write, read-only preparation and setup, no project dependencies or
build/verification in the write job, fresh triggering-revision checkout, git
object handoff with one-day retention, standard-library-only scripts on runner
Python, triggering-revision and base guards, environment-only output transfer,
full SHA validation, credential-limited steps, hooks-disabled git, no persisted
checkout credential, and documentation of permissions, push prerequisites and
bootstrap without automatic repository-setting changes. The two replacements
thus preserve the original credential boundary together.

| Original scenario | Replacement owner | Disposition |
| --- | --- | --- |
| Setup fails before reports exist | Reporting | Unchanged |
| Reused workspace fails before verification | Reporting | Unchanged |
| Release fails after a confirmed push | Reporting | Unchanged |
| Reporting fails after publication | Reporting | Restated as Diagnostics fail around publication |
| Build runs without the publication credential | Credential | Unchanged |
| Write job runs no project build | Credential | Unchanged |
| Read-only job names another revision | Credential | Unchanged |
| Push outcome is summarized | Reporting | Unchanged |
| Sensitive or executable source text | Reporting | Unchanged |

Every original scenario appears exactly once. The prepared-candidate scenario
is additional. Source-text safety remains with reporting; the credential's
reach remains with isolation. `test_publication_permissions_and_runtime_boundaries`,
`test_handoff_connects_checked_candidate_to_writer`,
`test_base_guard_rejects_stale_revision_before_consumption`, and
`test_malformed_shas_are_rejected_before_any_fetch_or_push` exercise the boundary.
`workflow_support.git` disables hooks; the existing write-side runtime tests
check standard-library-only imports. All these existing tests passed unchanged
in the 691-test baseline.

Independent documentation review of `f76a129..404e770`: approved with no
findings; the reviewer confirmed the guide changes and link-check evidence.
