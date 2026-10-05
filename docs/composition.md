# Pack composition

Each output contains at most one selected build per logical app family. Families
form after family rules and denials, over the candidates that survive and are
eligible for at least one pack. A candidate's family is keyed by its project URL,
in the normalized form `github.com/owner/repo`: every candidate at one URL that
no rule places elsewhere belongs to the family named by that URL, whichever
source lists it and whatever package id it carries. A shared package id joins
nothing, so two repositories that reuse one package id stay separate families
unless a rule joins them.

Maintained rules assign explicit families named `app:<name>`. A family rule
claims its selector's whole URL: when every family rule at a URL names one
family, every candidate at that URL belongs to it. When rules at one URL name
different families, each covers only the candidates there carrying its
selector's package id, and any other build at that URL stays in the URL's
family; that is how melonDS stable and nightly, which RJNY lists at one
repository, ship as two apps. Rules at different URLs naming one family join
those URLs, as the Cemu, Minish Cap, CTR and Dusklight rules do. The exported
Obtainium records carry each selected build's package id as its source supplied
it, or as an overlay patches it; family and source-selection metadata remain
internal.

## Baseline and dual-screen builds

Every build is either a baseline build or a dual-screen build. An app's baseline
build, when it has one, is what the single-screen pack uses. Absent a pin, a
family's dual-screen build, when one exists, replaces its baseline build in the
dual-screen pack; a family with no dual-screen build uses its baseline build
there. An app may instead have only a dual-screen build, which appears only in
the dual-screen pack, as an app only codm2000 supplies does.

Each source alone decides which kind a build is:

- BBoi by asset: standard-asset records are baseline builds for both packs, and
  dual-asset records are dual-screen builds;
- codm2000 entries are always dual-screen builds;
- Quiver entries are always baseline builds for both packs;
- RJNY by its export flags: an entry in both exports is a baseline build for both
  packs, an entry only in the dual-screen export is a dual-screen build, and an
  entry only in the standard export is a baseline build that upstream keeps out
  of dual;
- extras by `"dualScreen": true`, which makes the extra a dual-screen build;
  without it, an extra is a baseline build for both packs.

No candidate rule or other composition setting changes a build's kind or which
packs it can appear in.

Source records from every catalog and extras must not carry top-level `family`
or `variant`, even with null values. Ingestion rejects those fields with the
source, entry and field identified. Composition policy in
`config/composition.json` owns app families and per-pack selection; editing that
policy does not repair an invalid source record.
RJNY entries excluded from export are dropped before normalization, so they are
not validated. Other unmodeled fields pass through unchanged. The extras adapter
consumes `dualScreen` to set eligibility, so it never reaches that extra's
rendered record; on upstream records it is an ordinary unmodeled field.

A valid pin comes first: it selects the one candidate it names ahead of
dual-screen replacement and source precedence. Nothing else makes the dual pack
select a baseline build over an available dual-screen build. Among builds of one
kind, source precedence is extras, RJNY, Quiver, BBoi, then codm-generated
entries.

Different candidates of one family can tie at the winning rank, typically two
builds one source lists at one repository that no rule separates. The build does
not fail: it publishes the tied candidate whose import record, as ingested and
serialized canonically, sorts first, so input order never decides, and records a
same-rank tie finding naming the family, pack, tied candidates and winner. Pin
one of them or give each its own family rule.

To keep a family's baseline build in dual in place of its dual-screen build, pin
the baseline build for dual. This works even when the two share a project URL,
as the BBoi Zelda 3 and Harvest Moon 64 builds do, where a denial could not
remove one without the other. A denial removes every build at its project URL
from both packs and leaves the family's builds at other URLs selectable, so an
app is absent from a pack only when no selectable build of its family remains
there. Minish Cap's family joins Picori's baseline extra with the BBoi builds at
another repository; the extra wins single by source precedence while the BBoi
dual build wins dual.

Every entry in a committed generated catalog joins the candidate set and
competes with the other builds of its family through the rules above.

## Candidate policy

`config/composition.json` requires integer `schemaVersion: 1`, `candidates` and
`pins` arrays, and accepts an optional [`categories`](#categories) object.
Unknown fields and invalid selectors fail, and so does a JSON object key
repeated anywhere in the file, which `pack build`, `pack verify` and the offline
gate all reject naming the key rather than letting one occurrence win. Candidate
rules require `match` and a nonempty rationale, and may carry `family`; any
other field fails as unknown. A rule never changes a package id or a build's
eligibility or dual preference, which come only from the build's source. A rule
with only a rationale records why a candidate matters and changes nothing.
Track-only entries are ordinary candidates: a rule may give one a family, and
split rules separate a tracker from an app sharing its URL. Without them, a
dual-only tracker at an app's URL joins the app's family and, being a
dual-screen build, replaces the app in dual.

A match names original `source`, `origin`, `id`, and project `url`. Sources are
`rjny`, `bboi`, `extras`, `codm2000` and `quiver`. Their origins are
`rjny-catalog`, `bboi-standard-asset` or `bboi-dual-asset`, `extras`,
`codm-generated` and `quiver-generated`.
Project URLs use the shared normalization rule. A rule matches one candidate's
source identity exactly once, and two rules projecting different families onto
one package id at one URL fail.

A complete policy joining a baseline build and a dual-screen build at different
repositories, with a dual pin that keeps the baseline build in dual, has this
shape:

```json
{
  "schemaVersion": 1,
  "candidates": [{
    "match": {"source": "bboi", "origin": "bboi-standard-asset", "id": "org.example.app", "url": "https://github.com/example/app"},
    "family": "app:example",
    "rationale": "The standard build of the example app"
  }, {
    "match": {"source": "codm2000", "origin": "codm-generated", "id": "org.example.app.ds", "url": "https://github.com/fork/app-ds"},
    "family": "app:example",
    "rationale": "The dual-screen fork of the same app"
  }],
  "pins": [{
    "family": "app:example", "variant": "dual",
    "match": {"source": "bboi", "origin": "bboi-standard-asset", "id": "org.example.app", "url": "https://github.com/example/app"},
    "rationale": "Maintainer-selected dual build"
  }]
}
```

A pin names `family`, `variant`, `match`, and `rationale`. Its family is the
`app:` family its candidate belongs to, or otherwise its candidate's normalized
project URL. The referenced candidate must exist, belong to the family, be
eligible for that pack, and survive denials. A denial does not disable a
contradictory pin silently; the build fails. A pin on a denied candidate, or on
one its source makes eligible for no pack, fails on that removal, since the
candidate belongs to no family. When the rules at the pinned candidate's URL
place it in an `app:` family, a pin naming a different family fails when the
policy loads; any other pin names the family its candidate forms, which the
build checks.

## Categories

Every category in a pack comes from one fixed set, spelled as RJNY and BBoi
spell them so that imported categories merge with the ones users already have:
Emulator, PC Emulation, Decomps/Recomps, PC Ports, Frontend, Utilities,
Streaming and Track Only.

The policy's optional `categories` object maps a family name, an `app:<name>` or
a normalized project URL, to one category from the set other than Track Only:

```json
"categories": {
  "app:ctr": "Decomps/Recomps",
  "github.com/igawa6/dualsouls": "PC Ports"
}
```

A value that is not one of the categories above other than Track Only, a
non-string value, or a key that is neither an `app:` name nor a project URL
already in normalized form with a host and a path fails policy loading with the
key identified. A full `https://` URL, a GitHub URL with uppercase letters
(normalization lowercases only GitHub paths), or a family name typed without
`app:` is therefore caught rather than left stale.

After overlays apply, every selected entry in each pack gets its categories in
this order:

1. An entry whose final settings carry `trackOnly: true` carries exactly Track
   Only, whatever its source or the map says.
2. Otherwise, an entry whose family the map names carries exactly the mapped
   category.
3. Otherwise, the entry keeps the categories its source supplied that belong to
   the set, other than Track Only, in source order. Anything else, such as
   BBoi's Dual Screen, is dropped, and an entry left with none carries no
   category.

The map is keyed by family, so a mapping survives a fork switch and covers both
packs. Only map an app whose source categories are missing or wrong; most
sources already use the set's spellings. codm2000 entries carry no source
category, so each one the packs select needs a map key. Overlays cannot set
categories.

Neither outcome below fails the build; the build report lists both, and
`pack report` displays them:

- `uncategorizedFamilies`: each family whose selected entry ended with no
  category, naming exactly the packs where that happened. Each pack selects its
  own winner, so a family can be uncategorized in dual only. Such an entry
  carries no category in that pack, and the README catalog lists it under
  "Other" only when it is the family's presenting entry, which is the
  single-screen one when the family has one. Add a `categories` key for the
  family.
- `staleCategoryAssignments`: each map key that set no selected entry's
  category, because no pack selects that family or every selected entry of it
  is track-only. Remove or correct the key, for example after a family rename.

## Denials and patches

Each denylist record contains exactly a project `url` and a `reason`, and
applies to both packs. It removes every candidate at that normalized project URL
before selection, whichever source supplied it and whatever package id it
carries, and leaves candidates at other URLs selectable even when they share a
family or a package id. Any other field fails with the record identified. An
unmatched denial is reported as stale but does not fail the build. A repository
rename escapes a denial of its old URL; deny the new URL too.

The overlay file contains an array of `{url, patch}` records. A record patches
every selected entry at its normalized project URL, in every pack that selects
one. A losing candidate cannot satisfy a record. Two records with one normalized
URL fail, and so does a record that matches no selected entry, so a fork switch
must deliberately update its patches. A record applies to every selected entry
at its URL, including the entries of different families where rules split that
URL; a setting meant for only one of them belongs in its source.

Patches retain recursive JSON Merge Patch, including null deletion of allowed
fields. The protected fields are exactly `url`, `overrideSource`, `family`,
`variant` and `categories`; patches cannot assign or delete them, including by
null deletion. Every other field is patchable. Whole-app removal uses the
denylist, and categories use the [category map](#categories). A non-array
overlay fails with an array-shape error.

A patch may set `id` to a nonempty string, which is how a source's wrong package
id is fixed by hand; [curation](curation.md#wrong-package-ids) describes when.
The patched id changes only the rendered entry: family formation, denials, pins
and overlay matching still read the source's id and URL, while the repeated-id
record, offline verification and the README catalog see the patched id. An `id`
patch is accepted only at a URL whose candidates form one family. A record
patching `id` at a URL whose rules name different families fails when the
overlay and policy load, in `pack build` and `pack verify` alike, naming the
record and the families.

Valid denylist and overlay records are arrays keyed by project URL:

```json
[{"url": "https://github.com/example/retired", "reason": "No supported build"}]
```

```json
[{"url": "https://github.com/example/app", "patch": {"id": "org.example.app", "additionalSettings": {"versionDetection": false}}}]
```

Every family selected in single is expected to have a dual winner. When it has
none, the family still ships in single and the build records a single-only
coverage finding with its single selection's package id and normalized URL.
This is the usual result of an upstream single-only build and a dual-only fork
at another repository that share a package id: they no longer pair, and a
family rule joining the two URLs fixes it, as the Cemu rules do. A
different-repository replacement in one family satisfies coverage, and an app
with only a dual-screen build needs no single counterpart. To keep an app out
of both packs, deny every project URL its family's builds sit at.

After overlays apply, the build also records each package id that more than one
selected entry of one pack carries, with those entries' families and normalized
URLs. Obtainium stores imported apps by package id and would keep only one of
them. The fix is a family rule putting the entries in one family, or correcting
the overlay `id` patch that produced the repeat.

## Build report

`changes` lists the entries added and removed in each pack since the previous
output, each with its package id and normalized project URL, so a move to
another repository with the same id shows as one removed and one added entry.
`selections` records every family's winner in each pack with its package id,
URL, source and origin, the other available candidates it was chosen over, and
one reason: `pin`, `dual-preferred`, `ordinary-fallback` (dual with no available
dual-screen build), or `source` (single-screen precedence). `denylistRemovals`
lists each denial that removed candidates, once under its URL with the families
it removed, and `staleExclusions` each denial that matched nothing.
`repeatedIds`, `singleOnlyFamilies` and `sameRankTies` hold the nonfatal
outcomes described above. `sourceAdmissions` lists each committed codm and
Quiver entry the build admitted, with its source, id, URL and whether it is an
APK or track-only entry. `uncategorizedFamilies` and `staleCategoryAssignments`
are the [category outcomes](#categories); a build that fails before categories
are assigned records both empty, along with the single-only and repeated-id
lists, while its stage and error say the checks did not run.
`offlineVerification` holds the offline gate's status, its errors in `findings`,
and its nonfatal findings in `nonfatalFindings`. For example:

```json
{
  "schemaVersion": 5,
  "status": "success",
  "changes": {"single": {"added": [{"id": "org.example.app", "url": "github.com/example/app"}], "removed": []}, "dual": {"added": [], "removed": []}},
  "selections": [{
    "family": "app:example", "variant": "dual", "id": "org.example.app",
    "url": "https://github.com/example/app", "source": "bboi",
    "origin": "bboi-standard-asset", "reason": "pin",
    "considered": [{"source": "codm2000", "origin": "codm-generated", "id": "org.example.app.ds", "url": "https://github.com/fork/app-ds"}]
  }],
  "denylistRemovals": [{"url": "github.com/example/retired", "reason": "No supported build", "families": ["github.com/example/retired"]}]
}
```

The example is abridged; the other build fields remain present in the full
report. A considered candidate records its identity, not why it lost; compare a
losing candidate's settings with the winner's by reading the source catalogs.
`pack report` reads only build reports of the current schema; an older report
must be regenerated with `pack build`.

Offline verification labels each rendered entry with the explicit family the
rules project onto its package id and URL, or otherwise its normalized URL, and
pairs single and dual entries with equal labels in one pass. A label repeated
within a pack is an error, and those entries are left out of pairing and
coverage. A package id repeated within a pack and a single entry without a dual
pair are nonfatal findings. It also checks pins, against the overlay-patched id
at the pin's URL, entries at denied URLs, overlay targets, and that every entry
carries `allowIdChange: true`. It does not check eligibility, which rendered
entries cannot reveal, and it cannot prove source provenance, ranking, presence
of losing upstream candidates, or that patch values were applied. It checks only
that each entry's categories are a list of strings, not that they come from the
[category set](#categories) or that Track Only matches `trackOnly`; composition
enforces both. Composition policy bytes participate in input fingerprints;
changed inputs or a different supported verifier identity make evidence stale.
A verification report with any schema other than the current one requires
regeneration with `pack verify`.

The README catalog pairs the rendered packs the same way and writes one row per
pair or unpaired entry. Rows sharing a label are never merged. Catalog
generation fails when a label repeats within a pack.

Selected-project metadata failure prevents publication. It never switches to a
family alternative. Existing configured fallback among releases of the selected
project is unchanged. Nightly does not edit composition policy.

## Migration and rollback

Different package identities may leave an old Obtainium entry and installed app
alongside the replacement. Export Obtainium settings and back up app data before
migration. Inspect the package/project transition, import the target pack, and
verify the intended repository and package. Only remove an old entry or app after
checking the replacement and preserving any needed data. Re-import and installation
must be tested on a device; metadata success does not prove either.

Rollback restores implementation, policy, overlay schema, and both output files
as one compatible revision. Restoring JSON does not undo installations or restore
removed app data.
