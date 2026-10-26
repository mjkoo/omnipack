# Game ports discovered through Quiver

Quiver is a discovery source. Generation admits a new port only when Quiver's
release asset names show an APK in its latest release, which does not establish
gameplay compatibility with a particular device. Notes for users, where the
pack's configuration calls for one, are in [app notes](app-notes.md).

## Existing preferences

Quiver ranks below extras and RJNY and above BBoi and codm, so its
entries win over BBoi's for the same app: CTR (single),
BattleShip, Crash Bandicoot, KartPad, Silent Hill and Dusklight (single) come
from Quiver, with display names kept by overlay. The curated Julius, VCMI,
Minish Cap and Gen1Recomp extras still win. Overlay settings patch the
selected entry whichever source wins; otherwise the winning source's settings apply whole. Dual
selection prefers dual-screen builds before precedence, so Dusklight, CTR and
Emerald keep their dual-screen sources. BBoi's KartPad, Silent Hill and
Dusklight standard entries list the same repositories as Quiver's, so they
group with Quiver's entries by project URL instead of shipping as duplicates.
Builds at different repositories can be grouped through explicit reviewed family
rules; package ids and titles alone never determine a family.

For existing fork and signer details, see [source reconciliation](source-reconciliation.md).
For discovery, screening and maintenance, see [source generation](source-generation.md).
A project denial without `packs` excludes an unwanted project across every
source and both packs.
