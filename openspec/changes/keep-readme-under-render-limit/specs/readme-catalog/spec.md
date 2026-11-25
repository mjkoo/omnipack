# Spec Delta

## MODIFIED Requirements

### Requirement: Individual links preserve exported app configuration

Each link SHALL use the documented Obtainium HTTPS redirect with an app deep link
carrying the final exported JSON object, except that for an entry whose source
type is GitHub or GitLab, each additionalSettings key whose value equals that
source's value in omnipack's committed settings defaults table SHALL be left
out. Decoding the redirect parameter and deep-link payload SHALL recover every
other field and setting exactly, preserving field types, unknown fields and
string-valued additionalSettings. Pack-wide settings SHALL NOT be included. Link
generation SHALL be deterministic and network-free.

#### Scenario: Encoded values contain reserved characters

- **WHEN** app fields contain Unicode, percent signs, ampersands, hashes or regex escapes
- **THEN** decoding the generated link recovers every value and type unchanged

#### Scenario: A GitHub entry carries default-valued settings

- **WHEN** a GitHub entry's additionalSettings hold one setting at its value
  in the GitHub defaults table and one setting at another value
- **THEN** decoding its link recovers the entry without the default-valued
  setting, with the other setting and every other field unchanged

#### Scenario: An HTML entry carries default-valued settings

- **WHEN** an HTML entry's additionalSettings hold settings at their values in
  the HTML defaults table
- **THEN** decoding its link recovers the entry exactly, those settings
  included

#### Scenario: A GitHub entry's settings are not a JSON object

- **WHEN** a GitHub entry's additionalSettings string does not decode to a JSON
  object
- **THEN** decoding its link recovers the entry exactly
