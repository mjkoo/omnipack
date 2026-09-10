# rolling-pack-release Specification

## Purpose

Provide stable JSON downloads and a native Obtainium notification source through one persistent GitHub release, without retaining nightly release history.

## Requirements

### Requirement: One owned rolling release publishes both variants

The publisher SHALL maintain one mutable prerelease at tag `continuous` in `mjkoo/omnipack`, with title `omnipack revision N` for a nonnegative integer N and assets named `single-screen.json` and `dual-screen.json`. The release SHALL carry the exact ownership marker `<!-- omnipack:rolling-pack -->`. The publisher SHALL NOT create per-run releases, per-variant releases, or delete and recreate the established release or tag. A pre-existing unowned or malformed release SHALL be a blocking conflict, not permission to overwrite it. The release tag SHALL remain a stable locator; recorded published commit metadata SHALL identify asset provenance rather than implying the tag advances with every asset upload.

#### Scenario: Another successful nightly changes the pack

- **WHEN** the owned release exists and verified JSON content changes
- **THEN** the same release id and tag remain while its assets and revision are updated

### Requirement: Revision changes follow completed content publication

The publisher SHALL compare the pair of desired JSON byte digests with the pair recorded for the last completed release revision. Equal content SHALL preserve the revision; changes to either JSON SHALL advance it once after both desired assets have been verified remotely. Documentation-only, cache-only and unchanged nightly runs SHALL NOT advance it. Final release assets SHALL exactly match a fresh verified pair associated with a confirmed main publication or verified main no-op. Unknown main publication outcomes SHALL prohibit release mutation.

GitHub asset replacement is not atomic across the pair. The publisher SHALL NOT claim atomic download visibility during uploads, and SHALL advertise the new revision only after confirming both assets. The release SHALL retain sufficient owned state to distinguish the previous completed revision from an in-progress target, its digests and source commit.

#### Scenario: Second asset upload fails

- **WHEN** one replacement succeeds and the other fails
- **THEN** the published title revision stays unchanged, the run fails, and diagnostics identify partial release synchronization

#### Scenario: No JSON changes

- **WHEN** fresh verification succeeds and both desired assets match the last completed revision
- **THEN** no revision is added, even if main received a cache or catalog commit

### Requirement: Release synchronization is resumable and bounded

Release read and write operations SHALL use bounded requests and retries. Ambiguous writes SHALL be reconciled by reading owned remote state before retrying. A later fresh verified run SHALL repair pending or missing assets even when main requires no new commit. Missing or corrupt assets for unchanged completed content SHALL be repaired without advancing the revision. An acknowledged or remotely confirmed completed target SHALL NOT increment twice. A superseding target SHALL reconcile against the last completed pair and SHALL NOT promote a stale pending target. Authentication errors, immutable-release restrictions and ownership conflicts SHALL fail without changing repository settings or touching unrelated releases.

#### Scenario: Final title update succeeds but response is lost

- **WHEN** readback confirms the desired revision, digests and both assets
- **THEN** synchronization is recorded as complete without another increment

#### Scenario: Later run repairs interrupted publication

- **WHEN** main is a verified no-op but the release is incomplete
- **THEN** the publisher reconciles the verified pair and completes or repairs publication instead of skipping the release stage

### Requirement: Bootstrap and device acceptance are explicit

Initial activation SHALL establish an owned revision-zero prerelease as a tracking seed before live verification of exports containing the tracker. The seed SHALL clearly state that JSON assets are not yet published. Creation SHALL require an explicitly authorized maintainer operation, validate ownership and tag conflicts, and SHALL NOT upload unverified pack files. Routine runs SHALL fail clearly if the seed is absent rather than exempting the tracker from verification or creating a release before verification. The first verified asset publication SHALL advance revision zero to one.

Maintainer acceptance SHALL check both stable JSON downloads and Obtainium import, unchanged polling, revision-change notification, acknowledgement and re-import. Controlled tests SHALL NOT be described as completed device or live publication acceptance.

#### Scenario: First normal run has no seed

- **WHEN** a normal publish run cannot find the tracker release
- **THEN** it fails with bootstrap guidance and preserves verification gates
