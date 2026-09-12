# Validation

## Final checks

Run at the branch head after the review, its fixes, and the fixes for the
verification findings:

- `just check-all` in the dev shell passed: lock, format, lint and type
  checks, 732 tests with coverage, `pack verify`, the write-side tests under
  CPython 3.12 (`just check-py312`, 121 tests), actionlint and zizmor, the
  documentation link check, the nix format check and `nix flake check`.
- A live `uv run pack build` exited zero, and
  `git diff --exit-code dist/ README.md` then reported no change, so the
  committed packs and README catalog match what the current upstream
  sources build.
- `uv run pack verify` exited zero.
- `openspec validate standardize-publication --strict` reported the change
  valid.

## Test count

732 tests pass, against 771 when this change started. The retired
publishers' suites left with their modules: the six old nightly test
modules, the nightly workflow substring checks, `test_source_publication.py`
and `test_source_workflow.py`. New suites cover `prepare`, `push` and
`release`, `stage` and `publish`, the shared write-side helpers, the
write-side runtime guard and the structured workflow test.

## Line counts

Counted as the lines of the `.py` files tracked under each path.

| Path | Start (main, 42980a8) | End | Delta |
|---|---|---|---|
| `src/` and `scripts/` | 8,791 | 6,731 | -2,060 |
| `tests/` | 12,224 | 12,031 | -193 |

The proposal estimated about 5,800 and 8,200 lines. It was written before
four later decisions, which account for the gap:

- the split of each workflow into a read-only job and a write job, which
  added the bundle hand-off and its checks;
- the shared standard-library helper module for the write side;
- the tests added after a mutation review showed that several guards (the
  parent check, the bot-branch overwrite, disabled hooks, the canonical
  release body, `gh` write failures and the workflow step conditions) had
  no test that failed when they broke;
- the tests added after verification, each shown to fail against a planted
  defect: that `stage` never stages the policy, packs or README, that fork
  and duplicate PRs are left alone when the candidate is unchanged, that
  hooks stay disabled in `publish`, that the release step refuses a
  symlinked pack file and reports each release state failure's exact
  reason, that repairs upload both assets, that every action is pinned to a
  commit SHA, and that the runtime guard reads `scripts/__init__.py`.

## Live generation comparison

Ran `uv run pack generate-source codm` against the live network. The command
exited zero and `.build/source-generation/codm/report.json` reported
`"status": "success"`.

`.build/source-generation/codm/catalog.json` differs from the committed
`config/catalogs/codm.json`: the generator picked up two projects added to
the upstream README since the committed catalog was last generated
(`github.com/igawa6/tomba2recompds` and `github.com/kalenjohnson/chrono-duo`),
matching the report's `changes.added` list. No entries were removed or
changed (`changes.removed` and `changes.changed` are both empty), and every
other committed project resolved identically.

The run also recorded one retained failure, for
`github.com/rsigristc/dw3-ds-android`: its eligible APK assets declare
disagreeing package IDs (`com.digitaladventure.dw2003` and
`com.digitaladventure.dw2003.remote`). Its effective policy is unchanged, so
the generator kept its committed entry instead of failing the run. Whether
the disagreement is temporary is unknown; if it persists, the project stays a
retained failure on every run until its policy selects one APK family.

This is the expected behavior of stateless generation: real upstream drift
since the catalog was last committed, not a defect in this change. The
generated candidate was not copied over the committed catalog.

Because the live candidate adds two projects, the first source workflow run
after main is pushed is expected to open a proposal rather than reproduce the
committed catalog. That run is the first real exercise of the source
hand-off.

## Not established

- No GitHub Actions run of either rewritten workflow. The bundle hand-off
  between real jobs, the write jobs on the runner's preinstalled `python3`,
  `gh auth setup-git` with a real job token, artifact upload and download
  between jobs, and `actions/download-artifact` at its pinned commit are
  tested only locally, with temporary repositories, a bare remote and a
  stubbed `gh`.
- No PR created, edited or closed on GitHub, and the "Allow GitHub Actions to
  create and approve pull requests" setting is unverified.
- No release write. The digest record, the served-asset digests GitHub
  reports after an upload, and the published-prerelease checks are tested
  only against stubbed `gh release view` output. Locally, gh 2.100.0 reports
  a missing release as `release not found` with exit status 1, the text the
  release step matches before adding the bootstrap guidance; the `gh`
  version on the runner image is unverified.
- No device check of the published packs.
