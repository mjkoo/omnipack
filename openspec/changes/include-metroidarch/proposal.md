## Why

Removing the retired Super Metroid port also removed useful second-screen functionality.
The maintainer approved its vetted successor, MetroidArch, for the dual-screen pack.

## What Changes

- Add stable MetroidArch releases to the dual-screen pack with verified Android identity and source-version tracking.
- Keep normal RetroArch available and the retired Super Metroid source excluded from both packs.
- Document APK vetting, shared storage defaults, and how internal directories can be configured through the app or ADB.
- Regenerate the pack pair and verify the addition without device writes or publication.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-curation`: include the Super Metroid successor for dual-screen devices and describe its configuration boundary.

## Impact

Builds on the existing reconciliation branch. Changes curation configuration, regression evidence,
generated packs and documentation. Supersedes the earlier explicit exclusion of MetroidArch;
the retired source stays excluded. No resolver changes, new dependencies, device installation,
automatic configuration utility, publication, save migration, or controller tuning.
