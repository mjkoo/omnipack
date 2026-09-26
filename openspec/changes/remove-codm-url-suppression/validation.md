# Implementation validation

Validated on 2026-09-26 against committed outputs at
`ef70a954784e2e37d23560a8ba9490653dd29858`.

## Output equivalence

The production `pack build` command entry point ran successfully with the new
code and configuration in a temporary checkout-shaped directory. It fetched the
configured upstream catalogs, composed both packs, generated the README catalog,
and passed the publication path's offline validation. Each resulting file was
compared as bytes against `git show <baseline>:<path>`.

| File | Bytes | SHA-256 | Comparison |
| --- | ---: | --- | --- |
| `dist/single-screen.json` | 105550 | `4b0526d7a6b4fe2781a01b91f7c04a9a8f1f98c5c6883b462d86d3b678df06b4` | Identical |
| `dist/dual-screen.json` | 132459 | `4c51ea78cd84439367d3c60e72e9a6ff5da80a4a4c9a07d2348c29bdda0ee24e` | Identical |
| `README.md` | 530618 | `10cce9af68ff2e3cba2f1609a7b8885554679b62bef382a17c89405d5f9fe43e` | Identical |

The build report contains exactly the 30 identities in the committed codm2000
catalog. Pixel Guide and EmuLnk retain RJNY as their dual selections with reason
`pin`. The retired codm2000 Super Metroid identity is denied. Published files
require no changes.

To repeat the comparison from this branch, run `uv run --locked pack build`, then
compare the three files above to their bytes at the baseline commit. Upstream
catalogs can change, so a later run may contain independent upstream differences.

## Tests and checks

- Baseline: 856 tests passed before implementation.
- Red regression: the same-URL, different-package-ID ingestion test failed
  because the generated candidate was omitted.
- Green ingestion: 113 source and captured-fixture tests passed. The full suite
  passed 851 tests after adding the newly admitted candidates to the recorded
  family membership fixture. Historical export snapshots remained unchanged.
- Red configuration: reconciliation failed while the retired codm2000 package
  was still selected. With the denial and pins, all 3 reconciliation tests passed.
- Completed configuration suite: 851 tests passed in 30.51 seconds.
- Final full suite after the fix review and completion audit: 851 tests passed
  in 27.44 seconds.
- Formatting, Ruff lint, and ty checks passed.

## Implementation review

All three implementation groups received independent evidencing reviews. The
output reviewer independently compared the rebuilt files against the fixed
baseline commit and confirmed the report's 30 admissions, pins and denial.

The whole-change review covered correctness, test proportionality and Python
idioms. It found no behavior defects and one redundant overlap fixture case.
That case was removed while retaining dedicated ingestion coverage. All 113
focused source tests passed, and a scoped review confirmed the finding resolved
without new issues.

The final independent completion audit confirmed all four implementation and
output tasks, identifying an implementation commit and a proving test or byte
comparison for each. It rechecked the fixed-baseline output bytes and exact
catalog admissions. It found no unevidenced checkbox and confirmed the completed
checks and reviews satisfy the remaining process task.
