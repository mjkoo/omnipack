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
  selected entry it targets in any variant (a key setting the value the entry
  already has, or a null deleting a key already absent).
- Composition records every selected entry chosen from extras when a catalog
  also lists a candidate, not denied, at the same normalized project URL,
  with the catalogs listing it and the fields where the extra's output differs
  from that catalog candidate with the same overlay applied.
- Both records are non-blocking build diagnostics: they never change selection
  or output and never fail the build. `pack report` displays them.
- The nightly alert job raises one finding per overlay URL with no-op keys
  (`build/redundant-patch/<url>`) and one per extra a catalog lists
  (`build/listed-extra/<url>`), with the existing issue lifecycle; closing an
  issue as not planned keeps a deliberate guard key or extra.
- The build report schema version increases for the two new fields.

Nothing is retired. Estimated size: 1 new requirement and 3 modified
requirements, about 10 new scenarios; about 150 implementation lines and 300 test
lines.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-composition`: adds the requirement that overrides changing nothing are
  reported, covering no-op overlay keys and extras a catalog also lists.
- `pack-cli`: the build report display lists the two new diagnostics.
- `maintenance-alerts`: the build warnings that raise findings include no-op
  overlay keys and extras a catalog lists, one finding per URL each.

## Impact

- `src/omnipack/merge.py` (detection inside `compose`, next to the stale
  category and repeated id records), `src/omnipack/report.py` and
  `src/omnipack/report_model.py` (fields, validation, display, schema version).
- `scripts/alerts.py` (two build-warning key kinds and their titles and
  details).
- `docs/alerts.md` (key table and a section), `docs/composition.md` (retiring
  overrides).
- Tests: composition, report and alert tests with synthetic fixtures.
- First nightly run after merge is expected to open about 12 issues (the
  counts above), which are triaged as ordinary curation work.
