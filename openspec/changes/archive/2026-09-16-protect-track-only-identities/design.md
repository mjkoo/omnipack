## Context

See proposal.md for motivation. Policy parsing has selectors but no candidate settings. `apply_composition_policy` receives normalized candidates, matches rules, and applies identity/family changes before exclusions and selection. Settings are already decoded from object or JSON-string source forms.

## Goals / Non-Goals

**Goals:** reject invalid transformations where both the matched rule and ingested settings are available, and reject any ordinary candidate whose effective id takes a track-only id, using the existing error and output-preservation paths.

**Non-Goals:** changing track-only generation, pin or denial semantics, overlay settings, generic settings type validation, or offline verification of source-only candidates. Track-only ids are reserved against every other candidate's effective id, but this change makes no claim to prevent other identity collisions or later settings edits.

## Decisions

### Guard matched candidates before transforming them

In `apply_composition_policy`, when a matched candidate's normalized `additional_settings` has boolean `trackOnly` true, reject a non-None `family` or `package_id` on its rule using `CompositionPolicyError` and the existing selector formatter. Checking presence rejects even identity restatements. Existing parsing already rejects null or empty assignments. Rules containing only match and rationale stay valid.

Apply the guard uniformly across sources, before exclusions and selection. A denylist must not hide an invalid rule. Parsing alone cannot perform this check because track-only status comes from source records. Rejecting only family assignment would leave identity corrections able to alter the default family, so both are forbidden. Track-only ids are also reserved: any candidate that is not track-only whose effective id (its rule's `package_id` when present, otherwise its ingested id) equals the ingested id of a track-only candidate fails with that candidate's selector, whether or not it has a rule, because it would otherwise land in the tracker's `package:<id>` family where precedence or a pin could hide the tracker. A correction onto a tracker id and an ingested source collision are both cases of this one invariant. Use exact boolean true; broad validation or coercion of malformed settings is outside this change.

Both checks run in one pass over all collapsed candidates before any rule transform and before the existing per-candidate rendered-projection check. The pass first builds the set of ingested ids whose settings have `trackOnly` exactly true, then rejects a track-only candidate whose rule has `family` or `package_id`, and rejects a candidate that is not track-only whose `rule.package_id or app.id` is in that set. The projection check then runs only after every candidate has passed. Because collapsed candidates keep input order and the projection check names the first contradicting candidate, running it first could name an unruled tracker, or another candidate sharing the offending rule's effective id and normalized URL, instead of the candidate whose rule or ingested id violates the track-only restrictions; the separate pass makes those selector-bearing errors take precedence regardless of candidate order.

### Reuse existing behavior and evidence

Keep APK rules, projections, pins, exclusions and overlays unchanged. The readme-source-generation contract already requires resources not to replace their host app; the new enforcement belongs in pack-composition, so no duplicate requirement is added there.

Add compact policy tests for family assignment, changed/restated package id, an ordinary correction to a track-only id, an ordinary ingested id equal to a track-only id without a rule, an offending candidate that shares an id and normalized URL with an earlier-ordered candidate, descriptive rules and APK controls. A composition case should demonstrate rejection despite a pin or denial that would otherwise hide the resource. Reuse current-configuration composition and tracker tests, and compare rendered bytes before and after with identical captured source inputs. Use one existing CLI failure harness to confirm invalid policy preserves prior outputs; do not expand filesystem fault matrices.

## Risks / Trade-offs

- A previously accepted configuration becomes invalid, either because a rule transforms a track-only candidate or corrects an ordinary id onto a tracker id, or because an ingested ordinary record already collides with a tracker id: report the offending candidate's selector so the maintainer can remove the transformation, apply a supported correction of the ordinary candidate's effective id, or fix the source record. No current configuration is expected to trip either case; confirm this against current captured candidates, including ingested collisions onto tracker ids, during implementation.
- Later overlays can change settings: the guard intentionally evaluates ingested settings, without extending this change into overlay policy.
- Offline verification cannot reconstruct all ingested candidates: retain the build-time boundary rather than inventing incomplete source reconstruction.

## Migration Plan

No configuration or generated-output migration is expected. Implement on an isolated branch under the implementation workflow, retain behavior/spec changes together, and validate against captured inputs plus the full suite and repository checks. A rollback reverts the guard, tests and spec delta together; no external state needs repair. Leave the change active after implementation and its required reviews.
