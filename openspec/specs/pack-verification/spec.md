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

### Requirement: Offline verification labels and pairs rendered entries by family

The system SHALL validate the composition policy, denylist and overlay without
fetching source catalogs. It SHALL give each rendered entry a family label: the
explicit family of the policy projection covering the entry's package id and
normalized project URL, as "Composition policy assigns app families by project
URL" in pack-composition defines, and otherwise the entry's normalized project
URL. A track-only entry SHALL be labelled by the same projections as an
installable entry, so its label always names the family composition placed it
in. It SHALL pair a single-screen entry with the dual-screen entry carrying
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
candidate pins, and overlay records whose URL matches no entry in either
variant. A single entry with no dual pair SHALL be reported as a nonfatal
single-only coverage finding naming its label, package id and project URL, and
SHALL NOT fail verification, matching the build's single-only coverage
finding. A pin SHALL be checked by the presence of its id and normalized
project URL in its variant, which needs no family name; when an overlay record
at the pin's URL patches `id`, the pin SHALL be checked against the patched id,
since rendered entries carry it. A package id carried by more than one entry
within a variant SHALL be reported as a nonfatal finding naming the variant,
the package id and the entries, and SHALL NOT affect pairing or coverage.
A denial matching no rendered entry SHALL NOT be a finding.

Each offline finding SHALL be either an error or a nonfatal finding. The
single-only coverage and repeated package id findings are nonfatal; every other
finding is an error. Only errors SHALL fail `pack verify` and the build's
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
outputs or require previous build reports to interpret family coverage.

#### Scenario: Overlay has no target

- **WHEN** an overlay record's URL matches an entry in neither variant
- **THEN** verification reports a stale overlay

#### Scenario: Single family is missing from dual

- **WHEN** a family present in single has no dual output
- **THEN** verification succeeds and reports a nonfatal single-only coverage
  finding naming that family's label, package id and project URL

#### Scenario: Different-repository family replacement is present

- **WHEN** policy projects single and dual output entries at different URLs
  onto one explicit family
- **THEN** offline coverage passes without requiring the single entry in dual

#### Scenario: One repository's entries pair by URL

- **WHEN** single and dual entries share a normalized project URL, carry
  different package ids, and no projection covers either
- **THEN** they pair under that URL's label

#### Scenario: Only nonfatal findings are recorded

- **WHEN** the rendered pair holds one single entry without a dual pair and one
  package id repeated within a variant, and nothing else is wrong
- **THEN** `pack verify` exits zero with status success and lists both
  findings as nonfatal findings in `.build/verify.json`
- **AND** `pack build` publishes both packs and the regenerated README, and its
  report's offline verdict passes and lists both nonfatal findings

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

- **WHEN** either variant holds an entry whose normalized project URL a denial
  names
- **THEN** offline verification fails with the variant, entry and denial
  identified

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
input bytes it checked, and its errors and its nonfatal findings, each kind in
its own list, with variant, entry and field context where applicable. Fingerprints SHALL cover both output files, denylist, overlay,
composition policy and README. Missing and unreadable inputs SHALL be explicit.
HTTP configuration and credentials SHALL NOT be required, read, or fingerprinted
by structural verification. Reports SHALL NOT contain resolved versions, asset
probes, compatibility classifications, or an Obtainium compatibility guarantee.

Verification SHALL check and fingerprint one captured set of input bytes,
collect independently discoverable errors across both variants, and succeed
only when those bytes have no errors; nonfatal findings SHALL NOT affect the
recorded status. The command's exit status SHALL be the
verification outcome; the report SHALL NOT serve as authorization for
publication. Previous reports SHALL NOT bypass these checks. The report's
schema version SHALL advance whenever its fields change, as adding the
nonfatal findings list does. A verification report with any schema other than
the current one SHALL require regeneration with `pack verify`, and SHALL be
labelled neither current nor stale.

The verifier identity recorded in a report SHALL advance whenever a change
alters what verification checks or which findings it reports, so a report of
the current schema saved by an earlier verifier over unchanged input bytes is
labelled stale rather than treated as current evidence.

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

#### Scenario: Verification checks change over unchanged inputs

- **WHEN** a release changes what verification checks without changing the
  report schema, and a report saved by the previous verifier passed over input
  bytes that are still unchanged
- **THEN** the running verifier's identity differs from the report's, and
  `pack report` labels that report stale until `pack verify` regenerates it
