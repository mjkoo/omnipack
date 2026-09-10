# Ports and tracker integration validation

Validation date: 2026-09-10 UTC. The checks ran on macOS aarch64 with Python
3.14.7, uv 0.12.5, verifier 0.6.0, report schema 1, and Obtainium compatibility
baselines 1.6.14 for GitHub/HTML and 1.6.15 for the bounded GitLab adapter.

This record covers generated output, offline verification, controlled publisher
tests, the authorized real revision-zero release bootstrap, and complete live
metadata verification. Nightly publication and device import remain unaccepted.

## Rebuilt outputs

`UV_CACHE_DIR=/private/tmp/omnipack-uv-cache uv run --no-sync pack build` used
fresh public upstream reads and completed successfully. The build report had
schema 2 and status `success`. It added the five curated ports and the shared
tracker to each variant and removed no entries. The resulting pair contains 93
single-screen entries and 112 dual-screen entries.

The following ids occur exactly once in each file:

- `com.aurora.store`
- `com.karin.idTech4Amm`
- `is.xyz.vcmi`
- `com.github.bvschaik.julius`
- `su.xash.engine.test`
- `809443320`

Three existing source soft failures remained visible in the successful build:
AverageConsumer/kanto-gear had no eligible latest APK, and latest-release lookups
failed for castdrian/showdown-ds and
mastercook777/Heimdall-AYN-Thor-Assistant. These entries were not silently
replaced with fixture output.

| File | SHA-256 |
| --- | --- |
| `dist/single-screen.json` | `48384aaf02d0ba849f4aba13d8471214c30dad4650eb0955045c7f5b00bc2abf` |
| `dist/dual-screen.json` | `8e8eccb5d2d5adfd4e6cfac1d671600aa418fcd0868bcb8d919efc2c020be9fd` |
| `README.md` | `6a478bc60224656380f33b12b1cd44f3fe056f4e3f6160b86d7c9f65b8fd22d2` |
| `config/package-ids.json` | `82415239318dcef65db1d107163ddf9a3ccb5077a573270f6fed043ca96a69e7` |
| build report snapshot | `4ce08174ac2b8409ee2c57cef45b5566d92eab47624e9508faaa8ff94cdca39a` |

The package-id cache did not change. The generated README catalog includes all
six entries and preserves its handwritten prefix and suffix through the normal
catalog replacement path.

## Offline and controlled checks

| Command | Result |
| --- | --- |
| `UV_CACHE_DIR=/private/tmp/omnipack-uv-cache uv run --no-sync pack verify` | Complete offline success with zero errors and warnings |
| Focused GitLab, ingestion, tracker, curation, and release tests | 161 passed in 1.68 seconds |
| `UV_CACHE_DIR=/private/tmp/omnipack-uv-cache just check-all` | Passed |
| `git diff --check` | Passed |

The focused command was:

```sh
UV_CACHE_DIR=/private/tmp/omnipack-uv-cache uv run --no-sync pytest -q \
  tests/test_resolution_gitlab.py tests/test_sources.py \
  tests/test_nightly_release.py tests/test_pack_tracker.py \
  tests/test_port_curation.py
```

The original integration check passed 927 tests. After the review fixes, the
final full check ran lock, format, lint, type, dependency audit, Python package
build, all 958 tests with 92% package coverage, offline pack verification,
actionlint, zizmor, Nix formatting, and native flake checks. All passed. The
audit found no known vulnerabilities or adverse statuses in ten packages.
Zizmor ran in its default offline mode with one suppressed finding and no
reported findings. Nix reported the dirty working tree and omitted incompatible
non-host systems.

The recorded offline report ran from
`2026-09-10T08:09:37.128926+00:00` to
`2026-09-10T08:09:37.159590+00:00`. It was complete, successful, and covered the
full current pair, including tracker `809443320`; it did not omit the tracker to
avoid its live dependency. Its input hashes matched both output hashes above and
README hash `6a478bc60224656380f33b12b1cd44f3fe056f4e3f6160b86d7c9f65b8fd22d2`.

Documentation checks confirmed that the consumer guide names the shared numeric
revision, raw-main and release links, manual acknowledgement and re-import,
per-port setup, interruption visibility, and incomplete device acceptance. The
publisher guide names the exact bootstrap command, `main` target, token and
protection boundaries, partial-upload recovery, and rollback. No maintained
document refers to implementation scratch material or presents the discarded
HTML tracker approach as the selected strategy.

## Authorized bootstrap and live metadata verification

After explicit maintainer authorization, the documented bootstrap command ran
successfully on 2026-09-10. Its authenticated conflict checks allowed creation
of the [owned continuous prerelease](https://github.com/mjkoo/omnipack/releases/tag/continuous).
Readback confirmed release id `386243625`, title `omnipack revision 0`,
`draft: false`, `prerelease: true`, `immutable: false`, and no assets. The owned
state has completed revision zero, null digests and source commit, and no pending
revision. The release was published at `2026-09-10T11:58:31Z`.

The `continuous` tag points to commit
`6212a54f8f9e8a317e4a76f6837d031db6c79891`, matching the independently read remote
`main` at bootstrap. No settings or protections were changed. The credential
used for this operation could create the seed; this does not establish the
permissions of the nightly workflow token.

`UV_CACHE_DIR=/private/tmp/omnipack-uv-cache uv run --no-sync pack verify --live`
then exited zero. The fresh metadata-only report ran from
`2026-09-10T11:59:15.749041+00:00` to
`2026-09-10T12:03:15.702104+00:00`, with `complete: true`, `status: success`,
zero errors and zero warnings. All 205 entries were included: 93 single-screen
and 112 dual-screen. Verifier 0.6.0 used report schema 1 and the compatibility
baselines listed above. All captured input hashes matched the current inputs;
the JSON pair and README hashes are the exact outputs listed above.

Both tracker entries (`809443320`) resolved `omnipack revision 0` to effective
version `0` from tag `continuous`, with no APK candidates, errors or warnings.
The tracker was not omitted from verification. The exact live report SHA-256 is
`7ff55a2109ce89abe1eb02bd38f5e38f0f195de3ad5a42dfd10601faf5d9bb8d`.
No live metadata blockers remained in this run. Asset probes were not requested;
metadata verification does not establish download, installation or device behavior.

## Operational checks still incomplete

No workflow was dispatched, no push or release synchronization occurred, and no
real failure issue was created, updated, or closed. Nightly token permissions,
publication under tag or release protections, stable asset downloads,
interruption recovery, and actual main-to-release publication remain
operationally unaccepted. The seed still has no JSON assets; the first successful
synchronized pair will advertise revision one.

No Android device acceptance was performed. Initial import of each JSON,
unchanged checks, a changed shared-revision notification, acknowledgement,
download and manual re-import, app setup, and installed behavior all remain
explicitly incomplete. Source metadata and APK manifest evidence do not satisfy
these device checks.
