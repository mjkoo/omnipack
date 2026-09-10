## ADDED Requirements

### Requirement: Curated store and established ports are present in both variants

Both exports SHALL include installable entries for Aurora Store (`https://gitlab.com/AuroraOSS/AuroraStore`), idTech4A++ (`https://github.com/glKarin/com.n0n3m4.diii4a`), VCMI (`https://github.com/vcmi/vcmi`), Julius (`https://github.com/bvschaik/julius`) and Xash3D FWGS (`https://github.com/FWGS/xash3d-fwgs`). Aurora SHALL use native GitLab and select ordinary `AuroraStore-<numeric-version>.apk` assets, excluding hw and preload variants. The game engines SHALL be categorized as PC Ports; Aurora SHALL be categorized as Utilities. Entries SHALL use manifest-backed package identities and intentional architecture selection, survive upstream refreshes without duplication, and document required user-supplied game data. idTech4A++, VCMI and Julius SHALL exclude prereleases and track stable source versions with manifest-backed version policy.

#### Scenario: Upstream refresh repeats a curated project

- **WHEN** an upstream also supplies one of these projects
- **THEN** each variant contains one effective entry with the maintained identity and selection policy

### Requirement: Xash3D tracks the continuous Android asset

Xash3D SHALL select the GitHub release titled exactly `Xash3D FWGS Continuous master Build`, permit prereleases, select only `xash3d-fwgs-android.apk`, use that asset's update date as its release date and the resulting epoch-microsecond value as its effective version, and disable installed-version detection. Latest-release endpoint prioritization SHALL be disabled; release scanning SHALL permit finding the title past other release channels. No fixed build or tag-date snapshot SHALL be embedded. Documentation SHALL identify this as a rolling prerelease channel.

#### Scenario: APK changes under the same tag

- **WHEN** the selected APK's update timestamp advances while the release tag remains continuous
- **THEN** its effective version changes and retains numeric ordering

#### Scenario: A different platform or channel changes

- **WHEN** only a non-Android asset or continuous-freevgui release changes
- **THEN** the selected Android version remains unchanged

#### Scenario: Upstream temporarily removes the release

- **WHEN** the continuous master release or required APK is unavailable
- **THEN** verification fails without accepting another channel or suppressing the error

### Requirement: Hollow Knight entries have recognizable presentation

The existing `igawa6.dualsouls` and `com.jakobkhansen.silksong` entries SHALL retain their package ids, GitHub repositories and dual-only eligibility. Their maintained names SHALL be `Hollow Knight: Dual Souls` and `Hollow Knight: Silksong`, categorized as PC Ports. Setup documentation SHALL explain user-supplied game files, their second-screen features, and the currently documented Android 13 restriction for Silksong without claiming device validation.

#### Scenario: Catalog is rebuilt

- **WHEN** upstream entries retain their raw project names
- **THEN** the dual-screen catalog and import entries use the maintained recognizable names and categories without adding single-screen entries

### Requirement: Both packs include one shared omnipack notification tracker

Each export SHALL contain exactly one identical GitHub track-only entry with stable synthetic id `809443320`, name `omnipack updates`, repository `https://github.com/mjkoo/omnipack`, and Utilities categorization. It SHALL select titles matching `^omnipack revision [0-9]+$`, extract the trailing integer from the release title, allow prereleases and scanning past unrelated releases, disable latest-endpoint prioritization and asset-date versioning, and retain background notifications. The rendered tracker SHALL NOT embed the observed revision, installed version or asset URLs. Source revision changes SHALL NOT require an APK.

Consumer documentation SHALL explain that either variant changing can notify everyone, that acknowledgement is not synchronization, and that updating the pack requires downloading the appropriate JSON and re-importing. Existing raw-main links and the RJNY tracker exclusion SHALL remain in force.

#### Scenario: Only one variant changes

- **WHEN** a complete release publication increments the shared revision
- **THEN** either variant's tracker can report that revision as an update

#### Scenario: Rebuild observes a newer release revision

- **WHEN** the curated configuration and other build inputs are unchanged
- **THEN** observing the tracker revision alone does not change either generated pack
