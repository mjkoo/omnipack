# MetroidArch pack validation

Validated September 10, 2026. This extends the earlier
[source reconciliation validation](source-reconciliation-validation.md) with
MetroidArch in the dual-screen pack. The [setup and vetting guide](metroidarch.md)
covers its source, APK observations, storage separation and remaining device work.

## Output scope

The packs were regenerated using captured upstream catalogs and maintained cached
package identities. This was not a fresh refresh of every external catalog.
Comparison with the preceding reconciliation output found:

| Output | Apps | Added | Removed or modified existing entries |
| --- | ---: | --- | --- |
| Single-screen | 92 | None | None |
| Dual-screen | 112 | `com.metroidarch.app.aarch64` | None |

Global settings were identical. Normal RetroArch remains in both packs. The two
reviewed retired Super Metroid catalog IDs are excluded. Single-screen output is
byte-for-byte unchanged; dual-screen output and the README catalog were regenerated.

| File | SHA-256 |
| --- | --- |
| `dist/single-screen.json` | `f55841cc37706d93256f67b679c9b61eaf52f9fe05f61bf285cb3d0c8626f56f` |
| `dist/dual-screen.json` | `d4ca1649afdb746f8f6a04abbb1bbc6a5d863e73614ada51889fab28d1f7a6c8` |

## Verification

`pack verify` passed with no errors or warnings for the current pair and curation
inputs. A fresh live check of the new entry selected GitHub tag `v1.0.1`, published
September 2, 2026, and exactly
[MetroidArch-v1.0.1.apk](https://github.com/Raekwon1603/RetroArch/releases/download/v1.0.1/MetroidArch-v1.0.1.apk).
The bounded asset probe read 1,024 bytes with HTTP 206 and succeeded. The verifier
classified it as version detection disabled, as intended for source-tag tracking.
There were no live errors or warnings. Unchanged entries were not live-checked
again; the preceding validation record describes their earlier check.

The full suite passed: **979 tests**. Ruff lint, formatting and ty checks passed.
The curation regressions exercise repeated captured-catalog composition, coexistence
with normal RetroArch, stable tag tracking for both captured releases despite equal
APK version names, prerelease exclusion, unrelated-asset filtering, and failure
when the newest stable release has no matching APK rather than older fallback.

The committed release evidence was compared with captured GitHub metadata and both
downloaded APKs: hashes, sizes, package names, version names, debuggable flags and
successful signature observations agreed. Both v1.0.1 patched cores matched the
committed release assets. All 16 configuration keys in the guide were checked
against release source. These checks do not establish reproducible builds.

## Implementation reconciliation

A subsequent September 10, 2026 check rebuilt from the same captured catalogs
and confirmed both output hashes above remained unchanged. Offline verification
passed with no errors or warnings. The two CTR sources were independently checked
from their APKs and are preserved alongside MetroidArch, including original
catalog provenance and disabled APK version detection; see the dated
[CTR evidence](source-reconciliation.md#ctr-release-and-manifest-evidence).

A fresh MetroidArch metadata check again selected tag `v1.0.1` and
`MetroidArch-v1.0.1.apk`; the bounded probe returned HTTP 206 and read 1,024 bytes,
with no errors or warnings. Both captured MetroidArch APKs were rechecked against
the committed release fixture for hashes, sizes, package/version and signature
observations. Both bundled cores matched the release source assets, and all 16
settings keys in the guide remained present in the release source.

The ADB guide now requires discovery of the installed app's current UID, checks
of file/sibling/parent metadata, preservation of UID, GID, mode and SELinux context,
and confirmation that an in-app save persists after relaunch. These are setup
instructions; no device configuration or permission repair was performed.

## Remaining acceptance

No publication or device changes were performed. On-device acceptance still needs
installation, directory isolation and persistence, HTTPS asset/core-info updates,
ROM loading, second-screen behavior, controller setup, save/relaunch and Obtainium
update tracking. Start with vanilla Super Metroid and bundled Snes9x; evaluate
bsnes-hd/Redux separately. Do not treat the documented ADB procedure as an executed
or device-verified setup.
