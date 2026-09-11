# Reviewed source generation validation

Validation date: 2026-09-11 on macOS aarch64, from source revision
`a43017a`. This record covers controlled source generation, a live source
candidate, pack composition, structural verification, and an Obtainium 1.6.15
import on an AYN Thor. It records observed results without embedding device
exports or transient source bodies.

## Accepted source and generated outputs

The accepted source contains 28 entries: 27 APK projects and one track-only
resource. Its exact accepted inputs were:

| Input | SHA-256 |
| --- | --- |
| `config/catalogs/codm.json` | `aa9521a185fe7e255222670fc74594d2043004f1c5f3dba71fdd8a80d93b68ce` |
| `config/catalogs/codm.source.json` | `6a2e42d1c165cc42f7c857094d3be2cacbea58e23b1682633664bec128b316b2` |
| `config/codm-projects.json` | `3fe94ce5cc25ea27a9d096bab1a739a34bae2589ef5cd20d00b6e1963dd2125f` |
| `config/package-ids.json` | `840f6ccbd4aa3a222db40b463bad6012d9f891f11be06ec08e853fd80de44a86` |

Accepted metadata binds the codm README bytes as
`db4468c41568266667bbf17a52bce96ba5628a855b6978ef39defc8e7ef372dc`,
the policy bytes as
`3fe94ce5cc25ea27a9d096bab1a739a34bae2589ef5cd20d00b6e1963dd2125f`,
and catalog bytes as
`aa9521a185fe7e255222670fc74594d2043004f1c5f3dba71fdd8a80d93b68ce`.

The frozen controlled baseline reproduced 92 single-screen and 109 dual-screen
entries byte-for-byte. Its output SHA-256 values were
`f55841cc37706d93256f67b679c9b61eaf52f9fe05f61bf285cb3d0c8626f56f`
and `77f39d1ff147b542c393ce33920876998e78bf6eeb3cfe6eaf421a053c1aa11d`.
An independent controlled composition using the frozen 24-project README kept
the single pack at 92 and changed dual from 109 to 112. Every old serialized
entry and maintained family winner was identical; only Showdown, Heimdall and
the Kanto tracker were added.

A live 28-project source build fetched RJNY applications and the two BBoi JSON
assets but made no codm README, GitHub release, or APK request during normal pack
composition. It produced:

| Output | Apps | SHA-256 |
| --- | ---: | --- |
| `dist/single-screen.json` | 92 | `f55841cc37706d93256f67b679c9b61eaf52f9fe05f61bf285cb3d0c8626f56f` |
| `dist/dual-screen.json` | 115 | `e90c6359a1f8ec38fe2e99955bdfd619a67fc6d55b394e10150e3b689dbe4e23` |

The live single pack remained byte-identical. The live dual pack preserved all
112 existing entries without changes or removals and added only Showdown
`dev.adrian.showdown`, Heimdall `com.mastercook777.heimdall`, and Kanto tracker
`1845280017`. The promoted README retained all handwritten bytes outside its
catalog markers. A fresh `UV_CACHE_DIR=/private/tmp/omnipack-uv-cache uv run
--no-sync pack verify` passed after promotion.

## Controlled workflow coverage

The suite exercises the actual generator, candidate checker, and controlled git
and remote transports. In particular,
`test_retries_never_accept_partial_resolutions` covers an unresolved complete
generation attempt followed by a successful retry;
`test_accepted_gate_and_fresh_inspection` covers policy-only input changes and
forced inspection; `test_changed_proposal_incorporates_unrelated_main_advancement`
covers updating an owned open proposal; and
`test_build_runs_the_real_pipeline_with_transport_only_fixtures` denies any codm
README, release, or APK access while a normal build consumes the committed
catalog. `test_source_input_change_is_rejected` separately proves nightly cannot
publish source-input mutations. Publication tests use local repositories and
controlled API doubles. No real remote branch, pull request, main, release,
issue, workflow, or repository-setting write was performed.

## Obtainium device acceptance

A user-authorized session imported only the three intended additions into
Obtainium 1.6.15 on an AYN Thor. A fresh before export contained 96 entries and
the after export contained 99. All 96 existing serialized app entries were
identical; none changed or was removed. The only top-level export difference
outside the app additions was `exportedAt`. The export SHA-256 values were
`2747bf9ab88c8fda3a47a0ae65c85437c087370af18b96891a73811cd50c96de`
before and `fef252e5c6c9d5a9c30f7e7fced3a40a9474b59d74c9a9af090370a5d04cac8c`
after.

Targeted refresh selected Showdown version `0.1.2-alpha.25` with asset
`showdown-v0.1.2-alpha.25.apk`, and Heimdall version `0.2.1-alpha.1` with asset
`heimdall-v0.2.1-alpha.1.apk`. Heimdall's debug channel was excluded and its
consumer older-release fallback setting was enabled. Kanto selected release
`v3.2.8`, remained track-only with no APK URL or installed version, and exposed
release tracking only. Zero APK installations occurred. The pre-session export
option was restored afterward.

This proves import preservation and the measured selector results for these
three entries on this client and device. It does not establish APK installation,
signature or architecture compatibility, future upstream availability, Kanto
mod installation, or behavior in other Obtainium versions.

## Development checks

The complete project gate passed with
`UV_CACHE_DIR=/private/tmp/omnipack-uv-cache just check-all`. Lock validation,
Ruff formatting and lint, Ty, the OSV dependency audit, sdist and wheel builds,
all 782 tests, structural pack verification, actionlint, zizmor, Nix formatting,
and native flake checks passed. Coverage was 91%; pytest took 45.75 seconds. The
audit found no known vulnerabilities or adverse statuses in 10 packages. Zizmor
reported no findings in its default offline mode. Nix reported the expected
dirty-tree notice and omitted incompatible systems; aarch64-darwin checks passed,
which does not establish cross-system builds.

### Final software review corrections

The final corrections tighten Markdown table structure and code-example
exclusion, reuse supported GitHub repository-route validation, and discover
source-branch PRs across all bases before checking ownership. Controlled
transport evidence proves a retargeted PR is rejected without a push or PR
creation. One redundant stale-selector test row and three unused test helpers
were removed; the real CLI stale-selector test, source collision boundaries,
and historical migration fixtures remain.

After these corrections, the focused suite passed 244 tests. The full suite
passed 791 tests in 47.90 seconds with 91% coverage, compared with the earlier
782-test run: ten new regression cases and one redundant row removed. Lock
validation, Ruff formatting and lint, Ty, sdist/wheel builds, structural pack
verification, actionlint and zizmor passed. Nix formatting and native flake
checks passed with an isolated temporary cache and local daemon access; the
same incompatible systems were omitted.

The new `just check-all` attempt stopped at the OSV audit because sandbox DNS
could not resolve `api.osv.dev`. All later checks were run separately. The
dependency audit subsequently passed with network access, reporting no known
vulnerabilities or adverse project statuses in the same ten packages. This
correction changed neither dependency declarations nor the lock file. No live
source generation, downloads, device checks or real remote writes were repeated.
The earlier baseline and device measurements remain unchanged.

## Review and specification closure

Four review lenses covered behavior, publication races and failure handling,
idiomatic structure, and test proportionality. One combined correction pass
addressed the findings, and one scoped re-review closed all five important
findings and the documentation clarification. No findings remain from that
review. The strict change check and all ten main-spec checks passed. The four
affected main specifications match their reviewed deltas, including preserved
unmentioned requirements and surviving scenarios. The change artifacts were
archived on 2026-09-11; the final task-evidence audit follows that archival step.
