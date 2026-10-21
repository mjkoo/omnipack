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
  Android is described but there are no releases. Other F-Zero repositories that
  do publish APKs were rejected for thin or suspicious provenance (brand new
  accounts, one-off or download-less releases).
  Promote when a release from a project with a real history carries an Android APK.
- **RetroArch transfer** - a utility for moving RetroArch data between devices,
  not yet identified. Promote once its source link is known and it passes the
  usual checks.

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

## Declined

- **Jet Force Gemini recomp** - https://github.com/TK22-26/JetForceGemini-Recomp.
  Windows only.
- **Pokemon Emerald 3DS** - https://github.com/ZallaxDev/emerald-3ds. Nintendo
  3DS homebrew; no Android app.
- **Pokemon Odyssey** - a FireRed ROM hack distributed as a patch, not an app.
- **Repugnant Bounty** - a commercial Game Boy Color ROM; no Android app.
- **Vita3K-Plus** - https://github.com/nckstwrt/Vita3K-Plus. Declares the same
  package id as the official Vita3K entry, so both cannot be in a pack, and it
  does not follow upstream.
