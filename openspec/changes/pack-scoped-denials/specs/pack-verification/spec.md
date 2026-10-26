# Spec Delta

## MODIFIED Requirements

### Requirement: Offline verification labels and pairs rendered entries by family

The system SHALL validate the composition policy, denylist and overlay without
fetching source catalogs. It SHALL give each rendered entry a family label: the
explicit family of the policy projection covering the entry's package id and
normalized project URL, as "App families form by project URL under the composition policy" in pack-composition defines, and otherwise the entry's normalized project
URL. A track-only entry SHALL be labelled by the same projections as an
installable entry, so its label always names the family composition placed it
in. Offline verification SHALL NOT pair entries across variants; README
catalog generation pairs a single-screen entry with the dual-screen entry
carrying the same label. When a label repeats within a variant, the denial,
pin, overlay-target and structural checks SHALL still consider the entries
carrying it, so no finding depends on entry order. README catalog generation
SHALL fail on any such repeat instead of pairing. These labels serve
verification messages, README pairing and README ordering only. Projections SHALL carry the family only; offline verification
SHALL NOT check a build's kind, which no candidate rule declares and which
rendered entries cannot reveal. Ambiguous projections, invalid configuration
and forbidden overlay fields SHALL fail.

It SHALL reject a label repeated within a variant with those entries
identified, an entry at a project URL a denial names in a variant that denial
applies to, violations of candidate pins, and overlay records whose URL matches
no entry in either variant. A label present in one variant and absent from the
other SHALL NOT be a finding. A pin SHALL be checked by the presence of its id and normalized
project URL in its variant, which needs no family name; when an overlay record
at the pin's URL patches `id`, the pin SHALL be checked against the patched id,
since rendered entries carry it. A package id carried by more than one entry
within a variant SHALL be reported as a nonfatal finding naming the variant,
the package id and the entries, and SHALL NOT affect the entries' labels.
A denial matching no rendered entry SHALL NOT be a finding.

Each offline finding SHALL be either an error or a nonfatal finding. The
repeated package id finding is nonfatal; every other finding is an error. Only errors SHALL fail `pack verify` and the build's
offline gate, and only errors SHALL withhold publication of the packs and the
regenerated README. A build whose offline verification records only nonfatal
findings SHALL publish the packs and the regenerated README, and its build
report's offline verdict SHALL carry those findings in their own list without
failing the verdict.

Verification reads the ids entries are rendered with, so it sees any overlay
`id` patch. An overlay record that patches `id` at a URL whose family rules
name different families SHALL fail when verification loads the overlay and
composition policy, identifying the record and the families at that URL,
before any entry is labelled. An accepted `id` patch therefore sits only at a
URL whose rules agree or that no rule names, where the label does not depend
on the id.

These checks SHALL NOT claim to verify source provenance, optimal winner ranking,
rule presence in unfetched catalogs or actual patch values. Those candidate-level
checks remain build responsibilities. Offline verification SHALL NOT rewrite
outputs or require previous build reports to interpret family labels.

#### Scenario: Overlay has no target

- **WHEN** an overlay record's URL matches an entry in neither variant
- **THEN** verification reports a stale overlay

#### Scenario: Single family is missing from dual

- **WHEN** a family present in single has no dual output
- **THEN** verification succeeds and records no finding for that family

#### Scenario: Different-repository family replacement is present

- **WHEN** policy projects single and dual output entries at different URLs
  onto one explicit family
- **THEN** both entries get that family's label

#### Scenario: One repository's entries pair by URL

- **WHEN** single and dual entries share a normalized project URL, carry
  different package ids, and no projection covers either
- **THEN** both entries get that URL's label

#### Scenario: Only nonfatal findings are recorded

- **WHEN** the rendered pair holds one package id repeated within a variant, and
  nothing else is wrong
- **THEN** `pack verify` exits zero with status success and lists the finding
  as a nonfatal finding in `.build/verify.json`
- **AND** `pack build` publishes both packs and the regenerated README, and its
  report's offline verdict passes and lists the nonfatal finding

#### Scenario: Pinned output is another repository

- **WHEN** the rendered family winner differs from the pin's id-and-URL projection
- **THEN** offline verification fails with the family and target identified

#### Scenario: Absent losing candidate cannot be assessed offline

- **WHEN** a policy selector refers to a candidate not represented in the outputs
- **THEN** offline verification does not claim whether that source candidate exists
- **AND** build must still enforce selector presence against fetched candidates

#### Scenario: A label repeats within a variant

- **WHEN** two entries of one variant carry the same label, whether through
  one explicit family or through one URL no projection covers
- **THEN** offline verification fails with the label and both entries
  identified
- **AND** the result is the same in either entry order, and README catalog
  generation fails

#### Scenario: A package id repeats within a variant

- **WHEN** one variant's output holds two entries with one package id under
  different labels
- **THEN** offline verification succeeds and reports the repeated package id
  as a nonfatal finding naming both entries
- **AND** each entry keeps its own label

#### Scenario: A tracker sits at a ruled URL

- **WHEN** rules at project URL X assign an installable entry's package id
  `app:a` and a track-only entry's package id `app:a-tracker`, and dual holds
  both entries
- **THEN** each entry carries its own rule's label, no label repeats, and
  verification succeeds
- **AND** a track-only entry at a URL whose rules all name `app:a` is labelled
  `app:a`, as an installable entry there would be

#### Scenario: A pin's URL carries an overlay id patch

- **WHEN** a pin names id `p` at URL X, an overlay record at X patches `id` to
  `q`, and the pin's variant holds an entry with `q` at X
- **THEN** the pin check passes

#### Scenario: An id patch at a split URL fails on load

- **WHEN** rules at URL X assign ids `a` and `b` to `app:a` and `app:b`, and an
  overlay record at X patches `id` to `c`
- **THEN** offline verification fails while loading the overlay and
  composition policy, naming the record and the families `app:a` and `app:b`,
  before labelling any entry

#### Scenario: An entry at a denied URL is published

- **WHEN** a variant holds an entry whose normalized project URL a denial
  applying to that variant names
- **THEN** offline verification fails with the variant, entry and denial
  identified

#### Scenario: An entry in a variant its URL's denial does not name

- **WHEN** dual holds an entry whose normalized project URL a denial naming
  only the single-screen pack names
- **THEN** offline verification records no finding for that entry
