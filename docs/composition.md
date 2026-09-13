# Pack composition

Each output contains at most one selected build per logical app family. A family
normally follows the effective Android package id, using `package:<id>`. Maintained
rules can associate different package identities under `app:<name>`. The exported
Obtainium records carry each selected build's effective package id; family and
source-selection metadata remain internal.

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
- RJNY by its export flags: an entry in both exports is a baseline build for both
  packs, an entry only in the dual-screen export is a dual-screen build, and an
  entry only in the standard export is a baseline build that upstream keeps out
  of dual;
- extras by `"dualScreen": true`, which makes the extra a dual-screen build;
  without it, an extra is a baseline build for both packs.

No candidate rule or other composition setting changes a build's kind or which
packs it can appear in.

A valid pin comes first: it selects the one candidate it names ahead of
dual-screen replacement and source precedence. Nothing else makes the dual pack
select a baseline build over an available dual-screen build. Among builds of one
kind, source precedence is extras, RJNY, BBoi, then codm-generated entries. A tie
between different candidates at the winning rank fails and needs a pin or a
policy correction.

To keep a family's baseline build in dual in place of its dual-screen build, pin
the baseline build for dual. This works even when the two share a package id, as
the Zelda 3, Minish Cap and Harvest Moon 64 builds do, where a denial could not
remove one without the other. A package denial removes every build carrying that
package id from both packs and leaves the family's builds with other package ids
selectable, so an app is absent from a pack only when no selectable build of its
family remains there. Those three families have no other build, so a denial of their shared
package id removes each of those apps from both packs.

A committed codm entry is dropped at ingestion when a higher-precedence candidate
that its own source makes eligible for dual covers the same project, so a baseline
build kept out of dual does not suppress it. Appearing in codm does not make a
higher-source candidate a dual-screen build.

## Candidate policy

`config/composition.json` requires integer `schemaVersion: 1`, `candidates` and
`pins` arrays. Unknown fields and invalid selectors fail. Candidate rules require
`match` and a nonempty rationale; the optional changes are `family` and
`packageId`. A rule cannot set eligibility or dual preference, which come only
from the build's source.

A match names original `source`, `origin`, `id`, and project `url`. Sources are
`rjny`, `bboi`, `extras`, and `codm2000`. Their origins are `rjny-catalog`,
`bboi-standard-asset` or `bboi-dual-asset`, `extras`, and `codm-generated`.
Project URLs use the shared normalization rule. Corrections match original
identity once and never trigger another rule through a corrected package id.

A complete policy with one corrected family and a dual pin that keeps its
baseline build in dual has this shape:

```json
{
  "schemaVersion": 1,
  "candidates": [{
    "match": {"source": "bboi", "origin": "bboi-standard-asset", "id": "org.example.old", "url": "https://github.com/example/app"},
    "family": "app:example", "packageId": "org.example.app",
    "rationale": "Primary APK manifest and device policy"
  }],
  "pins": [{
    "family": "app:example", "variant": "dual",
    "match": {"source": "bboi", "origin": "bboi-standard-asset", "id": "org.example.old", "url": "https://github.com/example/app"},
    "rationale": "Maintainer-selected dual build"
  }]
}
```

Identity correction needs primary APK manifest evidence recorded in curation
documentation. It changes the effective package used by selection and exports,
while retaining the original id in diagnostics. It does not establish signature,
installation, or data-migration compatibility.

A pin names `family`, `variant`, `match`, and `rationale`. The referenced candidate
must exist, belong to the family, be eligible for that pack, and survive
denials. A denial does not disable a contradictory pin silently; the build fails.

## Denials and patches

Each denylist record contains exactly an effective package `id` and a `reason`,
and applies to both packs. It removes every candidate carrying that package id
before selection, whichever source supplied it. Any other field, including a
`family` or `variant` selector, fails with the record identified. An unmatched
denial is reported as stale but does not fail the build.

The overlay file contains an array of `{id, url, patch}` records. A record matches
the selected effective id and normalized project URL together, and patches the
matching entry in every pack that selects that pair. A losing candidate cannot
satisfy a patch selector. Duplicate selectors and records that match no selected
entry fail, so a fork switch must deliberately update its patches.

Patches retain recursive JSON Merge Patch, including null deletion of allowed
fields. They cannot assign or delete `id`, `url`, `overrideSource`, or composition
metadata such as `dualScreen`. Whole-app removal uses the denylist.

Valid denylist and overlay records are arrays whose selectors are explicit:

```json
[{"id": "org.example.retired", "reason": "No supported build"}]
```

```json
[{"id": "org.example.app", "url": "https://github.com/example/app", "patch": {"additionalSettings": "{\"versionDetection\":false}"}}]
```

Every family selected in single needs a dual winner, with no exemptions, so an app
cannot be published in single only. To keep an app out of both packs, deny every
package id its family's builds carry. Source ineligibility and denials of other
packages in the family do not waive coverage. A different-package replacement in
the same family satisfies it, and an app with only a dual-screen build needs no
single counterpart. Different families selecting the same package in one output
fail.

## Build report

Build reports use schema 3. `changes` lists the package ids added and removed in
each pack since the previous output. `selections` records every family's winner
in each pack, the other available candidates it was chosen over, and one reason:
`pin`, `dual-preferred`, `ordinary-fallback` (dual with no available dual-screen
build), or `source` (single-screen precedence). `denylistRemovals` and
`staleExclusions` list what each denial removed or failed to match. Selection
records use snake_case field names:

```json
{
  "schemaVersion": 3,
  "status": "success",
  "changes": {"single": {"added": ["org.example.app"], "removed": []}, "dual": {"added": ["org.example.app"], "removed": []}},
  "selections": [{
    "family": "app:example", "variant": "dual",
    "original_id": "org.example.old", "effective_id": "org.example.app",
    "url": "https://github.com/example/app", "source": "bboi",
    "origin": "bboi-standard-asset", "reason": "pin",
    "considered": [{"source": "codm2000", "origin": "codm-generated", "original_id": "org.example.app", "url": "https://github.com/example/app-ds"}]
  }]
}
```

The example is abridged; the other build fields remain present in the full
report. A considered candidate records its identity, not why it lost; compare a
losing candidate's settings with the winner's by reading the source catalogs.
`pack report` reads only schema 3 build reports; an older report must be
regenerated with `pack build`.

Offline verification checks serialized family and package uniqueness, rendered
family projections, pins, denied packages, coverage, and overlay targets. It does
not check eligibility, which rendered entries cannot reveal, and it cannot prove
source provenance, ranking, presence of losing upstream candidates, or that patch
values were applied. Composition policy bytes participate in input fingerprints;
changed inputs or a different supported verifier identity make evidence stale.
Obsolete verification schemas require regeneration with `pack verify`.

Selected-project metadata failure prevents publication. It never switches to a
family alternative. Existing configured fallback among releases of the selected
project is unchanged. Nightly does not edit composition policy.

## Retired configuration

These pieces were removed, and configuration that still carries them fails:

- History records and family-change reporting. A `history` array in the policy is
  an unknown field. The report's `changes` still lists added and removed package
  ids, and its selections name each family's current winner.
- Rule-level eligibility and dual preference, and the extras `variants` list and
  its dual-preference flag. Candidate rules and extras that carry them fail with
  the field identified. An extra that belongs only in the dual-screen pack sets
  `"dualScreen": true` instead.
- Family denials, variant-scoped denials and coverage exemptions. Express a family
  denial as one denial per package id. A variant-scoped denial has no replacement:
  an app can no longer be published in single only.
- The separate dual-screen overlay file and the pack settings file. One overlay
  record patches every pack that selects its id-and-URL pair; a patch can no
  longer target one pack only. Category colours are derived from category names,
  and pack settings and colours can no longer be configured.
- Per-alternative selection detail: loss reasons, differing fields and
  history-based family classification. Selections keep the winner, the candidates
  considered and one reason.

## Migration and rollback

Different package identities may leave an old Obtainium entry and installed app
alongside the replacement. Export Obtainium settings and back up app data before
migration. Inspect the package/project transition, import the target pack, and
verify the intended repository and package. Only remove an old entry or app after
checking the replacement and preserving any needed data. Re-import and installation
must be tested on a device; metadata success does not prove either.

Rollback restores implementation, policy, overlay schema, and both output files
as one compatible revision. Restoring JSON does not undo installations or restore
removed app data. Ludashi's v4.0 flavor/identity migration remains deferred; this
change preserves its current release selection and source-version policy.
