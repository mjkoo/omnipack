## Context

See proposal.md for motivation. This change depends on the existing, unmerged
reconciliation work, whose revised CTR identity and version-policy verification
remains open, and supersedes only its decision to omit MetroidArch. Its
modified requirement is copied in full from that preceding delta. Implementation
can proceed on this stacked branch, but synchronize or archive the predecessor
before publishing this change's spec. Preserve its other app choices and evidence.

## Goals / Non-Goals

Use existing curation mechanisms. Do not add a new resolver, device automation
utility, or automatic directory provisioning. Device setup is documented only.

## Decisions

Add a dual-only extra for com.metroidarch.app.aarch64, displayed as MetroidArch
(Super Metroid), classified app:super-metroid, with an explicit dual winner pin.
Replace the family-wide deny with existing config-only deny support for exactly
the two reviewed retired catalog IDs, com.raekwon1603.supermetroid and
com.raekwon1603.supermetroidds, so they cannot return while the successor can be
selected. Do not add URL-deny behavior. A future changed or additional retired ID
requires curation review. Keep normal RetroArch as its own package family. Do not
modify upstream captures.

Use stable GitHub tags, releaseTitleAsVersion=false, versionDetection=false,
trackOnly=false, includePrereleases=false, includeZips=false, and
fallbackToOlderReleases=false with
apkFilterRegEx=^MetroidArch-v[0-9]+(?:\.[0-9]+)+\.apk$.
Disable autoApkFilterByArch: the sole APK has no architecture marker and its
bundled game cores are ARM64. Select the newest eligible stable release. If that
release has no matching versioned APK, resolution fails rather than selecting an
older release.

Promote concise metadata and source references from the inspected v1.0.0/v1.0.1
APKs into committed regression evidence, without committing binaries or scratch
references. Test through real composition with captured catalog data and mocked
release HTTP. Preserve existing version policies and the rest of both packs.
Reverify the predecessor's revised CTR requirements: Simon single-screen and
igawa6 dual-screen both use `com.ctrnative` with APK version detection disabled,
original catalog IDs retained in provenance, and separate dated manifest evidence
for each repository's selected APK. This propagation does not establish that evidence.

Publish a durable MetroidArch setup/vetting document. State menu Directory
settings and exact config keys from the release source. ADB procedure is:
first launch to create configuration, stop app, locate and back up its actual
config, change only directory settings, restore through app-appropriate access,
then inspect settings and confirm isolation after relaunch. Prefer app-specific
external files through adb shell when accessible; run-as is a fallback for this
debuggable APK, not a guarantee for future builds. No device changes occur here.
Recommend a MetroidArch content root and separate all writable directories that
otherwise share RetroArch, with ROM sharing deliberate. Keep cores app-private.

## Risks / Trade-offs

- Shared external paths can cross-affect saves/remaps: document explicit separation and later device verification.
- APK versionName differs from tags: source-version tracking avoids treating the frontend version as the release version.
- Debuggable APK, HTTP updater defaults, young project and widescreen bugs: preserve vetting limits and HTTPS setup advice; start device acceptance with vanilla ROM and Snes9x.
- Two open deltas touch the same reviewed-app requirement: this change depends on the reconciliation delta and carries the full replacement requirement; stacked implementation can proceed now, but later spec publication waits until the predecessor is synchronized or archived.

## Migration Plan

Regenerate from existing captured inputs, run targeted composition/resolution
checks, offline validation, and fresh live verification for the new entry.
Compare rendered membership/settings against the preceding branch head to prove
only the intended app is added. No need to re-fetch all unrelated catalogs.
Run the full suite at baseline and completion. Leave the branch unpushed.
Rollback is restoring the curation changes and regenerated output; no device
state is modified. Update current docs to reflect the successor decision.
