# Pack composition

Each output contains at most one selected build per logical app family. A family
normally follows the effective Android package id, using `package:<id>`. Maintained
rules can associate different package identities under `app:<name>`. The exported
Obtainium records carry each selected build's effective package id; family and
source-selection metadata remain internal.

Single-screen selection considers candidates eligible for single. Dual-screen
selection prefers eligible dual-specific candidates, falling back to ordinary
eligible candidates when no preferred candidate remains. A valid explicit pin
wins before this preference. Within the chosen tier, source precedence is extras,
RJNY, BBoi, then codm-generated entries. A tie between different candidates at the
winning rank fails and needs a pin or a policy correction.

## Candidate policy

`config/composition.json` requires integer `schemaVersion: 1`, `candidates` and
`pins` arrays. Optional `history` defaults to an empty array. Unknown fields and
invalid selectors fail. Candidate rules require `match` and a nonempty rationale;
optional changes are `family`, `packageId`, `eligible`, and `dualPreferred`.

A match names original `source`, `origin`, `id`, and project `url`. Sources are
`rjny`, `bboi`, `extras`, and `codm2000`. Their origins are `rjny-catalog`,
`bboi-standard-asset` or `bboi-dual-asset`, `extras`, and `codm-generated`.
Project URLs use the shared normalization rule. Corrections match original
identity once and never trigger another rule through a corrected package id.

A complete policy with one corrected family and a dual pin has this shape:

```json
{
  "schemaVersion": 1,
  "candidates": [{
    "match": {"source": "bboi", "origin": "bboi-standard-asset", "id": "org.example.old", "url": "https://github.com/example/app"},
    "family": "app:example", "packageId": "org.example.app",
    "eligible": ["single", "dual"], "dualPreferred": false,
    "rationale": "Primary APK manifest and device policy"
  }],
  "pins": [{
    "family": "app:example", "variant": "dual",
    "match": {"source": "bboi", "origin": "bboi-standard-asset", "id": "org.example.old", "url": "https://github.com/example/app"},
    "rationale": "Maintainer-selected dual build"
  }],
  "history": [{"id": "org.example.app", "url": "https://github.com/example/app", "family": "app:example", "rationale": "Previously published identity"}]
}
```

Identity correction needs primary APK manifest evidence recorded in curation
documentation. It changes the effective package used by selection and exports,
while retaining the original id in diagnostics. It does not establish signature,
installation, or data-migration compatibility.

A pin names `family`, `variant`, `match`, and `rationale`. The referenced candidate
must exist, belong to the family, be eligible for that target, and survive
exclusions. A family exclusion does not disable a contradictory pin silently.

RJNY target flags determine eligibility; only `excludeFromExport` prevents policy
from restoring eligibility. BBoi's standard records normally serve both targets,
while dual records are dual-only and preferred. Both asset origins remain present.
Extras default to both targets and ordinary preference. Committed codm catalog
entries retain the `codm-generated` origin and are dual-only and preferred.
Higher-source policy is applied before codm URL coverage,
so a single-only candidate does not suppress generation for dual. Merely appearing
in codm does not promote an ordinary higher-source candidate.

## Exclusions and patches

Each denylist record contains exactly one effective package `id` or `family`, a
reason, and an optional `variant`. Without a variant it applies to both targets.
Exclusions remove matching candidates before selection. Denying one package leaves
a different-package alternative available; denying a family removes all its builds.
An unmatched exclusion is reported but does not fail the build.

Both overlay files contain arrays of `{id, url, patch}` records. They match the
selected effective id and normalized project URL together. Common patches apply
to matching entries in either output, followed by dual-only patches. A losing
candidate cannot satisfy a patch selector. Duplicate selectors and stale targets
fail, so a fork switch must deliberately update its patches.

Patches retain recursive JSON Merge Patch, including null deletion of allowed
fields. They cannot assign or delete `id`, `url`, `overrideSource`, or composition
metadata. Whole-app removal uses the denylist.

Valid exclusion and overlay records are arrays whose selectors are explicit:

```json
[{"family": "app:retired-example", "variant": "dual", "reason": "No supported dual build"}]
```

```json
[{"id": "org.example.app", "url": "https://github.com/example/app", "patch": {"additionalSettings": "{\"versionDetection\":false}"}}]
```

Every single-selected family needs a dual winner unless a dual-applicable denial
names that family or the single winner's effective package id. A denial of another
package in the family is insufficient. Source ineligibility alone is not an
exemption. Different families selecting the same package in one output fail.

## Historical reporting

History records contain effective `id`, project `url`, `family`, and `rationale`.
They preserve family classification for previous published identities after old
candidates and stale active rules disappear. Include default package families as
well as explicit app families. Retiring an active rule does not retire its history.
History cannot change current family selection, eligibility, pins, or coverage.

Reports compare previous outputs using committed history without a prior build
report. Known retained families show package/project transitions; known absent
families are removals. Previous identities without history remain unknown. If a
previous target contains unknown identities, unmatched current families have
unknown addition status. Raw package changes remain available. A missing previous
output means all current families are additions.

Offline verification checks serialized family/package uniqueness, active rendered
projections, pins, explicit eligibility, exclusions, coverage, and patch targets.
It cannot prove source provenance, ranking, presence of losing upstream candidates,
or that patch values were applied. Composition policy bytes participate in input
fingerprints; changed inputs or a different supported verifier identity make
evidence stale. Obsolete verification schemas require regeneration with `pack verify`.

Build reports use schema 2 and selection records use snake_case field names:

```json
{
  "schemaVersion": 2,
  "status": "success",
  "selections": [{
    "family": "app:example", "variant": "dual",
    "original_id": "org.example.old", "effective_id": "org.example.app",
    "url": "https://github.com/example/app", "source": "bboi",
    "origin": "bboi-standard-asset", "eligibility": ["dual", "single"],
    "dual_preferred": false, "reason": "pin", "alternatives": []
  }],
  "familyChanges": {"dual": {"retained": [], "removed": [], "added": ["app:example"], "unknownAdditions": [], "unmappedPrevious": [], "unknownReason": null}}
}
```

The example is abridged; other build fields remain present in the full report.
Alternatives record why they lost, including ineligibility, exclusion, preference
tier, or lower source precedence.

Selected-project metadata failure prevents publication. It never switches to a
family alternative. Existing configured fallback among releases of the selected
project is unchanged. Nightly does not edit composition policy or history.

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
