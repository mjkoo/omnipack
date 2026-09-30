# Game ports discovered through Quiver

Quiver is a discovery source. Obtainium installs and updates the selected APK;
most ports still need game data that you supply. Importing a pack does not import
that data. Follow the linked project's instructions for supported regions,
revisions, extraction and save locations.

The catalog includes experimental community ports. Basic manifest and signature
checks do not establish gameplay compatibility with a particular device. The
initial review used downloaded APKs and public project records, with no device
access. Back up saves before changing between forks or uninstalling an app.

## Setup for newly discovered ports

| Port | Required data | Android setup and update notes |
| --- | --- | --- |
| [AeroGauge Recompiled](https://github.com/alondero/aerogauge-recomp) | Supported USA AeroGauge `.z64` ROM | Experimental Android release; touch controls and graphics have limited testing. |
| [Automobili Lamborghini Recompiled](https://github.com/alondero/automobililamborghini-recomp) | Supported USA N64 ROM | Experimental Android port. Uninstalling or clearing private app data can erase saves. |
| [Star Fox Enhanced](https://github.com/kandowontu/starfox-enhanced) | Supported Star Fox/Starwing ROM or generated `Starfox-Assets.BIN` | Android arm64 build; optional MSU content is separate. |
| [Melee PC](https://github.com/999sian/melee-pc) | USA 1.02 GALE01 game image | The source explicitly opts into beta releases. Requires arm64 and Vulkan 1.1. The app also has its own update checker. |
| [Open Nectar](https://github.com/SSunnKing/Open-Nectar---Pikmin-Native-PC-Mobile-Port) | Supported Pikmin USA Rev 1 or Europe ISO/GCM | Android needs an unpacked image rather than RVZ/WIA/GCZ. Requires Android 10+, arm64 and GLES 3.0; allow space for imported data. |
| [Resident Evil Gaiden Recompiled](https://github.com/sergiomanzur/regaiden-recomp) | Exact supported USA `.gbc` ROM | Use the first-run picker. The project's README supplies the required ROM hash. |
| [KartPad](https://github.com/chrissotraidis/kartpad) | Mario Kart Wii PAL RMCP01 rev 0 ISO/WBFS | Requires Android 9+, arm64 and Vulkan. Optional Retro Rewind content is downloaded separately. Online features and background content downloads use network services. |
| [Silent Hill native port](https://github.com/SlickAmogus/silent-hill-decomp) | Supported PSX BIN disc image | The reviewed filter omits release assets explicitly marked `_OLD`. The project's nightly/launcher update channel is separate from this repository's release APKs. |
| [Eternal Sonata Reprise](https://github.com/birabittoh/EternalSonataReprise) | Supported dumped Xbox 360 game files | Experimental Android build. Follow the project's extraction and region instructions; its in-app updater is a second update channel. |
| [Sonic 3 A.I.R.](https://github.com/Eukaryot/sonic3air) | Compatible Sonic 3 & Knuckles ROM | Transfer the ROM to Android and follow the project's import instructions. Generation retains an accepted entry if a later selected release temporarily has no Android APK. |
| [Augustus](https://github.com/Keriew/augustus) | Original Caesar III files | Extended gameplay fork of Julius, with its own package. Follow `doc/RUNNING.md` for Android touch controls and data import. |
| [OpenRCT2](https://github.com/OpenRCT2/OpenRCT2/wiki/Android) | RollerCoaster Tycoon 2 `Data` and `ObjData` | Follow the Android setup guide. The interface is not optimized for phones; current releases include the engine's own data. |
| [doukutsu-rs](https://github.com/doukutsu-rs/doukutsu-rs) | Supported Cave Story freeware or Cave Story+ data | The engine does not include game data. Copy the supported files using the project's Android instructions. |
| [Yakumo](https://github.com/TeamGDB/Yakumo) | Supported Monster Hunter Portable 3rd HD NPJB-40001 image | Alpha Android arm64 build using Vulkan 1.1. Allow space for data import; physical-device coverage is limited. |
| [EmeraldRecomp](https://github.com/mstan/EmeraldRecomp) | Supported USA Pokemon Emerald ROM and GBA BIOS | Early Android port. The dual-screen pack keeps the existing preferred Emerald dual-screen build. |
| [LEGO Island Portable](https://github.com/isledecomp/isle-portable) | LEGO Island 1.1 English data | Upstream continuous builds are developer-oriented. The reviewed filter selects `app-release.apk`, since the debug APK uses a different signing key. Its single rolling `continuous` tag is tracked by release date (`releaseDateAsVersion`), so each new build still registers as an update. This source stands in until the owner's fork is adopted; see [project context](project-context.md). |

## Existing preferences

Quiver ranks below extras and RJNY and above BBoi and codm, so its
manifest-verified entries win over BBoi's for the same app: CTR (single),
BattleShip, Crash Bandicoot, KartPad, Silent Hill and Dusklight (single) come
from Quiver, with display names kept by overlay. The curated Julius, VCMI,
Minish Cap and Gen1Recomp extras still win. Quiver exception filters
apply to Quiver candidates; the winning source's settings apply whole. Dual
selection prefers dual-screen builds before precedence, so Dusklight, CTR and
Emerald keep their dual-screen sources.
Different package IDs can be grouped through explicit reviewed family rules;
titles alone never determine a family.

For existing fork and signer details, see [source reconciliation](source-reconciliation.md).
For discovery settings and maintenance, see [source generation](source-generation.md).
A discovery skip pauses Quiver inspection and retains a matching accepted entry;
a package denial excludes an unwanted package across every source and both packs.
