# Design

## Context

`compose` in `src/omnipack/merge.py` selects one candidate per family and
variant, validates overlay targets, applies overlay records per variant with
`apply_overlay`, then assigns categories and records the stale category, single
only and repeated id diagnostics on `CompositionReport`. Rendering later fills
each entry's settings defaults for its source type (`hydrate_settings` in
`src/omnipack/render.py`, from `SETTINGS_DEFAULTS`), fills a missing `author`
and, in `render_pack`, forces `allowIdChange` true. `write_report` serializes
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

**Both checks compare published forms through the render path.** One helper,
beside `render_pack` in `src/omnipack/render.py`, returns an entry's published
form: it renders the single entry with `render_pack`, takes the one app, parses
`additionalSettings` back from its JSON string and drops `categories`. Its
output therefore carries `allowIdChange` forced true, `author` filled and the
settings hydrated with the rendering defaults for the entry's source type,
exactly as published. Reusing the render path, rather than re-listing what
render fills or forces, keeps both checks consistent with the published pack
when rendering changes. Alternative considered: hydrating import data with
`hydrate_settings` alone. Rejected: it misses the fields render overwrites or
fills, so it reports `allowIdChange` or `author` differences the published
packs do not have, and it misses patches that set them.

**A no-op key is judged by its published effect, one leaf at a time.** For each
record, collect the selected entries it targets in every variant, as they
stand before overlays apply, and walk the patch's leaves (a leaf is any value
that is not an object; arrays compare whole). For each leaf and target, build
a patch holding that leaf alone at its path, merge it into the entry with
`merge_patch`, and compare the published forms of the entry with and without
it. A leaf is a no-op when every target's two published forms are equal. The
same test covers values and nulls: a value the entry already has, a default
rendering would fill, a field rendering forces, a null on an absent key and a
null on a defaulted setting the entry lacks or holds at its default all leave
the published form unchanged. A leaf whose patched entry fails to render
counts as changing it, so the check never raises and the build's own render
reports the error. A leaf is identified by its dotted path, the keys along it
joined with `.`. That path is unambiguous only because `parse_overlay` now
rejects any patch key, at any depth, that contains a `.`, failing with the
record and the key: without that rule a top-level key `guard.flag` and a
nested path `guard` -> `flag` would both serialize to `guard.flag`, share one
report entry and one alert key, and let one key's mute hide the other. The
same check, with the same error, also rejects any patch key containing a `/`,
so a dotted path never holds a `/`; the alert key needs that (see below).
Keys inside array values are part of a value and are not checked. An empty
object has no leaves, so `parse_overlay` also rejects an empty patch and any
empty object nested within the patch's objects (not inside array values),
failing with the record identified; a record
whose last live key is deleted is removed, not left empty and unreported.
Alternative
considered: an escaping scheme for literal dots and slashes. Rejected by the
owner: no current overlay key contains a `.` or a `/`, and rejecting them keeps the dotted path,
the report field and the alert key identical with no encoding to carry
through each. The check is `_redundant_overlay_keys` in
`src/omnipack/merge.py`, beside `_listed_extras` and `_differing_fields`, and
is called once in `compose` before overlays apply. It lives there rather than
in `src/omnipack/overlay.py` because it calls `published_form` from
`src/omnipack/render.py`, and render imports overlay; `overlay.py` keeps
`merge_patch` and a `patch_object` helper that merges an object patch into an
object. Its cost is two renders per leaf and target, linear in the patch size.
Alternative considered: comparing raw values at each path after hydrating the
settings. Rejected: it disagrees with the published effect for a null on a
defaulted setting, which hydration makes look present, and for fields render
forces.

**Listed extras come from the extra's own family selection.** For each
`FamilySelection` whose winner's source is extras, take the `considered`
candidates whose normalized URL equals the winner's and whose source is not
extras; each is a listing source. `considered` already holds only the family's
candidates that were eligible for the variant and not denied, so a candidate
at the same URL that a split family rule puts in another family never appears,
and neither does any selected entry of another family. Each considered
candidate is resolved back to its formed candidate by selector to get its
import data. Its differing fields come from comparing the published form of
the extra's entry after overlay with the published form of that candidate's
import data with the same record applied, over the union of top-level keys
and `additionalSettings` keys, excluding `categories` (the category map
assigns them) and `url` (equal under normalization by construction). The two
candidates' eligibilities are also compared and reported as the pseudo-field
`variants` when they differ; dual preference derives from eligibility (a build
offered only to dual is dual-preferred), so this one field covers both which
packs carry the app and whether dual prefers it. A differing `overrideSource`
is reported like any other field. When pack rendering rejects the candidate's
import data with the overlay applied but renders the extra, that candidate's
fields are the pseudo-field `unpublishable` instead of the field comparison,
and `variants` is still compared and added: "no differences" would invite
retiring an extra whose replacement cannot be published, which makes the
catalog candidate win and the build fail at rendering. When the extra itself
fails to render, the candidate records no fields, since the build fails at
rendering anyway. Records are keyed by the extra's normalized
URL and published package id and merged across variants: sources are unioned
and each source's differing fields are unioned. Two extras at one URL in
separate families are two records. Alternative considered: report only when
the outcome would be identical without the extra. Rejected by the owner:
extras almost always carry curated settings, so it would rarely fire, while
"a catalog now lists this" is the signal to review. Alternative considered:
URL-wide lookup across every formed candidate. Rejected: at a split URL it
finds catalog builds the extra was never chosen over and that ship beside it.

**The extras rule is a diagnostic on owner config, not a source rule.**
Composition never treats a source specially when selecting or excluding. This
check looks only at extras because extras, like denials and the category map,
are owner-written; it does not change which candidate wins.

**Report fields and schema.** `CompositionReport` gains
`redundant_overlay_keys` (URL and sorted dotted keys, one entry per record)
and `extras_listed_by_catalog` (one entry per selected extra: URL, published
package id, and per source the sorted differing fields), serialized as
`redundantOverlayKeys` and `extrasListedByCatalog`, the first sorted by URL
and the second by URL then package id. The build report schema version
increases, so an older report is directed to `pack build` as today. When
overlay validation fails, both stay empty, as uncategorized families do.

**Alert keys and text.** A redundant patch raises one finding per no-op key:
`build/redundant-patch/<url>/<dotted key>`, titled "Overlay patch key changes
nothing: <url> <dotted key>", with `URL:` and `Key:` details. The dot rule
alone makes the dotted key name one location within one record, but it does
not make the alert key unique: normalized URLs have variable path depth on
non-GitHub hosts and the alert subject keeps `/` unescaped, so a record at
`example.org/a` with key `b/c` and a record at `example.org/a/b` with key `c`
would both give `build/redundant-patch/example.org/a/b/c`. Because patch keys
also contain no `/`, the dotted key holds no `/`, so distinct URL and key
pairs give distinct alert subjects. The existing alert-key shortening, which
cuts a subject over the key length limit and appends a digest of the whole
encoding, keeps distinct subjects distinct, so two pairs never share an alert
key. The key is an identity, not a record: a shortened key cannot be split
back into its URL and key, so each finding's `URL:` and `Key:` details carry
both in full. Muting a key therefore covers exactly that
key; another key of the same record that goes
dead later raises its own finding. Listed extras raise one finding per
normalized URL: `build/listed-extra/<url>`, titled "A catalog lists an extra
at: <url>", with, for each extra at that URL, a `Package: <id>` detail
followed by one `<source>: <fields>` detail per source (or "no
differences"). The URL is the alert's unit because it is what the owner
reviews and the extras file and policy rules key on. Both are build warnings,
so the existing re-check scope (only after a successful build) applies
unchanged.

**Retiring a listed extra.** The documented retirement moves the extra's
movable differing fields into an overlay record for the URL and deletes the
extra, and also re-points or removes every composition candidate rule and pin
that names the extra's selector, since a rule or pin matching no candidate
fails the build: each is re-pointed to the catalog candidate's selector, which
keeps any family join the URL needs, or removed when it no longer serves a
purpose. `overrideSource` and `variants` cannot be moved into an overlay
(`overrideSource` is a protected field, and the packs a build is offered to
are its source's decision), so a difference in either means retiring the extra
accepts the catalog's value, which the docs say.

## Risks / Trade-offs

- [A guard key deliberately repeats a source value] → close that key's issue
  as not planned; the mute covers only that key, so other keys of the record
  that go dead later still alert. If the source drifts the key becomes
  effective, the warning stops and the mute clears.
- [Muting a listed-extra URL mutes every extra at it] → accepted: listed
  extras are keyed per URL, so closing the issue as not planned hides a second
  extra at that URL that a catalog starts listing later, until the URL stops
  being reported. Two extras at one URL are rare, and the issue's details name
  every extra there.
- [A muted listed extra whose differing fields shrink to none] → the finding
  persists at the same key, so it stays muted; the report still shows the
  current fields on every build.
- [First run opens one issue per dead key and per listed URL] → expected; each
  is ordinary curation triage, and the clear-cut ones are one-line removals.
- [Defaults table differs from Obtainium's actual default] → the table is
  already what rendering publishes, so the diagnostic stays consistent with
  the published pack.

## Migration Plan

Merge, then the next nightly raises the new issues; no data migration. Older
`.build/report.json` files are regenerated by `pack build`.
