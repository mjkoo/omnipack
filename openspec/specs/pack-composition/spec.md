# pack-composition Specification

## Purpose

Combines the candidate entries ingested from every source into exactly one
entry per package id per variant, applying the curation the pack exists to
express: which source wins, which apps are excluded, and which fixes are
layered on top.

## Requirements

### Requirement: Selected build verification does not change composition

A selected build failing structural verification SHALL prevent publication
without causing composition to select another project or family alternative.
After successful source ingestion and building, publication eligibility SHALL NOT
depend on a separate lookup of the selected project's release metadata.
Unavailable release metadata SHALL NOT trigger reselection or block an otherwise
eligible candidate. Standard fallback SHALL occur when no eligible preferred
dual candidate remains after successful ingestion and deliberate exclusions,
unless a pin requires one. An entire source fetch failure SHALL still abort the
build. Existing configured release fallback within one selected project SHALL
remain separate and unchanged.

#### Scenario: Preferred dual project fails metadata verification

- **WHEN** a selected dual build fails structural verification and a standard candidate exists
- **THEN** publication fails and the previously published pair remains intact
- **AND** the pipeline does not replace the selected project with the standard candidate

#### Scenario: Selected project release metadata is unavailable after a successful build

- **WHEN** source ingestion, building, checks and fresh structural verification succeed but the selected project's release metadata is unavailable
- **THEN** the otherwise eligible candidate remains eligible for publication without a separate release metadata lookup
- **AND** the pipeline does not replace the selected project with a standard candidate or another family alternative

#### Scenario: Preferred build is absent from a valid source snapshot

- **WHEN** all source acquisition succeeds, no preferred candidate exists, and no pin requires one
- **THEN** dual selection uses an eligible ordinary candidate if available

### Requirement: Each build is a baseline build or a dual-screen build

Every candidate build SHALL be either a baseline build or a dual-screen build.
A build SHALL be a dual-screen build exactly when it is eligible for dual only,
and dual preference SHALL be derived from that alone, with no separate
preference setting. A build's kind and eligibility SHALL come only from its
source, as source ingestion defines for each source. No candidate rule or other
composition setting SHALL change a build's eligibility or dual preference.

The single-screen pack SHALL select among a family's baseline builds. A valid
pin comes first: it selects the one candidate it names for its family and pack
ahead of dual-screen replacement and source precedence, as explicit selections
define, and it may name a dual-eligible baseline build for dual even when the
family has an available dual-screen build. Absent a pin, a family's available
dual-screen build SHALL replace its baseline build in the dual-screen pack, a
family with no available dual-screen build SHALL use its dual-eligible baseline
build, and source precedence SHALL decide among builds of one kind. A family
whose only builds are dual-screen builds SHALL appear only in the dual-screen
pack. Nothing other than a pin naming a specific candidate SHALL make the
dual-screen pack select a baseline build over an available dual-screen build.

A package denial removes builds, not families, as "Denied packages are excluded
from both variants" defines. Where a family's baseline and dual-screen builds
share a package id, a denial of that id SHALL remove both builds from both
packs, and the family's builds carrying other package ids SHALL stay
selectable. The Zelda 3, Minish Cap and Harvest Moon 64 standard and dual
builds share a package id and those families have no other build, so a denial
of that id removes each of those apps from both packs. A dual pin naming a
family's baseline build SHALL keep it in the dual-screen pack in place of the
family's dual-screen build, whether or not the two builds share a package id.

#### Scenario: A dual-screen build replaces the baseline in dual

- **WHEN** a family has a baseline build eligible for both packs and a
  dual-screen build, and no pin applies
- **THEN** single selects the baseline build and dual selects the dual-screen
  build, even when the baseline build comes from a higher-precedence source

#### Scenario: A family has no dual-screen build

- **WHEN** a family's builds are all baseline builds eligible for both packs,
  and no pin applies
- **THEN** both packs select among those baseline builds by source precedence

#### Scenario: A family has only a dual-screen build

- **WHEN** a family's only build is a dual-screen build
- **THEN** it is selected in the dual-screen pack and the single-screen pack
  has no entry for that family

#### Scenario: A denied package shared by both builds leaves other packages selectable

- **WHEN** a denial names a package id carried by both a family's baseline
  build and its dual-screen build, and the family has another baseline build
  with a different package id that is eligible for both packs
- **THEN** neither denied build is selected in either pack, and the
  different-package baseline build is selected in both

#### Scenario: A dual pin keeps a baseline build that shares its package

- **WHEN** a family's baseline build eligible for both packs and its
  dual-screen build share a package id, and a valid dual pin names the
  baseline build
- **THEN** both packs select the baseline build, the dual-screen build is
  selected in neither, and the dual selection's reason is the pin

### Requirement: Explicit selections identify an eligible candidate

Policy SHALL permit one candidate pin per family and variant. A pin SHALL name
an original candidate selector and a rationale, and SHALL select that candidate
ahead of device preference or source ranking. A dual pin MAY therefore name a
dual-eligible baseline build even when the family has an available dual-screen
build. A missing, ambiguous, excluded,
wrong-family or target-ineligible pinned candidate SHALL fail the build. A pin
SHALL NOT implicitly override an exclusion or eligibility restriction. Multiple
pins for one family and target SHALL fail.

#### Scenario: Maintainer selects a standard build for dual

- **WHEN** a valid dual pin names a standard build eligible for dual and a preferred
  dual alternative exists
- **THEN** the pinned build wins and the report identifies the explicit selection

#### Scenario: Pinned build disappears

- **WHEN** successful ingestion does not supply the pinned candidate
- **THEN** the build fails without selecting another build

#### Scenario: Pin conflicts with a denial

- **WHEN** a pin names a candidate whose effective package is denied
- **THEN** the build fails with the conflicting pin and denial identified

### Requirement: Explicit policy separates app families from package identities

The system SHALL load a versioned committed composition policy. A candidate
SHALL retain original source, source origin, package id and normalized project
URL. These fields SHALL identify a candidate after identical duplicates collapse;
different records sharing that identity SHALL fail rather than be chosen by order.
Policy candidate selectors SHALL match this original identity exactly once.
Corrections SHALL NOT recursively match other rules. Unmatched or ambiguous selectors,
duplicate selectors, invalid targets, unknown fields and inconsistent rules SHALL
fail with the affected selector identified.

A candidate SHALL default to family `package:<effective-package-id>`. Explicit
family assignments SHALL use the separate `app:` namespace and SHALL NOT be
inferred from names, categories or repository ancestry. A candidate rule SHALL
contain a `match` selector and a `rationale`, SHALL permit an effective
package-id correction (`packageId`) and a family assignment (`family`), and
SHALL preserve original provenance. A rule SHALL NOT set eligibility or dual
preference, which come only from the build's source: an `eligible` or
`dualPreferred` field SHALL fail as an unknown candidate-rule field with the
rule and field identified. Identity corrections SHALL have recorded primary APK
manifest evidence. Rules projecting to the same effective id and normalized URL
SHALL agree on family, so rendered-family interpretation is unambiguous, and a
projection SHALL carry the family only. Build SHALL reject any candidate
sharing that rendered key whose family contradicts the projection, including
candidates without their own rule. Projections SHALL impose no offline
eligibility restriction, because source-derived eligibility cannot be
reconstructed from rendered entries. Composition metadata SHALL NOT be
serialized into Obtainium app records.

#### Scenario: Different package ids represent replacement builds

- **WHEN** explicit policy assigns a standard build and a different-package dual
  build to one family
- **THEN** they compete within that family for dual selection
- **AND** each selected output retains its build's own effective package id

#### Scenario: Similar fork names have no family declaration

- **WHEN** two candidates have different ids and similar names or repository ancestry
- **THEN** they remain separate default families

#### Scenario: Corrected package participates in collisions

- **WHEN** an evidenced rule changes a candidate's effective package id
- **THEN** grouping, exclusions and final package uniqueness use the effective id
- **AND** reports retain both original and effective ids

#### Scenario: Rules disagree on a rendered identity

- **WHEN** two source-specific rules project to one effective id and URL but assign
  different families
- **THEN** configuration fails instead of making offline interpretation ambiguous

#### Scenario: A rule declares eligibility or dual preference

- **WHEN** a candidate rule carries an `eligible` or `dualPreferred` field
- **THEN** configuration fails with the rule and the unknown field identified

### Requirement: Each variant is composed independently

The system SHALL compose the single-screen and dual-screen variants
separately, so that a package id may carry different content in each.

#### Scenario: Variants disagree on one id

- **WHEN** a package id has different candidate entries in each variant
- **THEN** each variant's rendered entry reflects its own candidate, and
  neither overwrites the other

### Requirement: Composition runs in a fixed stage order

The system SHALL normalize candidates, apply identity and family rules, remove
excluded candidates, validate explicit selections, select by family and target,
validate overlay targets, apply overlays, and check unique packages and family
coverage. Exclusions SHALL observe corrected package identities before selection
and SHALL NOT be re-applied after overlays. Overlays SHALL NOT change identity,
URL, source type or composition metadata, including by null deletion. Failures
SHALL preserve the previous output pair and diagnostics already collected.

#### Scenario: An overlay cannot move an entry onto a denylisted package id

- **WHEN** an overlay contains an id field naming a denied package
- **THEN** the build fails because identity fields are forbidden in overlays

#### Scenario: Denylist removes an entry an overlay names

- **WHEN** candidate exclusions leave no selected entry matching an overlay selector
- **THEN** the build fails with that stale selector identified

### Requirement: Entries are unioned by package id under a fixed precedence

The system SHALL use effective package id as the default family key and explicit
family rules for declared replacements. It SHALL select at most one candidate
per family per variant, honoring a valid explicit pin first. Otherwise single
SHALL consider single-eligible candidates; dual SHALL consider dual-preferred
eligible candidates when any exist, or all dual-eligible candidates otherwise.
Within that tier, precedence SHALL be extras, RJNY, BBoi34, then generated.
The winning candidate SHALL be retained whole, not merged with losing entries.

Identical duplicates SHALL collapse. Different candidates tied at the winning
rank SHALL fail with the family, variant and selectors identified, requiring an
explicit selection. Ties among nonwinning candidates SHALL NOT displace a unique
winner. Iteration order, names, URLs and release dates SHALL NOT break ties.
Different families selecting the same effective package id in one variant SHALL
fail rather than be silently collapsed. A package id SHALL occur at most once
in each output, including when family rules separate candidates sharing an id.

#### Scenario: Two sources contribute the same id

- **WHEN** ordinary RJNY and BBoi entries compete for one family and target
- **THEN** RJNY wins and retains its complete entry

#### Scenario: Dual suitability outranks source precedence

- **WHEN** ordinary RJNY and dual-preferred BBoi builds compete for the same dual family
- **THEN** BBoi wins dual selection while the eligible ordinary build remains available to single

#### Scenario: Standard extra does not suppress a dual fork

- **WHEN** an ordinary extra and a dual-preferred generated build compete without a pin
- **THEN** dual selects the preferred build and single selects the extra if eligible

#### Scenario: One source contributes the same id with different content

- **WHEN** one source contributes two different candidates tied at the winning tier
- **THEN** composition fails with both selectors rather than choosing by input order

#### Scenario: One source contributes an identical entry twice

- **WHEN** a source contributes an identical candidate twice
- **THEN** it contributes one candidate and does not create a selection conflict

#### Scenario: Families select a colliding package

- **WHEN** two families select candidates carrying one effective package id in dual
- **THEN** the build fails with the package id and both families identified

#### Scenario: An extras entry collides with an upstream entry

- **WHEN** an extras entry shares a family with an upstream candidate at the same device-preference tier and no pin applies
- **THEN** extras wins and its complete entry is selected

### Requirement: Family selections are reported

The system SHALL report every selected family and variant with the winning
candidate's original and effective package ids, project URL, source and origin,
the other candidates of that family it was chosen over, and one selection
reason: pin, dual preference, ordinary fallback or source precedence. Exclusions
and stale exclusions SHALL also be reported.

#### Scenario: Lower-source dual build wins

- **WHEN** a dual-preferred BBoi entry defeats an ordinary RJNY entry
- **THEN** the report names the winner, lists the RJNY candidate as considered
  and identifies device preference as the reason

#### Scenario: Identity correction is visible in the selection

- **WHEN** an evidenced rule changes the winning candidate's effective package id
- **THEN** the selection records both its original and effective package ids

### Requirement: Denied packages are excluded from both variants

A denylist entry SHALL contain exactly a nonempty effective package `id` and a
nonempty `reason`. The system SHALL exclude every candidate carrying that
effective package id from both variants before selection and report the
exclusion. Package denials SHALL match effective package identities across
sources. A package denial SHALL NOT remove different-package alternatives merely
because they share a family, so a family SHALL be absent from a variant after
denials only when none of its remaining candidates is eligible there. An entry
matching no candidate SHALL be reported as
a stale exclusion and SHALL NOT fail the build. Any other field, including a
family or variant selector, SHALL fail explicitly with the entry identified.

#### Scenario: Denied by package id

- **WHEN** several sources contribute a denied package
- **THEN** no candidate carrying that package is selected in either output

#### Scenario: Package exclusion permits an alternative

- **WHEN** a preferred dual package is denied and its family has another eligible package
- **THEN** dual can select that alternative unless a conflicting pin fails validation

#### Scenario: Denylist entry matches no candidate

- **WHEN** a denial names a package that no candidate carries
- **THEN** the exclusion is reported stale, changes nothing and does not fail the build

#### Scenario: Denylist entry carries a retired selector

- **WHEN** a denylist entry carries a `family` or `variant` field
- **THEN** the build fails with the entry and the unknown field identified

### Requirement: One overlay patches composed entries

The overlay file SHALL contain an array of records with effective package `id`,
project `url` and object `patch`. Each record SHALL apply to the matching
selected entry in every variant that selects it. Matching SHALL use both
effective id and normalized project URL. Duplicate selectors SHALL fail. A
non-object patch, including null, SHALL fail. An obsolete id-keyed overlay
object SHALL fail with migration guidance.

Patches SHALL use recursive JSON Merge Patch, where null deletes an allowed key.
Patches SHALL NOT contain `id`, `url`, `overrideSource` or composition metadata
fields with any value, including null. All other unpatched data SHALL remain
unchanged. Shared settings for distinct project URLs SHALL require explicit
records for each project; a common package id SHALL NOT make a patch transfer
to another fork. Whole-app removal SHALL remain the denylist's responsibility.

#### Scenario: Overlay changes a setting

- **WHEN** both variants select the same effective id and normalized URL
- **THEN** a matching patch applies to both

#### Scenario: Shared package id uses different repositories

- **WHEN** single and dual select one package id from different project URLs
- **THEN** a patch naming the single repository does not affect the dual repository

#### Scenario: Overlay deletes a key

- **WHEN** a patch maps an allowed key to null
- **THEN** the key is deleted before normal rendering hydration

#### Scenario: Protected field is assigned or deleted

- **WHEN** a patch contains an id, URL, source type or composition field, including null
- **THEN** the build fails naming the selector and forbidden field

#### Scenario: Overlay maps a package id to something other than an object

- **WHEN** an overlay record has a null patch
- **THEN** the build fails rather than removing the app

#### Scenario: Overlay patch contains the source-type field

- **WHEN** an overlay record's patch contains overrideSource
- **THEN** the build fails with the selector and protected field identified

#### Scenario: Overlay patch contains the package-id field

- **WHEN** an overlay record's patch contains id
- **THEN** the build fails with the selector and protected field identified

#### Scenario: Overlay patch maps the source-type or package-id field to null

- **WHEN** a patch maps overrideSource or id to null
- **THEN** the build fails because protected fields cannot be deleted

### Requirement: An overlay record that patches nothing fails the build

The system SHALL fail when an overlay record's id-and-URL selector matches no
selected entry in either variant. A selector matching one variant SHALL be
valid and apply only where matched. The presence of the package id under a
different project URL SHALL NOT satisfy a selector. Losing or excluded
candidates SHALL NOT satisfy overlay targets.

#### Scenario: Old fork was replaced

- **WHEN** the package id remains selected but under a different normalized URL
- **THEN** the old fork's overlay fails as stale

#### Scenario: Overlay names an id present in one variant only

- **WHEN** a selector matches only the dual output
- **THEN** it is valid and applies only there

#### Scenario: Overlay names an id that no longer exists

- **WHEN** a selector's id is absent from both selected outputs
- **THEN** the build fails with the stale id-and-URL selector

### Requirement: Every single-screen family has a dual-screen selection

Every family selected in single SHALL have a selected build in dual. Upstream
eligibility restrictions, unresolved generated links, denials of other packages
in the family and verification failures SHALL NOT waive family coverage. An app
therefore cannot be published in single only. An app is kept out of both packs
by denying every package id its family's builds carry, since a package denial
leaves the family's builds with other package ids selectable. Different-package replacements in one declared
family SHALL satisfy coverage. Dual-only additions SHALL NOT require a single
counterpart.

#### Scenario: Different-package dual replacement

- **WHEN** single and dual select different package ids in the same declared family
- **THEN** family coverage passes without requiring both packages in dual

#### Scenario: An app is missing from the dual-screen variant

- **WHEN** single selects a family with no dual-eligible candidate
- **THEN** the build fails with the family coverage gap rather than copying an ineligible build

#### Scenario: The only dual build is denied

- **WHEN** the only dual-eligible candidate of a single-selected family carries a denied package
- **THEN** the build fails with the family coverage gap
