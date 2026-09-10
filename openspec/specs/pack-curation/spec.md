# pack-curation Specification

## Purpose

Defines the maintained app additions and per-app version policies that make the
published packs useful beyond their upstream catalogs, including the limits of
source-version tracking and the evidence supporting each policy.

## Requirements

### Requirement: Cinderbox is included in both packs

The packs SHALL include Cinderbox from `https://github.com/Ekyso/Cinderbox`
under package id `com.game.cinderbox`, named `Cinderbox`, in category `PC Ports`,
in both variants. It SHALL be installable rather than track-only, exclude
prereleases, and use release tags with standard version detection. It SHALL NOT
use a date override or version-extraction rule for the observed numeric releases.

#### Scenario: Stable Cinderbox release and build-dependency prerelease coexist

- **WHEN** release metadata contains stable app tag `0.8.1` with
  `Cinderbox-v0.8.1.apk` and a newer build-dependency prerelease
- **THEN** both variants select the stable app release and version `0.8.1`
- **AND** the rendered package id is `com.game.cinderbox`

### Requirement: Numeric app versions are selected without release labels

The maintained policies SHALL extract the dotted numeric substring from
BanjoRecomp (`com.aure.banjorecomp`) and SymphonyRecomp
(`com.sergiomanzur.sotnrecomp`) release tags, retaining all numeric components.
The configured extraction SHALL fail when no dotted numeric substring exists.
Both variants of Cemu (`info.cemu.cemu`) SHALL use their respective release tag
instead of the release title. These apps SHALL retain standard version detection.
RPCSX (`net.rpcsx`) SHALL retain its existing complete tag and standard version
detection; its single numeric component SHALL NOT be rewritten as a dotted version.

#### Scenario: Android labels are removed

- **WHEN** BanjoRecomp selects `android-v0.1.1` and SymphonyRecomp selects
  `android-v0.10.1b`
- **THEN** their effective versions are `0.1.1` and `0.10.1` in both packs
- **AND** SymphonyRecomp `android-v0.10b` produces `0.10`, a distinct version

#### Scenario: Cemu variants have different release metadata

- **WHEN** single-screen Cemu selects tag `0.5` with title `Cemu 0.5`, and
  dual-screen Cemu selects tag `0.5.2` with a descriptive title
- **THEN** their effective versions are `0.5` and `0.5.2`, respectively
- **AND** their source URLs and variant membership are preserved

#### Scenario: Future numeric extraction input no longer matches

- **WHEN** a selected BanjoRecomp or SymphonyRecomp release has no dotted
  numeric version in its tag
- **THEN** live verification fails extraction and prevents nightly publication
- **AND** the policy does not substitute an old or invented version

### Requirement: Source-version tracking preserves build identity

The packs SHALL explicitly set `versionDetection: false` for the following
configured package ids in every variant containing them:

- `com.simon358.ctrnative`
- `com.waterdish.shipwright`
- `org.citron.citron_emu`
- `org.vita3k.emulator`
- `xendroid.compose`
- `com.winlator.ludashi`
- `com.winlator.cmod`
- `xyz.blacksheep.mjolnir`

These policies SHALL preserve complete selected source versions, without adding
numeric extraction or date conversion. They SHALL NOT enable track-only mode,
disable update checks or notifications, or change release/APK selection settings.
Verification SHALL retain the existing disabled-detection classification. Package
ids, URLs and variant membership SHALL remain unchanged by these version policies.

#### Scenario: Patch builds share a numeric base

- **WHEN** Shipwright releases use tags `v9.0.2`, `v9.0.2P1`, and `v9.0.2P2`
- **THEN** the exported policy preserves three different effective source versions
- **AND** it does not reduce all three releases to `9.0.2`

#### Scenario: Build number differs from APK version name

- **WHEN** Vita3K selects build tag `4093` with APK versionName `0.2.1`
- **THEN** its effective source version remains `4093` with standard version
  detection explicitly disabled
- **AND** the next distinct build tag remains distinguishable without changing
  the APK version name

### Requirement: Curation evidence states its limits

Durable curation documentation SHALL state each maintained policy and rationale,
observed release/APK versions and package identities, observation date, and primary
upstream references. It SHALL distinguish format lint from APK agreement and
metadata verification from device validation. It SHALL explain that explicit
source-version tracking keeps update checks enabled but cannot guarantee
eliminating a one-time spurious update after re-import or detecting an in-place
asset replacement that leaves the source version unchanged.

Known upstream package-id mismatches SHALL be recorded without claiming that a
version policy repairs them. A clean lint result SHALL NOT be described as proof
of safe identity, installation, re-import, or update behavior for those entries.

#### Scenario: Resolved APK declares another package id

- **WHEN** the inspected Shipwright APK declares `com.dishii.soh` while the
  configured entry uses `com.waterdish.shipwright`
- **THEN** documentation identifies the mismatch as unresolved identity work
- **AND** this version curation preserves the configured id

### Requirement: The upstream pack tracker is excluded

Both published variants SHALL exclude the RJNY/Obtainium-Emulation-Pack track-only entry with id `904332840` through maintained exclusion policy, including after upstream refreshes. This exclusion SHALL preserve RJNY as an app catalog source and retain its attribution and provenance. Consumer migration guidance SHALL explain that previously imported tracking entries may require manual removal in Obtainium.

#### Scenario: Upstream refresh contains its pack tracker

- **WHEN** the RJNY source includes the track-only entry with id `904332840`
- **THEN** neither generated pack nor the generated README catalog includes that tracker
- **AND** other eligible RJNY apps remain available to composition

#### Scenario: An existing user has the tracker installed

- **WHEN** an existing user follows migration guidance
- **THEN** the guidance explains manual removal of that tracking entry without claiming pack re-import removes it automatically
