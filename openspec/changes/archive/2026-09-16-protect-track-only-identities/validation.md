# Implementation validation

Branch: `protect-track-only-identities`.

## Behavior and regression evidence

The pre-change full suite passed: 646 tests. Before implementation, the focused
policy suite failed seven cases: prohibited family, changed and restated identity,
corrected and ingested reserved-id collisions, descriptive-rule collision, and
selector precedence over rendered projections. Composition/CLI regressions failed
four cases before implementation. After implementation, all 117 focused policy,
composition, CLI and tracker tests passed.

The guard gathers every ingested track-only id before inspecting candidates,
uses exact boolean true, checks every collapsed candidate before transforms and
projections, and retains original selectors in errors. Controls cover descriptive
tracker rules, two trackers sharing an id, non-boolean settings, ordinary APK
rules and correction away from a reserved id.

## Captured-source compatibility

The shared current-configuration fixture ingested 130 candidates from captured
RJNY and BBoi inputs, committed extras and the generated catalog. All ordinary
effective ids were audited against all six ingested track-only ids:
`1845280017`, `476086958`, `767644078`, `809443320`, `904332840`, `994078275`.
No collisions occurred, including among candidates later excluded.

Rendering the same captured inputs before and after the guard produced identical
UTF-8 bytes for both variants:

| Variant | Bytes | SHA-256 |
| --- | ---: | --- |
| single | 102039 | f55841cc37706d93256f67b679c9b61eaf52f9fe05f61bf285cb3d0c8626f56f |
| dual | 129129 | d4b0ffe433274c4c6fbb63c753daaeb9836b2593e0933aecdf90e763a22a55bd |

No configuration migration is needed for these inputs. This audit does not claim
future upstream inputs cannot collide. Later overlay changes remain outside the
ingested-settings guard, as designed.

## Checks

Locked dependency check, formatting, lint, type checking, offline pack verification
and strict change validation passed. Independent reviews and final suite results
are recorded below.

## Independent implementation-group review

The independent evidencing reviewer approved `d59a15a..ab4efb4` with no
Critical, Important or Minor findings. It linked each implementation task to
`ab4efb4`, the policy/composition/CLI regression tests, and the captured-source
audit and byte comparison above. The reviewer used the reported focused green
result; the subsequent full-suite transcript independently records 663 passing
tests with 93% coverage.

Workflow lint and offline documentation links passed (542 links examined, zero
errors). Zizmor reported its default offline-mode notice and no findings; online
audits were not run. Configuration, committed packs and workflows have no diff
against main. No ADB or device access was performed.

The Python 3.12 compatibility suite passed all 104 tests. Nix formatting passed
without changes. The flake check passed for the host, aarch64-darwin; Nix reported
that incompatible systems were omitted. This is host validation, not an
all-systems build. Initial sandbox cache-access failures were resolved by rerunning
with cache and daemon access.

## Whole-diff review wave

Three independent reviewers examined the full main merge-base through `ab4efb4`.
The production correctness and idiomatic-patterns reviewers returned no findings.
The proportionality reviewer found one redundant third candidate in
`test_track_only_violation_precedes_earlier_rendered_projection_conflict`: the
earlier track-only record already reserves the same id. Removing the redundant
record preserves the test's failure discrimination. No production defect or
scope change was identified. No accepted or parked warnings remained from the
planning review, and no residual note became a production finding.

The fix commit `bc9c3e8` removes only that redundant candidate and initializes the
earlier track-only candidate directly. All 29 policy tests, Ruff checks and
commit hooks passed after the fix. The assertion identifying the offending
ordinary candidate is unchanged.

The scoped re-review approved `ab4efb4..bc9c3e8` and confirmed the sole finding
resolved, with no remaining findings. The independent validation-group review
approved the recorded checks and completed review-wave work in `edf2304`.

## Completion audit

A fresh independent auditor confirmed all four completed implementation/check
boxes with commit and test evidence and found zero gaps. It also confirmed the
review/fix/evidence portions of the final review task and authorized its completion
mark upon successful audit. Evidence maps to `ab4efb4` for the implementation and
regressions, `bc9c3e8` for the test simplification, and `edf2304` for the durable
validation and review record. No findings were deferred and no scope exceptions
were taken. The change remains active on `protect-track-only-identities`.

After the completion audit, the final full-suite rerun passed all 663 tests in
29.04 seconds. OpenSpec apply reports 5/5 tasks complete. Separate verification
and archive workflows were not invoked.

## Follow-up code review

A later review of the new code found no correctness or completeness defects and
raised idiom points, all addressed without changing behavior. The track-only
checks moved into a private helper that shares one track-only predicate and one
effective-id computation with the rule transform, and its error messages now wrap
like the rest of the module. Parametrized tests take their cases as data rather
than branching on a mode, the CLI test imports its helpers at module level, and
the current-configuration tracker test no longer repeats the check composition
already performs; it asserts only that track-only candidates exist to reserve.
One composition case was added: a rule correcting an ordinary candidate's
`packageId` onto a track-only id fails before a pin or a denial can hide it.

With the policy module restored to its pre-change version, all 13 track-only
behavior tests failed. With the change, the full suite passed 665 tests, and Ruff
format, Ruff lint, ty and strict change validation passed.
