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

ADB can transfer and edit the same configuration file without root when the
selected file is accessible. These instructions are source-backed, not an
on-device validation record. They assume one connected owner-user device; with
multiple devices, add `-s <serial>` to each `adb` command.

1. Install and open MetroidArch once, without loading a game. Save its current
   configuration and note the path shown by the app. Quit normally to flush it.
2. Stop the app before editing so its running settings cannot overwrite the file:

   ```sh
   adb shell am force-stop com.metroidarch.app.aarch64
   ```

3. Locate the actual file. The preferred default is
   `/storage/emulated/0/Android/data/com.metroidarch.app.aarch64/files/retroarch.cfg`;
   the fallback is `files/retroarch.cfg` inside the private application directory.
   A launcher can supply a different `CONFIGFILE`, so verify the loaded path.
   If the external file is accessible, back it up locally:

   ```sh
   adb pull /storage/emulated/0/Android/data/com.metroidarch.app.aarch64/files/retroarch.cfg metroidarch.before.cfg
   ```

   Keep that backup unchanged. Make an edited copy named `metroidarch.after.cfg`,
   changing only the intended settings and ensuring each key occurs once.
   Create the selected directories on the device before relaunching.
4. For the verified external path, stage the edited file, then replace the config:

   ```sh
   adb push metroidarch.after.cfg /storage/emulated/0/Android/data/com.metroidarch.app.aarch64/files/retroarch.cfg.new
   adb shell mv /storage/emulated/0/Android/data/com.metroidarch.app.aarch64/files/retroarch.cfg.new /storage/emulated/0/Android/data/com.metroidarch.app.aarch64/files/retroarch.cfg
   ```

   Stop if transfer fails; do not delete the original as a workaround. Pull the
   result back and compare it with the edited copy before launching the app.
5. If the **actual loaded file is private**, this debuggable release supports
   Android's `run-as` mechanism on compatible devices. Check access first:

   ```sh
   adb shell run-as com.metroidarch.app.aarch64 pwd
   adb exec-out run-as com.metroidarch.app.aarch64 cat files/retroarch.cfg > metroidarch.before.cfg
   ```

   After editing a separate local copy, write as the app user, preserving ownership:

   ```sh
   adb shell 'run-as com.metroidarch.app.aarch64 sh -c "cat > files/retroarch.cfg.new"' < metroidarch.after.cfg
   adb shell run-as com.metroidarch.app.aarch64 mv files/retroarch.cfg.new files/retroarch.cfg
   ```

   Use this route instead of the external-path write only when the private file
   is the active configuration. Creating a private file will not override an
   existing preferred external config. Check every command's exit status and
   round-trip the resulting file before launch. `run-as` can be disabled by a
   device, and a future non-debuggable release will reject it. In that case use
   the app's Directory settings; broad storage permission is not root access.
6. Relaunch MetroidArch, inspect its Directory settings, and confirm that saves,
   remaps and overrides are written below the chosen MetroidArch root. Quit and
   re-read the config to check persistence. Compare normal RetroArch's relevant
   configuration/remap files against their pre-test copies. Test save/relaunch
   and both screens before treating isolation as validated.

Use the same stopped-app procedure to restore the backup if needed. These steps
edit paths; they do not migrate existing saves or tune controller mappings.

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
