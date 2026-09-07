# Pack verification

Pack verification uses Obtainium v1.6.14 as its compatibility baseline. The
behavioral references are the source files at that immutable tag:

- [GitHub source](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/app_sources/github.dart)
- [HTML source](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/app_sources/html.dart)
- [shared version handling](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/providers/source_provider.dart)

The RJNY verifier was evaluated as an implementation reference at revision
[`5bb57f833652c389c3b063d3b4af9b42ee11602a`](https://github.com/RJNY/Obtainium-Emulation-Pack/tree/5bb57f833652c389c3b063d3b4af9b42ee11602a),
particularly `scripts/test-apps.py`. That repository dedicates its code to the
public domain under the Unlicense. No RJNY helper has been copied or adapted in
the compatibility classifier. Any future adaptation must retain this revision,
source path, and licence attribution.

## Compatibility boundary

Live verification interprets only behavior needed by the committed packs. Each
setting is classified before resolution. An unknown key is an error even if its
value is false or empty, because a value cannot be assumed inactive without
knowing its semantics.

| Settings | Classification | Live behavior |
| --- | --- | --- |
| `trackOnly`, `versionExtractionRegEx`, `matchGroupToUse`, `versionDetection`, `releaseDateAsVersion`, `apkFilterRegEx`, `invertAPKFilter` | Implemented | Applied during version and candidate selection |
| GitHub release eligibility, title and notes filters, older-release fallback, `date` or `none` sorting, asset-date selection, and release-title versions | Implemented | Applied to the first 100 release records |
| HTML intermediate links, link and text filters, outside-anchor matching, sorting controls, whole-page extraction, and non-secret request headers | Implemented | Applied to each configured page in order |
| App name, author, description, notification/background controls, Shizuku presentation, refresh behavior, and OS version-code preference | Harmless for source resolution | Retained but does not alter the device-independent check |
| `autoApkFilterByArch` and `preferredApkIndex` | Device-specific | Validated but not used to claim device compatibility |
| `includeZips`, ZIP filters, `verifyLatestTag`, GitHub credentials or request proxies, insecure TLS, and non-`date`/non-`none` GitHub sorting | Inactive unsupported or live error | Default false or empty values are accepted; active values fail by setting name |
| HTML pseudo-versioning | Inactive unsupported or live error | Ignored when explicit extraction supplies the version; otherwise active pseudo-versioning fails |
| Authorization or Cookie request headers and device-dependent intermediate filtering | Live error | Rejected before a request is made |
| Any unknown additional setting | Live error | Requires an intentional compatibility decision |

The check establishes source resolution and bounded HTTP reachability. It does
not establish APK identity, signature, installation success, architecture
coverage, or behavior on a particular Android device.

## Fixture evidence

The fixture manifest at `tests/fixtures/verification/manifest.json` maps every
committed HTML entry and every distinct GitHub behavior to response evidence.
All seven HTML fixtures and the configured RJNY track-only GitHub fixture are
trimmed live captures dated in their provenance. Synthetic GitHub records cover
cases that need controlled alternatives. They are labeled as synthetic, cite the
pinned behavioral source instead of a purported capture URL, and include the
complete selection settings needed to reproduce each expectation. Cases make
incorrect sorting, traversal, asset filtering, or regex group handling produce
a different result. GitHub evidence covers prereleases, title and date versions,
concatenated extraction groups, and track-only release and tags paths.

Fixtures contain only the response fragments needed to reproduce selection.
They are deterministic compatibility evidence, not cached claims that the live
source remains reachable.
