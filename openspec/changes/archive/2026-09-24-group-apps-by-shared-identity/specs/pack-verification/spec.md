## MODIFIED Requirements

### Requirement: Offline verification checks rendered composition consistency

The system SHALL validate the composition policy, denylist and overlay without
fetching source catalogs. It SHALL pair single-screen and dual-screen output
entries without source provenance in two whole passes over all entries, the
second considering only entries the first left unpaired: the same package id;
then the same explicit family through the policy's effective id and normalized
project URL projections. No pass SHALL pair two entries whose projections name
different explicit families; each such entry is judged unpaired under the usual
rules. When a package id repeats within either variant, the entries carrying
that id in both variants SHALL be left out of pairing and coverage; when an
explicit family is projected onto more than one entry within either variant,
the entries projecting that family in both variants SHALL be left out of
pairing and coverage. Such entries SHALL receive no pairing or coverage
finding, while the denial, pin, overlay-target and structural checks SHALL still
consider them, so each pass finds at most one counterpart and no finding or row
depends on entry order. README catalog generation SHALL fail on any such violation
instead of pairing. A pair's label SHALL be the explicit family either entry's
projection names, and otherwise `package:<id>` after the package id the pair
shares; an unpaired entry is labelled the same way from its own projection and
id. These labels serve verification messages and README ordering only.
Projections SHALL carry the family only; offline verification SHALL
NOT check eligibility, which no candidate rule declares and which rendered
entries cannot reveal. Ambiguous projections, invalid configuration and
forbidden overlay fields SHALL fail.

It SHALL reject a package id repeated within a variant, an explicit family
projected onto more than one entry within a variant with those entries
identified, a denied package present in either variant, violations of candidate
pins, overlay records whose id-and-URL pair is in neither variant, and single
entries with no dual pair. A repeated package id SHALL be reported once, by the
entry-level duplicate-id finding. An entry that violates both package-id and
explicit-family uniqueness SHALL be reported by both uniqueness findings. A pin SHALL be
checked by the presence of its effective id and normalized project URL in its
variant, which needs no family name. Stale exclusions SHALL remain nonfatal. A
pair satisfies coverage whether its two entries share a package id or an
explicit family.

These checks SHALL NOT claim to verify source provenance, optimal winner ranking,
rule presence in unfetched catalogs or actual patch values. Those candidate-level
checks remain build responsibilities. Offline verification SHALL NOT rewrite
outputs or require previous build reports to interpret family coverage.

#### Scenario: Overlay has no target

- **WHEN** an overlay record's id-and-URL pair exists in neither variant
- **THEN** verification reports a stale overlay

#### Scenario: Single family is missing from dual

- **WHEN** a family present in single has no dual output
- **THEN** verification reports the coverage gap for that family

#### Scenario: Different-package family replacement is present

- **WHEN** policy maps single and dual output entries with different ids to one family
- **THEN** offline coverage passes without requiring the single package in dual

#### Scenario: Pinned output is another repository

- **WHEN** the rendered family winner differs from the pin's effective id-and-URL projection
- **THEN** offline verification fails with the family and target identified

#### Scenario: Absent losing candidate cannot be assessed offline

- **WHEN** a policy selector refers to a candidate not represented in the outputs
- **THEN** offline verification does not claim whether that source candidate exists
- **AND** build must still enforce selector presence against fetched candidates

#### Scenario: An explicit family repeats within a variant

- **WHEN** projections assign one explicit family to two entries of one
  variant, whether or not the other variant holds entries of that family
- **THEN** offline verification fails with the family and both entries
  identified
- **AND** no entry projecting that family in either variant pairs or is
  reported as a coverage gap, in either entry order, and README catalog
  generation fails

#### Scenario: Matching entries name different explicit families

- **WHEN** a single entry and a dual entry share a package id, and their
  projections name different explicit families
- **THEN** they do not pair, and the single entry is reported as a coverage gap
  unless another dual entry pairs with it

#### Scenario: A package id repeats within a variant

- **WHEN** one variant's output holds two entries with one package id, and the
  other variant holds that id once, whether single or dual holds the repeat
- **THEN** offline verification reports the repeated package once as a
  duplicate id, in either entry order
- **AND** no entry carrying that id in either variant pairs or is reported as a
  coverage gap
