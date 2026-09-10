## Why

Visitors should immediately find the appropriate pack and understand how to import and install its apps. The README currently mixes consumer and development guidance, while the nightly schedule and inherited upstream tracker need small curation updates.

## What Changes

- Put labeled raw single-screen and dual-screen JSON downloads immediately below the README title.
- Follow with a short description and prominent numbered installation steps; present credits as bullets.
- Move development, build, and verification guidance to `docs/development.md`, accessible through a brief Contributing section linking to `docs/`; put navigation in `docs/README.md`.
- Schedule nightly publishing for 03:00 America/New_York, including daylight saving time.
- Exclude the RJNY pack's track-only entry from both exports through maintained curation policy, retaining RJNY ingestion and attribution.
- Record self-tracking feasibility and the recommended follow-up, without adding an unvalidated tracker.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `readme-catalog`: Download-first layout, numbered installation, bulleted attribution, and linked development documentation.
- `nightly-publishing`: Daily scheduling at 03:00 Eastern instead of 06:23 UTC.
- `pack-curation`: Exclude the inherited RJNY pack tracking entry from both outputs.

## Impact

Touches README prose, development and publishing documentation, workflow schedule and its test, denylist configuration, regenerated packs and catalog, and corresponding specifications. Existing catalog generation and publisher protections remain applicable. Future manual app additions and adding an omnipack tracker are outside this change.
