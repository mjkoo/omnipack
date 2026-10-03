## ADDED Requirements

### Requirement: Offline verification labels and pairs rendered entries by family

The system SHALL validate the composition policy, denylist and overlay without
fetching source catalogs. It SHALL give each rendered entry a family label: the
explicit family of the policy projection covering the entry's package id and
normalized project URL, as "Composition policy assigns app families by project
URL" in pack-composition defines, and otherwise the entry's normalized project
URL. It SHALL pair a single-screen entry with the dual-screen entry carrying
the same label. When a label repeats within either variant, the entries
carrying that label in both variants SHALL be left out of pairing and coverage
and SHALL receive no pairing or coverage finding, while the denial, pin,
overlay-target and structural checks SHALL still consider them, so no finding
or row depends on entry order. README catalog generation SHALL fail on any such
repeat instead of pairing. These labels serve verification messages and README
ordering only. Projections SHALL carry the family only; offline verification
SHALL NOT check eligibility, which no candidate rule declares and which
rendered entries cannot reveal. Ambiguous projections, invalid configuration
and forbidden overlay fields SHALL fail.

It SHALL reject a label repeated within a variant with those entries
identified, an entry at a denied project URL in either variant, violations of
candidate pins, overlay records whose URL matches no entry in either variant,
and single entries with no dual pair. A pin SHALL be checked by the presence of
its id and normalized project URL in its variant, which needs no
family name. A package id carried by more than one entry within a variant SHALL
be reported as a nonfatal finding naming the variant, the package id and the
entries, and SHALL NOT affect pairing or coverage. Stale exclusions SHALL
remain nonfatal.

These checks SHALL NOT claim to verify source provenance, optimal winner ranking,
rule presence in unfetched catalogs or actual patch values. Those candidate-level
checks remain build responsibilities. Offline verification SHALL NOT rewrite
outputs or require previous build reports to interpret family coverage.

#### Scenario: Overlay has no target

- **WHEN** an overlay record's URL matches an entry in neither variant
- **THEN** verification reports a stale overlay

#### Scenario: Single family is missing from dual

- **WHEN** a family present in single has no dual output
- **THEN** verification reports the coverage gap for that family

#### Scenario: Different-repository family replacement is present

- **WHEN** policy projects single and dual output entries at different URLs
  onto one explicit family
- **THEN** offline coverage passes without requiring the single entry in dual

#### Scenario: One repository's entries pair by URL

- **WHEN** single and dual entries share a normalized project URL, carry
  different package ids, and no projection covers either
- **THEN** they pair under that URL's label

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
- **AND** no entry carrying that label in either variant pairs or is reported
  as a coverage gap, in either entry order, and README catalog generation fails

#### Scenario: A package id repeats within a variant

- **WHEN** one variant's output holds two entries with one package id under
  different labels
- **THEN** offline verification succeeds and reports the repeated package id
  as a nonfatal finding naming both entries
- **AND** each entry pairs and is checked for coverage under its own label

#### Scenario: An entry at a denied URL is published

- **WHEN** either variant holds an entry whose normalized project URL a denial
  names
- **THEN** offline verification fails with the variant, entry and denial
  identified

## MODIFIED Requirements

### Requirement: Offline verification checks the serialized entry shape

The system SHALL validate both rendered import documents without fetching,
hydrating, repairing or rewriting them. It SHALL reject missing or unreadable
files, invalid JSON including non-finite numbers, non-object roots, non-list
`apps`, non-object `settings`, malformed app records and unsupported source
types. A package id repeated within a variant SHALL be reported as a nonfatal
finding, as "Offline verification labels and pairs rendered entries by family"
defines, not rejected as malformed. Each app SHALL have nonempty string `id`,
`name` and absolute HTTP(S) `url`, string `author`, string-list `categories`,
`overrideSource` equal to GitHub, HTML or GitLab, `allowIdChange` equal to
`true`, and `additionalSettings` as a string decoding to an object. Track-only ids SHALL NOT be required to follow
Android package-name syntax. Unknown fields SHALL NOT be removed or rejected
solely for being unknown offline.

Within decoded settings, a setting named by the committed defaults for the
entry's source type SHALL have the same JSON type as its default. For HTML
entries, each `intermediateLink` step SHALL be an object carrying every step
field with its expected type, and each `requestHeader` record SHALL be an
object with a string `requestHeader`. Optional `preferredApkIndex`, when
present, SHALL be an integer, not a boolean. These values reach the packs from
upstream catalog records and overlay patches, and rendering copies them without
checking their types, so offline verification is their only check before
publication.

Default-key completeness, the rendered pack settings and category colours, and
GitLab project URL rules SHALL be outside offline verification. Rendering fills
every default key and derives every category colour from the entries it
renders, and ingestion enforces the GitLab URL rules.

#### Scenario: A rendered settings object is not string encoded

- **WHEN** an entry carries an object directly as `additionalSettings`
- **THEN** verification fails with its variant, id and field identified
- **AND** no repair or network request occurs

#### Scenario: Invalid entries in both variants

- **WHEN** one variant contains an app record without a name and the other
  contains a setting of the wrong type
- **THEN** both independently discoverable errors are reported

#### Scenario: Unknown fields are structurally valid

- **WHEN** a structurally valid entry includes an unknown extra setting
- **THEN** offline verification preserves the input and does not claim that the
  setting behaves correctly in Obtainium

#### Scenario: Unsupported source remains an offline error

- **WHEN** either rendered pack contains an `overrideSource` other than GitHub, HTML or GitLab
- **THEN** offline verification fails with the variant, id and offending source identified and no network requests occur

#### Scenario: A known setting has the wrong type

- **WHEN** a rendered entry's decoded settings hold a known setting whose type
  differs from its default, or the entry's `preferredApkIndex` is a boolean or a
  string
- **THEN** offline verification fails with the variant, id and field identified,
  without hydrating or repairing the entry

#### Scenario: A nested HTML step or request header is malformed

- **WHEN** an HTML entry's `intermediateLink` step lacks a step field or holds
  one of the wrong type, or a `requestHeader` record lacks a string
  `requestHeader`
- **THEN** offline verification fails with the variant, id and setting
  identified

#### Scenario: A default key is absent

- **WHEN** a rendered entry's decoded settings lack a default key, and every
  other check passes
- **THEN** offline verification succeeds without claiming that the settings
  behave correctly in Obtainium


## REMOVED Requirements

### Requirement: Offline verification checks rendered composition consistency

**Reason**: Rendered entries now pair by one family label, explicit projection or normalized URL, in one pass, and a repeated package id is no longer fatal.

**Migration**: Replaced by "Offline verification labels and pairs rendered entries by family".
