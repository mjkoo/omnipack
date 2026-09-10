# Ports and tracker integration validation

Validation date: 2026-09-10 UTC. The checks ran on macOS aarch64 with Python
3.14.7, uv 0.12.5, verifier 0.5.0, report schema 1, and Obtainium compatibility
baselines 1.6.14 for GitHub/HTML and 1.6.15 for the bounded GitLab adapter.

This record covers generated output, offline verification, and controlled
publisher tests. It does not claim that the real rolling release exists, that a
nightly publication ran, or that a device imported the new pack.

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
| Focused offline, tracker, release, nightly Git, reporting, and workflow tests | 178 passed in 19.72 seconds |
| `UV_CACHE_DIR=/private/tmp/omnipack-uv-cache just check-all` | Passed |
| `git diff --check` | Passed |

The focused command was:

```sh
UV_CACHE_DIR=/private/tmp/omnipack-uv-cache uv run --no-sync pytest -q \
  tests/test_offline.py tests/test_pack_tracker.py \
  tests/test_nightly_release.py tests/test_nightly_git.py \
  tests/test_nightly_reporting.py tests/test_nightly_workflow.py
```

The full check ran lock, format, lint, type, dependency audit, Python package
build, all 927 tests with 92% package coverage, offline pack verification,
actionlint, zizmor, Nix formatting, and native flake checks. All passed. The
audit found no known vulnerabilities or adverse statuses in ten packages.
Zizmor ran in its default offline mode with one suppressed finding and no
reported findings. Nix reported the dirty working tree and omitted incompatible
non-host systems.

The final offline report ran from
`2026-09-10T07:54:04.352977+00:00` to
`2026-09-10T07:54:04.385259+00:00`. It was complete, successful, and covered the
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

## Operational checks still incomplete

The public release endpoint returned 404 before this validation. No authenticated
conflict or permission preflight was performed, and the write-capable bootstrap
command was not run. A fresh complete live metadata verification therefore
remains pending until a maintainer explicitly authorizes creation or validation
of the real owned seed. A missing seed must fail normal live verification with
bootstrap guidance; it is not grounds to disable or omit the tracker.

No workflow was dispatched, no push or release synchronization occurred, and no
real failure issue was created, updated, or closed. Repository token permissions,
tag or release protections, stable asset downloads, interruption recovery, and
actual main-to-release publication remain operationally unaccepted.

No Android device acceptance was performed. Initial import of each JSON,
unchanged checks, a changed shared-revision notification, acknowledgement,
download and manual re-import, app setup, and installed behavior all remain
explicitly incomplete. Source metadata and APK manifest evidence do not satisfy
these device checks.
