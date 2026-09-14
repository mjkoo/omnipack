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

### Requirement: The upstream pack tracker is excluded

Both published variants SHALL exclude the RJNY/Obtainium-Emulation-Pack track-only entry with id `904332840` through maintained exclusion policy, including after upstream refreshes. This exclusion SHALL preserve RJNY as an app catalog source and retain its attribution and provenance. Consumer migration guidance SHALL explain that previously imported tracking entries may require manual removal in Obtainium.

#### Scenario: Upstream refresh contains its pack tracker

- **WHEN** the RJNY source includes the track-only entry with id `904332840`
- **THEN** neither generated pack nor the generated README catalog includes that tracker
- **AND** other eligible RJNY apps remain available to composition

#### Scenario: An existing user has the tracker installed

- **WHEN** an existing user follows migration guidance
- **THEN** the guidance explains manual removal of that tracking entry without claiming pack re-import removes it automatically

### Requirement: Curated store and established ports are present in both variants

Both exports SHALL include installable entries for Aurora Store (`https://gitlab.com/AuroraOSS/AuroraStore`), idTech4A++ (`https://github.com/glKarin/com.n0n3m4.diii4a`), VCMI (`https://github.com/vcmi/vcmi`), Julius (`https://github.com/bvschaik/julius`) and Xash3D FWGS (`https://github.com/FWGS/xash3d-fwgs`). Aurora SHALL use native GitLab and select ordinary `AuroraStore-<numeric-version>.apk` assets, excluding hw and preload variants. The game engines SHALL be categorized as PC Ports; Aurora SHALL be categorized as Utilities. Entries SHALL use manifest-backed package identities and intentional architecture selection, survive upstream refreshes without duplication, and document required user-supplied game data. idTech4A++, VCMI and Julius SHALL exclude prereleases and track stable source versions with manifest-backed version policy. Their single-screen selection SHALL come from source precedence rather than a pin. Because no build or offline verification check fails when single stops selecting one of these extras, a regression check over the committed configuration SHALL assert that each is its family's single-screen winner.

#### Scenario: Upstream refresh repeats a curated project

- **WHEN** an upstream also supplies one of these projects with the same package id and project URL, including a dual-preferred BBoi34 candidate with different APK or version settings
- **THEN** each variant contains one effective entry, the maintained extra, retaining its identity, APK selection and version policy; single selects it by source precedence and dual by an explicit pin
- **AND** unpinned families retain the existing composition precedence

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

### Requirement: Reviewed installed applications use verified identities and maintained sources

The packs SHALL render the reviewed retained apps using their September 10, 2026
APK package identities, with original catalog identities retained in provenance.
The retained identity corrections SHALL be exactly:

- `com.sergiomanzur.sotnrecomp` to `com.blacklabelhq.sotn` for
  `https://github.com/sergiomanzur/SymphonyRecomp`
- `com.carlox33.hitandrun` to `com.c4rlox.simpsons` for
  `https://github.com/Carlox33/The-Simpsons-Hit-and-Run-Android`
- `com.waterdish.shipwright` to `com.dishii.soh` for
  `https://github.com/Waterdish/Shipwright-Android`
- `com.samyost1.zelda3android` to `com.dishii.zelda3` for
  `https://github.com/samyost1/zelda3-android`
- `com.izzy2lost.spaghettikart` to `com.izzy.kart` for
  `https://github.com/izzy2lost/SpaghettiKart`
- `com.izzy2lost.perfectdark` to `com.perfectdark.port` for
  `https://github.com/izzy2lost/perfect_dark`
- `487343354` to `com.retroarch.aarch64` for
  `https://buildbot.libretro.com/stable`
- `com.izzy2lost.starship` to `com.starship.android` for
  `https://github.com/izzy2lost/Starship`
- `com.bryanthaboi.pokemonredblue` to `com.theboisclub.pokemonred` for
  `https://github.com/bryanthaboi/pokemon-gen1-recomp-project`
- `org.linkzenic.twoship` to `com.twoshipfork.mm` for
  `https://github.com/linkzenic/2ship2harkinian-Android`
- `com.samyost1.tmcandroid` to `dev.picori.tmc` for
  `https://github.com/samyost1/tmc-android`
- `com.igawa6.dusklight` to `dev.twilitrealm.dusk` for
  `https://github.com/igawa6/dusklight`
- `com.igawa6.harvestmoon64` to `io.github.hm64recomp` for
  `https://github.com/igawa6/HarvestMoon64Recomp`
- `com.matteo842.crashbandicoot` to
  `io.github.matteo842.crashlauncher.runtime` for
  `https://github.com/Matteo842/CrashBandicoot-Launcher`
- `com.joshdaniels.openmwds` to `org.openmw.ds` for
  `https://github.com/Josh-Daniels/OpenMW-DS`
- `com.simon358.ctrnative` to `com.ctrnative` for
  `https://github.com/simon358/ctr-native-android` in the single-screen pack

The listed identity corrections SHALL affect only the enumerated app identities
and SHALL NOT correct `com.winlator.ludashi`.
They SHALL retain Symphony from sergiomanzur, OpenMW-DS from Josh-Daniels, igawa6
CTR for dual and Simon CTR for single. Gen1Recomp SHALL use its canonical
bryanthaboi/gen1recomp repository. Both packs SHALL select HarbourMasters/Ghostship
as dev.net64.ghostship from its Android ZIP, exclude legacy izzy2lost Ghostship,
and deny the reviewed retired Super Metroid catalog IDs
`com.raekwon1603.supermetroid` and `com.raekwon1603.supermetroidds`. The dual-screen
pack SHALL include MetroidArch as specified below; the single-screen pack SHALL omit it.
Future changed or additional retired IDs SHALL require curation review rather than
automatic repository-wide exclusion.

Both retained CTR repositories SHALL use effective package `com.ctrnative`:
`https://github.com/simon358/ctr-native-android` in the single-screen pack and
`https://github.com/igawa6/ctr-native-android` in the dual-screen pack. The igawa6
catalog ID is already `com.ctrnative` and SHALL remain unchanged, without an
additional identity mapping. Both original catalog IDs SHALL remain in provenance.
Implementation acceptance SHALL require separate dated manifest evidence from
each repository's selected APK confirming `com.ctrnative`, plus verification that
both rendered entries explicitly set `versionDetection: false` and preserve their
complete selected source versions after repeated upstream refreshes. Metadata
resolution SHALL NOT substitute for that APK evidence.

Curation acceptance SHALL use documented source reputation and basic source/APK
vetting; independent binary reproduction SHALL NOT be required. Documentation
SHALL distinguish tracking-only corrections from actual binary, signing, package,
and removal changes. It SHALL NOT claim device installation or save migration.

#### Scenario: Catalog refresh restores old identifiers and retired entries

- **WHEN** upstream catalogs contain the previously observed incorrect identifiers,
  legacy Ghostship, and both standard and dual retired Super Metroid entries
- **THEN** maintained corrections yield verified identities with at most one winner
  per family and package in each target
- **AND** official Ghostship wins in both targets and the two reviewed retired Super Metroid catalog IDs are absent
- **AND** Symphony and OpenMW-DS remain available despite non-reproducible binaries

#### Scenario: Existing installation differs from the curated choice

- **WHEN** the captured installed app has a different package or signing key
- **THEN** the comparison identifies the exact source/package change and fresh-install
  implication without performing device writes
- **AND** an ID-only correction does not imply an APK reinstall is required

### Requirement: MetroidArch preserves a separate dual-screen Super Metroid selection

The dual-screen pack SHALL include exactly one MetroidArch entry from
`https://github.com/Raekwon1603/RetroArch` with package `com.metroidarch.app.aarch64`
and stable APK release selection. The single-screen pack SHALL omit MetroidArch.
Both packs SHALL retain ordinary RetroArch and exclude the retired
catalog IDs `com.raekwon1603.supermetroid` and `com.raekwon1603.supermetroidds`,
including after repeated upstream refreshes. This exclusion SHALL use existing
catalog-ID deny configuration and SHALL NOT add URL-deny behavior. Future changed
or additional retired IDs SHALL require curation review.
The source SHALL be classified as the Super Metroid family, not ordinary RetroArch.

MetroidArch SHALL track complete GitHub release tags with APK version detection
disabled, because the reviewed releases share the APK version name `1.22.2_GIT`.
Update checks SHALL remain enabled. Selection SHALL match only versioned
`MetroidArch-v<dotted numeric version>.apk` assets, exclude prereleases and ZIPs,
and not depend on architecture text in the filename. It SHALL set
`fallbackToOlderReleases=false` and select the newest eligible stable release. If
that release has no matching versioned APK, resolution SHALL fail without selecting
an older release.

Documentation SHALL record the dated source/reputation and APK evidence,
ARM64 core limitation, debuggable build, inherited HTTP updater defaults, and
known widescreen limitations without claiming device validation. It SHALL explain
that the main app configuration and cores are package-specific but external saves,
overrides and remaps can share RetroArch directories. It SHALL describe app-menu
and stopped-app ADB configuration mechanisms, including backup and verification,
without claiming that Obtainium imports configure those directories automatically.

#### Scenario: Catalogs contain both old port variants and the successor

- **WHEN** catalogs are composed and refreshed repeatedly with the retired source and MetroidArch candidates
- **THEN** only dual exports MetroidArch with the verified package and intended source
- **AND** ordinary RetroArch remains in both targets, the two reviewed retired catalog IDs remain absent, and no duplicate family or package is exported

#### Scenario: Release and APK versions disagree

- **WHEN** the source publishes stable tags `v1.0.0` and `v1.0.1`, both with APK versionName `1.22.2_GIT`
- **THEN** their source versions remain distinct and the current matching APK is selected
- **AND** unrelated APK names, ZIP assets, and prereleases are not selected

#### Scenario: Newest stable release lacks a matching versioned APK

- **WHEN** the newest eligible stable release has no asset matching `MetroidArch-v<dotted numeric version>.apk`
- **THEN** resolution fails for that release
- **AND** no APK from an older release is selected

#### Scenario: A user imports the pack on a device with RetroArch

- **WHEN** the user reads the MetroidArch setup documentation
- **THEN** it identifies the new-package install, potential shared-directory effects, and manual or ADB configuration procedure
- **AND** it distinguishes source-backed instructions from unperformed on-device checks

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
