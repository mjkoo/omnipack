## Context

See proposal.md for motivation and scope. The current model and renderer support GitHub and HTML; Aurora requires a third native source. The existing GitHub resolver already supports title filtering, APK filtering, asset-date versions and track-only release titles. Nightly publication verifies a candidate pair, publishes allowed files to main, and handles ambiguous pushes. Release synchronization is a new external write stage after that confirmed result.

Research on 2026-09-10 checked public release APIs and Obtainium v1.6.15 source. Aurora 4.8.4 publishes ordinary, hw and preload APK links in the release description, with no asset links; a ranged request to the ordinary GitLab upload returned ZIP magic. Xash3D's continuous master release contains `xash3d-fwgs-android.apk`. VCMI 1.7.5 and Julius 1.8.0 expose direct Android APKs; idTech4A++ 1.1.0harmattan72 exposes universal, arm64 and armv7 choices. These are observations, not version pins or gameplay acceptance.

## Goals / Non-Goals

Goals: preserve deterministic exports, use supported Obtainium source semantics, retain verified-byte provenance across main and release publication, and recover without duplicate notifications or release history.

Non-goals: automatic app-configuration synchronization on devices, changing APK distribution for upstream apps, adding arbitrary GitLab instance support, ZIP installation support, expanding Hollow Knight device eligibility, or changing repository protections automatically.

## Decisions

### Native GitLab with a bounded compatibility surface

Extend source types, extras normalization, settings hydration, catalog source labeling and live dispatch together. An explicit extras `overrideSource` takes precedence over URL inference; undeclared extras retain the current GitHub-or-HTML inference. Validate native GitLab URLs as public HTTPS gitlab.com projects with full case-sensitive subgroup paths. Commit GitLab defaults, preserve explicit setting overrides during hydration, and admit GitLab in ordinary offline source validation with the same complete-key and type checks used for existing sources. Retain GitHub/HTML live compatibility at v1.6.14 and document the bounded GitLab adapter behavior at v1.6.15. Add a GitLab resolver using the existing shared HTTP abstraction. Preserve subgroup paths; look up the encoded full project path, then request at most 100 releases in API order. Combine asset links and markdown `/uploads/...apk` links using the numeric project upload route, matching Obtainium's adapter. Use `^AuroraStore-[0-9]+(?:\.[0-9]+)+\.apk$` for Aurora. Keep a supported-settings table and reject active unsupported options rather than claiming full GitLab parity. Public requests need no token; any optional token retains exact-host scoping and never enters exports.

An HTML workaround would preserve fewer source semantics and make Aurora's upload parsing a one-off. A broad GitLab implementation would add options no chosen app needs. Explicit extras supply manifest-backed ids, so generated GitHub package discovery stays unchanged. Extend offline/live fixtures and evidence invalidation to cover the new source, including source defaults in catalog deep links.

### Curation uses existing extras and overlays

Use explicit extras for the five new apps. Validate release APK manifests during implementation before choosing final package ids and version policies. Preserve full idTech4A++ source versions if its manifest differs; do not truncate descriptive hotfix identity to silence lint. Prefer the universal idTech4A++ APK via an exact suffix filter excluding `_arm64` and `_armv7`; use architecture-aware selection for VCMI's published architecture-specific APKs, and the ordinary single APK for Julius. Capture selected names and manifests as regression evidence.

Xash3D uses `includePrereleases: true`, exact continuous-master title and Android APK filters, `fallbackToOlderReleases: true`, `verifyLatestTag: false`, `useLatestAssetDateAsReleaseDate: true`, `releaseDateAsVersion: true`, and `versionDetection: false`. The tag URL supplied by the maintainer is a release locator; the stored Obtainium URL is the repository. Exact title filtering prevents branch-specific continuous builds from qualifying. Its upstream script deletes the release and tag before rebuilding them; transient absence must fail normally, not fall back to a different channel.

Overlay the two existing Hollow Knight entries' names, PC Ports category and setup notes. Their preserved identities avoid an unnecessary migration. Keep dual-only eligibility until separate single-screen acceptance. Silksong documentation currently excludes Android 15 and specifies Android 13; refresh this evidence before recording final notes.

### One shared native GitHub tracker

Use synthetic id `809443320` after checking it against both outputs and source fixtures. Both variants get the same static entry. Configure `trackOnly: true`, `releaseTitleAsVersion: true`, title filter `^omnipack revision [0-9]+$`, extraction `[0-9]+$` with group `0`, prereleases and older-release scanning enabled, latest prioritization disabled, and both release/asset-date options disabled. Never embed the observed revision or installer state.

Obtainium filters to APK assets before selecting an asset date. JSON assets therefore cannot supply the desired per-asset timestamp for this tracker. A numeric title works for track-only releases and avoids hash fragments being treated numerically by hide-downgrades logic. One shared revision intentionally notifies both variants when either changes. Users download their JSON and re-import manually.

### Persistent release and recoverable promotion

Maintain one prerelease at `continuous`, title `omnipack revision N`, with two fixed JSON asset names. The tag is created once at bootstrap and remains a locator, not a current-build claim. Record the actual verified source commit in the release body. Require the ownership marker and a versioned machine-readable state block with completed revision, source commit and SHA-256 digest pair, plus an optional pending target containing its proposed revision, commit and digest pair. Reject malformed state, unexpected assets, ownership conflicts or immutable releases without mutation.

After confirmed main publication or a verified no-op, compare the fresh verified pair to completed release digests. For changed content, write pending state while preserving the title and completed record, replace only assets that differ, then download/read back both JSON assets to verify their exact digests. Promote title and completed state together in one release update and verify readback. Unchanged completed content needs no increment, but missing or corrupt assets are repaired. A run that changes only README or cache does not advertise a pack update.

On an ambiguous write, rediscover release and asset state before another mutation. If promotion succeeded, retain its revision. If interrupted, reconcile against the next run's freshly verified target; preserve the last completed revision until both current target assets are ready. A superseded pending target is not promoted. If the new target equals the completed pair, restore that pair and clear pending state without incrementing. Never infer publication from an upload acknowledgement alone. Bound requests and retries, serialize with the existing publisher lock, and expose main and release outcomes independently.

The two asset replacements are not atomic: a manual downloader can see a missing asset or mixed pair during publication. Advertising the revision last prevents announcing a known incomplete pair. Raw-main URLs remain available and documentation describes this limitation. Retaining an incremental release history would permit stronger atomic switching but conflicts with the agreed two-asset rolling model.

### Explicit bootstrap preserves live verification

The tracker cannot verify against a release that does not exist. Provide a narrowly scoped maintainer bootstrap command that checks canonical repository and tag/release conflicts and creates an owned revision-zero seed with empty completed digests and no JSON assets. Its body states that initial pack publication is pending. Bootstrap is a separately authorized remote operation, never an automatic exception inside normal verification. Tests use a seed fixture; real live verification of the tracker requires the seed. The first successful synchronized pair becomes revision one.

Keep the current main publication allowlist. Release state lives in the release body, not a new generated repository file. Only confirmed main outcomes enter release synchronization. Release failures fail the run and retain the owned failure issue; cleanup diagnostics cannot erase already confirmed outcomes. This requires adjusting both issue recovery and fallback finalization, not merely appending an upload step.

## Risks / Trade-offs

- Mutable upstream assets can disappear during checks: report failure and let a later normal run retry; never claim stable-build availability for Xash3D.
- First activation depends on an external seed: document and test missing-seed errors explicitly, without a verification bypass.
- Partial uploads expose temporarily inconsistent downloads: preserve the old notification revision, keep raw-main links, and reconcile on a subsequent fresh run.
- Release protections or permissions can reject writes: preflight and report the restriction; do not toggle immutability or bypass protections.
- Release/source metadata is not device evidence: require manifest checks and separately record import, notification and re-import acceptance.

## Migration Plan

Implement and validate on an isolated change branch after spec convergence. Bootstrap the real release only after explicit maintainer authorization, then run fresh live validation and record device acceptance separately. Land implementation and specs together; activate the existing nightly workflow through the maintainer's normal publication process. Existing raw-main consumers keep their links. Re-import adds the tracker and new apps; renamed Hollow Knight entries retain package identities. Update docs/curation.md to replace the deferred HTML proposal and document the single shared revision.

Rollback stops new nightly writes and inspects any active run before reverting configuration or publishing code. Do not delete the release or tracker silently. Already imported entries require manual device removal if the maintainer elects to retire them. Restoring older pack bytes through the working publisher is a new content publication with a higher revision.

## References

- [Obtainium GitLab adapter](https://github.com/ImranR98/Obtainium/blob/v1.6.15/lib/app_sources/gitlab.dart)
- [Obtainium GitHub adapter](https://github.com/ImranR98/Obtainium/blob/v1.6.15/lib/app_sources/github.dart)
- [Obtainium version handling](https://github.com/ImranR98/Obtainium/blob/v1.6.15/lib/providers/source_provider.dart)
- [Xash3D release script](https://github.com/FWGS/xash3d-fwgs/blob/master/scripts/gha/make_release.sh)
- [Aurora release](https://gitlab.com/AuroraOSS/AuroraStore/-/releases/4.8.4)
- [Dual Souls setup](https://github.com/igawa6/dualsouls)
- [Silksong setup](https://github.com/jakobkhansen/SilksongAndroid)
