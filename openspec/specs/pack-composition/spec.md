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

### Requirement: Explicit selections identify an eligible candidate

Policy SHALL permit one candidate pin per family and variant. A pin SHALL name
an original candidate selector and a rationale, and SHALL select that candidate
ahead of device preference or source ranking. A missing, ambiguous, excluded,
wrong-family or target-ineligible pinned candidate SHALL fail the build. A pin
SHALL NOT implicitly override an exclusion or eligibility restriction, and a
family exclusion SHALL NOT silently disable a pin. Multiple pins for one family
and target SHALL fail.

#### Scenario: Maintainer selects a standard build for dual

- **WHEN** a valid dual pin names a standard build eligible for dual and a preferred
  dual alternative exists
- **THEN** the pinned build wins and the report identifies the explicit selection

#### Scenario: Pinned build disappears

- **WHEN** successful ingestion does not supply the pinned candidate
- **THEN** the build fails without selecting another build

#### Scenario: Pin conflicts with a denial

- **WHEN** a pin names a candidate excluded for its target by package or family
- **THEN** the build fails with the conflicting pin and denial identified

### Requirement: Historical family mappings survive candidate retirement

The composition policy SHALL accept an optional `history` array, defaulting to
empty, of records containing nonempty effective `id`, project `url`, `family`
and `rationale`. Family values SHALL use the `package:` or `app:` namespace.
Keys SHALL use effective id and normalized project URL. Unknown fields, duplicate
normalized keys and family disagreement with an active rule projection for the
same key SHALL fail configuration validation with the conflicting key identified.
Historical mappings SHALL be maintainer-authored committed input and SHALL remain
usable after their candidates and obsolete active rules disappear. They SHALL NOT
require current candidate presence or satisfy active candidate selectors. They
SHALL be used only for previous-output family classification, never for current
selection, corrections, eligibility, pins or current rendered-family coverage.
Nightly SHALL NOT update history or expand its publication allowlist.

#### Scenario: Retired candidate retains its family authority

- **WHEN** an old selected candidate disappears from successful ingestion and its obsolete active rule is removed while its historical mapping remains
- **THEN** history does not fail candidate-presence validation and remains available to classify the previous output

#### Scenario: Historical mappings conflict

- **WHEN** history duplicates a normalized rendered key or disagrees with an active rule projection for that key
- **THEN** configuration fails with the key identified rather than silently choosing a family

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
inferred from names, categories or repository ancestry. Rules SHALL permit an
effective package-id correction, family assignment, device eligibility and dual
preference, require a rationale, and preserve original provenance. Identity
corrections SHALL have recorded primary APK manifest evidence. Rules projecting
to the same effective id and normalized URL SHALL agree on family and explicitly
declared eligibility, so rendered-family interpretation is unambiguous. Build
SHALL reject any candidate sharing that rendered key whose family or eligibility
contradicts the projection, including candidates without their own rule. Absent
explicit eligibility SHALL impose no additional offline restriction, because
source-derived eligibility cannot be reconstructed from rendered entries.
Composition metadata SHALL NOT
be serialized into Obtainium app records.

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
  different families or eligibility
- **THEN** configuration fails instead of making offline interpretation ambiguous

### Requirement: Each variant is composed independently

The system SHALL compose the single-screen and dual-screen variants
separately, so that a package id may carry different content in each.

#### Scenario: Variants disagree on one id

- **WHEN** a package id has different candidate entries in each variant
- **THEN** each variant's rendered entry reflects its own candidate, and
  neither overwrites the other

### Requirement: Composition runs in a fixed stage order

The system SHALL normalize candidates, apply identity/family/device rules, remove
excluded candidates, validate explicit selections, select by family and target,
validate overlay targets, apply overlays, and check unique packages and family
coverage. Exclusions SHALL observe corrected package and family identities before
selection and SHALL NOT be re-applied after overlays. Overlays SHALL NOT change
identity, URL, source type or composition metadata, including by null deletion.
Failures SHALL preserve the previous output pair and diagnostics already collected.

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

### Requirement: Displaced candidates are reported

The system SHALL report every selected family/variant with the winning candidate,
effective package id, source and origin, and selection reason: pin, dual preference,
ordinary fallback or source precedence. It SHALL list displaced alternatives,
their identities and eligibility, why they lost, and fields differing from the
winner. Exclusions and identity corrections SHALL also be reported. Reports SHALL
distinguish project/package replacements from app-family additions and removals
using historical mappings for previous outputs, and mark missing-history
classifications unknown rather than infer family changes.

#### Scenario: Lower-source dual build wins

- **WHEN** a dual-preferred BBoi entry defeats an ordinary RJNY entry
- **THEN** the report names both candidates and identifies device preference as the reason

#### Scenario: Losing candidate differs from the winner

- **WHEN** a displaced candidate differs in its version or APK settings
- **THEN** the report identifies the differing fields for maintainer review

### Requirement: Denylisted apps are excluded

A denylist entry SHALL contain exactly one nonempty package `id` or `family`, a
reason, and optionally a known variant. Missing variant SHALL mean both targets.
The system SHALL exclude all matching candidates before selection and report the
exclusion. Package denials SHALL match effective package identities across sources;
family denials SHALL match every build in the logical family. A package denial
SHALL NOT remove different-package alternatives merely because they share a family.
Stale exclusions SHALL be nonfatal and reported against their applicable targets.
Invalid shapes, both selector kinds, or unknown variants SHALL fail explicitly.

#### Scenario: Denied by package id

- **WHEN** several sources contribute a denied package and the denial names no variant
- **THEN** no candidate carrying that package is selected in either output

#### Scenario: Package exclusion permits an alternative

- **WHEN** a preferred dual package is denied and its family has another eligible package
- **THEN** dual can select that alternative unless a conflicting pin fails validation

#### Scenario: Family exclusion removes all builds

- **WHEN** a family denial applies only to dual
- **THEN** no build of that family is selected in dual and single is unaffected

#### Scenario: Denylist entry matches no composed entry

- **WHEN** a dual-only denial matches only a single-only candidate
- **THEN** the exclusion is reported stale, changes nothing and does not fail the build

#### Scenario: Denylist entry names an unknown variant

- **WHEN** a denial names an unrecognized target
- **THEN** the build fails with the selector and rejected target

#### Scenario: Denied in one variant only

- **WHEN** a package denial names dual and that package is eligible for both variants
- **THEN** all dual candidates carrying that package are excluded and single remains unaffected

### Requirement: Overlays patch composed entries

Each overlay file SHALL contain an array of records with effective package `id`,
project `url` and object `patch`. The common overlay SHALL apply to matching
selected entries in both variants, followed by the dual overlay in dual only.
Matching SHALL use both effective id and normalized project URL. Duplicate
selectors within one file SHALL fail. A non-object patch, including null, SHALL
fail. An obsolete id-keyed overlay object SHALL fail with migration guidance.

Patches SHALL use recursive JSON Merge Patch, where null deletes an allowed key.
Patches SHALL NOT contain `id`, `url`, `overrideSource` or composition metadata
fields with any value, including null. All other unpatched data SHALL remain
unchanged. Shared settings for distinct project URLs SHALL require explicit
records for each project; a common package id SHALL NOT make a patch transfer
to another fork. Whole-app removal SHALL remain the denylist's responsibility.

#### Scenario: Overlay changes a setting

- **WHEN** both variants select the same effective id and normalized URL
- **THEN** a common matching patch applies to both

#### Scenario: Shared package id uses different repositories

- **WHEN** single and dual select one package id from different project URLs
- **THEN** a patch naming the single repository does not affect the dual repository

#### Scenario: Dual overlay refines the common overlay

- **WHEN** both files patch the same id and URL
- **THEN** dual receives the common patch followed by the dual patch and single receives only common

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

### Requirement: An overlay that patches nothing fails the build

The system SHALL fail when an overlay's id-and-URL selector matches no selected
entry in its applicable variants. A common selector matching either variant SHALL
be valid and apply only where matched. A dual selector SHALL match dual. The
presence of the package id under a different project URL SHALL NOT satisfy a
selector. Losing or excluded candidates SHALL NOT satisfy overlay targets.

#### Scenario: Old fork was replaced

- **WHEN** the package id remains selected but under a different normalized URL
- **THEN** the old fork's overlay fails as stale

#### Scenario: Common overlay names an id present in one variant only

- **WHEN** a common selector matches only the dual output
- **THEN** it is valid and applies only there

#### Scenario: Dual overlay names an id the dual-screen variant lacks

- **WHEN** a dual selector matches only the single output
- **THEN** the build fails with the stale dual selector

#### Scenario: Overlay names an id that no longer exists

- **WHEN** a common overlay selector's id is absent from both selected outputs
- **THEN** the build fails with the stale id-and-URL selector

### Requirement: The dual-screen variant covers every single-screen app

Every family selected in single SHALL have a selected build in dual, except an
explicit applicable family denial or a dual-applicable package denial naming
the single winner's effective package id. An exemption SHALL apply even if its
denial removed no dual candidate. A denial of some other package in that family
SHALL NOT waive coverage. Upstream eligibility restrictions, unresolved generated
links and verification failures SHALL NOT themselves waive family coverage.
Different-package replacements in one declared family SHALL satisfy coverage.
Dual-only additions SHALL NOT require a single counterpart.

#### Scenario: Different-package dual replacement

- **WHEN** single and dual select different package ids in the same declared family
- **THEN** family coverage passes without requiring both packages in dual

#### Scenario: An app is missing from the dual-screen variant

- **WHEN** single selects a family with no dual-eligible candidate or explicit exemption
- **THEN** the build fails with the family coverage gap rather than copying an ineligible build

#### Scenario: A variant-scoped denial leaves a gap

- **WHEN** the single winner's family or effective package id is explicitly denied for dual
- **THEN** missing dual coverage is permitted even if the denial removed nothing

#### Scenario: Another package was denied

- **WHEN** a different package in a single-selected family is denied for dual and no dual winner exists
- **THEN** coverage fails because that denial does not exempt the single winner

#### Scenario: A variant-scoped denial removed nothing but still exempts

- **WHEN** a dual denial names the single winner's effective package, no dual candidate carried it, and its family has no dual selection
- **THEN** coverage is exempt and the unmatched denial is reported stale
