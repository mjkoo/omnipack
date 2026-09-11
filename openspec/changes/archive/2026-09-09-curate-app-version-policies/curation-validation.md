# Curation validation

Validation date: 2026-09-09 UTC. Verifier identity 0.3.1, report schema 1,
Obtainium compatibility baseline 1.6.14.

## Commands and outcomes

| Command | Outcome |
| --- | --- |
| `uv run pytest -q` before implementation | 651 passed |
| `uv run pytest -q tests/test_curation.py tests/test_live.py` before policies | 10 expected failures, 40 passed |
| `uv run pytest -q tests/test_report.py -k changed_verifier` before identity bump | Expected failure asserting 0.3.1 |
| `uv run pytest -q tests/test_curation.py tests/test_live.py tests/test_report.py` after policies | 98 passed |
| `uv run pytest -q tests/test_curation_evidence.py` | 5 passed |
| `uv run pack build` | Success, local output pair rebuilt |
| `uv run pack verify` | Success, zero errors and warnings; 2026-09-09T12:00:33.687931+00:00 to 2026-09-09T12:00:33.693546+00:00 |
| `just check-all` | Success, including 674 tests, lock/format/lint/type checks, dependency audit, Python build, offline verification, workflow lint, Nix formatting and host flake checks |
| `uv run pack verify --live` | Success, 199 entries, zero errors and zero warnings; 2026-09-09T12:00:33.905743+00:00 to 2026-09-09T12:04:26.653290+00:00 |
| `adb devices -l` | No connected devices |

The first check-all attempt stopped at formatting; formatting was corrected and
the complete command passed. The dependency audit found no known vulnerabilities
or adverse project statuses in ten packages. Zizmor reported its default offline
mode and one suppressed finding, with no findings to report. Nix reported the
working tree was dirty and omitted incompatible non-host systems. These notices
are recorded limitations, not claims of online workflow auditing or cross-platform
build execution. No publication, workflow dispatch, GitHub issue operation, push,
or merge was performed. Test-created local git remotes are isolated fixtures.

## Generated outputs and upstream drift

The captured affected-entry baseline contains 23 historical format warnings.
Composition/rendering/resolution regression tests account for all 23, with zero
remaining under the curated policies, and add Cinderbox once in each variant.
Existing ids, source URLs, membership, asset candidates and unrelated settings
are compared against captured pre-curation entries.

The live rebuild produced 88 single-screen entries (previously 87) and 111
dual-screen entries (previously 107). Cinderbox is the only manual catalog
addition. Unchanged upstream ingestion also added these dual entries:

- `com.chimeragaming.pixelnavigator`, from `ChimeraGaming/PixelNavigator`.
- `com.darkaxt.dualdex`, from `DarkAxt/DualScreenDex`.
- `com.digitaladventure.dw2003`, from `rsigristc/dw3-ds-android`.

Their resolved ids were added to the package-id cache; the existing
`ChimeraGaming/FanMakePokemonMaps_Android` cache release id also advanced.
No existing entry was removed, and existing non-settings fields were unchanged.
These are separately accounted upstream refresh results, with no extra manual
policy or filter changes. Three pre-existing ingestion soft failures remain:
AverageConsumer/kanto-gear has no eligible latest APK, while castdrian/showdown-ds
and mastercook777/Heimdall-AYN-Thor-Assistant failed latest-release lookups.

| File | SHA-256 |
| --- | --- |
| `dist/single-screen.json` | `fe4fcc44de39718ae2de87e874afd7393a6719467ebdecbfd981541b71154e08` |
| `dist/dual-screen.json` | `8d81c9ddbf7ac1d0ac7016662abcfec40da6d892e8dec49db46e44e71ddfe7f7` |
| `config/package-ids.json` | `f85c087d2ba318e4abd222dbb36704e0ae0ff0e2fc9180b83b384c556dc77f99` |

## Device acceptance outstanding

No Android test device was connected. Import, re-import and source-version
update acceptance remain outstanding, independently of fixture and metadata
validation. On an available device, exercise a numeric entry such as Cinderbox
and a correctly identified source-tracked entry such as Vita3K, recording initial
import, repeated import, recorded/installed versions, and a distinct source build.
Check the one-time re-import prompt and external-install limitations described
in [curation](../../../../docs/curation.md). The four known mismatched identities must not be
used as evidence of successful device behavior. Earlier import validation of
older packs does not establish acceptance of these policies.
