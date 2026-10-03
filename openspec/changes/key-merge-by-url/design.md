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
- 2 families are joined only by a shared package id across URLs. Cemu
  (`sapphirerhodonite/cemu` dual-only, `SSimco/Cemu` single-only) splits
  harmlessly: each pack still selects one. Minish Cap (`samyost1/tmc-android`,
  `999sian/tmc`) would put both builds in both packs, so it needs a join rule.
- 2 URLs carry several package ids. Super Metroid's three are all denied
  today. melonDS stable and nightly (RJNY) would merge, so each needs a
  rule of its own.
- Simulating URL-wide family rules without `packageId` corrections, with the
  melonDS and Minish Cap rules, gives 108 single and 134 dual entries with the
  same project per family as today's `dist/`, and no package id repeated
  within a pack. Without the Minish Cap rule, `dev.picori.tmc` repeats in both
  packs; with rules covering only their own candidates, CTR and Dusklight
  builds split out and repeat their ids in dual.

## Goals / Non-Goals

**Goals:**

- Family identity, denials and overlays need no package id.
- The rebuilt packs select the same project for every family as today's;
  emitted ids change only where a correction is removed.

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
category key not already in normalized form fails loading, so a key typed as
a full `https://` URL is caught rather than silently stale.

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

### Denials and overlays key on the URL alone

`config/deny.json` records become `{url, reason}` and remove every candidate
at that URL. All three ids at Super Metroid's URL are denied today, so no
current denial needs a narrower selector. Overlay records become
`{url, patch}` and patch every selected entry at the URL; both current records
name unique URLs. An id-plus-URL key was rejected because it keeps the package
id as an identity input, which is what this change removes. A repository
rename escapes a URL denial; that is the accepted aliasing cost.

### A repeated package id is reported, not prevented

Shared-id families used to make a repeat impossible. Now the build records each
package id more than one selected entry of a pack carries, `pack report` shows
it, and verification reports it as a nonfatal finding. Failing was rejected:
the owner wants identity problems reported and fixed in configuration, and
one repeat should not stop the nightly publication of every other app. The
build report's schema version is bumped because exclusions change identity and
a field is added; `pack report` already directs an old report to `pack build`.

### Package-id corrections are removed; every entry allows an id change

Obtainium refuses to install an imported app whose id disagrees with its APK,
unless the app record carries `allowIdChange: true`; it then adopts the APK's
id on first install and clears the flag, so later updates keep the id-change
protection. Rendering sets the flag on every entry, so the 24 `packageId`
correction rules, the effective-id concept and the original-versus-effective
report columns are deleted, and an entry ships the id its source supplied.
Keeping corrections was rejected: each one needs a maintainer to read an APK
manifest, which is the requirement this change and its successor remove. The
cost is that the repeated-id report sees the ids sources wrote, so two forks of
one package at different URLs, where one source spells the id wrong, are not
reported; Obtainium collapses them on install. The rule forbidding a
candidate's id from equalling a track-only candidate's id existed only to keep
trackers out of shared-id families and is deleted, as is `packageId` from the
fields a source record may not carry.

### Change comparison keys on id and URL

The build report's added and removed lists compare entries by (id, normalized
URL): URL alone cannot tell melonDS stable from nightly, and id alone is what
this change stops trusting.

### One-pass offline pairing

Each rendered entry gets one label, its explicit projection or its URL, and
single and dual entries with equal labels pair. A label repeated within a
variant fails verification and README generation, covering what the separate
duplicate-id and duplicate-explicit-family checks did.

## Risks / Trade-offs

- [A fork reusing an existing app's package id is published beside it] → the
  repeated-id report names both entries; the fix is one family rule.
- [A renamed repository forms a new family and escapes its denial] → the build
  report's added list and the source proposal PR show the new URL; the fix is
  a family rule or a denial for the new URL.
- [Two builds of one repository merge when a split was wanted] → selection
  ties or a changed winner show in the report; the fix is a rule per build, as
  for melonDS.
- [Obtainium's re-import of an app that has already adopted its real id
  misbehaves] → it is read from Obtainium's code, not observed; a device check
  on the AYN Thor, with the owner's approval, gates the change, and keeping
  corrections is the fallback.
- [Forks of one package at different URLs with a wrongly spelled id are not
  reported] → the app goes missing on a device rather than in a report; the
  fix is a family rule, as for Minish Cap.

## Migration Plan

Code and configuration change together on one branch, since the old and new
key spellings are not interchangeable:

1. `config/composition.json`: remove `packageId` from every rule, deleting the
   18 rules that carried nothing else; add `app:melonds` and
   `app:melonds-nightly` rules for RJNY's two melonDS builds; give the BBoi
   `tmc-android` rules `family: app:minish-cap` and add one for the extras
   Picori entry; rename the 23 remaining `package:` category keys to URLs and
   `package:dev.picori.tmc` to `app:minish-cap`; rename the seven `package:`
   pins to URLs.
2. `config/deny.json`: the seven id denials become five URL denials (the three
   Super Metroid ids share one URL).
3. `config/overlay.json`: drop `id` from both records.
4. Rebuild and compare with the previous `dist/`: each pack keeps the same
   number of entries (108 and 134 in the simulation) and the same project URL
   per family; ids change only where a correction was removed; every entry
   gains `allowIdChange: true`; the repeated-id, uncategorized and
   stale-category lists are empty; `pack verify` passes.
5. On the AYN Thor, with the owner's approval first: import a rebuilt pack,
   install an app whose source id differs from its APK, re-import the pack,
   and confirm Obtainium holds one working entry for it.

Rollback is reverting the branch; no published data depends on the new keys.
