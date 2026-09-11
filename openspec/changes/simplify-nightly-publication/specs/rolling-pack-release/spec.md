## MODIFIED Requirements

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

### Requirement: Bootstrap and device acceptance are explicit

Initial activation SHALL establish an owned revision-zero prerelease as a tracking
seed before routine rolling-release synchronization. The seed SHALL clearly state
that JSON assets are not yet published. Creation SHALL require an explicitly
authorized maintainer operation, validate ownership and tag conflicts, and SHALL
NOT upload unverified pack files. Structural pack verification SHALL NOT query
the seed. Routine publishers SHALL check seed existence and ownership at the
release stage after confirmed main publication or a verified main no-op. An absent
seed SHALL fail that stage with bootstrap guidance without undoing or preventing
main publication. Routine publishing SHALL NOT create the seed automatically.
This release prerequisite is separate from structural verification and main
eligibility. The first verified asset publication SHALL advance revision zero
to one.

Maintainer acceptance SHALL check both stable JSON downloads and Obtainium import,
unchanged polling, revision-change notification, acknowledgement and re-import.
Controlled tests SHALL NOT be described as completed device or live publication
acceptance.

#### Scenario: First normal run has no seed

- **WHEN** a normal run completes valid main publication or a verified no-op but finds no tracker release
- **THEN** the release stage fails with bootstrap guidance and no automatic seed creation
- **AND** the confirmed main result remains valid

#### Scenario: Offline verification before bootstrap

- **WHEN** valid local exports include the tracker but the remote seed is absent
- **THEN** `pack verify` succeeds without a remote lookup
- **AND** a routine publisher can publish valid main output before failing the separate release prerequisite

#### Scenario: Explicit seed creation enables a later run

- **WHEN** a maintainer establishes the owned seed and a later run freshly verifies an unchanged main pair
- **THEN** the no-op main result allows the first verified release assets to be published at revision one
