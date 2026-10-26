# Proposal

## Why

A family whose every build is a dual-screen build never reaches the
single-screen pack, because "dual-screen build" carries two meanings: a
preference (dual selects it over a baseline build) and an exclusion (single
never selects it). codm lists only dual-screen builds, so general apps it carries
(PKForge, Native Alpha, Hollow Knight: Silksong and 15 others) are missing from
single although they run on one display. The exclusion half lets an upstream
flag decide pack membership, which contradicts the pack model: aggregate every
source, resolve by precedence, and let only the owner prune.

## What Changes

- **Build kind becomes a preference only.** A build stays a baseline build or a
  dual-screen build, decided by its source as today. Single prefers baseline
  builds and falls back to a family's dual-screen build; dual prefers dual-screen
  builds and falls back to a baseline build, as today. Pins and source
  precedence are unchanged.
- **Every candidate can appear in both packs.** Per-candidate pack eligibility is
  retired. **BREAKING** for pack contents: the 33 families that are dual-only
  today become selectable in single; the migration below keeps 15 of them out.
- **Denials may name packs.** A denylist entry gains an optional `packs` field, a
  nonempty list of distinct pack names (`single`, `dual`). Absent means both
  packs, so every existing denial keeps its meaning. A pack-scoped denial removes
  the builds at its URL from the named packs only.
- **RJNY export flags set kind only.** An entry only in the dual-screen export is a
  dual-screen build; an entry in the standard export is a baseline build; an
  entry in neither export is not a candidate, like one excluded from export.
- **Retired:** pack eligibility on candidates; the pin failures for a
  target-ineligible candidate or one eligible for no variant; the denial case
  for candidates eligible for neither variant; the single-only coverage finding
  in the build (report section `singleOnlyFamilies`) and in offline
  verification. A family is now missing from dual only through the owner's
  dual-scoped denial.
- **Repeated package ids raise an alert.** The upstream pattern the coverage
  finding used to catch, a single-only build and a dual-only fork at different
  URLs sharing a package id with no family rule joining them, now puts both
  builds in both packs. The existing repeated-package-id finding records it;
  it now also raises a maintenance alert, because a repeated id in a published
  pack leaves the user with one of the two apps after import.
- **Migration:** 15 single-scoped denials for families pointless or broken on one
  display, or duplicating an app single already carries: Heimdall, Megingiard,
  Wayfinder, ZomboidDS, Minecraft Second Screen, Stardew-Thor-DS, Eden Duo
  Companions, Eden Duo, ChronoDuo, Showdown!, MetroidArch, HuntersRecomp, Pixel
  Navigator, GBA Duo and GBA DS. The other 18 dual-only families enter single.
- **Curation workflow:** arrival triage in the vet-candidates skill also decides,
  for a family with no baseline build, whether it belongs in single.

Estimated size: 1 requirement retired outright (single-only coverage); 5
replaced under new names, because OpenSpec refuses a modified requirement that
drops a scenario (pins, families, denials, RJNY export flags, the report
display); 12 modified and 1 renamed across seven capabilities. Roughly 13
scenarios added and 10 retired. About 60 implementation lines added and 140
removed; about 180 test lines added and 140 removed.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-composition`: build kind is a preference only; selection in single falls
  back to dual-screen builds; denials carry an optional pack scope; pins, family
  formation and stage order drop eligibility; the single-only coverage
  requirement is removed; the repeated-id requirement covers the cross-URL
  shared-id pattern.
- `source-ingestion`: RJNY, BBoi34, extras and codm set a build's kind only, not
  its packs; an RJNY entry in neither export is not a candidate.
- `pack-verification`: the denied-URL check applies per named pack; the
  single-only coverage finding is removed.
- `pack-cli`: the build report and `pack report` drop single-only coverage
  findings and show each exclusion's packs; the pin failure list drops
  target ineligibility.
- `readme-catalog`: a single-only row no longer refers to a coverage finding.
- `pack-curation`: a designated curated extra is defined by being a baseline
  build rather than by single eligibility.
- `maintenance-alerts`: a package id repeated within a pack raises an alert.

## Impact

- Code: `src/omnipack/model.py` (eligibility becomes a dual-screen kind),
  `src/omnipack/merge.py` (denial parsing and per-pack exclusion, selection,
  pins, removal of the single-only report), `src/omnipack/sources/` (rjny,
  bboi, extras, generated), `src/omnipack/source_registry.py`,
  `src/omnipack/offline.py`, `src/omnipack/report.py`, `scripts/alerts.py`.
- Configuration: `config/deny.json` gains 15 single-scoped denials.
- Packs: 18 apps join the single-screen pack at the next nightly; the
  dual-screen pack is unchanged, since today no family is single-only.
- Docs: `docs/composition.md`, `docs/curation.md`, `docs/alerts.md`,
  `docs/development.md`, and the vet-candidates skill.
- Build report schema: `singleOnlyFamilies` is removed and exclusion records gain
  their packs, so the report schema version advances.
