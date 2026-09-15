## Why

The suite contains 12,613 Python lines against 6,145 application and script lines, with 798 collected cases. An assertion-level audit found misleading tracker coverage, a timestamp-dependent APK oracle, repeated scenarios, and expensive test-only infrastructure. Consolidating now reduces maintenance before adding behavior.

## What Changes

- Repair tracker composition and APK identity assertions.
- Retire 17 duplicate or misleading test functions, transferring four useful assertions to surviving scenarios.
- Consolidate publication fixtures and structured workflow contracts, keeping distinct write and failure outcomes.
- Simplify curation and catalog fixtures and remove low-risk validation and filesystem permutations.
- Record surviving behavioral ownership, counterexample probes, and explained execution-coverage changes.

## Capabilities

### New Capabilities

None. This is test maintenance with no observable product behavior change.

### Modified Capabilities

None. Specs are explicitly skipped because all existing requirements remain intact.

## Impact

Only tests and change-local planning/validation records change. Production source, scripts, workflows, current configuration, frozen evidence, generated packs, public interfaces and dependencies remain unchanged. Estimated additions: zero requirements, zero normative scenarios, zero production lines, and 200-400 replacement test/helper lines before removals. The initial 17 removals span 353 lines; broader consolidation should yield a net reduction, with no numerical quota. No new retry, ownership, race, diagnostic or evidence requirement is introduced.
