## Why

The pack lacks several established Android ports and Aurora Store, while its Hollow Knight ports are difficult to recognize in the catalog. Consumers also need a notification when the published import files change without maintaining a history of nightly releases or relying on HTML extraction.

## What Changes

- Add Aurora Store from its canonical GitLab project, with native GitLab ingestion, rendering and verification support sufficient for its releases.
- Add idTech4A++, VCMI, Julius and Xash3D FWGS to both variants. Track Xash3D's continuous master APK by its asset update date.
- Give the existing dual-screen Hollow Knight and Silksong entries recognizable names, PC Ports categorization and setup notes. Preserve their current dual-only eligibility in this change; broader device acceptance remains a follow-up.
- Include the same omnipack GitHub track-only entry in both exports.
- Maintain one mutable `continuous` release containing `single-screen.json` and `dual-screen.json`. Update its numeric title revision when either JSON changes; retain neither per-build releases nor separate variant releases.
- Extend nightly publication with verified release synchronization, recoverable partial-write handling and separate main/release outcomes. Retain existing raw-main URLs and manual re-import semantics.
- Exclude Delta Touch. Defer fheroes2 archive support, additional port candidates and the unspecified isle-portable fork.

## Capabilities

### New Capabilities

- `gitlab-app-sources`: Native public GitLab app entries, settings and bounded release resolution, including APK links embedded in release descriptions.
- `rolling-pack-release`: A single persistent release with two verified JSON assets, content-driven numeric revisions and resumable synchronization.

### Modified Capabilities

- `source-ingestion`: Explicit GitLab source precedence, URL validation and source-specific defaults while retaining existing URL inference for undeclared extras.
- `pack-verification`: Accept structurally valid native GitLab entries in ordinary offline verification and extend the declared live compatibility boundary.

- `pack-curation`: New apps, Xash3D rolling version policy, Hollow Knight presentation and the omnipack tracker.
- `nightly-publishing`: Include release synchronization in publication success, failure and recovery semantics.

## Impact

Touches source typing/defaults, app adapters and rendering, live source dispatch and verification evidence, maintained extras/overlays, nightly publisher orchestration, tests, generated exports/catalog and consumer/publisher documentation. Existing shared HTTP credential boundaries and main publication gates remain in force. No new registry, release history, APK hosting or automatic device configuration synchronization is introduced. GitHub release operations use the existing contents permission after maintainer activation; creating this proposal performs no remote writes.
