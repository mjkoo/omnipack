# Candidate watchlist

Apps considered for the packs that are waiting on something before they can be
added. Each entry says why it waits and what would promote it. Re-check entries
periodically, by hand or with an agent sweep using the project's
`vet-candidates` skill, which holds the inclusion bar. To promote one, add it to
`config/extras.json` (with the usual provenance check against the current state
of the project) and remove it here. Drop an entry that is abandoned or rejected;
a rejected app needs a `config/deny.json` denial only when a catalog actually
brings it in.
Declined apps that a later search could find again are listed at the end, so
they are not re-proposed unless something material changes.

## No trackable Android build

- **Paper Mario 64 (PaperBoat)** - https://github.com/HarbourMasters/PaperBoat.
  The upstream repository contains an Android project, but its Android builds are
  CI artifacts only; releases carry desktop builds. Community forks with APK
  releases are one-off builds that do not follow upstream.
  Promote when an upstream release carries an Android APK.
- **EarthBound (Phase-Distorter)** - https://github.com/TheRunaway5/Phase-Distorter.
  A PC port with desktop builds only; Android is an open request.
  Promote when a release carries an Android APK.
- **Kingdom Hearts 358/2 Days (khdays-port)** - https://github.com/Yokimitsuro/khdays-port.
  A native port on the DS decompilation, Windows only; other platforms are
  planned. Promote when a release carries an Android APK.
- **Rush 2 Recompiled** - https://github.com/bryantmh/rush2recompiled.
  An N64 recomp with Windows and Linux builds only, forks included.
  Promote when a release carries an Android APK.
- **Daytona USA arcade recomp** - https://github.com/alphanu1/daytona-arcade-recomp.
  The Android build is reported to work, but game code is generated from the
  user's ROM set, so no release ships a distributable APK.
  Promote when a release carries an Android APK.
- **F-Zero GX recomp** - https://github.com/Pipyakas/fzero-gx-recomp.
  Android is buildable from source as a self-built debug APK, but there are no
  releases. Other F-Zero repositories that
  do publish APKs were rejected for thin or suspicious provenance (brand new
  accounts, one-off or download-less releases).
  Promote when a release from a project with a real history carries an Android APK.
- **RetroArch transfer** - a utility for moving RetroArch data between devices,
  teased by ItsRetroPup (https://github.com/ItsRetroPup) but not yet published.
  Promote once a repository with an Android APK release appears under that
  account and it passes the usual checks.

## Provenance or maturity

- **Super Mario Galaxy (Nebula)** - https://github.com/keepvaibin/nebula.
  A GPL Petari-based native port, playable to the end on Windows, with an
  Android app in its source tree that requests no sensitive permissions and keeps
  game data in app-private storage. Releases carry only a Windows installer so
  far. Promote when a release carries an Android APK and it passes the usual
  checks.
- **Pathfinder** - https://github.com/KaitonGxx/thor-pathfinder.
  An open-source AYN Thor utility in the spirit of Wayfinder, not a replacement
  for it: a smaller feature set, a short AI-written history, and accessibility
  service plus Shizuku access. Promote as an optional alternative to Wayfinder
  once it has a sustained release history and outside use.
- **New Super Mario Bros. Wii (NSMBW Recompiled)** - https://github.com/WitherBlitz/NSMB-Wii-Multiplayer-Recompilation.
  A GPL static recomp on WiiCompiled and aurora with one APK per release and
  outside contributors, but a young, almost entirely AI-written history in which
  releases have been pulled for game-breaking bugs. Its install permission
  serves a self-updater that checks its own release asset's digest.
  Promote when releases have stayed stable, with none pulled, for about a month.
- **WiiDS** - https://github.com/Maddex712/WiiDS. Denied in
  `config/deny.json`. Releases now install over one another under one signing
  key, and its notes report Super Mario Galaxy booting on an AYN Thor, but it
  has grown into a multi-game Wii hub that ships Nintendo's own menu music, HUD
  art and cover scans, bundles a large mod patch, and in a prerelease adds a
  Brawl engine that its own notes say still contains original Nintendo data,
  with redistribution permission unrecorded. It requests all-files storage, and
  its install permission serves an in-app updater, readable in the repository,
  that installs only the latest stable release after checking GitHub's asset
  digest, its own release inventory and the installed signing key. The author
  has replaced APKs under an existing release tag, which Obtainium does not
  detect as an update. The prerelease's notes call Brawl's single-screen
  acceptance incomplete. Promote by removing the denial when the owner accepts the
  takedown exposure; triage then decides single as
  for any codm arrival, with a
  `"packs": ["single"]` denial if it does not work on one display.
- **MOTHER 3 (Mother3Recomp)** - https://github.com/josiahg2502-glitch/Mother3Recomp.
  A gbarecomp-based recomp with one APK per release under a stable asset name,
  from a brand-new account with many quick recomps. The repository sets a
  development-suffixed package id and signs releases with a debug certificate.
  Promote when the account has a sustained history and the package id is final.
- **Super Mario Sunshine (Mareshine)** - https://github.com/TheM3dium/mareshine.
  A Sunshine port now built on chasem-dev's MIT-licensed PC port (earlier
  versions forked jbcgames/sms-android), from a brand-new single-repository
  account with a burst of commits and releases. It requests all-files storage,
  and its install permission serves a self-updater that verifies its own
  signature. Promote when it has a sustained history and outside use.
- **Donkey Kong 64 (DK64 Recompiled)** - https://github.com/deivid22srk/dk64-recomp-android.
  An Android port of the DK64 N64 recomp with one APK per release, from an author
  of many quick ports, with a short burst of largely automated commits and
  little outside use; development went quiet after its first releases.
  Promote when new APK releases show sustained maintenance and the project gains
  outside use.

- **Skies of Arcadia Legends: Recompiled** - https://github.com/ogdanimal/SkiesOfArcadiaLegends-Recomp.
  A GPL GameCube static recomp on a patched Dolphin Android app, by the author
  of the Goemon and Hybrid Heaven recomps, with one APK per release and a pinned
  signing key. Every release is a beta prerelease, some carry no APK, and it
  requests all-files storage for an optional data folder.
  Promote when a release that is not a prerelease carries an Android APK.
- **Need for Speed Underground 2 (nfsu2-recompiled)** - https://github.com/codepdbh/nfsu2-recompiled.
  A static recomp of the PC game with arm64 and armeabi-v7a APKs per release
  and wide outside use, from a recently created account with a rapid stream of
  AI-assisted ports that says it replaces a compromised earlier account. It
  requests all-files storage for its game folder. The same author's
  nfsmw-android, nfsu1-recompiled and NFS-CARBON-360-ANDROID-RECOMP ports wait
  on the same terms. A continuation by another author,
  https://github.com/mininxd/NFSU2-Revived-Android, signs its releases with a
  keystore whose password is committed to the public repository, so anyone can
  build an APK that installs over it; it waits until the history is sustained.
  Promote when the account has kept up Android releases that install over one
  another for about a month.
- **Link's Awakening (LASRecomp Android Plus)** - https://github.com/Nycolazs/LASRecomp-Android-Plus.
  An almost entirely AI-written Android fork of the LASRecomp Switch recomp,
  with one APK per Android release beside upstream test tags. The game is
  recompiled on the device from the user's dump and keys, and its signing key
  has changed between releases.
  Promote when several releases have installed over one another with no further
  key change.
- **Final Fantasy Tactics Advance Recomp** - https://github.com/james2doyle/ffta-recomp.
  A gbarecomp-based recomp under a noncommercial license from an established
  account, with one APK per release, but a short, heavily agent-driven history
  and debug-signed APKs built locally.
  Promote when releases have kept installing over one another for about a month.
- **Retro Launcher** - https://github.com/RetroPortingToolKit/Retro-Launcher.
  An MIT frontend for static recomps with one APK per release, all-files storage
  and a self-updater limited to its own package. Its own documentation calls
  Android support initial and unvalidated on devices.
  Promote when the documentation no longer describes Android as initial or as
  needing device validation.
- **Sonic R (sonic-r-android)** - https://github.com/ZinexDa/sonic-r-android.
  An Android port of the Sonic R PC decompilation under that project's
  noncommercial license, from a small single-author account, with drifting asset
  names and debug-signed local builds.
  Promote when asset names are stable and the history is sustained.
- **God of War III (gow3_android)** - https://github.com/zFitness/gow3_android.
  A GPL fork of gow3_pc (now SpartanPort) on FEXCore and the shadPS4 renderer
  with wide outside use. Its standalone APK releases changed package id and
  signing key repeatedly and have stopped; the port now ships as a package
  imported into the author's closed-source nixport host app, itself an alpha
  prerelease. Promote when a release carries a trackable Android APK whose
  package id and signing key hold across several releases; Sony trademark and
  takedown exposure is the owner's call.
- **Ninja Gaiden Black Recompiled** - https://github.com/gamboozino/ngbrecomp.
  A GPL static recomp of the Xbox game with outside interest and a few outside
  contributors, but a young, heavily AI-assisted history. Releases that are not
  prereleases now carry the APK, but the README still calls Android
  experimental and tested on a single phone. Promote when Android is no longer
  described as experimental and releases keep installing over one another.
- **Sin and Punishment (snprecomp)** - https://github.com/wootbeer/snprecomp.
  A GPL N64Recomp port with one APK per release and a private signing key, from
  a brand-new account with a rapid stream of almost entirely AI-written ports.
  The same account's other Android ports (Descent-Android, Descent2-Android,
  gsrandroid and its DOS ports) wait on the same terms.
  Promote when the account has a sustained history and Android releases have
  kept installing over one another for about a month.
- **Pokemon Snap (Snap64Recomp)** - https://github.com/JackandBeans/Snap64Recomp.
  A GPL N64 recomp from a dedicated, heavily AI-assisted account, with one APK
  per release signed with a private key. It requests all-files storage, and its
  README describes Android as beta, run on a single phone.
  Promote when several releases have installed over one another and Android
  leaves beta.
- **Dragon Ball Z: Budokai Tenkaichi 3 (Dragon Rage)** - https://github.com/dfdx047/Tenkaichi3DecompAndroid.
  An Android fork of the Tenkaichi3Decomp PC port with outside interest and one
  APK per release beside a nightly prerelease stream. Releases are signed with a
  test keystore whose password is committed to the public repository, and its
  install permission serves a self-updater that installs from its own releases
  without a digest check. Promote when the history is sustained and releases
  keep installing over one another.
- **Midnight Club: Los Angeles (mcla-recomp-android-g)** - https://github.com/gabrielbskk/mcla-recomp-android-g.
  An Android recomp built in a single burst of agent-written commits, with only
  open-beta and test releases, tested on one phone.
  Promote when it has a sustained history with stable releases.
- **Elder Scrolls 3 Morrowind (OpenMW-DS Duo Lite)** - https://github.com/SergeShack/OpenMW-DS.
  A GPL fork of Josh-Daniels/OpenMW-DS, the dual-screen OpenMW build already in
  the packs, tuned for the Retroid Pocket Duo Lite (a 30 fps cap, shorter view
  distance, larger text and inventory options, a fix for a first-cast freeze).
  It ships its own package id, `io.github.sergeshack.openmwds`, so it could sit
  beside upstream. It is a small, readable diff on top of upstream, but it comes
  from a single burst of commits and releases with almost no downloads, and it
  keeps upstream's all-files storage and the self-updater, now pointed at its
  own releases. A fork tuned for one device is worth carrying when that device
  is popular. Promote when it has a sustained history and keeps pace with
  upstream OpenMW-DS releases.
- **Zelda: Tears of the Kingdom (TotK Native)** - https://github.com/AurelioB/totk-android.
  An MIT native Android runner for the user's own Switch dump, by the author of
  the Banjo-Kazooie recomp and Cluster Tune already in the packs, with one APK
  per release, Adreno GPUs only, and an optional second-screen companion for
  the AYN Thor and Retroid Pocket Duo that is skipped on single-screen devices.
  It requests all-files storage for game data, and its install permission
  serves an opt-out self-updater that checks the APK's checksum and signing
  certificate. The project is brand new and targets a recent first-party Nintendo title.
  Promote when it has a sustained release history and the owner accepts the
  takedown exposure.
- **Need for Speed: Most Wanted (MostWanted-Android)** - https://github.com/RanggaCasper/MostWanted-Android.
  A GPL static recomp of the Xbox game on XboxXBE-Recomp, from an established
  account, with one APK per release, wide outside use and outside
  contributors, but a young, AI-assisted history. It requests all-files storage
  for its game folder; its update checker only links to its own releases. The
  same author's Black-Android and ShaolinMonks-Android ports share its Android
  host and have not been vetted. Promote when it has a sustained history and
  releases keep installing over one another.
- **Zelda: Breath of the Wild (BOTWRecompAndroid)** - https://github.com/mamcjr/BOTWRecompAndroid.
  An MIT recomp on Peiikai's LASRecomp engine, from an established account
  with outside contributors and wide outside use, with one APK per release.
  Every release is a beta prerelease, and the repository also builds a separate
  probe app. It requests all-files storage to read game files in place. The
  same author's TOTKDroid (https://github.com/mamcjr/TOTKDroid, a Tears of the
  Kingdom fork of it) waits on the same terms.
  Promote when a release that is not a prerelease carries the APK.
- **Sonic the Hedgehog 2006 (MarathonRecomp-Android)** - https://github.com/SansNope/MarathonRecomp-Android.
  A GPL Android port of the MarathonRecomp Xbox 360 recomp by the author of the
  Sonic Unleashed Recomp port already in the packs, with one APK per release
  and only the vibrate permission. Its README says upstream MarathonRecomp is
  not meant for public use yet and the port inherits that state.
  Promote when upstream MarathonRecomp makes a public release, or earlier if
  the owner decides upstream's stance does not hold the port back.
- **Super Mario All-Stars (SuperMarioAllStars)** - https://github.com/Darhkfox/SuperMarioAllStars.
  A native port that runs from the user's own SNES ROM, with an Android APK
  beside PC builds in each release, from a small account in a single burst of
  commits. Promote when it has a sustained history.
- **Persona 5 Royal (p5r-android)** - https://github.com/Brandon04Gonzalez/p5r-android.
  An MIT native runner for the user's own Switch dump and keys, with one APK per
  release under a fixed asset name, from an account whose history could not be
  checked, in a young burst of commits. Promote when the account's provenance
  is established and it has a sustained history.
- **Banjo-Tooie (Tooie Recompiled)** - https://github.com/Frostie77/Tooie-Recompiled.
  An N64Recomp and RT64 port, well documented with device reports and only the
  internet permission, but from a brand-new account in a single burst of
  commits. Its release builds add a `.release` package suffix.
  Promote when it has a sustained history and outside use.
- **Recompa** - https://github.com/kalasyan/recompa.
  A GPL launcher and installer for native ports from an established account,
  with one APK per release and a second-screen view on the AYN Thor. Installing
  and removing port APKs, with checksum and signature checks, is its main
  function, which overlaps what Obtainium does for the packs.
  Promote when releases have been stable for about a month and the owner
  decides an in-app port store belongs in the packs.
- **Fable II (FableDroid)** - https://github.com/hardsilinder/FableDroid.
  An Android port of the Fable-2-Recomp Xbox 360 recomp that keeps upstream
  history and requests only internet and vibrate, but every release is a beta,
  no license is stated, and its release assets have not been checked.
  Promote when a license is stated and releases carrying the APK have a
  sustained history.
- **Raitchi** - https://github.com/igawa6/Raitchi.
  An experimental runtime that runs Switch games natively with an Eden-derived
  frontend; its gradle files carry only test package ids and most listed games
  only boot. Promote when it ships a final package id and leaves the
  experimental stage.

## Declined

- **Jet Force Gemini recomp** - https://github.com/TK22-26/JetForceGemini-Recomp.
  Windows only.
- **Pokemon Emerald 3DS** - https://github.com/ZallaxDev/emerald-3ds. Nintendo
  3DS homebrew; no Android app.
- **Pokemon Odyssey** - a FireRed ROM hack distributed as a patch, not an app.
- **Repugnant Bounty** - a commercial Game Boy Color ROM; no Android app.
- **Zelda: A Link to the Past (moonpearl)** - https://github.com/DoutorRaposo/moonpearl.
  Duplicates the zelda3 port already in both packs, from a single burst of
  commits and releases.
- **Vita3K-Plus** - https://github.com/nckstwrt/Vita3K-Plus. A single-author
  fork that does not follow upstream Vita3K. Its releases now ship their own
  package id, so it could sit beside the official entry; whether it should is
  the owner's call.
- **Super Mario Strikers (Strikers-Android-Port)** - https://github.com/luisxl15/Strikers-Android-Port.
  A one-off Android build of the strikers port whose release republishes a
  committed debug-signed APK.
- **Super Mario Galaxy (Galaxy-Android) and Call of Duty: Modern Warfare 2
  (mw2-android)** - formerly https://github.com/OpenPort-Labs. Discontinued by
  their developer and the organization deleted. Galaxy-Android's early releases
  were signed with a compromised key, so reuploads are not candidates.
- **Rayman Origins and Rayman Legends recomps (edeegg)** - https://github.com/edeegg/origins-recomp
  and https://github.com/edeegg/Legends-Recomp. Reuploaded prebuilt APKs with no
  source and no license.
- **Grand Theft Auto IV (LibertyRecompAndroid)** - https://github.com/vaduur/LibertyRecompAndroid.
  Put on hiatus by its maintainer, who points users to forks.
