# MetroidArch setup and vetting

MetroidArch is included only in the dual-screen pack as **MetroidArch (Super
Metroid)**. It is a community RetroArch fork with its own frontend, two patched
cores, and a second-screen map/equipment/ammo interface. Normal RetroArch stays
in both packs. The two reviewed retired Super Metroid catalog IDs stay denied;
future changed catalog identities require review.

## What the pack configures

The entry uses `https://github.com/Raekwon1603/RetroArch` and the inspected package
`com.metroidarch.app.aarch64`. Stable GitHub tags are the update version, with
`versionDetection: false`, because v1.0.0 and v1.0.1 both declare APK versionName
`1.22.2_GIT`. Only versioned `MetroidArch-v<version>.apk` files qualify. A newest
stable release without a matching APK fails verification; no older fallback is
selected. The APK's filename has no ABI label, so automatic filename architecture
filtering is disabled. The bundled patched cores are ARM64 only.

Obtainium imports configure APK acquisition and tracking. They do not configure
MetroidArch's internal directories, controllers, ROM selection, or updater.
Installing it creates a new app alongside both normal RetroArch and the old
`com.raekwon.supermetroid`. Removing the old app is separate device cleanup.

## Separate the writable directories

The APK, default main `retroarch.cfg`, installed cores, and Android preferences
belong to MetroidArch's package. Its bundled-core repair writes to its own private
cores directory, not normal RetroArch's cores.

However, with shared storage permission, inherited defaults use
`/storage/emulated/0/RetroArch/` for saves, states, configuration overrides,
controller remaps, playlists and other content. Both apps can affect those files
when their directory settings and core/game filenames match. Separate packages
do not provide complete external-storage isolation. Without broad storage access,
Android may choose app-specific fallback paths instead.

In MetroidArch, use **Settings > Directory** to select separate writable
locations, then **Configuration File > Save Current Configuration**. A convenient
root for an owner-user device with shared-storage access is
`/storage/emulated/0/MetroidArch/`. Create the directories and verify they are
writable under the permissions actually granted. Keep the emulator cores in the
app-private default directory. Sharing the existing ROM directory is deliberate
and does not require sharing saves or controller remaps.

These are the corresponding `retroarch.cfg` entries for that example root:

```ini
rgui_config_directory = "/storage/emulated/0/MetroidArch/config"
input_remapping_directory = "/storage/emulated/0/MetroidArch/config/remaps"
core_options_path = "/storage/emulated/0/MetroidArch/retroarch-core-options.cfg"
savefile_directory = "/storage/emulated/0/MetroidArch/saves"
savestate_directory = "/storage/emulated/0/MetroidArch/states"
system_directory = "/storage/emulated/0/MetroidArch/system"
screenshot_directory = "/storage/emulated/0/MetroidArch/screenshots"
core_assets_directory = "/storage/emulated/0/MetroidArch/downloads"
log_dir = "/storage/emulated/0/MetroidArch/logs"
runtime_log_directory = "/storage/emulated/0/MetroidArch/logs/runtime"
playlist_directory = "/storage/emulated/0/MetroidArch/playlists"
thumbnails_directory = "/storage/emulated/0/MetroidArch/thumbnails"
cheat_database_path = "/storage/emulated/0/MetroidArch/cheats"
cache_directory = "/storage/emulated/0/MetroidArch/temp"
```

`core_options_path` names a file; the other entries above name directories.
Replace existing assignments rather than appending duplicate keys. Inspect any
existing core/game overrides as well. Do not copy normal RetroArch's entire
configuration into MetroidArch: it can carry shared paths and incompatible core
settings. Adjust other writable paths if the existing configuration customized
them away from their package-specific defaults.

## ADB method

Prefer the app's Directory settings when practical; saving there writes as the
app. ADB can edit the same configuration when access and file metadata have been
verified on the actual device. These instructions are source-backed, not an
on-device validation record. Confirm the device and Android user first. The
example paths assume owner user 0; with multiple devices, add `-s <serial>` to
every `adb` command.

1. Open MetroidArch once without loading a game, save its current configuration,
   and note the path shown by the app. Quit normally to flush it. Keep local
   pre-test copies of normal RetroArch's relevant config, remaps and overrides
   for the later no-change comparison.
2. Stop MetroidArch before editing, then resolve the installed app's current UID:

   ```sh
   adb shell am force-stop com.metroidarch.app.aarch64
   adb shell pm list packages -U com.metroidarch.app.aarch64
   adb shell dumpsys package com.metroidarch.app.aarch64
   ```

   Match the exact package and confirmed Android user. Repeat this discovery
   after a reinstall; a previously recorded UID may belong to a different app.
3. Locate the actual loaded config. The preferred default is
   `/storage/emulated/0/Android/data/com.metroidarch.app.aarch64/files/retroarch.cfg`;
   the fallback is `files/retroarch.cfg` in the private application directory.
   A launcher can supply a different `CONFIGFILE`, so verify the loaded path.
   Record the file's numeric owner UID, group GID, permission mode and SELinux
   context, plus those of its containing directory and an app-created sibling.
   For an accessible external config, inspect the directory and its entries:

   ```sh
   adb shell ls -ldnZ /storage/emulated/0/Android/data/com.metroidarch.app.aarch64/files
   adb shell ls -lnZ /storage/emulated/0/Android/data/com.metroidarch.app.aarch64/files
   ```

   Retain this metadata locally with the backup. Check it against the current
   app UID and the app-created sibling rather than preserving an already broken
   shell-owned file. An app-private file and an external app-data file can have
   different groups, modes and labels. Prior external app-data repairs on an
   AYN Thor used the app UID, group `ext_data_rw` (1078), and mode `660`; those
   historical values are not defaults for this app or another device. Confirm
   the actual expected metadata before any write.
4. If the actual external file is accessible, back it up locally:

   ```sh
   adb pull /storage/emulated/0/Android/data/com.metroidarch.app.aarch64/files/retroarch.cfg metroidarch.before.cfg
   ```

   Check successful exit and valid backup contents. Keep the backup unchanged
   and edit a separate `metroidarch.after.cfg`, replacing only intended settings
   and ensuring each key occurs once. Create the selected directories with
   access the app can use. Choose an app-owned or appropriately privileged write
   route that preserves the verified UID, GID, mode and SELinux context. A blind
   `adb push` to a temporary file followed by rename can replace the app's file
   with a shell-owned file; a successful transfer or byte comparison does not
   establish that the app can save. If no metadata-preserving route is available,
   use the app's Directory settings and Save Current Configuration instead.
5. If the **actual loaded file is private**, the inspected debuggable release
   supports `run-as` on compatible devices. Check access before relying on it:

   ```sh
   adb shell run-as com.metroidarch.app.aarch64 pwd
   adb shell run-as com.metroidarch.app.aarch64 ls -ldnZ files
   adb shell run-as com.metroidarch.app.aarch64 ls -lnZ files
   adb exec-out run-as com.metroidarch.app.aarch64 cat files/retroarch.cfg > metroidarch.before.cfg
   ```

   Check the backup and record file, sibling and parent metadata as above. Use
   an app-user write route that preserves the existing file's verified metadata.
   Writing a new temporary file as the app user alone does not guarantee the
   original group, mode or SELinux context survives replacement. Inspect all
   four fields after any write or rename. Creating a private config will not
   supersede an existing preferred external config. Some devices disable
   `run-as`, and future non-debuggable releases reject it; use the app menu when
   this access is unavailable. Broad storage permission is not root access.
6. Check every write's exit status, read the result back through the same access
   route, and compare it with the edited local copy before relaunch. Verify the
   resulting UID, GID, mode and SELinux context against the recorded expected
   values, including the sibling and parent comparison. If metadata changed,
   restore the verified ownership, permissions and context through an available
   app-appropriate privileged route and check again. Keep any repair scoped to
   the intended file; do not use broadly writable permissions or recursive
   ownership changes. Stop on failure instead of deleting the original or
   treating correct contents as sufficient. If the route cannot preserve or
   restore metadata, use app-menu configuration.
7. Relaunch MetroidArch, inspect Directory settings, and save a deliberate
   configuration change through the app. Quit normally, stop it again, and read
   back the actual config and metadata. Verify that the app persisted that
   change; relaunch once more to confirm it is loaded. During game testing,
   confirm actual save/state/remap/override destinations below the chosen
   MetroidArch root. Compare normal RetroArch's relevant files with their
   pre-test copies. Test save/relaunch and both screens before treating isolation
   as validated.

On an AYN Thor, failure of `su` or `run-as` does not establish that the
manufacturer's privileged root-script facility is unavailable. Its menu executes
each submitted line separately; any separately prepared, narrowly scoped repair
needs a one-line launcher invoking `/system/bin/sh` on the script. That service
may reach `/data/media/0` backing files when ordinary ADB cannot. Confirm the
active file, current UID and expected metadata before considering that route;
this guide supplies no device repair script. Remove temporary device scripts and
logs after a repair has been verified.

Rollback uses the unchanged backup while the app is stopped, with the same
content, ownership, group, mode, SELinux and post-relaunch saving checks. These
steps edit paths; they do not migrate saves or tune controller mappings. No
installation, configuration write, metadata repair or gameplay check is claimed
as performed by this guide.

## First-run content and updater

Start acceptance with a supplied, uncompressed vanilla Super Metroid ROM and the
bundled Snes9x core. That gives the second-screen interface without widescreen
patches. Test Android file-picker and SD-card loading, live map/items/ammo,
save/relaunch, and a second Obtainium update check. Test bsnes-hd widescreen and
Redux separately; open reports describe black screens and crashes with bsnes
while Snes9x works. Redux touch-ammo support is incomplete.

The upstream README requires Update Assets and Update Core Info Files, followed
by an app restart. The inspected APK inherits HTTP defaults for the internal
updater. Before those downloads, configure and verify the HTTPS equivalents:

```ini
core_updater_buildbot_assets_url = "https://buildbot.libretro.com/assets/"
core_updater_buildbot_cores_url = "https://buildbot.libretro.com/nightly/android/latest/arm64-v8a/"
```

Verify HTTPS operation on-device; the package entry does not set these values.
Keep the bundled patched cores. The stock core updater can overwrite them in
MetroidArch's directory; the fork repairs its bundled copies on the next launch.
This does not replace normal RetroArch's private cores.

## Vetting record

Observed September 10, 2026. Latest stable release was
[v1.0.1](https://github.com/Raekwon1603/RetroArch/releases/tag/v1.0.1), published
September 2. The downloaded `MetroidArch-v1.0.1.apk` SHA-256 was
`2c88bd1ee67a43759ebcafad7f538ceca85bed8e50fa825090e52a80314621da`, matching GitHub
asset metadata. Android package was `com.metroidarch.app.aarch64`, versionCode
`1788358393`, versionName `1.22.2_GIT`, minimum SDK 21, target SDK 36.

Both v1.0.0 and v1.0.1 signatures validated for Android 13/API 33 and used the
same certificate as the captured old Super Metroid app:
`3ee9faa59ed23aac0a7290f6c2a25d0e0dd1e4e7d12b217d4154e114b24e570d` (SHA-256).
Both patched cores exactly matched binaries committed at the release tag.
The app is debuggable and uses an Android Debug certificate. It requests broad
storage access, Internet and vibration, with legacy storage permissions. The
source manifest is unchanged from the RetroArch base.

The old project links to its successor, and the
[community announcement](https://www.reddit.com/r/AynThor/comments/1w4gdlg/metroidarch_super_metroid_dual_screen/)
contains concrete successful-user reports, troubleshooting and the v1.0.1 fix.
The reviewed fork changes match the advertised functionality. No added unrelated
network destinations or telemetry were found in those reviewed changes. This is
reputation and basic source/APK vetting, not a complete code audit, malware scan,
reproducible-build proof, or completed gameplay test. The small project's short
history and [open bsnes reports](https://github.com/Raekwon1603/RetroArch/issues)
remain relevant limitations.

Source references:

- [Release directory defaults](https://github.com/Raekwon1603/RetroArch/blob/v1.0.1/frontend/drivers/platform_unix.c)
- [Configuration keys](https://github.com/Raekwon1603/RetroArch/blob/v1.0.1/configuration.c)
- [Private core installation](https://github.com/Raekwon1603/RetroArch/blob/v1.0.1/pkg/android/phoenix-common/src/com/retroarch/browser/retroactivity/RetroActivityCommon.java)
- [Setup and limitations](https://github.com/Raekwon1603/RetroArch/tree/metroidarch-dual-screen)
- [Android ADB commands](https://developer.android.com/tools/adb)
- [Android run-as implementation](https://android.googlesource.com/platform/system/core/+/refs/heads/main/run-as/run-as.cpp)
