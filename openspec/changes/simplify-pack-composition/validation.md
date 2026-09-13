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
reported the change valid.

The suite has 761 tests, against 732 at the start of this change.

| Measure | Start | Now | Removed | Added | Net |
| --- | ---: | ---: | ---: | ---: | ---: |
| Implementation (`src/` and `scripts/` Python) | 6,731 | 6,151 | 1,332 | 752 | -580 |
| Tests (`tests/` Python) | 12,031 | 12,118 | 1,705 | 1,792 | +87 |

The proposal estimated about 850 implementation lines removed and 80 added, and
about 1,000 test lines removed and 200 added. The implementation removed more
than estimated, and added more, because the credential-scoped HTTP client moved
into its own module and git counts the moved lines once as removed and once as
added. The tests did not shrink as estimated, for three reasons:

- the credential, redirect and bounded-read tests moved with that client, and
  are likewise counted on both sides;
- each retired configuration field gained a test that it now fails with the
  entry and field identified;
- new tests cover the dual-screen build model, the guard that keeps each curated
  extra selected in the single-screen pack, and the build's one read of its
  local inputs.

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

The freshly built `dist/dual-screen.json` and `README.md` differ from the
committed copies, while `dist/single-screen.json` matches. The base and the
branch build the same bytes, so the difference is upstream change since the
last committed nightly output, not this change. This change does not update the
committed packs.

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
