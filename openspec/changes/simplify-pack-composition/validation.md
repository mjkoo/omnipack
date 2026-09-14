# Pack composition simplification validation

Validation date: 2026-09-13 UTC, macOS aarch64, Python 3.14.7. These are local
automated checks and two live builds run back to back, not device acceptance or
a nightly publication run.

## Checks

`just check-all` passed in the dev shell: lock validation, Ruff formatting and
lint, Ty, the full test suite, structural verification of the committed packs,
the Python 3.12 check, workflow lint, the offline link check, Nix formatting and
the flake checks. Nix omitted incompatible systems, so the flake checks ran for
aarch64-darwin only. `openspec validate simplify-pack-composition --strict`
reported the change valid. After the review fixes described below, both passed
again at the branch head, with the flake checks again limited to
aarch64-darwin.

The suite has 793 tests, against 732 at the start of this change.

| Measure | Start | Now | Removed | Added | Net |
| --- | ---: | ---: | ---: | ---: | ---: |
| Implementation (`src/` and `scripts/` Python) | 6,731 | 6,145 | 1,426 | 840 | -586 |
| Tests (`tests/` Python) | 12,031 | 12,316 | 1,771 | 2,056 | +285 |

The proposal estimated about 850 implementation lines removed and 80 added, and
about 1,000 test lines removed and 200 added. The implementation removed more
than estimated, and added more, because the credential-scoped HTTP client moved
into its own module and git counts the moved lines once as removed and once as
added. The tests did not shrink as estimated, for four reasons:

- the credential, redirect and bounded-read tests moved with that client, and
  are likewise counted on both sides;
- each retired configuration field gained a test that it now fails with the
  entry and field identified;
- new tests cover the dual-screen build model, the guard that keeps each curated
  extra selected in the single-screen pack, and the build's one read of its
  local inputs;
- a verification pass after the review added direct tests for scenarios that
  only the captured-baseline regression had covered.

## Output comparison

Clean `git archive` exports of the base commit `70f7514` and the branch at
`047e305` were built back to back, at 19:15:03 and 19:15:05 UTC, each against
the live upstream catalogs. Both builds succeeded and produced byte-identical
outputs:

| File | SHA-256 |
| --- | --- |
| `dist/single-screen.json` | `f55841cc37706d93256f67b679c9b61eaf52f9fe05f61bf285cb3d0c8626f56f` |
| `dist/dual-screen.json` | `08ced8b91083ebf45e9ec438fe5c02d9eafae5c78b56531678d04873f6c85570` |
| `README.md` | `50a200699c89d8ea78b32c03c50c87f24be845f168d66858196c94beb2ede6a0` |

The branch build wrote a schema 3 build report with status `success` and a
successful offline verification. `uv run pack verify` then passed both in the
branch export and in the repository checkout: schema 3, verifier 2.0.0,
structural scope, offline mode, complete, no errors, with fingerprints of the
six inputs (both packs, denylist, overlay, composition policy and README).

The comparison was repeated after the review fixes. Clean exports of `70f7514`
and the branch at `e5326d0` were built back to back, at 22:30:21 and 22:30:23
UTC, and again produced byte-identical outputs with the hashes above. `pack
verify` passed in the branch export. Later commits change only tests and this
change's records, not rendered output.

The freshly built `dist/dual-screen.json` and `README.md` differ from the
committed copies, while `dist/single-screen.json` matches. The base and the
branch build the same bytes, so the difference is upstream change since the
last committed nightly output, not this change. This change does not update the
committed packs.

## Review fixes

An independent review of the branch was followed by fixes on it. `pack report`
reads build reports strictly. A denial whose builds are eligible for neither
pack is no longer reported stale. Protected-field overlay failures name their
selector. The offline stale overlay finding is renamed `stale_overlay`. New tests
cover the remaining composition scenarios, and the curated single-screen guard's
mutation test now exercises the guard's own check. None of these fixes changes
rendered output: the captured-baseline regression still reproduces the exact
exports. The first live comparison ran before these fixes; the repeated one
above ran after them.

## Verification follow-ups

On 2026-09-14 a verification pass over the finished branch found every
requirement implemented, but some scenarios had no direct test. Tests now cover:

- two builds sharing a package id with no pin, where the standard build wins
  single and the dual build wins dual by preference;
- an RJNY build kept out of dual, whose family's dual-only build wins dual;
- rule-less forks with similar names staying in separate families, and denials
  and package collisions seeing a corrected package id;
- the committed codm2000 outcomes for EmuLnk, Showdown-DS, Heimdall and Kanto;
- the curated single-screen guard failing for each extra made a dual-screen
  build on its own, and curated extras reporting a pin in dual;
- the family and target a pin mismatch names, and the value an unsupported
  source finding names.

Disabling dual preference makes the first two fail. None of these changes
rendered output. The design now also names the shared HTTP request, response
and retry base. `just check-all` and `openspec validate
simplify-pack-composition --strict` passed again afterward.

## Not established

- No device check was run. The comparison shows the packs are unchanged, so no
  import or installation behavior changes, but Obtainium import was not
  exercised on a device.
- The comparison covers upstream catalogs at one moment. It shows the
  simplified model reproduces the current selections; it cannot show that
  future upstream records fit the model, such as a new source record whose
  kind the maintainer would want overridden. Those now need a pin or a denial.
- Linux and the nightly publication workflow were not exercised locally.
- Configuration written by anyone other than this repository, carrying a retired
  field, fails loudly; the failure is tested, but no external configuration was
  examined.
