## Context

Composition (`composition_policy.py`, `merge.py`) forms families transitively:
candidates sharing an effective package id join, explicit `family` rules join
candidates by selector or by their (effective id, normalized URL) projection,
and every other family is `package:<id>`. Denials, overlays, pins and category
keys are expressed in those terms. Offline verification (`offline.py`) and
the README catalog recover families from rendered entries in two passes, first
by shared package id and then by explicit projection. See proposal.md for why
the key moves to the project URL.

Measured on the sources as of 2026-10-03 (170 candidates, 138 families today):

- 7 explicit families span several URLs and keep working unchanged.
- 2 families are joined only by a shared package id across URLs, and both
  need a join rule. Cemu (`sapphirerhodonite/cemu` dual-only, `SSimco/Cemu`
  single-only, both `info.cemu.cemu` in RJNY) would split into a single-only
  family at `github.com/ssimco/cemu` with no dual build and a dual-only family
  at `github.com/sapphirerhodonite/cemu`, losing the dual replacement. Minish
  Cap (`samyost1/tmc-android`, `999sian/tmc`) would put both builds in both
  packs.
- 2 URLs carry several package ids. Super Metroid's three are all denied
  today. melonDS stable and nightly (RJNY) would merge, so each needs a
  rule of its own.
- Simulating URL-wide family rules without `packageId` correction rules, with the
  melonDS, Cemu and Minish Cap rules, gives 108 single and 134 dual entries with the
  same project per family as today's `dist/`, no package id repeated
  within a pack, and no single-screen family without a dual build. Without the Minish Cap rule, `dev.picori.tmc` repeats in both
  packs; with rules covering only their own candidates, CTR and Dusklight
  builds split out and repeat their ids in dual. Moving today's corrections
  into overlay `id` patches changes only rendered ids, after selection, so the
  counts and projects above hold and the corrected apps keep today's ids.

## Goals / Non-Goals

**Goals:**

- Family identity, denials and overlays need no package id.
- The rebuilt packs select the same project for every family as today's,
  and the corrected apps ship the same ids as today's, now from overlay `id`
  patches.

**Non-Goals:**

- Changing source generation, generated catalogs or what package ids sources
  carry; a later change removes APK inspection from generation.
- Detecting URL aliasing (a renamed or mirrored repository) automatically.

## Decisions

### A default family is named by its normalized URL, without a prefix

`github.com/owner/repo` names the family of every candidate at that URL that no
rule places elsewhere. Category keys and pins use the same string. The `app:`
prefix still marks explicit families, so the two cannot collide. A
`url:` prefix was considered and rejected: the normalized form is already
recognizable and the prefix would be one more spelling to get wrong. A
category key not already in normalized form, or without a host and a path,
fails loading, so a key typed as a full `https://` URL or a family name typed
without `app:` is caught rather than silently stale.

### A family rule claims its whole URL

A family rule's URL is its selector's normalized URL. When every family rule at
a URL names one family, every candidate at that URL belongs to it, whatever
package id it carries: Quiver's and codm's builds of CTR, Dusklight and OpenMW
join their explicit families this way without rules of their own. When rules at
one URL name different families, each covers only the candidates carrying its
selector's package id, and any other build there stays in the URL family; that
is how melonDS stable (`app:melonds`) and nightly (`app:melonds-nightly`) both
ship. Two alternatives were rejected. A rule covering only the candidate it
matches, plus candidates with the same id and URL, needs a rule for every
build of an explicit family, and a generated entry without a real package id
could only be named by its placeholder id. Joining every build at a ruled URL
with no way to split would make melonDS impossible. Nothing joins across URLs
except an explicit family, so the failure for two explicit families joined
through a shared package id has nothing left to detect and is deleted.

Offline code reads the same rules: a rendered entry at a URL whose rules agree
takes that family, one at a split URL takes the family of the rule naming its
id, and anything else takes its URL. Because composition and offline labelling
apply one rule, the composition-time pairing check (selected entries that do
not pair) can no longer fire and is deleted.

### Track-only candidates are ordinary candidates at their URL

A track-only candidate takes part in family formation exactly as an installable
build does: a rule matching it may carry `family`, a URL-wide projection covers
it, and when rules at one URL name different families it follows the rule
naming its id. Composition, offline labelling and the README catalog therefore
apply one projection to every entry, so a tracker's family and its rendered
label cannot disagree. A tracker sharing an installable app's URL joins that
app's family by default, and because codm entries are dual-preferred it can
win dual over the app; the owner separates them with split rules, exactly as
melonDS stable and nightly are split. URL equality is not what decides
replacement: owner rules may equally join a tracker and its app at different
URLs into one explicit family, and then single selects the app and dual the
dual-preferred tracker, while a tracker and its app in different families never
replace each other, whatever their URLs. Keeping trackers in their URL family
regardless of rules was rejected: offline labelling follows the projection, so
a URL-wide rule would label the tracker with the app's family and report a
repeated label, and no configuration could separate the two.

### A same-rank tie publishes one winner and is reported

Under URL keying, builds one source lists at one repository URL with different
package ids, such as melonDS stable and nightly, share the URL family and tie
at the winning rank until rules split them. Composition no longer fails on such
a tie. It selects the tied candidate whose canonical serialized form sorts
first: the candidate's import record as ingested, before overlays, category
assignment and the `allowIdChange` override, serialized the way rendering
serializes entries. Selection runs before those stages, so the rendered form
does not exist yet; the shared serializer keeps one encoding. The winner
depends only on candidate content and never on input order, and composition
records a same-rank tie finding naming the family, variant, tied selectors and
chosen winner. `pack report` displays the finding. The owner resolves it with a
pin or with split family rules. Failing was rejected for the same reason as for
a repeated id: one family's ambiguity should not stop the nightly publication of
every other app. Choosing by source order or release date was rejected because
it would make the published winner depend on how a source happens to list its
entries. Pin conflicts (a missing, ambiguous, excluded, wrong-family or
target-ineligible pinned candidate, or several pins for one family and target)
remain fatal, because they are owner configuration errors rather than upstream
data.

### Denials and overlays key on the URL alone

`config/deny.json` records become `{url, reason}` and remove every candidate
at that URL. All three ids at Super Metroid's URL are denied today, so no
current denial needs a narrower selector. Overlay records become
`{url, patch}` and patch every selected entry at the URL; every current record
names a unique URL. An id-plus-URL key was rejected because it keeps the package
id as an identity input, which is what this change removes. A repository
rename escapes a URL denial; that is the accepted aliasing cost. A patch may now
set `id` (see below); it is applied to the selected entry's rendered output
only, so overlay matching, like family formation, never reads a patched id.

### A repeated package id is reported, not prevented

Shared-id families used to make a repeat impossible. Now the build records each
package id more than one selected entry of a pack carries, `pack report` shows
it, and verification reports it as a nonfatal finding. Failing was rejected:
the owner wants identity problems reported and fixed in configuration, and
one repeat should not stop the nightly publication of every other app. The
build report's schema version is bumped because exclusions change identity and
fields are added for repeated ids, single-only coverage findings and
same-rank tie findings;
`pack report` already directs an old report to `pack build`.

### A single-screen family without a dual build is reported, not fatal

Today a family selected in single without a dual build fails the whole build.
Under URL keying an upstream single-only original at one URL and a dual-only
fork at another URL sharing its package id no longer pair, so that upstream
pattern produces exactly this gap. The family is still published in single,
the build records a single-only coverage finding naming the family and its
single selection's id and URL, `pack report` shows it, and offline
verification reports the unpaired single entry as a nonfatal finding instead
of failing; the README already gives an unpaired entry its own row. The fix
is a family rule joining the URLs, as for Cemu. Failing was rejected for the
same reason as for a repeated id: one project's gap should not stop the
nightly publication of every other app.

### Package-id corrections become overlay id patches; every entry allows an id change

Obtainium refuses to install an imported app whose id disagrees with its APK,
unless the app record carries `allowIdChange: true`; it then adopts the APK's
id. Rendering sets the flag on every published pack entry, so an entry whose
shipped id is still wrong installs rather than failing. The flag does not make
a wrong id harmless. Read from Obtainium's main-branch source: `import()`
(`lib/providers/apps_provider_import_export.dart`) saves every imported record
with `saveApps(importedApps, onlyIfExists: false)`, keyed only by the record's
`id` and never matched by URL, and `handleAPKIDChange`
(`lib/providers/apps_provider_install.dart`) re-saves a record under the APK's
id on install when the ids differ and `allowIdChange` is set or the id is a
temporary id (`isTempId` in `lib/models/app.dart`: all digits or 12 lowercase
hex). So when a shipped id differs from its APK's, every pack import after
install adds a never-installed duplicate under the shipped id beside the
installed app. Pack re-import is the normal update flow, so the duplicate
recurs, and it would also reach existing users of today's corrected apps on
their first import of the rebuilt pack if their corrections were dropped.

Corrections therefore stay, but no longer as a composition identity input or a
candidate-rule field: they become owner render-time patches keyed by URL. An
overlay record may patch `id`, so `id` leaves the overlay's protected fields,
and the owner fixes a wrong source id by hand exactly as a name or an APK
filter is fixed. The owner learns of one when Obtainium shows a duplicate or an
id error; no tooling reads APKs or manifests. The patch changes only the
selected entry's rendered output: family formation, deduplication, denials,
pins and overlay matching stay keyed by normalized URL and never read a patched
id, while the repeated-id record, offline verification and the README catalog
see the patched id because it is what ships. An `id` patch is accepted only at
a URL whose candidates form one family. At a URL whose rules name different
families, a patch would give every entry there one id; offline verification,
whose labels at such a URL come from rendered ids, would then fail on the
repeated label, and since offline verification gates publication, `pack build`
would publish nothing. That is an owner configuration error, not one project's
problem, so it fails loudly and early: a record patching `id` at such a URL
fails when the overlay and composition policy load, naming the record and the
URL's families, in `pack build` and `pack verify` alike, as two records with
one URL already fail. This also keeps every selected entry's family
recoverable from its rendered id and URL. Overlay scoping per family was
rejected as more machinery than one rare configuration error warrants; for
the same reason a non-`id` record at a split URL patches every family there,
and a family whose single and dual selections at one URL are different APKs
with different real ids cannot have both ids fixed, an accepted limitation
with no current case. Offline
pin checks compare a pin's id after the overlay `id` patch at its URL, since
rendered entries carry the patched id.

Today's 24 `packageId` rules lose that field; of the 18 that carried nothing
else, 16 are deleted and the two BBoi `tmc-android` rules gain a Minish Cap
family instead; and each correction whose URL carries a selected entry moves into
`config/overlay.json` as a `patch.id` record on that URL, merged into the
existing record when the URL already has one, since two records with one URL
fail. A correction whose candidate is never selected renders nothing today, and
a record matching no selected entry fails as stale, so it is not carried over.
The effective-id concept and the original-versus-effective report columns are
deleted: the selection report names the source id, and the rendered pack the
patched one.

Pack entries do not keep Obtainium's id-change protection: Obtainium clears
the flag only when an install actually changes the stored id, and every import
or re-import sets it back to `true`, so if an upstream build later declares a
different package id, Obtainium adopts it instead of raising its id-changed
error. This is accepted as the cost of letting unfixed entries install.

Generated catalogs are rendered through the same `render()` as the packs, so
the `allowIdChange` flag is added only when rendering the published packs from
composed entries, never in the canonical catalog rendering source generation
uses (`render_catalog` and `rendered_entry` in `source_catalog.py`), which
keeps committed catalogs unchanged. `source_catalog.py` also stops naming
families through the retired id-based `package:` helper.

The repeated-id report sees rendered ids, so two forks of one package at
different URLs, where one source spells the id wrong and no overlay fixes it,
are not reported; Obtainium collapses them on install. The rule forbidding a
candidate's id from equalling a track-only candidate's id existed only to keep
trackers out of shared-id families. Families no longer form by id, and a
tracker is now an ordinary candidate at its URL that rules can separate from
an app, so that rule is deleted together with the rule forbidding `family` on
a track-only candidate, as is `packageId` from the fields a source record may
not carry.

### Change comparison keys on id and URL

The build report's added and removed lists compare entries by (id, normalized
URL): URL alone cannot tell melonDS stable from nightly, and id alone is what
this change stops trusting.

### Rendering order breaks ties by URL

A pack may now carry one package id at two URLs, so primary category, name and
id no longer order every entry. Rendering adds the normalized project URL and
then the entry's canonical serialized form as tie-breakers, keeping the order
total and the bytes stable.

### One-pass offline pairing

Each rendered entry gets one label, its explicit projection or its URL, and
single and dual entries with equal labels pair. A label repeated within a
variant fails verification and README generation, covering what the separate
duplicate-id and duplicate-explicit-family checks did.

Today every offline finding is fatal: a finding carries no severity, the
build's offline gate fails on any of them and withholds the README, and the
verification report lists them all as errors. Offline findings now split into
errors and nonfatal findings (single-only coverage and repeated package ids).
Only errors fail `pack verify`, the build's offline gate and README
regeneration; nonfatal findings go in their own list in `.build/verify.json`
and in the build report's offline verdict, and `pack report` displays them.

Because offline verification now checks different things (it requires
`allowIdChange: true`, pairs in one pass and reports new nonfatal findings),
the verifier identity advances, and because the verification report gains the
nonfatal findings list, its schema version advances too. A report saved before
this change therefore carries the old schema and `pack report` directs the user
to `pack verify` rather than labelling it current or stale; the
verifier-identity staleness rule still governs later verifier changes that
keep the schema.

## Risks / Trade-offs

- [A fork reusing an existing app's package id is published beside it] → the
  repeated-id report names both entries; the fix is one family rule.
- [A renamed repository forms a new family and escapes its denial] → the build
  report's added list and the source proposal PR show the new URL; the fix is
  a family rule or a denial for the new URL.
- [Two builds of one repository merge when a split was wanted] → when they
  tie at the winning rank the build still succeeds, publishes the build whose
  canonical serialized form sorts first and records a same-rank tie finding in
  the build report and `pack report`; when ranks differ, the changed winner
  shows in the report's selections and added and removed lists. The fix is a
  pin or a rule per build, as for melonDS.
- [An entry whose source id differs from its APK's and has no overlay fix
  gains a never-installed duplicate on every pack import after install] →
  Obtainium saves imported records by `id` and re-saves an installed app under
  its APK's id, so the duplicate recurs with each re-import. The owner fixes
  the entry with an overlay `id` patch on its URL when Obtainium shows the
  duplicate or an id error; today's corrections move into such patches so
  existing users see no new duplicates. The behavior is read from Obtainium's
  code; a device check on the AYN Thor, with the owner's approval, records what
  actually happens.
- [An overlay `id` patch at a URL whose rules name different families would
  give them one id] → the overlay fails on load in `pack build` and
  `pack verify`, naming the record and the families; the fix is to remove the
  `id` patch.
- [Pack entries lose Obtainium's id-change protection] → every entry carries
  `allowIdChange: true`, Obtainium clears it only when an install changes the
  stored id, and each pack import or re-import sets it back to `true`, so if
  an upstream build later declares a different package id, Obtainium adopts
  it instead of raising its id-changed error. Accepted as the cost of letting
  unfixed entries install; the curation docs state it.
- [Forks of one package at different URLs with a wrongly spelled id are not
  reported] → the app goes missing on a device rather than in a report; the
  fix is a family rule, as for Minish Cap.
- [A tracker sharing an installable app's URL joins the app's family and,
  being dual-preferred, replaces the app in dual] → the report's removed list
  and the selection reasons show it; the fix is a family rule per build at
  that URL, separating the tracker into its own family.
- [An upstream single-only original and a dual-only fork at another URL share
  an id and no longer pair] → the single family ships without a dual build and
  the build report, `pack report` and verification name it as a single-only
  coverage finding; the fix is a family rule joining the URLs, as for Cemu.

## Migration Plan

Code and configuration change together on one branch, since the old and new
key spellings are not interchangeable:

1. `config/composition.json`: remove `packageId` from every rule, after
   carrying each correction whose URL carries a selected entry into
   `config/overlay.json` (step 3). Of the 18 rules that carried nothing else,
   delete 16 and give the remaining two, the BBoi `tmc-android` standard and
   dual rules, `family: app:minish-cap`; add one for the extras Picori entry;
   add `app:melonds` and `app:melonds-nightly` rules for RJNY's two melonDS
   builds; add `app:cemu` rules joining RJNY's `SSimco/Cemu` and
   `sapphirerhodonite/cemu` builds; rename the 23 remaining `package:` category keys to URLs and
   `package:dev.picori.tmc` to `app:minish-cap`; rename the seven `package:`
   pins to URLs.
2. `config/deny.json`: the seven id denials become five URL denials (the three
   Super Metroid ids share one URL).
3. `config/overlay.json`: drop the `id` selector field from every record, and
   add each carried correction as `patch.id` on its URL, merging it into the
   existing record when that URL already has one.
4. Rebuild and compare with the previous `dist/`: each pack keeps the same
   number of entries (108 and 134 in the simulation) and the same project URL
   per family; ids are unchanged from today's `dist/` for the corrected apps;
   every entry gains `allowIdChange: true`; the repeated-id, single-only coverage,
   same-rank tie, uncategorized and stale-category lists are empty; `pack verify` passes.
5. On the AYN Thor, with the owner's approval first: import a rebuilt pack,
   install an app whose non-temporary source id differs from its APK's id and
   has no overlay fix, re-import the pack, and record the entries Obtainium
   then holds for it; confirm that an app whose id is fixed by overlay keeps
   one entry across install and re-import; for an app whose source id matches
   its APK, record the `allowIdChange` value after install and after
   re-import.
6. Tests: delete the frozen codm source-generation reproduction
   (`tests/fixtures/source-generation/codm/` and its frozen-baseline checks)
   instead of migrating it. Its goldens pin the old pipeline's entry set,
   which URL keying changes; behavior is covered by synthetic tests and live
   outcomes by committed configuration over the latest capture.

Rollback is reverting the branch; no published data depends on the new keys.
