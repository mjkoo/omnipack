# pack-verification Specification

## Purpose

Establishes whether existing rendered packs, local configuration and the generated
catalog satisfy structural and consistency checks, with reproducible evidence tied
to exact input bytes. Verification makes no upstream or device-behavior guarantee.

## Requirements

### Requirement: Offline verification checks the serialized entry shape

The system SHALL validate both rendered import documents without fetching,
hydrating, repairing or rewriting them. It SHALL reject missing or unreadable
files, invalid JSON including non-finite numbers, non-object roots, non-list
`apps`, non-object `settings`, malformed app records, duplicate ids within a
variant, and unsupported source types. Each app SHALL have nonempty string `id`,
`name` and absolute HTTP(S) `url`, string `author`, string-list `categories`,
`overrideSource` equal to GitHub, HTML or GitLab, and `additionalSettings` as a
string decoding to an object. Track-only ids SHALL NOT be required to follow
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

- **WHEN** one variant contains duplicate ids and the other contains a setting
  of the wrong type
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

### Requirement: Offline verification checks the generated catalog

Verification SHALL reject a missing, unreadable or malformed README and a catalog
that differs from deterministic generation using the captured serialized packs
and current composition policy. Handwritten content SHALL NOT affect catalog
comparison but SHALL be included in the exact input fingerprint. Verification
SHALL NOT rewrite any inputs or fetch sources to generate the expected catalog.
Catalog errors SHALL prevent successful verification.

#### Scenario: Stale import link

- **WHEN** an app's exported configuration differs from its README import payload
- **THEN** offline verification fails without repairing either file

#### Scenario: Handwritten instructions change

- **WHEN** README instructions change outside valid markers and the catalog remains current
- **THEN** a new offline verification succeeds and fingerprints the new README bytes

### Requirement: Verification is limited to local structural guarantees

Verification SHALL make no network requests or simulate Obtainium release
selection, HTML traversal, Dart regular-expression semantics, effective-version
extraction, or device behavior. It SHALL retain local serialized-shape,
setting-value, composition and generated-catalog checks. Unknown settings SHALL
remain acceptable when structurally valid, without a support claim.
Regular-expression settings SHALL be checked only as the required data type,
not compiled in Python as a claim of Dart compatibility. Success SHALL establish
only the documented local checks, not upstream health, download availability,
package identity, installation, or absence of spurious update notifications.

#### Scenario: Upstream release becomes unavailable

- **WHEN** existing exports and local configuration pass structural checks but an app's upstream release is unavailable
- **THEN** `pack verify` succeeds without observing or making a claim about that upstream

#### Scenario: Pattern semantics are outside the guarantee

- **WHEN** a regex setting may be invalid in Obtainium
- **THEN** structural verification does not evaluate it or claim syntax compatibility

### Requirement: Structural verification evidence belongs to an exact input snapshot

Standalone verification SHALL write `.build/verify.json` separately from the
build report, as a diagnostic. It SHALL identify structural/offline scope, schema
and verifier versions, observation times, status, fingerprints of the exact
input bytes it checked, and errors with variant, entry and field context where
applicable. Fingerprints SHALL cover both output files, denylist, overlay,
composition policy and README. Missing and unreadable inputs SHALL be explicit.
HTTP configuration and credentials SHALL NOT be required, read, or fingerprinted
by structural verification. Reports SHALL NOT contain resolved versions, asset
probes, compatibility classifications, or an Obtainium compatibility guarantee.

Verification SHALL check and fingerprint one captured set of input bytes,
collect independently discoverable errors across both variants, and succeed
only when those bytes have no errors. The command's exit status SHALL be the
verification outcome; the report SHALL NOT serve as authorization for
publication. Previous reports SHALL NOT bypass these checks. A verification
report with any schema other than the current one SHALL require regeneration
with `pack verify`.

#### Scenario: Independent errors in both variants

- **WHEN** both exports contain structurally invalid entries
- **THEN** verification reports independently discoverable failures in both variants without network access

#### Scenario: Interrupted verification

- **WHEN** verification stops before it finishes checking its captured inputs
- **THEN** the command does not exit successfully, and any existing report describes only the inputs that report's run checked

#### Scenario: Inputs change during verification

- **WHEN** an input file changes after verification captured it
- **THEN** the report describes the captured bytes, and `pack report` labels it stale for the current files

#### Scenario: Network configuration is absent

- **WHEN** all structural inputs are valid but HTTP configuration and API credentials are absent
- **THEN** structural verification succeeds without consulting either

#### Scenario: Obsolete evidence

- **WHEN** a report uses a schema other than the current one
- **THEN** the user is instructed to regenerate it with `pack verify`
