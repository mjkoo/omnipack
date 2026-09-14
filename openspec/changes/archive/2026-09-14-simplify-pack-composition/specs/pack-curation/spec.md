## MODIFIED Requirements

### Requirement: Curated store and established ports are present in both variants

Both exports SHALL include installable entries for Aurora Store (`https://gitlab.com/AuroraOSS/AuroraStore`), idTech4A++ (`https://github.com/glKarin/com.n0n3m4.diii4a`), VCMI (`https://github.com/vcmi/vcmi`), Julius (`https://github.com/bvschaik/julius`) and Xash3D FWGS (`https://github.com/FWGS/xash3d-fwgs`). Aurora SHALL use native GitLab and select ordinary `AuroraStore-<numeric-version>.apk` assets, excluding hw and preload variants. The game engines SHALL be categorized as PC Ports; Aurora SHALL be categorized as Utilities. Entries SHALL use manifest-backed package identities and intentional architecture selection, survive upstream refreshes without duplication, and document required user-supplied game data. idTech4A++, VCMI and Julius SHALL exclude prereleases and track stable source versions with manifest-backed version policy. Their single-screen selection SHALL come from source precedence rather than a pin. Because no build or offline verification check fails when single stops selecting one of these extras, a regression check over the committed configuration SHALL assert that each is its family's single-screen winner.

#### Scenario: Upstream refresh repeats a curated project

- **WHEN** an upstream also supplies one of these projects with the same package id and project URL, including a dual-preferred BBoi34 candidate with different APK or version settings
- **THEN** each variant contains one effective entry, the maintained extra, retaining its identity, APK selection and version policy; single selects it by source precedence and dual by an explicit pin
- **AND** unpinned families retain the existing composition precedence
