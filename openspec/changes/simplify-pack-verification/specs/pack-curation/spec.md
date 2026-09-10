## ADDED Requirements

### Requirement: Curation regression checks protect exported configuration

Maintained source-selection, version, and asset policies SHALL be expressed as
Obtainium configuration and preserved across source refreshes. Their selection
scenarios describe intended Obtainium behavior; the pack builder SHALL NOT
independently execute those behaviors as a live compatibility guarantee.
Regression checks SHALL exercise composition and rendering with fixture source
records and assert the maintained IDs, URLs, variant membership, and override
values. Known observed versions and asset identities SHALL remain dated evidence,
not assertions of current upstream health. Tests SHALL NOT require maintaining
another implementation of Obtainium source resolution or regex semantics.

#### Scenario: Upstream refresh changes a curated setting

- **WHEN** fixture source records change a setting covered by a maintained override
- **THEN** composed and rendered output retains the intended curated value

#### Scenario: Recorded release examples remain available

- **WHEN** the live verifier is retired
- **THEN** dated curation evidence remains readable without claiming its observations were freshly verified


## MODIFIED Requirements

### Requirement: Numeric app versions are selected without release labels

The maintained policies SHALL extract the dotted numeric substring from
BanjoRecomp (`com.aure.banjorecomp`) and SymphonyRecomp
(`com.blacklabelhq.sotn`) release tags, retaining all numeric components.
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
- **THEN** the maintained extraction policy remains unchanged for Obtainium to evaluate
- **AND** structural pack verification does not inspect that tag or block publication because of it
- **AND** the policy does not substitute an old or invented version

### Requirement: Source-version tracking preserves build identity

The packs SHALL explicitly set `versionDetection: false` for the following
configured package ids in every variant containing them:

- `com.ctrnative`
- `com.dishii.soh`
- `org.citron.citron_emu`
- `org.vita3k.emulator`
- `xendroid.compose`
- `com.winlator.ludashi`
- `com.winlator.cmod`
- `xyz.blacksheep.mjolnir`

The `com.ctrnative` policy SHALL apply to both retained repository choices:
`https://github.com/simon358/ctr-native-android` in the single-screen pack and
`https://github.com/igawa6/ctr-native-android` in the dual-screen pack.

These policies SHALL preserve complete selected source versions, without adding
numeric extraction or date conversion. They SHALL NOT enable track-only mode,
disable update checks or notifications, or change release/APK selection settings.
Structural validation SHALL retain the boolean setting without classifying an effective upstream version. Package
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
upstream references. It SHALL distinguish current structural validation from dated metadata/APK
observations and device validation. It SHALL explain that automated source
resolution, format lint, and upstream-health publication gating are retired. It SHALL explain that explicit
source-version tracking keeps update checks enabled but cannot guarantee
eliminating a one-time spurious update after re-import or detecting an in-place
asset replacement that leaves the source version unchanged.

Known upstream package-id mismatches SHALL be recorded without claiming that a
version policy repairs them. A successful structural result SHALL NOT be described as proof
of safe identity, installation, re-import, or update behavior for those entries.

#### Scenario: Resolved APK declares another package id

- **WHEN** the inspected Shipwright APK declares `com.dishii.soh` while the
  configured entry uses `com.waterdish.shipwright`
- **THEN** documentation records the original identity and the manifest-backed correction
- **AND** the maintained identity policy exports com.dishii.soh while preserving source-version tracking

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
- **THEN** the exported policy remains restricted to the configured channel and asset
- **AND** structural verification neither detects the absence nor blocks publication because of it

