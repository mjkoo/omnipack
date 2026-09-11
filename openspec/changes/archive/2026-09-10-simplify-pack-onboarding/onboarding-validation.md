# Pack onboarding validation

Observed on 2026-09-10 UTC on macOS (aarch64-darwin).

## Consumer guidance

The README was rendered with markdown-it-py and its HTML inspected for the two
download links immediately after the title, four ordered installation steps,
bulleted credits, and a short Contributing link. Relative links in README,
docs/README.md, docs/development.md, and docs/curation.md resolve locally.
Browser screenshot inspection was unavailable; this verifies document structure,
not browser/device presentation.

Import labels and file selection were checked against Obtainium v1.6.14's
[import UI](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/pages/import_export.dart)
and [English translations](https://github.com/ImranR98/Obtainium/blob/v1.6.14/assets/translations/en.json).
The flow is Settings > Import/export > Obtainium import, followed by selecting a
JSON file. Installing desired apps remains a separate step. No new Android
installation or re-import acceptance test was performed.

## Output and source changes

`uv run pack build` completed successfully. Compared with the preceding packs,
both variants removed only the RJNY tracker (`904332840`); no other app was added
or modified. The README catalog lost its tracker row, and all bytes outside the
catalog markers were preserved by regeneration.

| File | Apps | SHA-256 |
| --- | --- | --- |
| `dist/single-screen.json` | 87 | `04c56265522ffe66c1aec03adcd7f02dfd11b91f2c63818288ebe3276b4fe470` |
| `dist/dual-screen.json` | 106 | `c9e25840e3beae7c178043d8e6689f52c790a2d38c4aef1a9aa4a96dacffd258` |

The package-id cache refreshed only release IDs for SilksongAndroid
(378938207 to 385854037) and DW3-DS-Android (383325582 to 385843316). Their
package IDs did not change. Generated-source soft failures were retained under
existing policy: AverageConsumer/kanto-gear had no eligible APK, and latest
release lookups failed for castdrian/showdown-ds and
mastercook777/Heimdall-AYN-Thor-Assistant. These failures did not remove existing
published apps in this refresh.

## Automated checks

- Baseline: 803 tests passed.
- New schedule and tracker regression checks failed before implementation on
  the old schedule and included tracker, then passed after the changes.
- Focused curation/workflow suite: 22 tests passed. The tracker regression sends
  refreshed upstream records through ingestion, composition, rendering and
  catalog generation, retaining an ordinary RJNY app in both variants.
- `just check-all` passed: 804 tests, locked dependencies, formatting, lint,
  types, dependency audit, Python package build, offline pack verification,
  actionlint, zizmor, Nix formatting, and native flake checks.
- All eight main specs passed `openspec validate --specs` after synchronization.

Zizmor ran in its configured offline mode with its existing suppression. Nix
reported the working tree as dirty and omitted incompatible target systems;
those notices do not claim cross-system build validation. No workflow was
dispatched and no publication was performed.

## Live metadata verification

`uv run pack verify --live` completed successfully from 04:24:38 to 04:28:57 UTC
on 2026-09-10, using verifier 0.5.0 with Obtainium compatibility target 1.6.14.
All 193 variant entries completed with zero report or entry errors and warnings.
Classifications were 137 numeric, 36 with version detection disabled, 14 not
applicable, and 6 track-only. No asset probes ran. Evidence fingerprints covered
both packs, README, denylist, overlays, settings, composition, and HTTP config.
This metadata result does not claim APK installation or Android re-import
acceptance, and it does not resolve the generated-source soft failures above.
