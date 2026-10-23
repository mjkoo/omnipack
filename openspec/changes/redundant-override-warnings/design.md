# Design

## Context

`compose` in `src/omnipack/merge.py` selects one candidate per family and
variant, validates overlay targets, applies overlay records per variant with
`apply_overlay`, then assigns categories and records the stale category, single
only and repeated id diagnostics on `CompositionReport`. Rendering later fills
each entry's settings defaults for its source type (`hydrate_settings` in
`src/omnipack/render.py`, from `SETTINGS_DEFAULTS`). `write_report` serializes
`CompositionReport` into `.build/report.json` under a schema version, `pack
report` displays it, and `scripts/alerts.py` maps the build warnings in that
report (uncategorized, stale denial, stale category) to findings under the
`build/` key prefix, re-checked only when the build succeeded.

A throwaway check against the live inputs found 5 overlay records whose every
key changes nothing, 4 with one such key, and 3 extras also listed by Quiver.

## Goals / Non-Goals

**Goals:**

- Detect both diagnostics from data composition already holds, without a
  second build or network access.
- Reuse the existing build-warning finding path, lifecycle and mute.

**Non-Goals:**

- Removing or rewriting any override automatically; the owner retires them.
- Flagging catalog candidates that duplicate each other; catalogs are not owner
  config.
- Comparing extras against candidates at other project URLs in the same
  family; replacing another project's build is what such an extra is for.

## Decisions

**No-op keys are computed per record before it applies, against hydrated
entries.** For each record, collect the selected entries it targets in every
variant, hydrate each entry's settings with the rendering defaults for its
source type, and walk the patch's leaves (a leaf is any value that is not an
object; arrays compare whole). A leaf is a no-op when every target holds an
equal value at its path, or, for null, holds nothing there. Hydrating first
means a patch that spells out a default the entry would publish anyway is
reported; comparing raw data would miss it. The check is a pure function over
the selected entries and the parsed records, placed beside `apply_overlay` in
`src/omnipack/overlay.py`, and called once in `compose` before overlays apply.
Alternative considered: render each variant with and without each key and
compare output. Exact, but quadratic in keys and far heavier for the same
answer.

**Listed extras come from the selection and the formed candidates.** For each
selected entry whose winner's source is extras, look up the formed candidates
(eligible for that variant, not denied) at the same normalized URL from other
sources. Each becomes a listing source. Its differing fields come from
comparing the extra's entry after overlay with that candidate's import data
with the same record applied, both hydrated, over the union of top-level keys
(excluding `categories`) and `additionalSettings` keys. Records are merged
per URL across variants: sources are unioned and each source's differing
fields are unioned. Alternative considered: report only when the outcome
would be identical without the extra. Rejected by the owner: extras almost
always carry curated settings, so it would rarely fire, while "a catalog now
lists this" is the signal to review.

**The extras rule is a diagnostic on owner config, not a source rule.**
Composition never treats a source specially when selecting or excluding. This
check looks only at extras because extras, like denials and the category map,
are owner-written; it does not change which candidate wins.

**Report fields and schema.** `CompositionReport` gains
`redundant_overlay_keys` (URL and sorted dotted keys) and
`extras_listed_by_catalog` (URL, package id, and per source the sorted
differing fields), serialized as `redundantOverlayKeys` and
`extrasListedByCatalog`, both sorted by URL. The build report schema version
increases, so an older report is directed to `pack build` as today. When
overlay validation fails, both stay empty, as uncategorized families do.

**Alert keys and text.** `build/redundant-patch/<url>` titled "Overlay patch
has keys that change nothing: <url>" with one `Key:` detail per key, and
`build/listed-extra/<url>` titled "A catalog lists this extra: <url>" with
`Package: <id>` and one `<source>: <fields>` detail per source (or "no
differences"). Both are build warnings, so the existing re-check scope (only
after a successful build) applies unchanged.

## Risks / Trade-offs

- [A guard key deliberately repeats a source value] → close its issue as not
  planned; if the source drifts the key becomes effective, the warning stops
  and the mute clears.
- [First run opens about 12 issues] → expected; each is ordinary curation
  triage, and the clear-cut ones are one-line removals.
- [Defaults table differs from Obtainium's actual default] → the table is
  already what rendering publishes, so the diagnostic stays consistent with
  the published pack.

## Migration Plan

Merge, then the next nightly raises the new issues; no data migration. Older
`.build/report.json` files are regenerated by `pack build`.
