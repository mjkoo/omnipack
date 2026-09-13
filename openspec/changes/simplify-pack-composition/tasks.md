## 1. Configuration features nothing uses

- [x] 1.1 Retire historical family mappings. Remove the `history` field from `parse_composition_policy`, `CompositionPolicy.history` and `historical_family`. In the same commit, delete the `history` array from `config/composition.json` and from `tests/fixtures/source-generation/codm/pre-migration-config/composition.json`, which the captured baseline regression parses with current code. Remove `_family_changes` and the `familyChanges` field from report writing and `pack report` display. Verify with a test that a policy carrying `history` fails as an unknown field, that the policy and report tests pass, that `test_current_captured_baseline_reproduces_exact_exports_and_family_winners` passes, and that `git grep -n -E "historical_family|familyChanges|family_changes" src tests` finds nothing.
- [x] 1.2 Remove rule-level eligibility and preference (design decision 2). `CandidateRule` loses `eligibility` and `dual_preferred`, and `_parse_rule` accepts only `match`, `family`, `packageId` and `rationale`, so `eligible` and `dualPreferred` fail as unknown fields naming the rule and field. `_eligibility` goes. `Projection` carries the family only, and projection conflicts compare family only. `apply_composition_policy` no longer sets eligibility or preference, checks projected eligibility, or checks that preference implies dual eligibility. Offline verification's `ineligible_output` check goes in the same commit, since it read projected eligibility. Also in the same commit, delete the MetroidArch rule's `eligible` from `config/composition.json` and from the frozen pre-migration fixture's `composition.json`. Rewrite or delete the tests that give a rule `eligible` or `dualPreferred`:
  - the rule-application test asserting rule-set eligibility and preference;
  - the invalid-policy cases for `eligible`;
  - `test_projection_adopts_the_only_explicit_eligibility`;
  - `test_rjny_policy_can_revive_target_flags_but_not_export_exclusions`;
  - the eligibility half of `test_family_projection_pin_eligibility_and_history_are_distinct`;
  - `test_ingestion_applies_policy_before_coverage_and_after_generation`, whose higher-precedence candidate becomes single-only through RJNY export flags instead of a rule.

  Verify with tests for:
  - a rule carrying `eligible`, and a rule carrying `dualPreferred`, each failing with the rule and field identified;
  - two rules projecting one rendered key to different families still failing, with the projection exposing no eligibility;
  - an RJNY entry marked out of both exports contributing to neither pack;
  - an ordinary extra still losing dual to a dual-preferred lower-source candidate when no pin applies.

  Also verify that `git grep -n "ineligible_output" src tests` finds nothing and that the captured baseline regression passes with byte-identical exports.
- [x] 1.3 Replace extras `variants` with `dualScreen` (design decision 2). `extras.fetch` reads an optional boolean `dualScreen`, default false. An entry without it is eligible for both packs. An entry with `"dualScreen": true` is eligible for dual only and dual-preferred, as every other source marks its dual-only builds. A non-boolean `dualScreen` fails naming the entry. `variants` and `dualPreferred` fail naming the entry and field. `dualScreen` stays out of the rendered record. In the same commit, drop `"variants": ["single", "dual"]` from the nine both-pack entries of `config/extras.json`, turn MetroidArch's `"variants": ["dual"]` into `"dualScreen": true`, and migrate the frozen pre-migration fixture's `extras.json` the same way. Rewrite `test_extras_requires_named_fields`, `test_extras_defaults_variants_derives_source_and_validates_subset` and `test_extras_rejects_empty_variants_and_invalid_dual_preference` for the new field. Verify with tests for:
  - an entry without `dualScreen` eligible for both packs and not dual-preferred;
  - a `"dualScreen": true` entry eligible for dual only and dual-preferred;
  - a non-boolean `dualScreen` failing with the entry named;
  - `variants` and `dualPreferred` each failing with the entry and field named;
  - `dualScreen` absent from the rendered record.

  Also verify that the captured baseline regression passes with byte-identical exports, with MetroidArch still in dual only, and that the MetroidArch curation tests pass.
- [x] 1.4 Make denials package-only and both-variant. `parse_exclusions` accepts exactly `id` and `reason`; `_Exclusion` and `StaleExclusion` lose `family` and `variant`; `_validate_coverage` and the offline coverage check lose their exemption branch. Rewrite existing tests that use family or variant-scoped denials to use package denials, including the pin-failure diagnostic regression, whose unrelated denial becomes a package denial recorded as a removal from every variant its candidate is eligible for. Verify with tests for:
  - a denylist entry with a `family` or `variant` field failing with the entry and field identified;
  - a denial matching no candidate reported stale without failing;
  - a package denial leaving a different-package alternative selectable in dual;
  - a package denial naming a package id carried by both a family's baseline build and its dual-screen build, where the family has no other build, removing both builds and leaving the family absent from both packs;
  - a three-build family whose baseline and dual-screen builds share the denied package id and whose other baseline build, with a different package id and eligible for both packs, survives the denial and is selected in both packs;
  - a single-selected family whose only dual-eligible candidate is denied failing coverage in both the build and offline verification.
- [x] 1.5 Narrow offline verification and move verification reports to schema 3 (design decisions 6 and 8), before either input file is deleted. `OfflineInputs` holds the two packs, denylist, overlay and policy, and the build's offline gate stops reading `config/overlay.dual.json` and `config/settings.json`. Offline verification drops the dual-overlay stale check, the pack settings and category colour comparison (`_validate_pack_settings`), the default-key completeness check and the GitLab URL check; the `ineligible_output` check went in 1.2. It keeps the known-setting type, HTML step, request header and `preferredApkIndex` checks, narrowing `_validate_additional` rather than removing it. `validate_offline` returns a tuple of findings, with no `ValidatedEntry` or `OfflineResult`. Kept checks keep their finding codes. In the same commit, `verify.INPUT_PATHS` become `single`, `dual`, `deny`, `overlay`, `composition` and `readme`, `SCHEMA_VERSION` becomes 3 and `VERIFIER_VERSION` becomes `2.0.0`. `pack report` requires schema 3 with exactly those inputs and directs a schema 2 report to `pack verify`. Verify with tests for:
  - an object `additionalSettings` failing with variant, id and field;
  - duplicate ids in one variant and a mistyped known setting in the other both reported;
  - a known setting of the wrong type, a malformed HTML step, a malformed request header, and a boolean or string `preferredApkIndex` each failing with its existing finding code;
  - an unknown setting accepted;
  - an unsupported `overrideSource` failing;
  - an entry whose settings lack a default key passing when every other check passes;
  - the report fingerprinting exactly the six captured inputs;
  - a schema 2 report producing the regeneration diagnostic;
  - an overlay change marking a schema 3 report stale.

  Remove the tests for the dropped checks. Also add a CLI test that runs `pack build` on fixture sources, then `pack verify`, then `pack report`. It asserts that each exits zero, that neither the build's offline gate nor `pack verify` records a finding, and that `pack report` displays the build selections and labels the verification current. This build, verify and report sequence test must pass at this commit and at every later one.
- [x] 1.6 Remove the dual-screen overlay. `compose` takes one overlay, and the CLI and build composition drop the dual overlay; offline verification and the verification report stopped reading it in 1.5. Delete `config/overlay.dual.json` and its frozen copy `tests/fixtures/source-generation/codm/pre-migration-config/overlay.dual.json`. Remove every remaining reader and mention in tests and fixtures: the captured-baseline harness in `tests/test_source_generation_fixtures.py`, which reads both the frozen copy and the live file; `tests/test_reconciliation_curation.py`; the test setups that write the file into temporary roots; and its entry in `tests/fixtures/source-generation/codm/baseline/index.json`. Add no check or compatibility handling for the path. Verify with tests for:
  - one record patching the same id-and-URL pair in both variants;
  - a selector matching only the dual output being valid and applying only there;
  - a selector matching neither variant failing in the build and being reported stale by offline verification.

  Also verify that `git grep -n "overlay.dual" src tests config` finds nothing, that `git ls-files` lists no file named `overlay.dual.json`, that the captured baseline regression passes with byte-identical exports, and that the build, verify and report sequence test passes at this commit.
- [x] 1.7 Remove the pack settings configuration. `render(apps)` emits a settings block holding only `categories`, and the build, `source_generation._render_catalog` and every test call it without settings. Delete `config/settings.json` and its frozen copy `tests/fixtures/source-generation/codm/pre-migration-config/settings.json`. Remove every remaining reader and mention in tests and fixtures: the captured-baseline harness in `tests/test_source_generation_fixtures.py`, which renders with the frozen copy; the test setups that write the file into temporary roots; and its entry in the baseline index. Add no check or compatibility handling for the path. Offline verification and the verification report stopped reading it in 1.5. Verify with render tests for derived colours, repeatable across runs, and for a category used in one variant being absent from the other's block. Also verify that `git grep -n "settings.json" src tests config` finds nothing, that `git ls-files` lists no file named `settings.json`, that the captured baseline regression still passes with byte-identical exports, and that the build, verify and report sequence test passes at this commit.
- [x] 1.8 Delete the 7 single-screen pins from `config/composition.json`. Update any test that expects those families' single-screen selection reason to be `pin`. Add a regression test that composes the committed configuration and asserts that each of the 7 curated extras, Aurora Store, idTech4A++, VCMI, Julius, Xash3D FWGS, Ghostship and Gen1Recomp, is the single-screen winner of its family by effective id and normalized project URL. This test is the guard that replaces the single pins: without them, `pack build` and offline verification no longer fail when single stops serving one of these extras. Verify that the new test passes and fails when one of these extras is made a dual-screen build with `"dualScreen": true`, that `test_current_captured_baseline_reproduces_exact_exports_and_family_winners` passes with byte-identical exports, and that the curation and port-curation tests pass.

## 2. One policy pass and the app model

- [x] 2.1 Apply the composition policy once (design decision 1). `ingest_all` takes no policy and returns unmodified candidates. codm2000 suppression reads each higher-precedence candidate's own dual eligibility, with no early policy application or lookup. `compose` calls `apply_composition_policy` once. That pass applies identity and family rules and validates candidate-rule selectors against the admitted set, and it no longer validates pins. Package exclusions are then processed and recorded. Pin validation runs after them and before any family is selected, against the admitted candidates after identity and family rules, as today: presence, the pin's family, source eligibility for the target and conflict with a denial. Remove the `require_all` and `validate_pins` parameters, `IngestionResult.policy` and `.policy_bytes`, and `IngestionReport.skipped` with its `skipped` report field. Verify with tests for:
  - a higher-precedence candidate that its source makes dual-eligible suppressing the matching codm2000 entry;
  - a higher-precedence candidate eligible for single only, such as an RJNY entry left out of the dual-screen export, not suppressing it;
  - codm2000 suppression following the higher-precedence candidate's source dual eligibility when a candidate rule changes that candidate's family or package id;
  - a rule naming a suppressed codm2000 entry failing as unmatched;
  - a pin naming an absent candidate failing;
  - a dual pin naming a family's BBoi standard build selecting it in dual over the family's dual-screen build that shares its package id, with the dual selection's reason `pin` and the dual-screen build selected in neither pack;
  - the pin-failure diagnostic regression still passing. A missing pin, and a pin whose candidate is ineligible for its target, each fail after exclusions, with a package denial of an unrelated candidate recorded as a removal and an unmatched denial recorded as stale.

  Also verify that `git grep -n "apply_composition_policy(" src` finds exactly one call outside `composition_policy.py`, and that `ingest_all` has no policy parameter.
- [x] 2.2 Finish the app model (design decision 10). Remove `App.variant` and the unset-eligibility default, and make `eligibility` required. Replace the stored `dual_preferred` with a property derived from eligibility, true exactly when the build is eligible for dual only. Drop the `variant` and `dual_preferred` parameters from `normalize_record` and the adapters, and reduce `ComposedApp` to a family plus a data dict. Update overlay application, rendering and `source_generation._render_catalog`. Verify with tests for:
  - a dual-only extra (`"dualScreen": true`) being preferred in dual: it wins dual over a dual-preferred lower-source candidate of its family when no pin applies;
  - each source's dual-only builds, and no other builds, being dual-preferred.

  Also verify that `just typecheck` and `just test` pass and that the captured baseline regression still passes.

## 3. Selection records and report schemas

- [x] 3.1 Slim selection records (design decision 7). `FamilySelection` keeps the family, variant, winner identity, reason and `considered`. Remove `Displacement`, `SelectionAlternative`, the loss reasons, the differing-field computation and the `displacements` report field. In the same commit, `pack report` reads the new selection shape: it displays each selection's winner, reason and considered candidates, and no longer requires `alternatives`, eligibility or preference on a selection. Verify with tests for:
  - each of the four reasons: pin, dual-preferred, ordinary-fallback and source;
  - `considered` excluding the winner and denied candidates;
  - an identity-corrected winner recording both original and effective ids;
  - a failed composition preserving the selections, removals and stale exclusions collected before the failure;
  - a selection in the new shape displayed by `pack report` with its reason and considered candidates.

  Also verify that the build, verify and report sequence test passes at this commit.
- [ ] 3.2 Write build reports as schema 3 with exactly the fields in design decision 8. `pack report` accepts only schema 3, and for any other schema, including a report without one, exits nonzero with a diagnostic telling the user to regenerate with `pack build`. Verify with tests for:
  - the written key set;
  - schemaless, schema 1 and schema 2 reports each producing the regeneration diagnostic;
  - the family-switch case, where the report lists the old package removed, the new one added, and the new winner in the selection.

  Also verify that the build, verify and report sequence test passes at this commit.

## 4. One check per command

- [ ] 4.1 Read the build's local inputs once (design decision 5). The CLI reads `sources.json`, `extras.json`, `deny.json`, `overlay.json`, `composition.json` and `README.md` into one snapshot at the start of `pack build`, and composition, the offline gate and catalog generation use those bytes. Remove `require_current_inputs` and its call sites. Verify with tests for:
  - a configuration or README file changed on disk after the snapshot, through a test hook, not failing the build, with the outputs reflecting the snapshot;
  - a failed README replacement still restoring both JSON files.

  Also remove the `input_changed` tests and verify that `git grep -n "input_changed" src tests` finds nothing.

## 5. Credential-free build HTTP

- [ ] 5.1 Split the HTTP client (design decision 9). `http.py` keeps the retrying plain `get` and `redact_url`. `omnipack/source_http.py` holds the credential-scoped client with `HttpConfig`, the redirect handler and bounded reads, used by `source_generation.py` and `package_id.py`. `pack build` constructs the plain client and never reads `config/http.json`. Move the credential, redirect and bounded-read tests with the code, keeping their assertions. Verify with:
  - a test that a build fetch with `GITHUB_TOKEN` set and no `config/http.json` present sends no Authorization header and succeeds;
  - the generation credential tests passing;
  - `git grep -n "http.json" src` finding only the generation side.

## 6. Documentation

- [ ] 6.1 Update `docs/composition.md`, `docs/verification.md`, `docs/development.md` and any other guide that describes the retired pieces, so each describes current behavior. In `docs/composition.md`, state the dual-screen build model in plain words:
  - every build is a baseline build or a dual-screen build, and an app's baseline build, when it has one, is what the single-screen pack uses;
  - absent a pin, a dual-screen build, when one exists, replaces the baseline in the dual-screen pack;
  - an app may instead have only a dual-screen build, which appears only in the dual-screen pack, as an app only codm2000 supplies does;
  - each source alone decides which kind a build is: BBoi by asset, codm2000 always dual-screen, RJNY by its export flags, and extras by `"dualScreen": true`;
  - a valid pin comes first: it selects the one candidate it names ahead of dual-screen replacement and source precedence, and nothing else makes the dual pack select a baseline build over an available dual-screen build;
  - to keep a family's baseline build in dual in place of its dual-screen build, pin the baseline build for dual, which works when the two share a package id, as the Zelda 3, Minish Cap and Harvest Moon 64 builds do;
  - a package denial removes every build carrying that package id from both packs and leaves the family's builds with other package ids selectable, so an app is absent from a pack only when no selectable build of its family remains there; those three families have no other build, so a denial of their shared package id removes each of those apps.

  The retired pieces are:
  - history records and family-change reporting;
  - candidate-rule `eligible` and `dualPreferred`, and extras `variants` and `dualPreferred`, replaced by extras `dualScreen`;
  - family and variant-scoped denials and coverage exemptions, stating that an app can no longer be published in single only;
  - the dual overlay and pack settings files, stating that an overlay record patches every pack that selects its id-and-URL pair and that a patch can no longer target one pack only;
  - per-alternative selection detail;
  - build HTTP credentials;
  - the removed offline checks, and the setting value checks that remain;
  - schema 2 reports.

  Verify with `just check-links`, a no-dash check, and a case-insensitive `git grep` over `docs/`, `README.md` and `AGENTS.md` that finds none of `"history"`, `"eligible"`, `"variants"`, `familyChanges`, `dualPreferred`, `overlay.dual`, `config/settings.json`, `loss_reason`, `differing_fields` or `displacements`.

## 7. Final checks and review

- [ ] 7.1 Run `just check-all` in the dev shell and `openspec validate simplify-pack-composition --strict`. Verify that both pass.
- [ ] 7.2 Build the base commit and the branch head back to back from clean exports of each, for example with `git archive`, and compare both packs and `README.md` byte for byte. Then run `uv run pack verify` on the branch. Verify that the outputs are identical and verification passes.
- [ ] 7.3 Write `openspec/changes/simplify-pack-composition/validation.md` with:
  - the test count against the 732 at the start of this change;
  - the implementation and test line deltas against 6,731 and 12,031;
  - the comparison from 7.2;
  - what remains unestablished, such as any device check.
- [ ] 7.4 Run an independent review of the branch diff against the delta specs and design, fix its findings, and re-run 7.1. Verify that the review's final pass reports no unresolved findings.
