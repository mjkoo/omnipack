# Live build and Obtainium import validation

Validation was performed on 2026-09-06 against the configured upstreams and
Obtainium v1.6.14, the latest official release at the time.

The live catalog produced 87 single-screen apps and 107 dual-screen apps.
The package `info.cemu.cemu` uses `https://github.com/SSimco/Cemu` in the
single-screen pack and `https://github.com/sapphirerhodonite/cemu` in the
dual-screen pack.

Thirteen generated projects resolved successfully. Three projects remained
unresolved: `AverageConsumer/kanto-gear` had no eligible APK in its latest
release, and the latest-release API returned HTTP 404 for
`castdrian/showdown-ds` and `mastercook777/Heimdall-AYN-Thor-Assistant`.
Four links to other hosts were skipped. These are reported soft failures;
they do not prevent the other apps from being exported.

Both packs were imported into the official Obtainium v1.6.14 Android ARM64
app on a connected Android emulator. Reading back Obtainium's stored app
data confirmed every expected package id, project URL, source type, and
supplied settings key and value. The app already tracked itself, giving
88 stored entries after the single-screen import and 108 after importing
the dual-screen pack. The Cemu entry changed to the dual-screen project.

All 87 single-screen apps passed the per-app settings UI check recorded
in `import-validation.json`.
The check opened each app by name, confirmed its package id and URL on
the detail screen, and inspected its actual additional-options form through
Android UI Automator. Every supported switch was present with a checked
state matching the imported value. This validates
import and settings display, not installation or operation of every
exported app.

The first two forms were inspected with overlapping scrolling at the
emulator's original display density. The remaining forms were inspected
at a temporary density of 120 dpi, making the full form visible together.
The original density was restored afterwards. The checklist records the
observed switches and hashes of the captured form XML for each app.

GitHub exposes 18 top-level switches, including the importer-added tarball
option. HTML exposes 16 top-level switches. The HTML source leaves
`showReleaseDateAsVersionToggle` and `allowIncludeZips` disabled, so
Obtainium omits those two controls even though the imported settings retain
`releaseDateAsVersion` and `includeZips`. This follows the official
[source provider](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/providers/source_provider.dart)
and [HTML source](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/app_sources/html.dart).
Play! additionally exposes six switches for its intermediate link, and
RetroArch exposes twelve across its two intermediate links. These nested
controls were also checked against their supplied values and importer
defaults.

Obtainium's import compatibility layer added `minimumUpdateAgeDays` to both
source types, plus `includeTarballs` and `tarballedApkFilterRegEx` to GitHub
entries. It preserved every supplied value. The committed defaults table
matches the upstream export fixtures; its version records provenance and
does not promise that the importer will never add further settings.

Two consecutive `uv run --no-sync pack build` executions succeeded with
byte-identical output, also identical to the files imported above. The
second report contained no additions or removals. SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `dist/single-screen.json` | `447f870805e3cd80fccd4752cfde4b6689719400f0300e0884401608bbf26520` |
| `dist/dual-screen.json` | `c2ce616c5e5c7a02f8dc0102cf876863da5df9916687d2d9abb5f04b7d636ca2` |

`just check-all` passed: lock consistency, Ruff formatting and lint, ty,
dependency audit, source and wheel builds, all 165 pytest tests with
coverage, actionlint, zizmor, Nix formatting, and Nix flake checks.
Nix built for the current `aarch64-darwin` host and reported that incompatible
systems were omitted. Zizmor reported no findings with one configured
suppression. The working-tree warning came from pending validation artifacts.
