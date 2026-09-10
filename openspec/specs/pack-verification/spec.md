# pack-verification Specification

## Purpose

Establishes whether existing rendered packs, local configuration and the generated
catalog satisfy structural and consistency checks, with reproducible evidence tied
to exact input bytes. Verification makes no upstream or device-behavior guarantee.

## Requirements

### Requirement: Offline verification checks the serialized pair

The system SHALL validate both rendered import documents without fetching,
hydrating, repairing or rewriting them. It SHALL reject missing/unreadable files,
invalid JSON including non-finite numbers, non-object roots, non-list `apps`,
non-object `settings`, malformed app records, duplicate ids within a variant,
and unsupported source types. Each app SHALL have nonempty string `id`, `name`
and absolute HTTP(S) `url`, string `author`, string-list `categories`, and
`overrideSource` equal to GitHub, HTML or GitLab. GitLab entries SHALL use
public HTTPS gitlab.com project URLs with a namespace and project, optionally
including subgroups (at most 21 path components in total), with the full case-sensitive project path preserved. Track-only ids SHALL NOT be required
to follow Android package-name syntax.

`additionalSettings` SHALL be a string decoding to an object with every key
defined by the committed defaults for its source type, with correctly typed
known settings. Nested HTML steps and header records SHALL be checked. Optional
`preferredApkIndex`, when present, SHALL be an integer, not a boolean. Unknown
fields SHALL NOT be removed or rejected solely for being unknown offline.
`settings.categories` SHALL decode from a string to a mapping of the exact
observed category names to unsigned 32-bit integer ARGB colours, consistent with
the configured colours and existing deterministic fallback rule. Other configured
pack settings SHALL agree with the rendered settings block.

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

#### Scenario: Ordinary offline verification accepts the rendered Aurora pair

- **WHEN** both normally rendered packs contain Aurora with `overrideSource: GitLab`, its canonical public HTTPS gitlab.com project URL and correctly typed complete GitLab settings, and all other offline checks pass
- **THEN** ordinary offline verification succeeds for both variants without network access, hydration, repair or rewriting

#### Scenario: Unsupported source remains an offline error

- **WHEN** either rendered pack contains an `overrideSource` other than GitHub, HTML or GitLab
- **THEN** offline verification fails with the variant, id and offending source identified and no network requests occur

#### Scenario: GitLab defaults are incomplete or mistyped

- **WHEN** a rendered GitLab entry lacks a committed default key or supplies a known setting with the wrong type
- **THEN** offline verification fails without hydrating or repairing the entry

### Requirement: Offline verification checks local composition constraints

The system SHALL validate the composition policy, denylist and build-bound
overlays without fetching source catalogs. It SHALL interpret rendered families
using effective id and normalized project URL projections from the policy,
falling back to package families where no active rule applies. Historical mappings
SHALL be validated as configuration but SHALL NOT participate in current output
family projection, eligibility, pins or coverage. Ambiguous projections,
invalid configuration and forbidden overlay fields SHALL fail.

It SHALL reject duplicate selected families within a variant, a denied package
or family remaining in scope, violations of projected eligibility or candidate
pins, stale id-and-URL overlay targets, and single families absent from dual
without the explicit composition exemptions. A common patch matching either
variant SHALL be valid; stale exclusions SHALL remain nonfatal. A different
package in the same declared family SHALL satisfy coverage. Unique output package
ids SHALL still be required independently.

These checks SHALL NOT claim to verify source provenance, optimal winner ranking,
rule presence in unfetched catalogs or actual patch values. Those candidate-level
checks remain build responsibilities. Offline verification SHALL not rewrite
outputs or require previous build reports to interpret family coverage.

#### Scenario: Dual-only overlay has no target

- **WHEN** the named id-and-URL pair exists only in single
- **THEN** verification reports a stale dual overlay

#### Scenario: An explicit exclusion permits different coverage

- **WHEN** a single family's dual output is absent and its family or single winner's package is denied for dual
- **THEN** coverage passes even if the denial removed no candidate

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

### Requirement: Offline verification checks the generated catalog

Verification SHALL reject a missing, unreadable or malformed README and a catalog
that differs from deterministic generation using the captured serialized packs
and current composition policy. Handwritten content SHALL NOT affect catalog
comparison but SHALL be included in the exact input fingerprint. Verification
SHALL NOT rewrite any inputs or fetch sources to generate the expected catalog.
Catalog errors SHALL prevent live requests like other offline errors.

#### Scenario: Stale import link

- **WHEN** an app's exported configuration differs from its README import payload
- **THEN** offline verification fails without repairing either file

#### Scenario: Handwritten instructions change

- **WHEN** README instructions change outside valid markers and the catalog remains current
- **THEN** a new offline verification succeeds and fingerprints the new README bytes

### Requirement: Verification is limited to local structural guarantees

Verification SHALL make no network requests or simulate Obtainium release
selection, HTML traversal, Dart regular-expression semantics, effective-version
extraction, or device behavior. It SHALL retain local serialized-output,
composition, settings and generated-catalog checks. Unknown settings SHALL remain
acceptable when structurally valid, without a support claim. Regular-expression
settings SHALL be validated as the required data type, not compiled in Python
as a claim of Dart compatibility. Success SHALL establish only the documented
local checks, not upstream health, download availability, package identity,
installation, or absence of spurious update notifications.

#### Scenario: Upstream release becomes unavailable

- **WHEN** existing exports and local configuration pass structural checks but an app's upstream release is unavailable
- **THEN** `pack verify` succeeds without observing or making a claim about that upstream

#### Scenario: Pattern semantics are outside the guarantee

- **WHEN** a regex setting has the correct structural type but may be invalid in Obtainium
- **THEN** structural verification does not evaluate it or claim syntax compatibility

### Requirement: Structural verification evidence belongs to an exact input snapshot

Standalone verification SHALL write `.build/verify.json` separately from the
build report. It SHALL identify structural/offline scope, schema and verifier
versions, observation times, completion and status, exact input fingerprints,
and errors with variant, entry and field context where applicable. Fingerprints
SHALL cover both output files, denylist, both overlays, composition policy, pack
settings and README. Missing and unreadable inputs SHALL be explicit. HTTP
configuration and credentials SHALL NOT be required, read, or fingerprinted by
structural verification. Reports SHALL NOT contain resolved versions, asset
probes, compatibility classifications, or an Obtainium compatibility guarantee.

The system SHALL write an incomplete running record before validation and replace
it atomically on completion, including failure. Independently discoverable errors
SHALL be collected across both variants. Input changes during the run SHALL
prevent success for the current files. Completion with no errors SHALL be
required for success. Cached package IDs and previous reports SHALL NOT bypass
these checks. Obsolete verification report schemas SHALL require regeneration
and SHALL NOT authorize publication.

#### Scenario: Independent errors in both variants

- **WHEN** both exports contain structurally invalid entries
- **THEN** verification reports independently discoverable failures in both variants without network access

#### Scenario: Interrupted verification

- **WHEN** verification stops after its running record and before completion
- **THEN** its evidence remains incomplete and cannot be presented as success

#### Scenario: Inputs change during verification

- **WHEN** the composition policy, README, or another fingerprinted input changes during verification
- **THEN** the result cannot be successful for the current files

#### Scenario: Network configuration is absent

- **WHEN** all structural inputs are valid but HTTP configuration and API credentials are absent
- **THEN** structural verification succeeds without consulting either

#### Scenario: Obsolete evidence

- **WHEN** an old report uses the retired live-capable schema
- **THEN** the user is instructed to regenerate it with `pack verify` and publication rejects it
