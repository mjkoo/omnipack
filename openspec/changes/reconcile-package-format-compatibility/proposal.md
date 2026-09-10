## Why

The verifier accepts Android package containers while the living specs describe
only direct APKs and enabled GitHub ZIPs. Reconcile the contract with the tested
runtime before consolidating GitLab capability ownership.

## What Changes

- Specify existing APK, XAPK, APKM and APKS candidate recognition and provider-specific filtering.
- Distinguish generic ZIP selection and HTML custom link selection from binary inspection.
- Preserve runtime behavior while updating verification documentation and focused regression coverage.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-verification`: Clarify recognized package formats, HTML filtering and outer-response verification limits.
- `gitlab-app-sources`: Clarify package-container recognition in named links and description uploads.

## Impact

Specification and documentation reconciliation plus regression tests. Runtime,
curated configuration, generated outputs, CLI behavior and dependencies stay
unchanged. Operational and on-device acceptance remain separately deferred.
