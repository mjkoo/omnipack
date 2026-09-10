## Why

Installed APK inspection found catalog package IDs that do not match the actual
applications and a retired Super Metroid selection. The maintainer approved
reconciliation using source reputation and basic APK vetting, accepting fresh
installation for publisher changes without save or controller migration.

## What Changes

- Correct retained installed-app identities persistently across catalog refreshes.
- Keep Symphony's unofficial beta, OpenMW-DS, Simon CTR for single-screen and
  igawa6 CTR for dual-screen; use `com.ctrnative` for both CTR repositories, require
  separate APK manifest evidence, preserve original catalog IDs in provenance,
  and disable APK version detection for both.
- Replace legacy Ghostship with HarbourMasters' Android ZIP release in both packs.
- Remove retired Super Metroid from both packs without adding MetroidArch.
- Support GitHub ZIP release selection with Obtainium's on-device APK extraction.
- Document reputation-based acceptance and produce a device change inventory.
- **BREAKING**: corrected tracking IDs and Ghostship's new package change imports;
  CTR's fork uses a different signing key. Device operations remain separate.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-curation`: verified identities, maintained source choices and trust policy.
- `pack-verification`: GitHub ZIP asset selection and explicit extraction boundary.

## Impact

Composition, denylist, extras, overlays, generated packs/catalog, GitHub resolver
setting support, regression evidence and curation documentation. No publication,
device installation, save migration, controller configuration or new dependency.
