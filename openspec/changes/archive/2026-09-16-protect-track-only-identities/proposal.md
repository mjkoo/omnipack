## Why

Composition currently permits a track-only resource to be assigned to an app's family or given a different effective identity. It can then disappear behind a pin or displace the app it tracks, despite the existing requirement that tracking resources remain separate.

## What Changes

- **BREAKING**: reject candidate rules containing `family` or `packageId` when the matched ingested candidate has `trackOnly: true`, including an identity assignment equal to its original id.
- **BREAKING**: reserve track-only ids: reject any candidate that is not track-only whose effective package id, ingested or corrected by a rule, equals the id of an ingested track-only candidate, with or without a rule, so an ordinary candidate cannot join a tracker's default family and hide it by source precedence or a pin.
- Preserve ordinary APK identity corrections and family assignments, and allow track-only rules containing only a selector and rationale.
- Retire silent acceptance of these track-only transformations; use the existing composition error path to identify the offending selector.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-composition`: restrict identity and family transformations to candidates that are not track-only, and reserve track-only ids against every other candidate's effective id.

## Impact

Affects `src/omnipack/composition_policy.py` and focused policy/composition tests. No dependencies, source-generation changes, workflow changes or configuration migration are expected. Current pack bytes should remain unchanged with identical source inputs.

Estimate: modify one requirement, add six scenarios, add 15-30 implementation lines and 70-120 test lines. No new retry, ownership, race, diagnostic-format or evidence requirement is introduced. Existing visible failure and a rerun after correcting configuration suffice; no recovery mechanism is added.
