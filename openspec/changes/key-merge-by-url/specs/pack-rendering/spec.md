## ADDED Requirements

### Requirement: Every rendered app lets Obtainium adopt its installed package id

A source's package id for an app can differ from the id the app's APK
declares, and Obtainium refuses to install an imported app whose id disagrees
with its APK unless the app allows an id change. Every rendered app SHALL
therefore carry `allowIdChange` set to `true`, whatever its source record or an
overlay patch says, so the first install adopts the APK's own package id.
Obtainium clears the flag once it has adopted the id, so later updates keep
its protection against an id change.

#### Scenario: A source's id differs from its APK

- **WHEN** a selected entry carries an id other than the package id its APK
  declares
- **THEN** the rendered app carries `allowIdChange: true`

#### Scenario: A source record or overlay sets the flag false

- **WHEN** a source record or overlay patch sets `allowIdChange` to `false`
- **THEN** the rendered app still carries `allowIdChange: true`

## REMOVED Requirements

### Requirement: Package ids are unique within a rendered file

**Reason**: Families no longer form by package id, so two selected entries of a pack can carry one id; composition reports that instead of failing.

**Migration**: See "A package id repeated within a pack is reported" in pack-composition.
