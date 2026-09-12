# rolling-pack-release Specification

## Purpose

Provide stable JSON downloads and a native Obtainium notification source through one persistent GitHub release, without retaining nightly release history.

## Requirements

### Requirement: One owned rolling release publishes both variants

The publisher SHALL maintain one mutable prerelease at tag `continuous` in
`mjkoo/omnipack`, with title `omnipack revision N` for a nonnegative integer N
and assets named `single-screen.json` and `dual-screen.json`. The release SHALL
carry the exact ownership marker `<!-- omnipack:rolling-pack -->`. The publisher
SHALL NOT create per-run or per-variant releases, or delete and recreate the
established release or tag. A pre-existing unowned or malformed release SHALL
block release synchronization without authorizing overwrite or blocking
otherwise valid main publication. The release tag SHALL remain a stable locator;
recorded published commit metadata SHALL identify asset provenance rather than
implying that the tag advances with every asset upload.

#### Scenario: Another successful nightly changes the pack

- **WHEN** the owned release exists and verified JSON content changes
- **THEN** the same release id and tag remain while assets and revision are updated

#### Scenario: Unowned release conflicts with synchronization

- **WHEN** a valid main publication or verified no-op is followed by discovery of an unowned release
- **THEN** release synchronization fails without altering that release
- **AND** the independently confirmed main outcome remains intact

### Requirement: Revision changes follow completed content publication

The release SHALL record the SHA-256 digests of its published JSON pair and the
main commit they came from. On each synchronization the publisher SHALL compare
the run's verified pair with both the recorded digests and the SHA-256 digests
GitHub reports for the two served assets. A missing asset, or an asset with no
reported digest, SHALL count as a mismatch. When the recorded digests and both
served-asset digests equal the run's pair, the publisher SHALL leave the release
unchanged. When the recorded digests equal the run's pair but a served asset
does not, the publisher SHALL replace both assets without editing the release,
so that repair SHALL NOT advance the title revision. When the recorded digests
differ from the run's pair, or none are recorded, the publisher SHALL replace
both assets and then, in one edit, advance the title revision by one and record
the new digests and commit. That edit SHALL replace the whole release body with
fixed text carrying the ownership marker, the stable download locations and the
digest record, so no seed statement or earlier body text survives it.
Documentation-only, cache-only and unchanged nightly runs SHALL NOT advance the
revision. Release assets SHALL only come from a verified pair associated with a
successful main push or a verified main no-op; a failed or erroring main push
SHALL prohibit release mutation. Release mutation SHALL also require main to
still be at the commit that pair came from, so a rerun of an earlier run's
publisher cannot move the release back to an older pair.

GitHub asset replacement is not atomic across the pair. The publisher SHALL NOT
claim atomic download visibility during uploads. If synchronization stops before
the final edit, the recorded digests SHALL still describe the previous pair. A
later verified run with a different pair SHALL then replace both assets again
and advance the revision once, and a later verified run whose pair equals the
recorded digests SHALL restore both assets without advancing the revision.
Missing, mixed or hand-replaced assets SHALL likewise be restored by the next
verified run without advancing the revision. A completed edit SHALL NOT cause a
later run with the same pair to advance the revision again. Authentication
errors, immutable-release restrictions and ownership conflicts SHALL fail
visibly without changing repository settings or touching other releases.

#### Scenario: Second asset upload fails

- **WHEN** one replacement succeeds and the other fails
- **THEN** the title revision and recorded digests stay unchanged and the run fails
- **AND** a later verified run with the same new pair replaces both assets and advances the revision once

#### Scenario: Interrupted upload, then the recorded pair returns

- **WHEN** an upload of a new pair replaced one asset before failing, and a later verified run's pair equals the recorded digests
- **THEN** that run replaces both assets with its pair and makes no release edit
- **AND** the title revision stays at the recorded pair's revision

#### Scenario: Served asset is missing or unverifiable

- **WHEN** the recorded digests match the run's pair but a served asset is missing, has no reported digest, or reports a different digest
- **THEN** both assets are replaced and the title revision and recorded digests stay unchanged

#### Scenario: Final edit succeeds but its response is lost

- **WHEN** the title and digest edit is applied but the publisher sees an error
- **THEN** the run fails, and a later run with the same pair finds matching recorded and served digests and makes no release change

#### Scenario: No JSON changes

- **WHEN** a verified run's pair matches the recorded digests and both served-asset digests
- **THEN** no asset or revision changes, even if main received a cache or catalog commit

### Requirement: Bootstrap and device acceptance are explicit

Initial activation SHALL establish an owned revision-zero prerelease as a
tracking seed before routine rolling-release synchronization, created by a
documented one-time maintainer command. The seed SHALL carry the ownership
marker, no recorded digests, and a statement that JSON assets are not yet
published. Structural pack verification SHALL NOT query the seed. Routine
publishers SHALL check the release's existence, ownership marker, title and
published-prerelease state at the release stage after a successful main push or
a verified main no-op: the release SHALL be a prerelease that is neither a draft
nor immutable. An absent, unowned, malformed, draft, non-prerelease or immutable
release SHALL fail that stage with bootstrap guidance and without release
writes, without undoing or preventing main publication. Routine publishing
SHALL NOT create the seed. The first verified asset publication SHALL advance
revision zero to one.

Maintainer acceptance SHALL check both stable JSON downloads and Obtainium import,
unchanged polling, revision-change notification, acknowledgement and re-import.
Controlled tests SHALL NOT be described as completed device or live publication
acceptance.

#### Scenario: First normal run has no seed

- **WHEN** a normal run completes valid main publication or a verified no-op but finds no tracker release
- **THEN** the release stage fails with bootstrap guidance and no automatic seed creation
- **AND** the main result remains valid

#### Scenario: Release is not a published mutable prerelease

- **WHEN** the owned `continuous` release is a draft, is not a prerelease, or is immutable
- **THEN** the release stage fails with bootstrap guidance, without uploading assets or editing the release
- **AND** the main result remains valid

#### Scenario: Offline verification before bootstrap

- **WHEN** valid local exports include the tracker but the remote seed is absent
- **THEN** `pack verify` succeeds without a remote lookup
- **AND** a routine publisher can publish valid main output before failing the separate release prerequisite

#### Scenario: Explicit seed creation enables a later run

- **WHEN** a maintainer creates the owned seed and a later run verifies an unchanged main pair
- **THEN** the no-op main result publishes the first verified release assets at revision one
