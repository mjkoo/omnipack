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
  Track-only candidates are ordinary candidates at their URL: rules may assign
  them a family, and split rules separate a tracker from an app sharing its
  URL.
  Category map keys and pins name URL families instead of `package:` families.
- **BREAKING** Candidate rules lose `packageId`: package-id corrections are no
  longer a composition identity input or a rule field but owner render-time
  patches keyed by URL. An overlay record may now patch `id`, so the owner
  fixes a wrong source id by hand, exactly as a name or an APK filter is fixed,
  when Obtainium shows a duplicate or an id error; no tooling reads APKs. The
  patch changes only the rendered entry; families, dedupe, denials, pins and
  overlay matching never read it. A wrong id matters because Obtainium saves
  every imported record under its `id`, never matching by URL, and re-saves an
  installed app under its APK's id, so an entry whose shipped id differs from
  its APK's gains a never-installed duplicate on every pack import after
  install. Every published pack app carries `allowIdChange: true`, so an entry
  not yet fixed still installs and adopts the APK's own id. Pack entries
  thereby give up Obtainium's id-change protection: each import or re-import
  sets the flag back to `true`, so a later upstream id change is adopted rather
  than reported. The canonical catalog rendering that source generation uses
  does not add the flag. `packageId` is no longer a reserved source-record
  field.
- **BREAKING** A denylist entry is `{url, reason}` and removes every candidate
  at that normalized project URL from both packs.
- **BREAKING** An overlay record is `{url, patch}` and patches every selected
  entry at that normalized project URL; `id` is no longer a protected patch
  field. An `id` patch is accepted only at a URL whose candidates form one
  family; one at a URL whose family rules name different families fails when
  the overlay and composition policy load.
- Offline verification and the README catalog label each rendered entry from
  the same family rules, otherwise by its normalized URL, and pair single and
  dual entries in one pass by equal label.
- A package id repeated within one pack is reported, without failing, in the
  build report, `pack report` and verification, because Obtainium stores apps
  by id and would keep only one of the two. The fix is a family rule.
- A family selected in single without a dual build is published in single and
  reported as a nonfatal single-only coverage finding in the build report,
  `pack report` and verification, instead of failing the build. The fix is a
  family rule joining its URL with the dual build's.
- Different candidates of one family tied at the winning rank, such as two
  builds one source lists at one repository URL, no longer fail the build:
  composition publishes the candidate whose canonical serialized form sorts
  first, so input order never decides, and records a same-rank tie finding
  (family, variant, tied selectors, chosen winner) in the build report and
  `pack report`. The fix is a pin or split family rules. Pin conflicts stay
  fatal.
- Rendering orders entries sharing primary category, name and package id by
  normalized project URL, then by their serialized form, keeping output
  deterministic now that one id may appear at two URLs.
- Configuration migration: the 24 `packageId` corrections leave composition
  rules (18 rules carried nothing else) and move into `config/overlay.json` as
  `patch.id` records on their URLs, merged into an existing record where the
  URL already has one, so the corrected apps keep today's ids; rules give RJNY's melonDS stable and nightly
  builds separate families so both ship; rules join RJNY's `SSimco/Cemu`
  (single-only) and `sapphirerhodonite/cemu` (dual-only) into one `app:cemu`
  family so dual keeps its replacement build; rules join `samyost1/tmc-android`
  and `999sian/tmc` into one Minish Cap family; `package:` category keys and pins
  become URL families; the seven package denials become five URL denials;
  overlay records drop their `id` selector field.
- Retired: the build failure for different candidates tied at the winning
  rank, transitive family formation through shared package ids, package-id
  correction rules in composition and the effective-id concept, the failure for two explicit
  families joined through a shared package id, the rule forbidding a
  candidate's id from equalling a track-only candidate's id, the rule
  forbidding a family assignment on a track-only candidate, the build failure
  for a single-screen family without a dual build, the `package:<id>`
  family namespace, the composition check that selected entries pair
  (unreachable once composition and offline labelling read the same rules),
  the two-pass offline pairing, the rendering, build and verification failures
  for a package id repeated within a pack, and maintained package-id mismatch
  records in curation docs.

Package ids stay ordinary entry data that selectors name and packs emit.
Source generation and its generated catalogs are unchanged; a separate later
change removes its APK inspection.

Estimate: about 17 restated or modified requirements across nine
capabilities, a net reduction of roughly 20 scenarios; implementation roughly
250 lines removed and 80 added in composition, overlay, rendering, offline
verification and reporting; roughly 500 test lines rewritten for the new keys.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-composition`: family formation by normalized URL with URL-wide family
  rules, no package-id corrections in rules, URL denials, URL overlays that may
  patch `id` after composition, URL families in
  pins and categories, repeated package ids, single-only families and
  same-rank ties reported without failing, and the track-only restrictions
  retired.
- `pack-rendering`: every published pack app carries `allowIdChange: true`,
  while the canonical catalog rendering does not; a repeated package
  id no longer fails rendering; entry order breaks ties by normalized URL.
- `pack-verification`: one-pass pairing by explicit projection or URL label,
  reading rendered ids including overlay `id` patches;
  a repeated package id and a single entry without a dual pair become
  nonfatal findings; track-only entries are labelled like any other; denials
  and overlays are checked by URL; `allowIdChange: true` is required; offline
  findings are errors or nonfatal findings, and only errors fail `pack verify`,
  the build's offline gate and README regeneration; the verification report
  records nonfatal findings in their own list and its schema advances, so
  earlier reports require regeneration; a later change to what verification
  checks advances the verifier identity, so earlier evidence of the same
  schema over unchanged inputs shows stale.
- `readme-catalog`: rows pair and label by explicit projection or URL,
  track-only entries included.
- `pack-cli`: the build report and `pack report` record exclusions by URL,
  one package id per selection, package ids repeated within a pack,
  single-only coverage findings and same-rank tie findings; the candidate
  comparison shows each added and removed entry's package id and project URL;
  `pack report` displays nonfatal verification findings.
- `pack-curation`: pruning an unwanted app uses the URL deny list, and
  curation records no longer maintain package-id mismatch records; a wrong id
  is fixed by an overlay `id` patch.
- `source-ingestion`: `packageId` is no longer a reserved source-record field;
  a cross-URL replacement through a shared id needs a family rule; a tracking
  resource keeps the app it extends when they belong to different families
  once family rules apply, whatever their URLs;
  references to the restated composition requirements and to project denials.
- `quiver-source-generation`: rejected candidates are recorded by project URL
  in the deny list.
- `readme-source-generation`: a track-only resource keeps the entry of the app
  it extends exactly when they belong to different families once family rules
  apply, whether their URLs are equal or not; in one family they compete under
  composition's ordinary selection, whatever their URLs.

## Impact

- Code: `composition_policy.py` (family formation, selectors' family names,
  category keys), `merge.py` (exclusions, selection report, repeated-id
  outcome), `overlay.py` (`id` patchable), `offline.py` (pairing, labels,
  findings, pins against patched ids), `report.py`, `render.py` (the flag only
  for the published packs) and the README catalog, `build.py` change
  comparison, and `source_catalog.py`, whose `render_catalog` and
  `rendered_entry` render the committed codm2000 and Quiver catalogs through
  the same `render()` and must replace their use of the retired id-based
  `default_family` helper with something that does not depend on the retired
  `package:` namespace.
- Configuration: `config/composition.json` (new and amended rules, renamed
  category keys and pins), `config/deny.json`, `config/overlay.json` (URL
  records and the moved `patch.id` corrections).
- Published packs: the rebuilt packs are expected to hold the same 108 single
  and 134 dual entries and the same project per family as today, measured by
  simulation over the current sources; ids are unchanged from today's for the
  corrected apps, every entry gains `allowIdChange: true`, and README row
  labels change. Generated catalogs keep their bytes.
- Docs: `docs/composition.md`, `docs/curation.md`, `docs/development.md` and any
  page naming `package:` families or package denials.
- Tests: the frozen codm source-generation reproduction
  (`tests/fixtures/source-generation/codm/` and the frozen-baseline checks in
  `tests/test_source_generation_fixtures.py`) is deleted rather than migrated;
  behavior tests use synthetic inputs and live-data outcome checks pair the
  committed configuration with the latest capture under
  `tests/fixtures/reconciliation/`.
