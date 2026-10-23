# Spec Delta

## ADDED Requirements

### Requirement: Overrides that change nothing are reported

After overlays apply, the system SHALL record two kinds of owner override that
no longer change what a catalog would publish. Neither record SHALL change
selection or any published entry, and neither SHALL fail the build.

A patch key is a path through a record's patch to a value that is not an
object: a top-level key, or a key nested under an object such as
`additionalSettings`. A key SHALL be recorded as changing nothing when, for
every selected entry the record applies to in every variant, the entry before
the record applied already held that value at that path, or, for a null value,
held no value at that path. A setting the published entry would receive by
default when it carries none, as pack rendering fills defaults, SHALL count as
held. A key that changes at least one such entry SHALL
NOT be recorded. The system SHALL record each overlay record that has any such
key, once, with its normalized project URL and every such key.

An extra is listed by a catalog when a selected entry chosen from extras was
chosen over a candidate from another source at the same normalized project
URL. The system SHALL record each such extra once, with its normalized project
URL, its package id, each other source listing it and, for each of those
candidates, the fields whose values differ between the extra's published entry
and that candidate's entry as it would be published with the same overlay
applied. Fields SHALL be
compared as top-level keys and as keys under `additionalSettings`; categories
SHALL NOT be compared, because the category map assigns them. An extra whose
family was chosen over candidates only at other project URLs SHALL NOT be
recorded.

#### Scenario: A patch whose value the source now ships

- **WHEN** an overlay record sets `name` to the name its selected entry
  already carries in every variant
- **THEN** the build succeeds, publishes the same entries, and records the
  record's URL with the key `name`

#### Scenario: A patch with one live and one dead key

- **WHEN** a record sets `name`, which changes the entry, and
  `additionalSettings.includeZips` to the value the entry already holds
- **THEN** the record's URL is recorded with `additionalSettings.includeZips`
  only

#### Scenario: A key that matters in one variant

- **WHEN** a record applies to a single and a dual entry and its key changes
  only the dual entry
- **THEN** the key is not recorded

#### Scenario: A patch setting a rendering default

- **WHEN** a record sets a setting the entry does not carry to the value
  rendering would publish for it by default
- **THEN** the key is recorded as changing nothing

#### Scenario: A null deleting an absent key

- **WHEN** a record's patch holds null for a key the entry does not carry
- **THEN** the key is recorded as changing nothing

#### Scenario: A catalog lists an extra's project

- **WHEN** an extra is selected over a Quiver candidate at the same project URL
  whose name and APK filter differ from the extra's
- **THEN** the build succeeds, the extra is still published, and the extra is
  recorded with its URL, package id, Quiver as a source, and the name and the
  APK filter setting as differing fields

#### Scenario: An extra replaces another project in its family

- **WHEN** an extra is selected over a catalog candidate at a different project
  URL that a family rule puts in the same family
- **THEN** no listed extra is recorded
