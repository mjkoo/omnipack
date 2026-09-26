## MODIFIED Requirements

### Requirement: One candidate is selected per family and variant under a fixed precedence

The system SHALL select within the families that shared identity and explicit
family rules form, as "Composition policy separates app families from package
identities" defines. It SHALL select at most one candidate
per family per variant, honoring a valid explicit pin first, as "Explicit
selections identify an eligible candidate" defines. Otherwise single
SHALL consider single-eligible candidates; dual SHALL consider dual-preferred
eligible candidates when any exist, or all dual-eligible candidates otherwise.
Within that tier, precedence SHALL be extras, RJNY, BBoi34, codm2000, then Quiver.
The winning candidate SHALL be retained whole, not merged with losing entries.

A family having no dual-preferred candidate left after successful ingestion and
deliberate exclusions SHALL be an ordinary outcome: dual SHALL select among that
family's remaining dual-eligible candidates and the build SHALL NOT fail for the
absence, unless a pin names a candidate that is absent. A source that cannot be
fetched SHALL abort the build instead, as "A failed fetch aborts the build" in
source-ingestion defines, so a missing preferred candidate and a missing source
are never confused.

Identical duplicates SHALL collapse. Different candidates tied at the winning
rank SHALL fail with the family, variant and selectors identified, requiring an
explicit selection. Ties among nonwinning candidates SHALL NOT displace a unique
winner. Iteration order, names, URLs and release dates SHALL NOT break ties.
A package id SHALL occur at most once in each output; because candidates sharing
an effective package id always form one family, selection places each package
id at most once.

After selection, every family that publishes in both variants SHALL have
selected single-screen and dual-screen entries that pair under the
provenance-free pairing that "Offline verification checks rendered composition
consistency" in pack-verification defines. Because a default family holds one
package id, selected entries can differ in package id only inside an explicit
family, and they pair only when each entry's effective package id and
normalized project URL is a projection of that explicit family; an explicit
assignment on a member the family did not select SHALL NOT make its selected
entries pair. Otherwise composition SHALL fail with the family and both entries
identified, directing the maintainer to add a `family` rule for each selected
entry that does not yet project the family, so offline verification and the
README catalog reproduce every family the build publishes in both variants.

#### Scenario: Two sources contribute the same id

- **WHEN** ordinary RJNY and BBoi entries compete for one family and target
- **THEN** RJNY wins and retains its complete entry

#### Scenario: Dual suitability outranks source precedence

- **WHEN** ordinary RJNY and dual-preferred BBoi builds compete for the same dual family
- **THEN** BBoi wins dual selection while the eligible ordinary build remains available to single

#### Scenario: Standard extra does not suppress a dual fork

- **WHEN** an ordinary extra and a dual-preferred generated build compete without a pin
- **THEN** dual selects the preferred build and single selects the extra if eligible

#### Scenario: Preferred build is absent from a valid source snapshot

- **WHEN** all source acquisition succeeds, no preferred candidate exists, and no pin requires one
- **THEN** dual selection uses an eligible ordinary candidate if available

#### Scenario: One source contributes the same id with different content

- **WHEN** one source contributes two different candidates tied at the winning tier
- **THEN** composition fails with both selectors rather than choosing by input order

#### Scenario: One source contributes an identical entry twice

- **WHEN** a source contributes an identical candidate twice
- **THEN** it contributes one candidate and does not create a selection conflict

#### Scenario: Families select a colliding package

- **WHEN** an RJNY candidate and a BBoi candidate carry one effective package id
  from different repositories and compete in one variant without a pin
- **THEN** RJNY wins whole and the BBoi candidate is reported as considered

#### Scenario: An extras entry collides with an upstream entry

- **WHEN** an extras entry shares a family with an upstream candidate at the same dual-preference tier and no pin applies
- **THEN** extras wins and its complete entry is selected

#### Scenario: Selected builds pair only through a losing candidate's rule

- **WHEN** rules assign `app:x` only to RJNY ordinary package `a` at project URL
  X and RJNY ordinary package `c` at project URL W, extras supplies rule-less
  baseline package `a` at project URL Y, and BBoi supplies rule-less
  dual-preferred package `c` at project URL V, so single selects `a` at Y and
  dual selects `c` at V
- **THEN** composition fails with `app:x` and both selected entries identified,
  directing the maintainer to add a `family` rule for each of them
- **AND** once rules assign both selected entries `app:x`, the build succeeds
  and offline verification pairs them

#### Scenario: Quiver cannot displace an existing baseline source

- **WHEN** a Quiver baseline and an existing-source baseline compete within one family without a pin
- **THEN** the existing-source candidate wins whole

#### Scenario: Quiver supplies a missing baseline

- **WHEN** Quiver is the only baseline candidate and codm2000 supplies a dual-screen build of the same family from the same or a different repository
- **THEN** single selects Quiver and dual selects codm2000
