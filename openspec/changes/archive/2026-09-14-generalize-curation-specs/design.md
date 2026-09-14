## Context

See proposal.md for motivation. These constraints shape the approach:

- OpenSpec 1.10 rejects a MODIFIED block that drops or renames a scenario.
  Every requirement whose scenarios name a project therefore has to be removed
  and re-added under a new name.
- A delta cannot change an existing capability's `## Purpose`; that line is
  edited directly in the main spec.
- The source workflow runs the full test suite with each candidate codm2000
  catalog in place before any PR write. The suite already has invariant tests
  parametrized over the committed catalog and a catalog with one project added
  and one removed. One test still asserts named projects in the committed
  catalog: Showdown-DS, Heimdall, Kanto Gear, and EmuLnk through suppression.
  Other tests read it too, three of them to check unique ids and normalized
  project URLs, canonical rendering, and kind-appropriate IDs and flags.
- The curated single-screen guard in `tests/test_port_curation.py` checks a
  hand-kept list of seven families. `config/extras.json` also carries curated
  extras outside that list that are eligible for single and whose families
  have no single pin, such as Cinderbox and the omnipack tracker. Of the nine
  committed extras eligible for single, seven have dual pins and none has a
  single pin; only Cinderbox and the omnipack tracker have no pin at all.
- `effective_settings` in `src/omnipack/source_generation.py` ends every
  track-only description with "Obtainium only tracks release notifications;
  acknowledgement does not install the mod or detect its installed version."
  The requirement it implements now covers any track-only resource. The
  committed catalog must equal the generator's rendering: an unchanged source
  regenerates byte-identically, and a tracker's committed entry is retained on
  a lookup failure only when the current rule reproduces it exactly. Kanto
  Gear is the only track-only resource in `config/codm-projects.json`.

## Goals / Non-Goals

**Goals:**

- Specs state generic rules; per-app values live only in reviewed
  configuration and tests. Once the change is archived, no main-spec
  requirement names an app, apart from the pack's own notification tracker.
- Every retired per-app fact stays either recorded in reviewed configuration
  or protected by an outcome check.
- No test can fail on a codm2000 catalog that composition, build, verification
  and catalog validation accept, with catalog validation defined by the checks
  it makes rather than by where they run. Composition here runs over the
  suite's frozen captured upstream records.
- Every curated extra that is eligible for single and whose family has no
  committed single pin is checked to win single, with no hand-kept list.
- Generated track-only descriptions are accurate for any track-only resource,
  and the committed catalog keeps reproducing what the generator renders.

**Non-Goals:**

- Changing production code or configuration beyond the generated track-only
  sentence and the one committed catalog entry that carries it; changing
  scripts or workflows, or documentation beyond setup notes for curated
  extras; editing rendered packs by hand.
- Removing or rewriting existing per-app tests other than the one that pins
  the automation-maintained catalog and the curated single-screen guard, which
  is rewritten to derive its set from configuration. Whether some of the others
  only restate configuration is a separate test-volume question.
  Implementation found two further tests that could fail a catalog the build
  accepts, the one-added-one-removed catalog helper and the Hollow Knight
  composition test's exact URL comparison, and fixed both at the user's
  direction.
- Renaming or splitting the pack-curation capability.

## Decisions

**Reviewed configuration is the record of per-app values.** Specs keep generic
rules, and tests check outcomes that depend on how composition combines
configuration with upstream records: overrides survive refreshes, and
designated curated extras win the single-screen pack. A curated extra is
designated when its `config/extras.json` entry is eligible for single, meaning
it is not a dual-screen build, and its family has no committed single pin. A
single pin is an explicit reviewed selection for that family, and composition
already fails when a pinned candidate is missing or ineligible, so the guard
steps aside for a pinned family rather than fail for as long as a reviewed pin
chooses another candidate. The guard derives that set from
`config/extras.json` and the committed single pins, so a newly curated extra
is covered with no hand-kept list.

The guard takes each extra's family the way composition assigns it. The
candidate rule whose selector matches the extras entry (source and origin
`extras`, the entry's id and normalized URL) gives the family: the rule's
`family`, or else `package:` plus the rule's `packageId`, or plus the entry's
id when the rule sets no `packageId`. An entry with no rule has family
`package:<entry id>`. Equivalently, the guard looks the family up in the
committed policy with the entry's effective, corrected id, never with an id a
rule corrects, since the policy keys its projections by effective id and falls
back to `package:<id>` for an id it does not know. The single-pin exclusion
uses the same family, and the expected single-screen winner carries the
effective id. No committed extras rule sets `packageId` today, so this matters
for the first correction added later: without it, the guard would name
`package:<uncorrected id>` while single still serves the extra.

The guard's failure test must displace an extra in a way composition accepts,
so that the guard's comparison, not a `CompositionError`, reports the family.
Composition validates pins after applying denials and before selection, and it
fails when a pinned candidate is denied, so denying the package id of a
dual-pinned extra tests the pin check instead of the guard. No composition rule
changes a build's eligibility, and an extra has the highest source precedence,
so a family or package-id rule cannot take single from it without composition
failing on ambiguous winners or the extra simply winning its reassigned
family. The displacement composition accepts is therefore a package denial of
an extra that no pin names. The test covers every designated extra: in its own
copy of the policy it drops each pin that selects the extra, which can only be
a dual pin because a designated family has no single pin, so the extra stays
designated; then it denies the extra's package id. As committed, only Cinderbox
and the omnipack tracker need no pin dropped. Alternatives rejected:
- keeping pack-curation as the designated home for per-app contract, which
  contradicts the project's spec rules and keeps a spec delta in every curation
  edit;
- adding committed-configuration assertions for every value, which duplicates
  the configuration in change-detector tests and, for the codm2000 catalog,
  would block valid source proposals;
- keeping the guard's hand-maintained list of families, which already leaves
  out Cinderbox and the omnipack tracker and would leave out every extra
  curated later.

**Replace rather than modify where a scenario is renamed.** Replacements get
names close to the old ones and carry their generic body text unchanged. The
composition change followed the same pattern. RENAMED plus MODIFIED was not
used because the renamed scenarios would still be dropped from the MODIFIED
block.

Implementation review found per-app examples in four requirements outside the
named projects' own: the Cemu illustration in the RJNY export-flag rule, the
Aurora Store scenarios of the source-type and GitLab identity requirements,
and the omnipack tracker's reference to the RJNY tracker. Three are modified
in place. "Public GitLab entries retain native source identity" is replaced
under a new name because its scenario is renamed, and the source-type
requirement that cites it now cites the replacement.

**No new requirement for "policies change only what they name".** Its generic
parts are already stated elsewhere:
- pack-composition forbids overlays from changing identity, URL or source type;
- pack-verification says verification does not evaluate version extraction or
  upstream health;
- pack-composition requires manifest evidence for identity corrections and
  matches denials by exact package id.

Restating them in pack-curation would create a second copy to keep in sync.

**Documentation duties fold into "Curation evidence states its limits".** The
per-app documentation clauses (MetroidArch configuration, Hollow Knight game
files, ports' game data, Xash3D's rolling channel, Kanto Gear's manual install)
become one duty: describe any user action a curated entry needs beyond
installing it. This duty is reviewed, not tested, as the per-app clauses were.
Dropping documentation duties entirely was rejected because a newly curated
app that needs setup would carry no obligation. A curated entry is an entry
maintained in `config/extras.json`; upstream entries that overlays or identity
corrections touch carry no setup duty. Ghostship and Pokémon Red/Blue Recomp
are curated extras that need a user-supplied ROM and were undocumented, so
this change adds setup notes to `docs/curation.md` for them and for any other
extra whose upstream needs user-supplied files. The duty to state each
maintained policy and its rationale stays. The sentence explaining that
automated source resolution, format lint and upstream-health publication gating
are retired is dropped, because it describes a finished transition, as the
upstream-tracker migration duty and the live-verifier scenario do.

**Tests reading the codm2000 catalog fail only where the build or catalog
validation would.** The co-authorities are composition, build and verification
with the committed configuration, and catalog validation. Catalog validation is
defined by content, not by where it runs:
- the catalog is an object with an apps list;
- entry ids are unique;
- no two entries share a normalized project URL;
- each entry's id and flags suit its kind: an APK entry carries a
  syntactically valid Android manifest package id and is not track-only, and a
  track-only entry carries a numeric-string resource id with `trackOnly` true
  and version detection, ZIP extraction and APK architecture filtering
  disabled;
- the file's bytes are the canonical rendering of its entries.

None of these checks depends on which projects the catalog contains or how
they resolved, so a test asserting particular committed ids or projects is not
part of catalog validation. Defining it by where it runs was rejected because
the source workflow has no separate validation step: its check job generates,
stages, runs the test suite, builds and verifies, and staging checks file type
and generation status, not catalog contents. A definition by location would let
any test in the suite count as validation. The named-project test is rewritten
to compose a small fixture codm2000 catalog with the frozen captured higher
sources. The fixture holds:
- an APK entry with prerelease settings and no higher coverage;
- a track-only resource that extends an app a higher source provides;
- an entry whose URL a dual-eligible higher-source candidate covers.

It asserts the same semantics without depending on committed contents. The
Hollow Knight composition test also reads the committed catalog, but only
entries that reviewed overlay records target. A catalog dropping or moving them
already fails the build on a stale overlay, so it stays, with its URL
assertion comparing normalized URLs as overlays do.

Composition in this rule means composition over the suite's frozen captured
upstream records. The source workflow builds from live records, and the suite
cannot promise results against records it does not hold, so a catalog whose
composition depends on upstream records newer than the captures, such as an
overlay target that only a live upstream supplies, is outside the guarantee.
Implementation found two tests that could fail a catalog the build accepts:
the one-added-one-removed catalog helper removed whichever entry sorted last,
which could be one composition depends on, and the Hollow Knight test compared
exact URL strings. Both were fixed at the user's direction.

Other code performs some of these checks. Ingestion, which `pack build`
reaches through the codm2000 source's `fetch`, rejects a document that is not
an object with an apps list and rejects duplicate ids. Source generation
rejects duplicate ids and duplicate normalized project URLs in the committed
catalog it reads as the accepted catalog, rejects duplicate ids in its
candidate, and renders the candidate it writes canonically. Composition itself
does not load the catalog; it composes the records ingestion returns.
Generation reads the committed catalog before staging replaces it, so in the
source workflow nothing but tests checks the staged file for duplicate
normalized project URLs, canonical bytes, or kind-appropriate ids and flags.
Three tests do: the test that entry ids and normalized project URLs are unique,
the test that the catalog's bytes are the canonical rendering of its entries,
and the test that each entry's ID and flags suit its kind. All three stay with
their assertions intact. They are where the workflow currently performs those
three checks, and a catalog they reject fails catalog validation, so it would
be blocked from publication anyway.

**The pack-curation Purpose is edited directly** during implementation, since
deltas do not carry Purpose. New text: pack-curation defines how curated app
decisions are recorded, protected and documented, plus the pack's own
notification tracker and the exclusion of upstream pack trackers.

**The upstream-tracker migration duty is dropped.** It served users who
imported RJNY's tracker before its exclusion, a finished transition. The
denial itself stays, and the rule is stated without the tracker's id.

**Generated track-only descriptions say "the resource".** The generated
sentence becomes "Obtainium only tracks release notifications; acknowledgement
does not install the resource or detect its installed version." A track-only
resource need not be a mod, and the rule's own rationale and installation
text, which come before the sentence, still say what the resource is. The
existing fixture assertion checks the substring "acknowledgement does not
install", which the new wording keeps.

The Kanto Gear entry in `config/catalogs/codm.json` is rewritten in the same
change to exactly what the changed generator renders for its committed rule.
Leaving it for the next source run was rejected, for three reasons:
- an unchanged source must regenerate the committed catalog byte-identically;
- a tracker's entry is retained on a lookup failure only when the current rule
  reproduces it exactly, so a stale entry would block retention during an
  upstream outage;
- the next scheduled source run would propose the rewording as a catalog
  change of its own.

`dist/` is not edited by hand. The nightly rebuild renders the dual-screen pack
from the committed catalog and picks up the wording. The single-screen pack
has no codm2000 entries, since those are dual-only. The committed entry's
agreement with its rule is checked once during implementation rather than by a
permanent test, because a test asserting a committed catalog entry would fail
on catalogs that catalog validation accepts.

## Risks / Trade-offs

- [A retired fact loses its only protection] → An audit maps each retired fact
  to its reviewed configuration and, where the fact is a composed outcome, to a
  check. An outcome with no check gets a test before the specs change.
- [Documentation drifts with no test] → Accepted. No curation document was
  tested before this change either.
- [A removed requirement name is still cited] → No spec, document, test or
  configuration file cites any of the sixteen removed names, the eight retired
  and the eight replaced, outside its own spec file. The implementation
  re-checks every one of them before the specs are synchronized.
- [The committed tracker entry drifts from the generator] → Implementation
  renders the committed track-only rule through `effective_settings` and
  compares the result with the committed entry, and confirms that no other
  catalog entry changes.
- [A test still depends on committed codm2000 contents] → Implementation runs
  the full suite against a candidate catalog. The candidate drops projects that
  no reviewed configuration references and re-resolves one. It is an object
  with an apps list, rendered canonically, with unique ids, unique normalized
  project URLs and kind-appropriate IDs and flags, so it passes all five
  catalog-validation checks, and the suite must pass.
- [An extra in the derived set does not win single as committed] → The guard
  rewrite stops and reports the entry instead of editing configuration, since
  changing a curated selection is outside this change.

## Migration Plan

None for users. On its next nightly rebuild, the dual-screen pack's Kanto Gear
description changes by one word. No identity, selection or other setting
changes, and the single-screen pack is unaffected. Archiving applies the deltas;
`openspec validate --specs --strict` must pass afterwards.
