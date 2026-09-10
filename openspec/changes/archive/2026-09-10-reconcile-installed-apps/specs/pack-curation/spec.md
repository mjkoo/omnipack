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
- **THEN** live verification fails extraction and prevents nightly publication
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
- **THEN** documentation records the original identity and the manifest-backed correction
- **AND** the maintained identity policy exports com.dishii.soh while preserving source-version tracking

## ADDED Requirements

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

No unrelated app identity SHALL change as part of this reconciliation;
`com.winlator.ludashi` is explicitly outside its identity-correction scope.
They SHALL retain Symphony from sergiomanzur, OpenMW-DS from Josh-Daniels, igawa6
CTR for dual and Simon CTR for single. Gen1Recomp SHALL use its canonical
bryanthaboi/gen1recomp repository. Both packs SHALL select HarbourMasters/Ghostship
as dev.net64.ghostship from its Android ZIP, exclude legacy izzy2lost Ghostship,
and exclude the retired Super Metroid family without adding MetroidArch.

Both retained CTR repositories SHALL use effective package `com.ctrnative`:
`https://github.com/simon358/ctr-native-android` in the single-screen pack and
`https://github.com/igawa6/ctr-native-android` in the dual-screen pack. The igawa6
catalog ID is already `com.ctrnative` and SHALL remain unchanged, without an
additional identity mapping. Both original catalog IDs SHALL remain in provenance.
Implementation acceptance SHALL require separate dated manifest evidence from
each repository's selected APK confirming `com.ctrnative`, plus verification that
both rendered entries explicitly set `versionDetection: false` and preserve their
complete selected source versions after repeated upstream refreshes. Metadata
resolution or this planning revision SHALL NOT substitute for that APK evidence.

Curation acceptance SHALL use documented source reputation and basic source/APK
vetting; independent binary reproduction SHALL NOT be required. Documentation
SHALL distinguish tracking-only corrections from actual binary, signing, package,
and removal changes. It SHALL NOT claim device installation or save migration.

#### Scenario: Catalog refresh restores old identifiers and retired entries

- **WHEN** upstream catalogs contain the previously observed incorrect identifiers,
  legacy Ghostship, and both standard and dual retired Super Metroid entries
- **THEN** maintained corrections yield verified identities with at most one winner
  per family and package in each target
- **AND** official Ghostship wins in both targets and retired Super Metroid is absent
- **AND** Symphony and OpenMW-DS remain available despite non-reproducible binaries

#### Scenario: Existing installation differs from the curated choice

- **WHEN** the captured installed app has a different package or signing key
- **THEN** the comparison identifies the exact source/package change and fresh-install
  implication without performing device writes
- **AND** an ID-only correction does not imply an APK reinstall is required
