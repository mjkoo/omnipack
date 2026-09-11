## ADDED Requirements

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

## MODIFIED Requirements

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


## REMOVED Requirements

### Requirement: Live checks honor a declared compatibility boundary

**Reason**: Live Obtainium compatibility verification is retired.

**Migration**: Use structural `pack verify` and maintain curated settings; validate source behavior in Obtainium when needed. There is no replacement automatic live guarantee.

### Requirement: GitHub resolution respects configured release selection

**Reason**: Live Obtainium compatibility verification is retired.

**Migration**: Use structural `pack verify` and maintain curated settings; validate source behavior in Obtainium when needed. There is no replacement automatic live guarantee.

### Requirement: GitHub latest metadata prioritizes release selection

**Reason**: Live Obtainium compatibility verification is retired.

**Migration**: Use structural `pack verify` and maintain curated settings; validate source behavior in Obtainium when needed. There is no replacement automatic live guarantee.

### Requirement: HTML resolution follows the configured path

**Reason**: Live Obtainium compatibility verification is retired.

**Migration**: Use structural `pack verify` and maintain curated settings; validate source behavior in Obtainium when needed. There is no replacement automatic live guarantee.

### Requirement: Effective versions are real extraction results

**Reason**: Live Obtainium compatibility verification is retired.

**Migration**: Use structural `pack verify` and maintain curated settings; validate source behavior in Obtainium when needed. There is no replacement automatic live guarantee.

### Requirement: Reachability checks are bounded and do not prove binary identity

**Reason**: Live Obtainium compatibility verification is retired.

**Migration**: Use structural `pack verify` and maintain curated settings; validate source behavior in Obtainium when needed. There is no replacement automatic live guarantee.

### Requirement: Live requests minimize work and respect host limits

**Reason**: Live Obtainium compatibility verification is retired.

**Migration**: Use structural `pack verify` and maintain curated settings; validate source behavior in Obtainium when needed. There is no replacement automatic live guarantee.

### Requirement: Live requests preserve credential boundaries

**Reason**: Live Obtainium compatibility verification is retired.

**Migration**: Use structural `pack verify` and maintain curated settings; validate source behavior in Obtainium when needed. There is no replacement automatic live guarantee.

### Requirement: Version lint evaluates effective GitHub versions

**Reason**: Live Obtainium compatibility verification is retired.

**Migration**: Use structural `pack verify` and maintain curated settings; validate source behavior in Obtainium when needed. There is no replacement automatic live guarantee.

### Requirement: GitHub ZIP releases expose outer assets with explicit extraction limits

**Reason**: Live Obtainium compatibility verification is retired.

**Migration**: Use structural `pack verify` and maintain curated settings; validate source behavior in Obtainium when needed. There is no replacement automatic live guarantee.

### Requirement: GitLab release resolution includes uploaded description APKs

**Reason**: Live Obtainium compatibility verification is retired.

**Migration**: Use structural `pack verify` and maintain curated settings; validate source behavior in Obtainium when needed. There is no replacement automatic live guarantee.


### Requirement: Verification evidence belongs to an exact input snapshot

**Reason**: The live-capable evidence schema and its resolution guarantees are retired.

**Migration**: Regenerate structural evidence with `pack verify`; older report schemas cannot authorize publication.
