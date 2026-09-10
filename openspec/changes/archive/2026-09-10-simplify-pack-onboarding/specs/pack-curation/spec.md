## ADDED Requirements

### Requirement: The upstream pack tracker is excluded

Both published variants SHALL exclude the RJNY/Obtainium-Emulation-Pack track-only entry with id `904332840` through maintained exclusion policy, including after upstream refreshes. This exclusion SHALL preserve RJNY as an app catalog source and retain its attribution and provenance. Consumer migration guidance SHALL explain that previously imported tracking entries may require manual removal in Obtainium.

#### Scenario: Upstream refresh contains its pack tracker

- **WHEN** the RJNY source includes the track-only entry with id `904332840`
- **THEN** neither generated pack nor the generated README catalog includes that tracker
- **AND** other eligible RJNY apps remain available to composition

#### Scenario: An existing user has the tracker installed

- **WHEN** an existing user follows migration guidance
- **THEN** the guidance explains manual removal of that tracking entry without claiming pack re-import removes it automatically
