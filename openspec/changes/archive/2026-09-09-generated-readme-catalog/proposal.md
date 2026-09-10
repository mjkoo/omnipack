## Why

Consumers currently have to discover how to install Obtainium and import the
packs themselves. A generated catalog will let them choose individual programs
while keeping every import link consistent with the published configurations.

## What Changes

- Add install-first guidance, direct main-branch pack downloads, and upstream credits.
- Generate collapsible category tables with program families and variant-specific
  source and Add to Obtainium links carrying complete exported app configurations.
- Build and verify the generated README section with both packs, preserving
  handwritten text and recovering previous outputs after handled write failures.
- Publish verified README changes through nightly automation, restricted to the
  generated section, with existing snapshot, staging, no-op and retry checks.

## Capabilities

### New Capabilities

- `readme-catalog`: Consumer guidance and deterministic, grouped per-app import links.

### Modified Capabilities

- `pack-cli`: Build publishes the README and packs together on success.
- `pack-verification`: Verify catalog consistency and fingerprint README bytes.
- `nightly-publishing`: Allow only generated README changes in verified commits.

## Impact

The renderer gains a catalog companion; build, offline verification, report
compatibility, nightly publication and their tests change. No package dependency,
configuration schema, additional GitHub permission or hosted service is added.
The completed device-aware composition implementation is the baseline. The
pending custom-fork request, GitHub push/merge and Android acceptance remain
separate; device support will not be claimed without an actual device test.
