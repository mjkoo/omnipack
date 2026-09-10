## Context

See proposal.md for motivation. This change depends on the completed, unmerged
reconciliation work and supersedes only its decision to omit MetroidArch. Its
modified requirement is copied in full from that preceding delta; synchronize
or archive that predecessor first. Preserve its other app choices and evidence.

## Goals / Non-Goals

Use existing curation mechanisms. Do not add a new resolver, device automation
utility, or automatic directory provisioning. Device setup is documented only.

## Decisions

Add a dual-only extra for com.metroidarch.app.aarch64, displayed as MetroidArch
(Super Metroid), classified app:super-metroid, with an explicit dual winner pin.
Replace the family-wide deny with a source URL deny for the retired repository,
so neither historical catalog ID can return but the successor can be selected.
Keep normal RetroArch as its own package family. Do not modify upstream captures.

Use stable GitHub tags, releaseTitleAsVersion=false, versionDetection=false,
trackOnly=false, includePrereleases=false, includeZips=false, and
apkFilterRegEx=^MetroidArch-v[0-9]+(?:\.[0-9]+)+\.apk$.
Disable autoApkFilterByArch: the sole APK has no architecture marker and its
bundled game cores are ARM64. No older-release fallback is needed for the
reviewed current release; do not silently select an older asset when the latest
stable release no longer matches the explicit filter.

Promote concise metadata and source references from the inspected v1.0.0/v1.0.1
APKs into committed regression evidence, without committing binaries or scratch
references. Test through real composition with captured catalog data and mocked
release HTTP. Preserve existing version policies and the rest of both packs.

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
- Two open deltas touch the same reviewed-app requirement: this change depends on the reconciliation delta and carries the full replacement requirement.

## Migration Plan

Regenerate from existing captured inputs, run targeted composition/resolution
checks, offline validation, and fresh live verification for the new entry.
Compare rendered membership/settings against the preceding branch head to prove
only the intended app is added. No need to re-fetch all unrelated catalogs.
Run the full suite at baseline and completion. Leave the branch unpushed.
Rollback is restoring the curation changes and regenerated output; no device
state is modified. Update current docs to reflect the successor decision.
