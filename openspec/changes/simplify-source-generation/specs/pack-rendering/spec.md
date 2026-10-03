## MODIFIED Requirements

### Requirement: Per-app settings are hydrated with the full default key set

Obtainium's app settings UI only shows a control for a key that is present, so
an entry carrying a partial settings object hides the rest of its switches.
The system SHALL fill each rendered entry's settings with every key defined for
the source type the entry carries, as established when the entry was ingested,
using the default value for any key the entry does not set, for every source
type the system holds defaults for. An entry with another source type, or with
none, SHALL be rendered with exactly the settings it carries, and SHALL NOT
fail rendering.

#### Scenario: Entry sets one setting

- **WHEN** a composed entry sets exactly one per-app setting
- **THEN** the rendered entry's settings carry that value together with the
  default value for every other key defined for the source type that entry
  carries

#### Scenario: Overlaid value survives hydration

- **WHEN** an overlay set a value for a key that also has a default
- **THEN** the rendered entry carries the overlaid value, not the default

#### Scenario: An entry's source type has no defaults

- **WHEN** a composed entry carries no source type, or one the system holds no
  defaults for
- **THEN** it renders with exactly its own settings and the build succeeds
