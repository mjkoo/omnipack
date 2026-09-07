# pack-composition Specification

## Purpose

Combines the candidate entries ingested from every source into exactly one
entry per package id per variant, applying the curation the pack exists to
express: which source wins, which apps are excluded, and which fixes are
layered on top.

## Requirements

### Requirement: Each variant is composed independently

The system SHALL compose the single-screen and dual-screen variants
separately, so that a package id may carry different content in each.

#### Scenario: Variants disagree on one id

- **WHEN** a package id has different candidate entries in each variant
- **THEN** each variant's rendered entry reflects its own candidate, and
  neither overwrites the other

### Requirement: Composition runs in a fixed stage order

Each guard in composition observes a different set of entries, so the order
the stages run in decides what each one sees. The system SHALL compose a
variant in this order: union the candidates by precedence, remove the entries
the denylist names, validate that every overlay target is present, apply the
overlays, then check that the dual-screen variant covers the single-screen
one. The denylist SHALL observe entries as their sources contributed them and
SHALL NOT be applied again after the overlays have been applied. Not
re-applying it is safe because an overlay's patch may not carry the package-id
field at all, so no overlay can move an entry onto a denied id once the
denylist has run.

#### Scenario: An overlay cannot move an entry onto a denylisted package id

- **WHEN** an overlay's patch for an entry contains the package-id field set to
  a package id the denylist names
- **THEN** the build fails with an error naming that package id, because an
  overlay's patch may not contain the package-id field

#### Scenario: Denylist removes an entry an overlay names

- **WHEN** the denylist removes the only entry carrying a package id that an
  overlay names
- **THEN** the build fails with an error naming that id, because overlay
  targets are validated after denylist removal

### Requirement: Entries are unioned by package id under a fixed precedence

Obtainium keys apps by package id on import, so a variant SHALL contain at
most one entry per package id. When more than one candidate shares an id, the
system SHALL keep the candidate from the highest-precedence source, where
precedence runs, highest first: hand-written extras, RJNY, BBoi34, then
generated entries. The winning candidate SHALL be kept whole rather than
merged field by field with the losers.

Source precedence cannot separate two candidates that come from the same
source. When one source contributes more than one candidate for the same
package id within one variant, the system SHALL keep a single entry when those
candidates are identical, and SHALL otherwise fail the build with an error
naming the source, the variant and the package id.

#### Scenario: Two sources contribute the same id

- **WHEN** both RJNY and BBoi34 contribute an entry for one package id
- **THEN** the composed variant contains the RJNY entry only

#### Scenario: An extras entry collides with an upstream entry

- **WHEN** an extras entry shares a package id with an upstream entry
- **THEN** the composed variant contains the extras entry only

#### Scenario: One source contributes an identical entry twice

- **WHEN** one source contributes two identical candidates for the same
  package id within one variant
- **THEN** the composed variant contains one entry for that id and the build
  succeeds

#### Scenario: One source contributes the same id with different content

- **WHEN** one source contributes two candidates for the same package id
  within one variant and their content differs
- **THEN** the build fails with an error naming the source, the variant and
  the package id

### Requirement: Displaced candidates are reported

An upstream fix landing on the losing side of a precedence decision would
otherwise be invisible. The system SHALL report every id where candidates were
displaced, naming the winning and losing sources and the fields whose values
differed.

#### Scenario: Losing candidate differs from the winner

- **WHEN** a losing candidate's per-app settings differ from the winner's
- **THEN** the build report names that id, both sources, and the differing
  fields

### Requirement: Denylisted apps are excluded

A package id is the only identifier that names the same app in both variants,
because one id can carry a different URL in each, so the denylist names apps by
package id alone. A denylist entry SHALL name a package id and MAY additionally
name a single variant. The system SHALL remove the entry carrying that package
id from both variants when the denylist entry names no variant, and from the
named variant only when it names one, and SHALL report each removal with the
reason recorded in the denylist. Denying an entry generated from a project link
uses the package id the build report records for that project.

A denylist entry that names a variant SHALL be evaluated against that variant
alone: it removes nothing from any other variant, and whether it matched is
decided by the named variant's composed entries whatever the other variant
contains.

A denylist entry whose package id matches no composed entry in the variant or
variants it applies to SHALL NOT fail the build: the removal is a no-op, and
the system SHALL record that entry in the build report as a stale exclusion.
Unlike an overlay that patches nothing, a denial that matches nothing has
already got what it asked for, since the app is absent, so failing would break
a scheduled rebuild at exactly the moment upstream did what the denial wanted.

A denylist entry that names a variant SHALL name a known one. The system SHALL
fail the build with an error naming that entry and the rejected value when a
denylist entry names anything else, because a stale exclusion is only a safe
outcome for a denial that was understood.

#### Scenario: Denied by package id

- **WHEN** a denylist entry names a package id present in the composed set and
  names no variant
- **THEN** no variant contains an entry with that id

#### Scenario: Denied in one variant only

- **WHEN** a denylist entry names a package id together with the dual-screen
  variant, and both composed variants contain that id
- **THEN** the dual-screen variant contains no entry with that id and the
  single-screen variant keeps its entry

#### Scenario: Denylist entry matches no composed entry

- **WHEN** a denylist entry names a package id that neither composed variant
  contains
- **THEN** the build succeeds, nothing is removed, and the build report records
  that denylist entry as a stale exclusion

#### Scenario: Denylist entry names an unknown variant

- **WHEN** a denylist entry names a variant the pack does not have
- **THEN** the build fails with an error naming that entry and the rejected
  value

### Requirement: Overlays patch composed entries

Upstream entries carry settings that need per-app correction, and those
corrections must survive every upstream refresh. The system SHALL apply the
common overlay to matching entries in both variants, then the dual-screen
overlay to matching entries in the dual-screen variant, treating each overlay
as a JSON Merge Patch keyed by package id.

An overlay's patch SHALL be an object. The system SHALL fail the build with an
error naming the package id when an overlay maps a package id to anything else,
including null, so that removing an app from a variant stays the denylist's job
alone and every removal is reported as one.

An overlay's patch SHALL NOT contain the source-type field or the package-id
field, and the system SHALL fail the build with an error naming the package id
when a patch contains either field with any value, including null. The guard is
on the field being present, not on the value assigned to it: under JSON Merge
Patch a null is a deletion rather than an assignment, and deleting an entry's
source type or package id rewrites its identity exactly as replacing the value
would. An entry's source type is what its own upstream record or URL
established, and it decides which settings key set the entry must carry, so
changing it describes a different app rather than correcting one app's
settings. The package id is the key the overlay is matched under, and rewriting
it would change the app's identity after every id-keyed guard has already run.

#### Scenario: Overlay changes a setting

- **WHEN** the common overlay sets a per-app setting for a package id
- **THEN** both variants' entries for that id carry the overlaid value and
  their other fields are unchanged

#### Scenario: Dual overlay refines the common overlay

- **WHEN** both overlays patch the same package id
- **THEN** the dual-screen entry reflects the common overlay with the
  dual-screen overlay applied on top, and the single-screen entry reflects the
  common overlay alone

#### Scenario: Overlay deletes a key

- **WHEN** an overlay maps a key other than the source-type field and the
  package-id field to null
- **THEN** that key is absent from the patched entry

#### Scenario: Overlay patch contains the source-type field

- **WHEN** an overlay's patch for a package id contains the source-type field
  set to a value
- **THEN** the build fails with an error naming that package id

#### Scenario: Overlay patch contains the package-id field

- **WHEN** an overlay's patch for a package id contains the package-id field
  set to a value
- **THEN** the build fails with an error naming that package id

#### Scenario: Overlay patch maps the source-type or package-id field to null

- **WHEN** an overlay's patch for a package id maps the source-type field or
  the package-id field to null
- **THEN** the build fails with an error naming that package id, because the
  guard is on either field being present rather than on the value assigned

#### Scenario: Overlay maps a package id to something other than an object

- **WHEN** an overlay maps a package id to null, or to any other value that is
  not an object
- **THEN** the build fails with an error naming that package id, because an app
  is removed from a variant by the denylist and by nothing else

### Requirement: An overlay that patches nothing fails the build

An overlay keyed by an id no source contributes is a fix that silently stopped
being applied, which is the exact failure this pack exists to prevent. The
common overlay SHALL name a package id present in at least one composed
variant, and SHALL apply to whichever composed variants contain that id. The
dual-screen overlay SHALL name a package id present in the composed
dual-screen variant. The system SHALL fail the build when an overlay names a
package id that is present in no variant the overlay applies to.

#### Scenario: Overlay names an id that no longer exists

- **WHEN** the common overlay names a package id absent from both variants
- **THEN** the build fails with an error naming that id

#### Scenario: Common overlay names an id present in one variant only

- **WHEN** the common overlay names a package id that composition placed in
  the dual-screen variant only
- **THEN** the build succeeds and the dual-screen entry for that id carries
  the patch

#### Scenario: Dual overlay names an id the dual-screen variant lacks

- **WHEN** the dual-screen overlay names a package id absent from the composed
  dual-screen variant
- **THEN** the build fails with an error naming that id

### Requirement: The dual-screen variant covers every single-screen app

The dual-screen pack is the single-screen pack plus dual-screen additions and
replacements, so a device importing it must not lose an app. The system SHALL
fail the build when a package id present in the composed single-screen variant
is absent from the composed dual-screen variant, except where a denylist entry
names that package id for the dual-screen variant, which is a deliberate
exclusion rather than an accidental gap. The denylist entry is what grants the
exemption, not the removal it performed: an id a denylist entry names for the
dual-screen variant SHALL be exempt whether or not an entry carrying it was
actually present to remove, so that upstream dropping the app the denial wanted
gone does not turn the denial into a build failure.

#### Scenario: An app is missing from the dual-screen variant

- **WHEN** composition leaves a package id in the single-screen variant that
  is absent from the dual-screen variant
- **THEN** the build fails with an error naming that id

#### Scenario: A variant-scoped denial leaves a gap

- **WHEN** a denylist entry naming the dual-screen variant removes a package id
  that remains in the composed single-screen variant
- **THEN** the build succeeds, because a package id a denylist entry names for
  the dual-screen variant is exempt from the coverage check

#### Scenario: A variant-scoped denial removed nothing but still exempts

- **WHEN** a denylist entry names a package id together with the dual-screen
  variant, the composed dual-screen variant contains no entry with that id
  before the denylist runs, and the composed single-screen variant carries it
- **THEN** the build succeeds and the build report records that denylist entry
  as a stale exclusion
