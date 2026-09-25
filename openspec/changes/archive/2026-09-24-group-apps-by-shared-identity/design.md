## Context

See proposal.md for motivation. Today `apply_composition_policy` gives every candidate without a
rule the family `package:<effective id>`, and an explicit rule gives it an `app:` family. `merge`
groups by that field and selects per family and variant: a valid pin, then eligibility, then dual
preference, then source precedence (extras, RJNY, BBoi, then generated builds). It then fails when
two families place one package id in a variant. The policy fails a candidate whose rendered key
(effective id, normalized URL) projects to a different family. Offline verification and the README
catalog rebuild families from the committed exports through `CompositionPolicy.rendered_family`,
which falls back to `package:<id>`.

Evidence from the current build report and policy:
- The policy holds 33 candidate rules and 8 pins. Its 6 explicit `app:` families all pair
  different package ids across forks.
- Of 120 families, 115 draw their single and dual winners from one repository.
- Regrouping every candidate in the report (winners plus considered losers, with package-id
  corrections applied) by shared effective id and explicit family reproduces exactly the 120
  current families. These are the candidates that survive denials and are eligible for some
  variant, which is exactly the set families form over, so denied and wholly ineligible
  candidates need no separate evidence.
- After same-id pairing, the only unpaired single entries in the committed exports
  (`app:dusklight` and `app:openmw`) pair with dual entries through both entries' `app:`
  projections.

## Goals / Non-Goals

**Goals:**
- Offline verification and the README catalog reproduce every family the build publishes in both
  variants.
- Collisions between sources settled by the existing precedence.
- Unchanged exports, README and report names for the current configuration.

**Non-Goals:**
- Configurable precedence.
- Changing codm2000's ingest-time URL suppression.
- Grouping by name or title.
- Joining candidates by project URL. Two sources listing different ids at one repository keep
  today's behavior, and an explicit `app:` rule or a `packageId` correction joins them.
- Any policy schema change.

## Decisions

### Form families once, by shared identity

After identity corrections and exclusions, the surviving candidates eligible for at least one
variant are joined transitively when they:
- share an effective package id; or
- are assigned the same explicit family: a `family` rule matches them, or their effective id and
  normalized URL equal such a rule's projection, even when the ruled candidate itself is denied or
  eligible for no variant.

The projection is the authority at formation so that the build name, the load-time pin check and
offline labels agree: a rule-less candidate at an explicit projection's key joins that family even
when the ruled candidate drops out. Only a rule carrying `family` projects a family; an
identity-only rule names none and takes no part in the rule agreement check.

With these two edges a family without an explicit assignment holds exactly one effective id and
keeps the name `package:<id>`, so current names and pins are unchanged. Track-only resources need
no special case: the existing rules already forbid them an explicit family and forbid any other
candidate their id.

The stage order is identity corrections, then denials, then family formation, then selection.
A denied candidate, or one its source makes eligible for no variant, never joins or names a
family, so it cannot bridge two apps. A denial is reported under `package:<its own effective id>`,
or its explicit family when a rule assigns one. A pin on such a candidate fails as a conflict with
the denial or the ineligibility before the build-time family comparison, since the candidate has
no formed family to compare. A pin contradicting its selector's explicit projection has already
failed at policy load, whatever the denylist says.

A union-find over candidates in `composition_policy` computes this, and `merge` groups by the
result. Two explicit names in one family fail with both names and the joining candidates.

A rule-less candidate that shares an id with an explicitly assigned one joins that `app:` family,
which policy parsing cannot see because it does not know the other candidates. So the parse-time
pin-family check applies only to pins whose selector has an explicit `app:` projection, and the
build checks every other pin against the formed family. Offline pin checks match by rendered key
(effective id and normalized URL) and need no family name.

Alternatives considered:
- Keep package-id families and add a post-selection pass that drops lower-source entries on an id
  collision. This leaves two notions of identity, one for pairing and one for collisions, which is
  the mismatch behind the failures.
- Also join candidates from different sources at one repository URL. That needs ambiguity rules
  for a source listing several ids at one repository (RJNY lists melonDS stable and nightly at one
  repository), an exception for tracking resources, a repository-host classification, and naming
  for families holding several ids, and every current different-id pair already has an explicit
  rule.

### Pair rendered entries without provenance

Offline verification, the README catalog and the build's post-selection check share one pairing
function. It runs two whole passes, the second considering only entries still unpaired:
1. the same package id;
2. the same explicit family through the policy's projections.

No pass pairs two entries whose projections name different explicit families. Offline
verification rejects a package id repeated within a variant (the existing duplicate-id finding)
and an explicit family projected onto more than one entry within a variant. When either repeats
in one variant, the entries carrying that id or projecting that family in both variants are left
out of pairing and coverage and get no pairing or coverage finding, so a repeat in dual cannot
cascade into a coverage gap for its single counterpart. The denial, pin, overlay-target and
structural checks still consider those entries, and an entry violating both package-id and
explicit-family uniqueness gets both uniqueness findings. README generation fails instead. Each
pass therefore has at most one counterpart and nothing depends on entry order. Unpaired dual
entries become dual-only rows. A pair is labelled by its explicit family or `package:<shared
id>`, which matches the build's family name. The catalog has one row per pairing result, never
one per family: a package-id pair and an unpaired entry can carry the same explicit label, and
their rows are not merged; the rows' package ids break the ordering tie.

The rendered projection-conflict error for rule-less candidates is dropped: the projection
assigns a rule-less candidate at its key to that family. `duplicate_family` is removed rather
than replaced: the two uniqueness findings cover it.

### Reject families offline pairing cannot reproduce

A default family's winners share its one id and always pair. Inside an explicit family the
winners can carry different ids, and offline pairing sees only the rendered entries: such
entries pair only when each entry's effective id and normalized URL is a projection of that family. A rule on
a losing member is not enough. For example, rules assign `app:x` to RJNY `a` at URL X and RJNY
`c` at URL W, while rule-less extras `a` at Y and rule-less BBoi dual-preferred `c` at V join
through their ids and win; neither winner projects `app:x`. After selection the build requires
every family that publishes in both variants to pair under the shared function, and otherwise
fails naming the family and both entries and asking for a `family` rule on each selected entry
that does not yet project the family. This keeps offline verification and the README
provenance-free with the export format unchanged, and it is why offline pairing reproduces every
published family.

Alternatives considered:
- Persist family evidence in the outputs or a side file. That changes the export contract and
  makes verification depend on build provenance.

### Retire the distinct-family package check

Candidates sharing an effective id always form one family, so the check that different families
never place one package id in a variant can no longer fail. It is removed rather than kept as dead
code. The spec keeps the output guarantee that a package id occurs at most once per variant, and
offline verification checks it directly.

## Risks / Trade-offs

- [A reused template package id joins two unrelated games into one family, so one silently loses]
  → The loser appears in the report's `considered` list. A denial or an explicit family rule
  separates them.
- [An explicit family's winners do not both project the family, so they do not pair] → The error
  names the family and both entries and asks for a `family` rule on each. The committed exports
  confirm the current configuration has none.
- [A rule-less candidate that starts sharing an id with an explicitly assigned one moves into
  that `app:` family and breaks a pin naming `package:<id>`] → The build fails as wrong-family
  with the pin and the formed family identified; the curator renames the pin.

## Migration Plan

No configuration or data migration. Ship the code and specs together, then rebuild and confirm
that the exports and README are byte-identical. To roll back, revert the change. The policy file
is untouched in both directions.
