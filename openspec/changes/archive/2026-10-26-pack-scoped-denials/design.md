# Design

## Context

See proposal.md - Why. Today each candidate carries `eligibility`, a set of
variants (`model.App.eligibility`), and "dual-screen build" is derived as
eligibility equal to `{dual}`. Sources compute the set: RJNY from its two export
flags, BBoi by asset, the generated-catalog registry gives codm `{dual}` and
Quiver both, and extras use `dualScreen`. Composition removes denied candidates,
forms families over candidates with a nonempty set, and `_select` filters each
variant's candidates by membership before applying dual preference. Pins are
validated against the set, and `_single_only_families` plus the offline
`single_only_coverage` finding report families single selects that dual does
not.

Pack-scoped ("variant-scoped") denials existed until they were retired as
unused configuration generality, together with eligibility rules on candidate
rules. Fifteen denials now need a pack scope, so the field returns in its
smallest form: a list of pack names on an ordinary denial.

## Goals / Non-Goals

**Goals:**
- One meaning for build kind: which build a pack prefers.
- Every pack exclusion is an owner denial with a reason.
- No change to the dual-screen pack for today's configuration.

**Non-Goals:**
- No per-family scope map, allow list or new alert key for screen scope. The
  arrival-triage workflow already reviews every new family.
- No change to pins, family rules, precedence or the categories map.
- No new selection reason for single falling back to a dual-screen build.

## Decisions

**Kind is a boolean on the candidate.** `App.eligibility: frozenset[Variant]`
becomes `App.dual_screen: bool`, and `dual_preferred` is removed in its favor.
Sources set it: RJNY true only for an entry in the dual export alone, BBoi true
for dual-asset records, codm true, Quiver false, extras from `dualScreen`. The
generated-catalog registry's `eligibility` becomes `dual_screen`. Alternative
considered: keep the set and make it always both variants. Rejected, since a
field that never varies is dead code.

**Selection is symmetric.** For each variant, `_select` takes the family's
candidates not denied in that variant, prefers those whose `dual_screen` equals
`variant is DUAL`, falls back to all of them, and ranks by precedence. Reasons:
pin as today; dual reports `dual-preferred` or `ordinary-fallback` as today;
single always reports `source`. Alternative considered: a new `dual-fallback`
reason for single. Rejected as YAGNI, since the winner's source and origin
already show its kind in the report.

**Denials carry their variants.** `Exclusion` gains `variants: frozenset[Variant]`,
parsed from optional `packs` (nonempty list of distinct `single`/`dual`; absent
is both). `_exclude` returns, per candidate, the variants it is denied in.
Families form over candidates denied in fewer than all variants; selection skips
a candidate in the variants it is denied in. A removal record carries its
variants. Stale stays "no candidate at the URL".

**Pins check the pin's variant.** A pin fails when its candidate is denied in the
pin's variant; a candidate denied in every variant belongs to no family, so the
existing pre-family check covers it. The ineligibility branches are deleted.

**Offline verification checks denials per variant.** The denied-URL check
flags an entry only in a variant the denial applies to. The coverage pass and
its finding are deleted; pairing stays for README ordering.

**RJNY entries in neither export are dropped at ingestion,** like entries
excluded from export, so no candidate has an empty set to special-case.

**Repeated package ids raise an alert.** `scripts/alerts.py` maps each
`repeatedIds` item to key `build/repeated-id/<variant>/<package id>`. This is
the one signal that replaces the single-only coverage finding for the cross-URL
shared-id pattern, and a repeated id in a published pack is user-visible
breakage.

**Build report schema advances** to drop `singleOnlyFamilies` and add the
variants to each `denylistRemovals` record; older reports already produce a
regeneration diagnostic.

## Risks / Trade-offs

- [A new codm companion app reaches single before triage decides] → Arrival
  triage runs on the uncategorized alert the same night; the skill now asks for
  a single-scoped denial for apps with no use on one display. The window is at
  most one nightly.
- [A family rule or pin matches an RJNY entry in neither export, which is now
  not a candidate, so its selector is unmatched and the build fails] → Check the
  committed policy against the live RJNY catalog during implementation; today's
  build reports no single-only family, and any such selector is removed in this
  change.
- [An RJNY standard-only build now reaches dual where its family has no
  dual-screen build] → Today's build has no single-only family, so nothing
  changes now; later cases show as a new dual entry in the source PR or nightly
  diff, and a dual-scoped denial removes it.
- [The 18 single additions include weak cases (Balatro DS, Skyrim Web Monitor)]
  → Each is one denial line to reverse, with a reason recorded in `deny.json`.

## Migration Plan

1. Land code, specs, tests and the 15 single-scoped denials together, so no
   build ever publishes a companion app in single.
2. Before committing, a local `pack build` confirms: dual-screen pack unchanged;
   single gains exactly the 18 expected families; no repeated package id; no
   stale denial. The rebuilt `dist/` and README are discarded, as the nightly
   publishes them.
3. Rollback: revert the merge; the denials' `packs` field then fails as an
   unknown field, so the revert includes `config/deny.json`.
