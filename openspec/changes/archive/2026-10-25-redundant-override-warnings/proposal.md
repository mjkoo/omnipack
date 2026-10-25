# Proposal

## Why

Overlay patches and extras are owner-written overrides of what the catalogs
ship. When a catalog catches up, the override silently becomes dead weight:
today 5 overlay records change nothing at all (each a `name` the source now
ships), 4 more carry one key that changes nothing, and 3 extras (`999sian/tmc`,
`bvschaik/julius`, `vcmi/vcmi`) are now also listed by Quiver at the same
project URL. Nothing surfaces this, so overrides accumulate and mask later
upstream fixes. The build already reports owner config that matches nothing
(stale denials and category assignments) as alert issues; overrides that match
but change nothing are the remaining blind spot.

## What Changes

- Composition records, per overlay record, every patch key that changes no
  selected entry it targets in any variant: merging that key alone into the
  entry leaves the entry as rendering publishes it unchanged (for example a
  value the entry already has, a default rendering fills anyway, or a null
  deleting a key that is absent or that rendering refills with the same
  default).
- Composition records every selected entry chosen from extras over a
  candidate from another source in its own family at the same normalized
  project URL, one record per extra (normalized URL and published package id),
  with the catalogs listing it and the fields where the two published forms
  differ, the packs each is offered to included, with the same overlay applied,
  or `unpublishable` when only the catalog candidate's form cannot be rendered.
- Both records are non-blocking build diagnostics: they never change selection
  or output and never fail the build. `pack report` displays them.
- The nightly alert job raises one finding per no-op patch key
  (`build/redundant-patch/<url>/<dotted key>`), so muting one key never hides
  another key that goes dead later, and one finding per project URL with
  extras a catalog lists (`build/listed-extra/<url>`), naming every such extra
  at that URL. Both use the existing issue lifecycle; closing an issue as not
  planned keeps a deliberate guard key, or every extra at that URL.
- The build report schema version increases for the two new fields.
- Overlay validation rejects any patch key, at any depth, that contains a
  `.` or a `/`, failing the build with the record and the key named, so a
  dotted key names exactly one patch location and holds no `/`, and
  distinct URL and key pairs give distinct per-key alert keys, even when a
  long subject is shortened to fit the key length limit; each finding's
  details carry the full URL and key.
  No current overlay key contains a `.` or a `/`. It also rejects an empty
  patch and any empty object nested in a patch, naming the record, so a record
  with no keys is removed rather than left in place unreported.

Nothing is retired. Estimated size: 1 new requirement and 4 modified
requirements, about 18 new scenarios; about 200 implementation lines and 450 test
lines.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-composition`: adds the requirement that overrides changing nothing are
  reported, covering no-op overlay keys and extras a catalog also lists.
  The overlay requirement additionally rejects patch keys containing a `.`
  or a `/`.
- `pack-cli`: the build report display lists the two new diagnostics.
- `maintenance-alerts`: the build warnings that raise findings include no-op
  overlay keys, one finding per key, and extras a catalog lists, one finding
  per project URL.

## Impact

- `src/omnipack/merge.py` (detection inside `compose`, next to the stale
  category and repeated id records), `src/omnipack/report.py`
  (fields, validation, display, schema version).
- `src/omnipack/overlay.py`: `parse_overlay` rejects patch keys containing a
  `.` or a `/` at any depth, and empty patches or nested empty objects.
- `scripts/alerts.py` (two build-warning key kinds and their titles and
  details).
- `docs/alerts.md` (key table and a section), `docs/composition.md` (the dotted-key
  rule, the slash rule and the empty-patch rule, retiring overrides, including re-pointing the policy rules and pins that name a
  retired extra).
- Tests: composition, report and alert tests with synthetic fixtures.
- The first nightly run after merge is expected to open one issue per dead
  key and one per listed extra's URL (the counts above), which are triaged as
  ordinary curation work.
