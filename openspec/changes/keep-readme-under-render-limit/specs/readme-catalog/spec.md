# Spec Delta

## MODIFIED Requirements

### Requirement: Individual links preserve exported app configuration

Each link SHALL use the documented Obtainium HTTPS redirect with an app deep link
carrying the final exported JSON object, except that for an entry whose source
type is GitHub or GitLab, each additionalSettings key whose value equals the
default Obtainium applies to an omitted setting of that source SHALL be left
out. Decoding the redirect parameter and deep-link payload SHALL recover every
other field and setting exactly, preserving field types, unknown fields and
string-valued additionalSettings. Pack-wide settings SHALL NOT be included. Link
generation SHALL be deterministic and network-free.

#### Scenario: Encoded values contain reserved characters

- **WHEN** app fields contain Unicode, percent signs, ampersands, hashes or regex escapes
- **THEN** decoding the generated link recovers every value and type unchanged

#### Scenario: A GitHub entry carries default-valued settings

- **WHEN** a GitHub entry's additionalSettings hold one setting at Obtainium's
  default for GitHub and one setting at another value
- **THEN** decoding its link recovers the entry without the default-valued
  setting, with the other setting and every other field unchanged

#### Scenario: An HTML entry carries default-valued settings

- **WHEN** an HTML entry's additionalSettings hold settings at Obtainium's
  defaults for HTML
- **THEN** decoding its link recovers the entry exactly, those settings
  included

## ADDED Requirements

### Requirement: The build warns before the README outgrows GitHub's render limit

GitHub stops rendering a README after 512,000 bytes. Each build SHALL record a
README-size warning holding the rendered README's size in bytes when that size
exceeds 460,800 bytes, and SHALL record none otherwise. The warning SHALL NOT
change whether the build succeeds or what it publishes.

#### Scenario: The README exceeds the threshold

- **WHEN** a build renders a README of 470,000 bytes
- **THEN** the build records a README-size warning of 470,000 bytes, succeeds,
  and publishes the packs and README as it would without the warning

#### Scenario: The README is under the threshold

- **WHEN** a build renders a README of 300,000 bytes
- **THEN** the build records no README-size warning
