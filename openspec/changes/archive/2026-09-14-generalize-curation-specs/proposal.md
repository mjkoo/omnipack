## Why

The main specs restate individual apps' curated values: package ids, URLs,
release channels, regexes, names and setup notes. That data already lives in
reviewed configuration, so every curation edit needs a matching spec delta, and
the copies in the specs rot. They carry a finished change's acceptance
criterion, a date stamp, a scenario about a transition that has ended, and an
installed-app comparison scenario that no code implements. The project's spec
rules already say per-app data belongs in configuration and tests, not in
normative requirements.

One test has the same problem in code. It asserts Showdown-DS, Heimdall and
Kanto Gear by name against the automation-maintained codm2000 catalog. The
source workflow runs the full test suite before it writes a PR, so a proposal
whose catalog is well formed, free of duplicate ids and project URLs,
kind-consistent and canonically rendered, and
that builds and verifies, but drops or re-resolves one of those projects would
fail its own check.

A second test keeps a hand-maintained list of the curated extras that must win
the single-screen pack. The list already leaves out curated extras such as
Cinderbox and the omnipack tracker, and it would leave out any newly curated
extra too, so single could stop serving one with no failing check.

The source generator carries the same per-app assumption in one sentence. It
tells users that acknowledging any track-only resource's notification "does not
install the mod", although the track-only rule covers any resource, and a
resource need not be a mod.

## What Changes

- **pack-curation becomes generic.** It keeps the omnipack notification
  tracker, which is this project's own feature, and three generic rules:
  - curated decisions live in reviewed configuration, and regression checks
    assert the outcomes that depend on how the pipeline combines that
    configuration with upstream records. A test that reads the
    automation-maintained codm2000 catalog fails only where composition over
    the suite's frozen captured upstream records, build, verification or
    catalog validation would also reject it. Catalog
    validation is defined by what it checks: the catalog is an object with an
    apps list, entry ids are unique, no two entries share a normalized
    project URL, each entry's id and flags suit its kind, and the file's
    bytes are the canonical rendering of its entries. None of
    these depends on which projects the catalog contains, so a test asserting
    particular committed ids or projects is not part of it;
  - curation documentation states each maintained policy and its rationale,
    and describes the user action a curated entry, one maintained in
    `config/extras.json`, needs, within stated evidence limits;
  - an upstream catalog's own pack tracker is excluded.

  Eight per-app requirements are removed: Cinderbox, numeric app versions,
  source-version tracking, the curated store and ports, Xash3D, Hollow Knight,
  the reviewed installed applications and MetroidArch. Their values stay in
  `config/` and their existing tests stay. The curated single-screen guard,
  which the spec states for the curated store and established ports and a test
  checks against a hand-kept list of seven families, becomes a generic
  obligation for every designated curated extra: each `config/extras.json`
  entry that is eligible for single and whose family has no committed single
  pin. A single pin is an explicit reviewed selection for its family, and
  composition already fails when a pinned candidate is missing or ineligible,
  so the check steps aside for a pinned family. The check derives that set
  from configuration, so it also covers Cinderbox, the omnipack tracker and
  any extra curated later.

  The curation documentation requirement keeps its duty to state each
  maintained policy and its rationale. It drops the sentence explaining that
  automated source resolution, format lint and upstream-health publication
  gating are retired, because that sentence describes a finished transition.
  The omnipack notification tracker requirement now refers to the generic
  upstream tracker exclusion instead of the RJNY tracker.
- **readme-source-generation drops its named projects.** The initial-policy
  paragraph naming EmuLnk, Showdown-DS, Heimdall and Kanto Gear goes. Its
  generic rules stay: unconfigured projects keep their fallback default, and
  consumer fallback never changes which release the generator resolves. The
  Kanto Gear paragraph becomes a generic rule for track-only resources:
  dual-only, never replacing the app they extend, with guidance that
  notifications do not install anything. The Heimdall and Kanto scenarios are
  restated generically.
- **source-ingestion** drops the EmuLnk scenario, which restates the existing
  dual-coverage suppression scenario, and restates the Showdown-DS, Heimdall
  and Kanto scenarios generically. It also drops the Cemu illustration from
  the RJNY export-flag rule, restates its Aurora Store GitLab scenarios for any
  GitLab extra, and replaces "Public GitLab entries retain native source
  identity" under a new name because one of its scenarios is renamed.
- **pack-cli** restates its Kanto scenario for any track-only rule.
- **pack-composition** drops one sentence naming Zelda 3, Minish Cap and
  Harvest Moon 64, which only illustrated the rule before it.
- **Two tests are rewritten.** The codm2000 composition test checks its
  semantics with fixture catalog entries instead of named entries in the
  committed catalog. The curated single-screen guard derives its designated set
  from `config/extras.json` and the committed single pins instead of a
  hand-kept list. It takes each extra's family the way composition assigns it,
  following any candidate rule's `packageId` correction. Its failure test
  displaces an extra in a way composition accepts, so the guard's own
  comparison is what reports the family.
- **Two more tests are fixed, at the user's direction during
  implementation.** The one-added-one-removed catalog helper removed whichever
  entry sorted last, which could be one composition depends on; it now removes
  only an entry nothing depends on. The Hollow Knight composition test compared
  exact URL strings where overlays match normalized ones; it now compares
  normalized URLs. Each could otherwise fail a catalog the build accepts.
- **Setup notes for curated extras.** `docs/curation.md` gains a setup note
  for every `config/extras.json` entry whose upstream needs user-supplied
  files. Ghostship and Pokémon Red/Blue Recomp need a user-supplied ROM and
  were undocumented.
- **The generated track-only description says "the resource".** The sentence
  that `src/omnipack/source_generation.py` appends to every track-only entry
  becomes "Obtainium only tracks release notifications; acknowledgement does
  not install the resource or detect its installed version." In the same
  change, the Kanto Gear entry in `config/catalogs/codm.json`, the only
  track-only entry, is rewritten to exactly what the changed generator renders
  for its committed rule. An unchanged source must regenerate byte-identically,
  and a tracker's entry is retained on a lookup failure only when its rule
  reproduces it exactly. `dist/` is not edited; the dual-screen pack picks up
  the wording on its next nightly rebuild.

That sentence and that one catalog entry are the only production code or
configuration changes. No script or workflow changes; the only documentation
change is the setup notes in `docs/curation.md`, and no rendered pack is
edited by hand. Nothing is **BREAKING**: every retired
statement describes values that the committed configuration still carries, and
the only output change is one word in a track-only entry's description, which
changes no identity, selection or other setting.

### Retired and added

- Retires 8 requirements outright, all in pack-curation.
- Replaces 8 requirements with generic ones under new names, because OpenSpec
  rejects a MODIFIED block that drops or renames a scenario: 2 in
  pack-curation, 3 in readme-source-generation, 2 in source-ingestion and 1 in
  pack-cli.
- Modifies 5 requirements whose scenarios keep their names: curation
  documentation, the omnipack notification tracker, the dual-screen build
  model, RJNY export flags and supported source types.
- Adds no new requirement.
- Scenarios: about 19 retired and 3 new, all in pack-curation and
  source-ingestion. pack-curation falls from 24 scenarios to about 8. The
  readme-source-generation, pack-cli and GitLab scenarios are restated, not
  removed.
- Estimated implementation change: one word in the generated track-only
  sentence in `src/omnipack/source_generation.py`, and the same word in one
  entry of `config/catalogs/codm.json`.
- Estimated test change: about 45 lines rewritten in the codm2000 composition
  test and about 45 in the curated single-screen guard, including the family
  derivation that follows a `packageId` correction, net change near zero. The
  wording change needs no test edit: the existing assertion checks a substring
  that the new wording keeps.

No new or replacement requirement concerns retries, ownership, races or
diagnostic formats. The documentation requirement concerns evidence only in
the sense of what curation docs may claim; it narrows the existing requirement
and adds no runtime mechanism.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-curation`: per-app requirements removed; regression checks, curation
  documentation and the upstream tracker exclusion restated as generic rules;
  the omnipack notification tracker keeps its rules and now refers to the
  generic upstream tracker exclusion.
- `readme-source-generation`: reviewed rules, APK package-ID resolution and
  track-only resources restated without named projects; the generated
  track-only description no longer calls every resource a mod.
- `source-ingestion`: committed codm2000 semantics restated without named
  projects; the RJNY export-flag, source-type and GitLab identity requirements
  lose their per-app examples.
- `pack-cli`: the source-generation command's track-only scenario restated
  generically.
- `pack-composition`: the dual-screen build model loses its per-app
  illustration.

## Impact

- Specs: `openspec/specs/pack-curation/spec.md` shrinks from 346 lines to
  roughly 100; the other four specs change locally.
- Tests: `tests/test_source_generation_fixtures.py` rewrites
  `test_committed_codm_entries_keep_their_source_semantics_in_composition`
  against fixture entries, and `tests/test_port_curation.py` rewrites the
  curated single-screen guard (`CURATED_SINGLE_WINNERS`,
  `curated_single_mismatches` and the tests that use them) to derive its set
  from configuration. The one-added-one-removed catalog helper and the Hollow
  Knight composition test's URL comparison are also fixed. Other per-app tests
  stay.
- Code: `src/omnipack/source_generation.py` changes "the mod" to "the
  resource" in the generated track-only description. No other `src/` change.
- Configuration: `config/catalogs/codm.json` rewrites the Kanto Gear entry's
  description to what the changed generator renders. No other configuration
  changes.
- Rendered packs: not edited by this change. `dist/dual-screen.json` and the
  Kanto Gear import link in the README catalog pick up the new wording on the
  next nightly rebuild; `dist/single-screen.json` has no
  track-only codm2000 entry and does not change.
- Docs: `docs/curation.md` gains setup notes for curated extras that need
  user-supplied files. No change to `scripts/`, `README.md` or workflows.
