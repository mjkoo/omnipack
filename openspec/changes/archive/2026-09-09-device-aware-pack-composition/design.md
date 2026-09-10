## Context

See proposal.md for motivation. Candidates currently carry a package id and a
single variant; BBoi ingestion discards its standard alternative when a dual
entry shares the id. Composition then ranks sources without device preference.
Offline verification independently enforces package-id coverage. Neither the
rendered JSON nor Obtainium understands a logical app family.

The committed baseline contains 88 single entries and 111 dual entries. Cemu
shares an id across different repositories. The recorded CTR manifest identity
collides with another fork already present in dual. These are distinct cases:
alternative selection and package correction must not be conflated.

## Goals / Non-Goals

**Goals:** Keep selection pure and deterministic; share policy interpretation
between build and offline verification; express exceptional family, eligibility,
identity and selection decisions as small committed rules; preserve original
provenance and make output changes reviewable.

**Non-Goals:** Automatic fork discovery, ranking by stars or release recency,
universal APK auditing, Android installation or data migration, new release
resolution behavior, and the incompatible Ludashi v4.0 upgrade. No new dependency
or extra consumer download is required.

## Decisions

### Candidate identity and policy are separate from Obtainium data

Extend the normalized model to retain a target eligibility set, a dual-preferred
flag, and an origin distinguishing RJNY catalog, BBoi standard/dual assets,
extras and generated entries. Original source, origin, package id and normalized
project URL identify a candidate. Identical duplicate records collapse before
matching; different records sharing that identity are an error. Origin prevents
two BBoi records with the same URL/id from becoming ambiguous selectors.

Add versioned `config/composition.json` with `schemaVersion: 1`, `candidates`
and `pins` arrays, plus an optional `history` array defaulting to empty. Candidate rules use a `match` object containing `source`,
`origin`, `id` and `url`; optional values are `family`, `packageId`, `eligible`
and `dualPreferred`. Pins contain `family`, `variant` and the same candidate
selector. Rules and pins require a nonempty rationale. Reject unknown fields,
unknown targets, duplicate selectors, multiple pins for one family/target,
empty eligibility, and dual preference without dual eligibility.

Candidate rules match original input identity once, without recursive rewriting.
After correction, the default family is `package:<effective-id>`; explicit
families use `app:<maintained-name>`, preventing namespace collisions. A rule
assigns at most one family. Changing a package id requires recorded primary APK
manifest evidence in durable curation docs, and preserves the original id in
reports. The serialized app contains only the effective package id.

For offline use, derive rule projections keyed by effective id and normalized
URL. Multiple provenance selectors projecting to the same rendered key must
agree on family and any explicitly declared eligibility; otherwise configuration
is rejected. Absent eligibility overrides impose no additional offline restriction:
source-derived flags cannot be reconstructed from rendered output. During build,
all candidates sharing a projected rendered key must agree with its family and
explicit eligibility, including otherwise unruled candidates. Conflicts require
consistent rules for those sources rather than silently changing family offline.
A selected entry with no projection uses the default package family. Pins project to their
corrected id and URL for output validation. Full candidate presence, provenance,
ranking and stale-rule validation remain build checks, because offline output
does not contain losing upstream candidates.

Retain previous-output family authority separately in `history` records containing
nonempty effective `id`, project `url`, `family` and `rationale`. Normalize URLs
with the same rendered-key helper; accept the `package:` and `app:` family
namespaces. Reject unknown fields, duplicate normalized keys and disagreement
with an active rule projection for the same key. History never supplies
eligibility, corrections, pins, current family assignments or candidate presence.
It is exempt from stale-candidate checks and is used only to classify previous
output entries. Removing an obsolete active rule does not remove its historical
mapping. Maintainers record mappings for published identities, including default
package families, in the committed policy; nightly never edits this input.

Keeping package id as the only app identity would prevent cross-package
replacements. Heuristic family detection would silently merge unrelated forks.
Explicit exceptions avoid both problems without maintaining a full local catalog.

### Preserve source intent, then apply explicit corrections

RJNY honors all exclusion flags; default entries are eligible for both targets
and ordinary, while entries eligible only for dual are dual-preferred. Standard
entries explicitly forbidden in dual are not silently copied there.

BBoi standard records are ordinary and eligible for both targets. Dual records
are dual-preferred and dual-only. Preserve both before selection. codm entries
are dual-only; a distinct generated repository is dual-preferred within a shared
family. Extras retain their existing variants default and accept a boolean
`dualPreferred` defaulting false. Policy rules override eligibility/preference.

Apply rules to higher-source candidates before codm URL suppression. A project
already contributed by a higher source eligible for dual is covered, irrespective
of whether it later wins or is denied. Merely appearing in codm does not promote
that higher-source build. A standard-only higher-source candidate does not cover
dual, preserving existing generation behavior. Apply generated-candidate rules
after resolution, then require all configured selectors to match exactly one
candidate. Suppression does not use live verification results. Existing unresolved
and cached-id behavior stays unchanged unless a missing candidate is required by
a rule or pin, which fails explicitly.

### Device preference precedes source precedence

After normalization and rules, apply exclusions. A deny record names exactly one
of `id` (effective package identity) or `family`, plus reason and optional variant.
Apply to all candidates, not just the winner. A package denial cannot be bypassed
by another source carrying that package; a different-package family alternative
remains eligible. A family denial removes every alternative. No match is a
nonfatal stale exclusion. A missing, denied or ineligible pin is always an error,
even if a family exclusion would otherwise remove it.

Select per family and target: a valid explicit pin wins; otherwise single ranks
all single-eligible candidates by source; dual first restricts to dual-preferred
candidates when any exist, then ranks sources. Source order remains extras,
RJNY, BBoi, generated. Different candidates tied at the winning rank fail.
Unselected lower-tier ties do not block a unique winner. Keep each winning entry
whole, then apply overlays. Package uniqueness is checked after all family
selections; different families selecting one package fail rather than being
silently collapsed.

A family included in single must have a dual winner, except a deliberate dual
family denial or a dual package denial naming that single winner's effective id.
An upstream eligibility restriction is not an exemption: without an alternative,
require explicit curation or exclusion. Dual-only families need no single entry.
Report family coverage separately from changes in package ids.

Failing a selected build's metadata verification never chooses another candidate.
Only absence from a successfully acquired catalog, explicit exclusions or policy
changes affect build selection. The existing release resolver can still fall
back among releases of the already selected project according to its settings;
this is separate from switching projects. An entire source fetch failure still
aborts, and nightly publication still preserves the last published pair.

This avoids arbitrary source priority overriding device suitability. It also
avoids network failures changing installed-app recommendations.

### Bind overlays to the selected repository

Migrate both overlay files from id-keyed objects to arrays of
`{id, url, patch}` records. The common file applies to both variants and the
dual file applies afterward to dual only. Match effective id plus normalized
project URL. Each selector must be unique within its file and match at least
one selected entry in that file's scope. A stale patch fails even if its old
package id is still present under another URL. Shared policies across forks
enumerate each URL rather than applying implicitly.

Retain recursive JSON Merge Patch and null deletion for allowed fields. Reject
patches containing `id`, `url`, `overrideSource` or composition metadata, including
null values. Reject non-object patches. Configuration changes that intentionally
switch forks must update or remove obsolete patches in the same change.

The one-time schema migration is preferable to silently retaining unsafe legacy
matching. Public Obtainium JSON remains unchanged. Existing source-version
policies, including Ludashi's current filter and version tracking, are preserved.

### Verification and reporting share the policy interpretation

Implement parsing and rendered-family projection as pure shared policy helpers.
Build loads policy before ingestion; offline verification loads it alongside the
existing exact-byte configuration snapshot. Offline checks enforce family and
package uniqueness, exclusions, projected eligibility/pins, coverage and patch
target existence. They do not prove winner optimality against unfetched catalogs
or prove patch values were applied.

Fingerprint the composition file alongside existing inputs, bump verifier
identity and version new report additions appropriately. Reports preserve older
supported formats and add per-target selections, family, original/effective id,
origin, preference tier, pin/source decision, fallbacks and rejected alternatives.
Preserve partial diagnostics on failure and existing `changes: null` semantics.
Compare previous import entries using only the committed historical mappings,
not current candidate rules or a prior build report. Current families come from
composition. A mapped previous family still selected in the same target is
retained, with changed package/project identity reported as a transition. A mapped
previous family absent now is removed. An unmapped previous entry has unknown
family history, never an inferred package family or family removal. When a target
has any unmapped previous entries, new families without a known previous match
have unknown addition status, since one of those entries might represent them;
report their keys and this reason instead of a definite addition or replacement.
Known matches and raw app/package diffs remain available. If the previous target
file is absent, all its current families are additions. This works in a fresh
scheduled checkout containing the previous import files and committed policy but
no `.build/report.json`. Missing history is a reporting limitation, not a selection
failure; malformed or conflicting history is a configuration failure.
No private policy fields reach the exported app records. Do not expand nightly's
write allowlist: composition policy is maintainer-authored input, not nightly output.

## Risks / Trade-offs

- Catalog membership can misrepresent real compatibility. Mitigation: document
  source-derived defaults and provide explicit, evidenced eligibility/preference
  corrections; do not describe metadata checks as device acceptance.
- Different-package replacement leaves existing Obtainium entries and device data
  untouched. Mitigation: list each identity transition and manual migration steps;
  never claim signature compatibility without evidence.
- Strict stale selectors and overlays can block refresh after upstream changes.
  Mitigation: actionable diagnostics identifying original and effective identity;
  require deliberate policy updates rather than silently abandoning curation.
- Existing mismatched ids can hide collisions. Mitigation: inspect the initial
  selection diff and recorded mismatches, apply only evidence-backed corrections
  necessary for the selected families, and fail unresolved package collisions.
  Do not group all Winlator forks into a single family.

## Migration Plan

1. Capture fixture candidates and the current two outputs. Enumerate actual
   competing standard/dual builds; record explicit family associations and any
   necessary identity evidence, especially for the competing CTR repositories.
   Seed historical mappings for baseline rendered identities, and retain them
   when removing active rules for candidates that no longer exist.
2. Implement policy, retained candidates and selection with regression coverage.
   Migrate extras metadata and all existing overlays without changing their
   intended settings. Introduce only family/candidate rules justified by the
   observed catalog and approved device policy.
3. Update offline validation, fingerprints, reports and compatibility tests.
   Rebuild both packs, explain every selected-project and package transition, and
   run offline/live verification and repository checks. Keep upstream drift
   distinct from policy-driven changes.
4. Document current limitations, exclusions, migration instructions and exact
   validation evidence. Device testing, if unavailable, remains explicitly
   outstanding and is not inferred from metadata success. Sync specs with behavior
   before archive. Deployment remains a separate maintainer action.

Rollback restores policy, overlay schema, implementation and both outputs as one
compatible revision. Reverting JSON alone does not undo installations, remove
device entries or restore data. No automatic rollback of device state is promised.
