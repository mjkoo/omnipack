## ADDED Requirements

### Requirement: Offline verification checks each entry's serialized shape

The system SHALL validate both rendered import documents without fetching,
hydrating, repairing or rewriting them. It SHALL reject missing or unreadable
files, invalid JSON including non-finite numbers, non-object roots, non-list
`apps`, non-object `settings` and malformed app records. A package id repeated within a variant SHALL be reported as a nonfatal
finding, as "Offline verification labels and pairs rendered entries by family"
defines, not rejected as malformed. Each app SHALL have nonempty string `id`,
`name` and absolute HTTP(S) `url`, string `author`, string-list `categories`,
`overrideSource`, when present, a string, `allowIdChange` equal to
`true`, and `additionalSettings` as a string decoding to an object. Track-only ids SHALL NOT be required to follow
Android package-name syntax. Unknown fields SHALL NOT be removed or rejected
solely for being unknown offline.

Within decoded settings, a setting named by the committed defaults for the
entry's source type SHALL have the same JSON type as its default; an entry
whose source type has no committed defaults, or that has none, SHALL have its
settings checked only for decoding to an object. For HTML
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

#### Scenario: An entry's source type has no committed defaults

- **WHEN** a rendered entry carries `overrideSource: Codeberg`, or none
- **THEN** offline verification accepts it when its settings decode to an
  object

## REMOVED Requirements

### Requirement: Offline verification checks the serialized entry shape

**Reason**: Verification no longer rejects source types the pack holds no defaults for.

**Migration**: Replaced by "Offline verification checks each entry's serialized shape".
