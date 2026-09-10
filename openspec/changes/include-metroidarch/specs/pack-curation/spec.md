## MODIFIED Requirements

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
- **AND** official Ghostship wins in both targets and the two reviewed retired Super Metroid catalog IDs are absent
- **AND** Symphony and OpenMW-DS remain available despite non-reproducible binaries

#### Scenario: Existing installation differs from the curated choice

- **WHEN** the captured installed app has a different package or signing key
- **THEN** the comparison identifies the exact source/package change and fresh-install
  implication without performing device writes
- **AND** an ID-only correction does not imply an APK reinstall is required

## ADDED Requirements

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
