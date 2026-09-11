## MODIFIED Requirements

### Requirement: Bootstrap and device acceptance are explicit

Initial activation SHALL establish an owned revision-zero prerelease as a tracking seed before routine rolling-release synchronization. The seed SHALL clearly state that JSON assets are not yet published. Creation SHALL require an explicitly authorized maintainer operation, validate ownership and tag conflicts, and SHALL NOT upload unverified pack files. Structural pack verification SHALL NOT query the seed. Routine publishers SHALL check seed existence and ownership before main publication and fail with bootstrap guidance if it is absent; they SHALL NOT create it automatically. This release prerequisite is separate from structural verification. The first verified asset publication SHALL advance revision zero to one.

Maintainer acceptance SHALL check both stable JSON downloads and Obtainium import, unchanged polling, revision-change notification, acknowledgement and re-import. Controlled tests SHALL NOT be described as completed device or live publication acceptance.

#### Scenario: First normal run has no seed

- **WHEN** a normal publish run cannot find the tracker release
- **THEN** it fails with bootstrap guidance and preserves verification gates

#### Scenario: Offline verification before bootstrap

- **WHEN** valid local exports include the tracker but the remote seed is absent
- **THEN** `pack verify` succeeds without a remote lookup
- **AND** a routine publisher still rejects the missing release prerequisite before a main push

