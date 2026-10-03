## Why

Composition groups apps into families by Android package id. That key is the
reason the source generators download every APK and read its manifest, and it
treats forks badly: different repositories that reuse one package id are
joined whether or not they are the same app, while one app whose builds carry
different package ids needs identity corrections before it groups at all.
Keying families by the normalized project URL removes the need to know a
package id at all before merging. The cost is URL aliasing (a renamed or
mirrored repository splitting a family), which is rare and is fixed by hand
with the family rules that already exist.

## What Changes

- **BREAKING** A candidate's default family is its normalized project URL
  instead of `package:<id>`, and a shared package id no longer joins anything.
  A family rule claims every build at its URL; when rules at one URL name
  different families, each covers only the builds carrying its selector's id.
  Category map keys and pins name URL families instead of `package:` families.
- **BREAKING** Candidate rules lose `packageId`: an entry ships the id its
  source supplied, and every rendered app carries `allowIdChange: true`, so
  Obtainium adopts the APK's own id on first install instead of refusing a
  mismatched one. `packageId` is no longer a reserved source-record field.
- **BREAKING** A denylist entry is `{url, reason}` and removes every candidate
  at that normalized project URL from both packs.
- **BREAKING** An overlay record is `{url, patch}` and patches every selected
  entry at that normalized project URL.
- Offline verification and the README catalog label each rendered entry from
  the same family rules, otherwise by its normalized URL, and pair single and
  dual entries in one pass by equal label.
- A package id repeated within one pack is reported, without failing, in the
  build report, `pack report` and verification, because Obtainium stores apps
  by id and would keep only one of the two. The fix is a family rule.
- Configuration migration: the 24 `packageId` corrections are removed (18
  rules carried nothing else); rules give RJNY's melonDS stable and nightly
  builds separate families so both ship; rules join `samyost1/tmc-android` and
  `999sian/tmc` into one Minish Cap family; `package:` category keys and pins
  become URL families; the seven package denials become five URL denials;
  overlay records drop their `id`.
- Retired: transitive family formation through shared package ids, package-id
  corrections and the effective-id concept, the failure for two explicit
  families joined through a shared package id, the rule forbidding a
  candidate's id from equalling a track-only candidate's id, the `package:<id>`
  family namespace, the composition check that selected entries pair
  (unreachable once composition and offline labelling read the same rules),
  the two-pass offline pairing, the rendering, build and verification failures
  for a package id repeated within a pack, and maintained package-id mismatch
  records in curation docs.

Package ids stay ordinary entry data that selectors name and packs emit.
Source generation is unchanged; a separate later change removes its APK
inspection. Acceptance includes an import, install and re-import check on the
AYN Thor, run only with the owner's approval.

Estimate: about 16 restated or modified requirements across seven
capabilities, a net reduction of roughly 20 scenarios; implementation roughly
250 lines removed and 80 added in composition, overlay, rendering, offline
verification and reporting; roughly 500 test lines rewritten for the new keys.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-composition`: family formation by normalized URL with URL-wide family
  rules, no package-id corrections, URL denials, URL overlays, URL families in
  pins and categories, repeated package ids reported, and the track-only id
  restriction retired.
- `pack-rendering`: every app carries `allowIdChange: true`; a repeated package
  id no longer fails rendering.
- `pack-verification`: one-pass pairing by explicit projection or URL label;
  a repeated package id becomes a nonfatal finding; denials and overlays are
  checked by URL.
- `readme-catalog`: rows pair and label by explicit projection or URL.
- `pack-cli`: the build report and `pack report` record exclusions by URL,
  one package id per selection, and package ids repeated within a pack.
- `pack-curation`: pruning an unwanted app uses the URL deny list, and
  curation records no longer maintain package-id corrections.
- `source-ingestion`: `packageId` is no longer a reserved source-record field;
  references to the restated composition requirements and to project denials.
- `quiver-source-generation`: rejected candidates are recorded by project URL
  in the deny list.

## Impact

- Code: `composition_policy.py` (family formation, selectors' family names,
  category keys), `merge.py` (exclusions, selection report, repeated-id
  outcome), `overlay.py`, `offline.py` (pairing, labels, findings),
  `report.py`, `render.py` and the README catalog, `build.py` change
  comparison.
- Configuration: `config/composition.json` (new and amended rules, renamed
  category keys and pins), `config/deny.json`, `config/overlay.json`.
- Published packs: the rebuilt packs are expected to hold the same 108 single
  and 134 dual entries and the same project per family as today, measured by
  simulation over the current sources; ids change where a correction is
  removed, every entry gains `allowIdChange: true`, and README row labels
  change.
- Docs: `docs/composition.md`, `docs/curation.md`, `docs/development.md` and any
  page naming `package:` families or package denials.
