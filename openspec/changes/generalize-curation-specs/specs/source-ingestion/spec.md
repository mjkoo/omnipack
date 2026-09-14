## ADDED Requirements

### Requirement: Committed codm2000 entries keep device-aware source semantics

The system SHALL ingest accepted codm2000 entries from committed Obtainium JSON.
README parsing and package-ID resolution SHALL occur only in the separate
source-generation operation. The source catalog SHALL contain generated GitHub
project entries independently of other upstream coverage, including APKs and
explicit track-only resources. It SHALL retain discovery settings such as
prerelease enablement and filename filters, and SHALL NOT reinterpret a
track-only resource ID as an Android package ID.

During routine ingestion, codm2000 entries SHALL be dual-screen builds,
eligible for dual only and preferred there; composition policy SHALL NOT change
that. A normalized project URL already supplied by a higher-precedence
candidate that its source makes eligible for dual SHALL suppress the
corresponding codm2000 candidate before exclusions and selection. Single-only
coverage SHALL NOT suppress it. Suppression SHALL use source eligibility alone,
and ingestion SHALL NOT read or apply the composition policy. Merely appearing
in codm2000 SHALL NOT promote an ordinary higher-source build.

Retained entries SHALL preserve codm2000 provenance, generated origin, original
package identity and source settings so existing family rules and fork-specific
overlays continue matching. Active candidate selectors SHALL be validated
against the complete admitted candidate set. Missing rules or pinned candidates
SHALL fail explicitly.

#### Scenario: Dual coverage suppresses a local catalog candidate

- **WHEN** a higher-source candidate covers dual with a normalized URL equal to a committed codm2000 entry
- **THEN** the codm2000 candidate is suppressed without promoting the higher-source candidate

#### Scenario: Single-only coverage leaves a dual candidate

- **WHEN** the higher-precedence candidate for that URL is eligible for single only, as an RJNY entry left out of the dual-screen export is
- **THEN** the committed entry remains a dual-screen codm2000 candidate, preferred in dual

#### Scenario: Existing generated family selector remains valid

- **WHEN** a retained committed entry has an existing generated-origin rule or overlay selector
- **THEN** its source identity is preserved and the same family and override behavior applies

#### Scenario: A selected project is removed

- **WHEN** an accepted source update removes a candidate required by an active rule or pin
- **THEN** pack composition fails explicitly rather than silently ignoring the stale selector

#### Scenario: Newly resolved prerelease apps are admitted

- **WHEN** the committed catalog includes manifest-verified APK entries with explicit prerelease settings and no higher-source coverage
- **THEN** they enter dual as installable APK entries, retaining those settings and their original identities without entering single

#### Scenario: A tracking resource keeps its identity

- **WHEN** the committed catalog includes an explicit track-only resource
- **THEN** dual retains its stable resource identity, track-only flag and manual-installation description
- **AND** neither pack's entry for the app the resource extends is replaced

## REMOVED Requirements

### Requirement: Committed codm2000 entries retain device-aware source semantics

**Reason**: Replaced by "Committed codm2000 entries keep device-aware source
semantics", which states the same rules. The EmuLnk scenario is dropped
because "Dual coverage suppresses a local catalog candidate" states the same
outcome. The Showdown-DS, Heimdall and Kanto Gear scenarios are restated without
naming projects; those projects' values remain in the reviewed project policy
and the committed catalog.

**Migration**: None. Ingestion behavior is unchanged.
