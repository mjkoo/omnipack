# App notes

Most apps need nothing beyond installing them in Obtainium. Many game ports
need game data or setup you supply; follow each project's own instructions,
linked from its catalog row, for required files, regions, logins and supported
devices. omnipack does not restate them.

The notes below cover only behavior that comes from how omnipack configures or
combines an app, which the project's own documentation would not tell you.

## MetroidArch (Super Metroid)

Dual-screen pack only. MetroidArch is a RetroArch fork, and the pack also ships
normal RetroArch. With shared storage access both apps default to
`/storage/emulated/0/RetroArch/`, so they can share saves, states and
controller remaps. Give MetroidArch its own writable directories as described
in [MetroidArch setup](metroidarch.md#separate-the-writable-directories).

## Kanto Gear (mod updates)

Track-only: Obtainium reports Kanto Gear's releases but cannot install the Lua
mod or detect its installed version. Install or update it through
[Gen1Recomp](https://github.com/bryanthaboi/gen1recomp) using its Mod Index or
ZIP import.

## Stardew-Thor-DS and Eden Duo Companions (mod updates)

Dual-screen pack only, and track-only: both ship mod packages, not Android
apps, so Obtainium reports their releases but cannot install them or detect an
installed version. Install Stardew-Thor-DS, a SMAPI mod for Stardew Valley in
Cinderbox, as its project describes. Install an Eden Duo companion from that
game's Add-ons menu in Eden Duo. Each companion release covers one game, so a
notification may be for a game you do not play.

## Melee PC

The pack opts into prereleases, so Obtainium offers beta builds.

## PT-PC

The project publishes every Android build as a prerelease, so the pack opts
into prereleases.

## Silent Hill Decomp

Builds replace the assets of one rolling release, so the entry is tracked by
the latest asset date. An upload of only another platform's build also
registers as an update.

## LEGO Island Portable

The entry follows the single rolling `continuous` release and is tracked by its
release date, so every new build registers as an update.

## Pegasus

Pegasus has published no tagged release since 2024, so the pack opts into
prereleases and follows the rolling `continuous` build, tracked by its latest
asset date. An upload of only another platform's build also registers as an
update.

## Xash3D FWGS

The entry follows the rolling continuous master Android build. When that
build is temporarily missing, Obtainium reports an update failure rather than
selecting another channel.
