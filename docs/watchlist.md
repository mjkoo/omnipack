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

- **Super Mario Galaxy (Galaxy-Android)** - https://github.com/OpenPort-Labs/Galaxy-Android.
  APK releases exist, but every one is a tester build with inconsistent asset
  names, from a new organization with one heavily AI-assisted committer, and the
  app requests all-files storage access.
  Promote when releases move past tester builds with consistent asset names and
  the project has a sustained history.
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
  `config/deny.json`: a new single-author project shipping one large APK that
  bundles other projects' Wii and GameCube ports, with all-files storage
  access. Reconsider, by removing the denial, once it has a sustained release
  history and clear provenance for the bundled ports.
- **GBA DS** - https://github.com/kyannon/gba-ds.
  A GPL libmgba emulator for dual-screen devices that shows the game's map, with
  one APK per release beside a Linux build. The history is short and almost
  entirely AI-written, and the app requests all-files storage and handles
  RetroAchievements credentials. Promote, dual-screen only, once it has a
  sustained history and outside use.
- **MOTHER 3 (Mother3Recomp)** - https://github.com/josiahg2502-glitch/Mother3Recomp.
  A gbarecomp-based recomp with APK releases from a brand-new account, with
  drifting asset names and a package id set by the external engine's build
  rather than the repository. Promote when the account has a sustained history,
  asset names are stable and the shipped package id is confirmed.
- **Resident Evil 4 Prototype (CubeEvil4)** - https://github.com/Andiweli/CubeEvil4-Android.
  A native port of the RE4 GameCube debug-build decompilation by the author of
  the pack's OpenMW build, with one APK per release and minimal permissions.
  Its package id has changed between flavors and releases, and which flavor
  ships is unconfirmed. Promote when the package id holds across several
  releases; the legal exposure of the reconstructed Capcom code is the owner's
  call.
- **Super Mario Sunshine (Mareshine)** - https://github.com/TheM3dium/mareshine.
  A fork of jbcgames/sms-android on the Sunshine decompilation, from a brand-new
  single-repository account with a burst of commits and releases. It requests
  all-files storage, and its install permission serves a self-updater that
  verifies its own signature. Upstream states no license.
  Promote when it has a sustained history and outside use and the upstream
  license is settled.
- **Grand Theft Auto IV (LibertyRecompAndroid)** - https://github.com/vaduur/LibertyRecompAndroid.
  An Android fork of the established LibertyRecomp Xbox 360 recomp with high
  reach, but the Android work comes from a single-repository account that calls
  it AI-generated and disclaims it, uses prereleases heavily, and requests
  all-files storage. Promote when the maintainer shows a sustained, owned release
  history; trademark and takedown exposure is the owner's call.
- **Call of Duty: Modern Warfare 2 (mw2-android)** - https://github.com/OpenPort-Labs/mw2-android.
  A GPL fork of mw2-recompiled from the Galaxy-Android organization, with
  inconsistent asset names and multiple flavors, and a self-updater that installs
  APKs from a different repository without its own signature check, alongside
  all-files storage. Promote when one repository publishes the releases with
  consistent asset names, the updater follows it, and the history is sustained.
- **Donkey Kong 64 (DK64 Recompiled)** - https://github.com/deivid22srk/dk64-recomp-android.
  An Android port of the DK64 N64 recomp with one APK per release, from an author
  of many quick ports, with a short burst of largely automated commits and
  little outside use; development went quiet after its first releases.
  Promote when new APK releases show sustained maintenance and the project gains
  outside use.

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
- **Vita3K-Plus** - https://github.com/nckstwrt/Vita3K-Plus. Declares the same
  package id as the official Vita3K entry, so both cannot be in a pack, and it
  does not follow upstream.
