## Why

A candidate without a family rule forms family `package:<id>`, and an explicit rule gives its
candidate an `app:` family. Source precedence only picks a winner inside one family, so when a
rule-less candidate and an explicitly assigned candidate carry one package id, or two explicit
families do, and both are selected in one variant, the build fails on the distinct-family package
check instead of letting precedence decide. A rule-less candidate at an explicit rule's projected
id and URL fails the rendered-projection check the same way. Every new source, and every pair of
independently checked source updates that later merge, can run into these failures and needs a
special-case rule. Families should form from shared identity so that precedence settles these
collisions the same way it settles everything else.

Two sources listing different package ids at one repository ship both entries today, or fail
dual coverage when one is single-only and the other dual-only. That stays as it is: an explicit
`app:` rule or a `packageId` correction joins them when that is wanted.

## What Changes

- Families form transitively from shared identity over the candidates that survive denials and
  are eligible for some variant, through two edges only: a shared effective package id, and a
  shared explicit `app:` family. A rule carrying `family` also assigns its family to rule-less
  candidates at its projected id and URL, whether or not the ruled candidate survives. Denied and
  wholly ineligible candidates never join or name a family. There is no project URL edge.
- A family without an explicit assignment holds exactly one effective package id and is named
  `package:<id>`, as today.
- Two different explicit `app:` families joined through a shared effective package id fail the
  build with both named. This replaces the rendered-projection conflict error.
- A pin on a rule-less candidate names its formed family, and the build checks it; the parse-time
  pin-family check remains only for pins with an explicit `app:` projection and runs first. A pin
  on a denied or wholly ineligible candidate fails as that exclusion, not as wrong-family.
- After selection every family that publishes in both variants must pair the way offline
  verification does. A family's winners can differ in package id only inside an explicit family,
  and then pair only when both selected entries project that family; a rule on a losing member is
  not enough. Otherwise the build fails naming the family and both entries and asking for a
  `family` rule on each selected entry that does not yet project it. Offline verification and the
  README stay provenance-free.
- Retired: the failure for different families selecting one effective package id, which can no
  longer occur because candidates sharing an id always form one family. Package ids stay unique
  per output.
- Offline verification and README catalog generation pair single-screen and dual-screen entries
  without source provenance in two passes: same package id, then same explicit family. Entries
  whose projections name different explicit families never pair. Verification rejects a repeated
  package id (the existing duplicate-id finding) and an explicit family repeated within a variant,
  leaving the entries carrying that id or family in both variants out of pairing and coverage
  (README generation fails on them), so pairing is order-independent. Coverage accepts a pair
  sharing an id or an explicit family. The `duplicate_family` finding is removed.
- No configuration or policy schema changes. Current exports and the README catalog are expected
  to stay byte-identical. Every candidate in the current build report, with identity corrections
  applied, regroups into exactly the current 120 families, and golden tests confirm this against
  the full candidate set.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-composition`: family formation, formation after denials in the stage order, pins on
  rule-less candidates, the post-selection pairing check, selection wording, retirement of the
  cross-family package collision.
- `pack-verification`: offline consistency pairs entries without provenance by id and explicit
  family, and rejects an explicit family repeated within a variant.
- `readme-catalog`: catalog rows come from the same pairing.
- `pack-cli`: the build-report conflict scenario no longer names a package collision and states
  what each composition conflict identifies.

## Impact

Code: `composition_policy.py` (family formation, pairing helper, pin parse check),
`merge.py` (family grouping after exclusions, pin family check, post-selection pairing check; the
distinct-family package check becomes unreachable and is removed), `offline.py` and `catalog.py`
(one shared pairing function). Tests in `test_composition.py`, `test_verify.py`,
`test_offline.py`, `test_catalog.py` and the golden fixtures. No new dependencies and no configuration edits.

Retires one failure mode (distinct families selecting one package), the projection-conflict error,
and `duplicate_family`. Estimate: 7 modified requirements, about 15 added or changed scenarios,
120-200 implementation lines and 200-350 test lines. These are estimates, not targets. No retry,
ownership or race requirement is added: an inconsistent policy fails visibly and a corrected
policy reruns.
