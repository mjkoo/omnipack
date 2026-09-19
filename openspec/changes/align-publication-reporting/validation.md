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
