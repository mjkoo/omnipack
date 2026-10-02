## MODIFIED Requirements

### Requirement: Both packs include one shared omnipack notification tracker

Each export SHALL contain exactly one identical GitHub track-only entry for this project's own rolling release, whose synthetic id, name and repository come from reviewed configuration rather than from this requirement, and which carries the Track Only category as every track-only entry does. It SHALL select release titles by a pattern matching the rolling release title format fixed by "One owned rolling release publishes both variants" in rolling-pack-release and no other release of that repository, so the pattern and that format SHALL change together. It SHALL extract the revision from the matched release title, allow prereleases and scanning past unrelated releases, disable latest-endpoint prioritization and asset-date versioning, and retain background notifications. The rendered tracker SHALL NOT embed the observed revision, installed version or asset URLs. Source revision changes SHALL NOT require an APK.

Consumer documentation SHALL explain that either variant changing can notify everyone, that acknowledgement is not synchronization, and that updating the pack requires downloading the appropriate JSON and re-importing.

#### Scenario: The tracker is categorized as track-only

- **WHEN** either pack is built
- **THEN** the omnipack tracker entry carries exactly the Track Only category

#### Scenario: Only one variant changes

- **WHEN** only one variant's content changes and a complete release publication
  increments the shared revision
- **THEN** either variant's tracker can report that revision as an update

#### Scenario: Rebuild observes a newer release revision

- **WHEN** the rolling release advances to a newer revision while the curated
  configuration and other build inputs are unchanged
- **THEN** a rebuild produces the same packs, because the rendered tracker embeds
  no observed revision
