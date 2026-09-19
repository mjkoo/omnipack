# Maintainer documentation validation

Validation performed 2026-09-18 on the implementation branch. This change edits
consumer documentation only; the planning and validation records accompany it.
No live source generation, live build, release write or device access was needed.

## Baseline and editing guidance

- Full baseline: `uv run pytest --cov`, 686 passed, 93% coverage, no warnings.
  The first sandbox invocation could not use the default uv cache; a temporary
  cache then lacked network access to build dependencies. The authorized run
  with the normal cache completed successfully.
- Before the repair, extracting the composition page's overlay JSON and calling
  `parse_overlay`, `apply_overlay` and `render` raised `RenderError` because
  `additionalSettings` was a string. After repair the same path rendered
  `versionDetection: false` while preserving an existing
  `includePrereleases: true` setting. This exercised the actual example, not a
  separately reconstructed patch.
- The composition page's complete policy and denial examples passed
  `parse_composition_policy` and `parse_exclusions`; the policy contained one
  candidate rule and one pin. The development page's extracted extra passed
  `sources.extras.fetch` with both variants eligible, and adding `dualScreen:
  true` limited eligibility to dual. Field names and original-selector mapping
  were checked against `composition_policy.py`, `sources/common.py` and the
  schema-3 report producer. Catalog category fallback and sorting were checked
  against `catalog.generate_catalog`.
- Manual path review: an ordinary overlay edit skips generation, builds, uses
  the pack/README diff against the PR base rather than the id-only report delta,
  then verifies and includes changed outputs. A codm policy edit generates,
  reviews that invocation's successful report and catalog, explicitly copies
  the candidate, and joins that same build/review path. A successful no-op
  requires intended report evidence or an expected inert edit: denial removal
  without stale exclusion, or the intended selection for a pin or rule.
- Conflict review: regenerate packs/catalog-region bytes; hand-merge only README
  prose outside markers. For a codm catalog conflict, use main as the base for
  fresh generation, reinspection and acceptance, then build. No instruction
  calls the automated staging script for manual acceptance.
- Compared `.github/workflows/ci.yml`, `.github/workflows/source-catalog.yml`
  and `scripts/source_proposal.py`: CI verifies committed packs offline; the
  source check job additionally builds; the proposal allowlist is only the codm
  catalog. Generated packs are neither proposal content nor uploaded artifacts.
- `pack --help` and `pack generate-source --help` confirmed the command surface.
- `just check-links`: 553 total links, 332 unique, 52 checked OK, zero errors
  (remote links excluded by the existing offline command).

## Publication and curation wording

- Compared curation and publishing wording with `scripts/nightly_write.py`
  `run_release`, `_upload` and `_edit`, and the rolling-pack-release spec:
  served digests are inspected before choosing unchanged/repair/advance;
  repair uploads without an edit; advance uploads then edits; neither branch
  performs a post-upload readback. The stable URLs can expose mixed or missing
  assets and the publishing page owns the raw-main fallback explanation.
- Curation now has a single-line non-atomic visibility note and a publishing
  link. Device acceptance remains explicitly separate. Rollback retains only
  restoring extras/overlay and rebuilding, with no release timing assertion.
- Ludashi review: composition owns deferred migration and retained selection
  and source-version policy; curation owns the current APK filter and older
  release fallback. Neither passage credits a past change; identity uncertainty
  and migration/device precautions remain.
- `just check-links`: 555 total, 333 unique, 54 checked OK, zero errors.
  Publication and policy fragment targets were also checked against headings;
  the offline link checker does not establish remote-link availability.
- `git diff --check`: passed.

## Remaining validation

- The abridged composition report example passed `format_reports` when its
  omitted fields were supplied by the existing `tests.test_report.build_report`
  helper. The displayed result contained its original id, effective id and pin
  reason. `parse_project_policy` accepted the committed codm rules whose behavior
  the source-generation reference illustrates; the baseline's fixture checks
  `test_reviewed_policy_sets_fallback_for_named_projects` and
  `test_committed_catalog_is_valid_canonical_and_composable` passed.
- Inspected help for `pack build`, `verify`, `report`, and `generate-source codm`:
  each documented invocation is supported. No live operation was invoked by
  checking help. The automated commands remain descriptions of automation.
- `uv run pack verify`: exit 0, successful offline verification. It ran with a
  writable temporary uv cache after dependency setup; the command and checked
  inputs were unchanged.
- Reviewed the report wording against `verify.INPUT_PATHS` and report staleness
  logic: development links to the owning fingerprint list without repeating it,
  and states that edits outside that set do not stale evidence until outputs
  change. Existing `test_verification_only_report_is_current_then_stale` passed
  in the baseline suite.
- `git diff --check`: passed. `git diff --name-only main...HEAD` contained only
  the five planned documentation paths and this change's artifacts. Production
  code, configuration, workflows, pack outputs and README were unchanged.

## Implementation review evidence

- Editing guidance review: independent reviewer approved `d70d119..d12759c`.
  Each of 1.1, 1.2 and 1.3 has implementation in `d12759c` and the parser,
  render, path-trace and workflow-comparison evidence above. No findings.
- Publication wording review: independent reviewer approved
  `d12759c..3c3d448`. Each of 2.1 and 2.2 has implementation in `3c3d448` and
  runtime/spec comparison, cross-page ownership and link evidence above.
  No findings. No exceptions or deferred implementation were accepted.
- Validation-group evidencing review approved `3c3d448..2ecf13a` for 3.1 with
  parser/render, fixture, CLI, link, verification and scope evidence. Task 3.2
  remains pending the final process gate and audit.
- Two independent final-wave reviewers examined `189e2cf..2ecf13a`: one for
  maintenance/publication correctness and one for documentation idioms,
  ownership and proportionality. Both reported no Critical, Important or Minor
  findings. No fix round was necessary. The correctness reviewer closed the
  parked categories warning: the recipe strongly recommends categories and
  states first-entry heading/sort behavior and the `Other` fallback, consistent
  with catalog generation. No warnings were deferred.
- All 14 local fragment links on the edited pages resolve to actual headings;
  the final link pass again found 555 total, 333 unique, 54 checked OK and zero
  errors. No prose-only tests were added.

## Completion audit

The fresh independent checkbox auditor examined `189e2cf..aaa5852` after the
review wave and the process evidencing review. All six checked tasks were
CONFIRMED, with zero UNEVIDENCED tasks and no Critical findings. The process
review approved all completed review stages; the auditor confirmed that this
successful audit satisfied the final condition for the seventh task, which
remained unchecked until that result.

| Task | Implementation/evidence commit | Proving checks |
| --- | --- | --- |
| 1.1 | `d12759c` | Extracted examples through parsers and overlay renderer, preserved settings, selector and category checks |
| 1.2 | `d12759c` | Ordinary/codm/no-op and conflict path traces, CLI help, report and staging boundary inspection |
| 1.3 | `d12759c` | Main/source workflow and catalog-only staging/allowlist comparison |
| 2.1 | `3c3d448` | Release branches and rolling spec comparison, visibility/fallback and rollback inspection |
| 2.2 | `3c3d448` | Cross-page Ludashi ownership and retained precautions review |
| 3.1 | `2ecf13a` | Parser/fixture checks, baseline suite, CLI help, offline verification, links, diff and path audit |
| 3.2 | `aaa5852` and this audit record | Three group evidencing reviews, two independent final-wave reviews, process review and fresh 6/6 checkbox audit |

No implementation exception, deferred warning or discretionary ruling was
needed. The change remains active. The separate OpenSpec verification and
archive workflows were not invoked.

Final post-audit suite: `uv run pytest --cov` passed all 686 tests in 23.91s,
93% coverage, no warnings. The final whitespace check passed. Only task status
and this evidence record were updated after the audit; no implementation fix
or behavior change followed the gate.

## Post-audit editorial pass

A later independent read of the shipped pages re-derived every factual claim
from source and found none wrong: catalog heading, sort and `Other` fallback in
`catalog.generate_catalog` with no colour claim; the repaired overlay example
through `parse_overlay` and `merge_patch`; `changes` against the pre-build id
snapshot; the fingerprinted set and staleness rule owned by the verification
page; the upload, served-digest, repair and advance branches of `run_release`;
the nightly allowed paths; both CI workflows; and the proposal staging path.
`uv run pytest` (686 passed), `uv run pack verify` (exit 0), `just check-links`
(555 total, 333 unique, 54 OK, zero errors) and `git diff --check` all passed
again. All new fragment links were resolved against actual headings by hand,
because the offline link checker does not follow fragments.

Three editorial defects were then repaired, changing no claim: a stray blank
line in the source-generation page, a ragged wrap in the development page's
verification paragraph, and an ambiguous sentence that said `pack report` does
not print "those id lists" while the following step sent readers to two more
lists it also omits. That sentence now names `selections` as the one list the
command prints. Links, whitespace and the suite were rechecked after the edits.

## Post-verification naming repair

Verification re-derived every factual claim from source a second time and found
none wrong. One naming imprecision was repaired, changing no claim: the manual
acceptance step named the staging entry point as `scripts.source_proposal
stage`, while the source-catalog workflow invokes it as `python -m
scripts.source_proposal stage`. The step now uses the invocable form. Links,
whitespace and the suite were rechecked after the edit.
