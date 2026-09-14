## Why

The composition side of the pipeline carries machinery that affects no output.
Some of it re-checks bytes it already produced. The rest is configuration
generality nothing uses:

- 113 historical family records exist only to classify previous outputs in a
  report nobody reads.
- The composition policy is applied three times per build.
- A build's device eligibility and dual preference can be set by its source, by
  a candidate rule and by an extras entry. Some combinations fail composition
  instead of doing what was meant. A rule restricting a BBoi dual asset to
  single ties it with its standard sibling for the single-screen winner rather
  than keeping the standard build in dual.
- The selection report explains every losing candidate at length.
- Offline verification re-checks parts of render's own output that render
  guarantees by construction: default-key completeness and category colours.

Narrowing these to what actually shapes the packs makes the curation rules
easier to follow and change. For the current configuration, both packs and the
README stay byte-identical.

## What Changes

- **Retire historical family mappings.** Remove the policy's `history` array
  (113 records), its validation and the build report's family-change
  classification. The build report keeps its plain added/removed package-id
  diff. **BREAKING** for a policy file that still carries `history`, which
  becomes an unknown field.
- **One dual-screen build model.** Every build is a baseline build or a
  dual-screen build. An app's baseline build, when it has one, is what the
  single-screen pack uses. Absent a pin, a dual-screen build, when one exists,
  replaces the baseline in the dual-screen pack. An app may instead have only a
  dual-screen build, which appears only in dual. Only a build's source decides
  its kind:
  - BBoi's standard asset gives baseline builds and its dual asset dual-screen
    builds;
  - every codm2000 entry is a dual-screen build;
  - RJNY entries in both exports are baseline builds, dual-only entries are
    dual-screen builds, and single-only entries are baseline builds that
    upstream keeps out of dual;
  - extras are baseline builds unless marked `"dualScreen": true`.

  A build is dual-screen exactly when it is eligible for dual only, and dual
  preference is derived from that. The only preference change is that a
  dual-only extra becomes preferred in dual. MetroidArch is the only one, and
  its family's dual pin already selects it. A valid pin still comes first: it
  selects the one candidate it names, ahead of dual-screen replacement and
  source precedence, so a dual pin can keep a baseline build in dual in place
  of an available dual-screen build. Nothing else can. Seven of the eight
  committed dual pins name curated baseline extras.
  - **BREAKING**: candidate rules reject `eligible` and `dualPreferred` as
    unknown fields. Rules keep `match`, `family`, `packageId` and `rationale`.
    The only `eligible` rule, MetroidArch's `["dual"]`, restates its extras
    entry and is removed.
  - **BREAKING**: extras replace `variants` with an optional boolean
    `dualScreen`, default false. `variants` and `dualPreferred` fail. A
    single-only extra can no longer be written; none exists.
- **Apply the composition policy once.** Ingestion takes no policy and returns
  unmodified candidates. Composition applies identity and family rules and
  validates candidate-rule selectors in one pass. Denials are processed next.
  Pins are validated after them and before selection, so a failed pin still
  leaves the denial removals and stale exclusions in the build report. The
  codm2000 dual-coverage check reads each higher-precedence candidate's source
  dual eligibility, which no rule can change, so suppression is unchanged.
- **Finish the internal app model.** Drop the per-variant field and its
  transitional defaults, and derive dual preference from eligibility instead of
  storing it. A composed entry becomes its family plus its data. No observable
  change.
- **Remove configuration features nothing uses:**
  - A denylist entry names only a package `id` and a reason and always applies
    to both variants. **BREAKING**: `family` and `variant` fields fail as
    unknown. With both-variant package denials only, a denial can never leave a
    single-screen winner without a dual counterpart, so the dual-coverage
    exemptions go too. An app can no longer be published in single only. A
    denial removes every build carrying its package id from both packs, and the
    family's builds with other package ids stay selectable, so an app leaves a
    pack only when none of its builds remains selectable there. For Zelda 3,
    Minish Cap and Harvest Moon 64 the standard and dual builds share one
    package id and those families have no other build, so a denial of that id
    removes the app. To keep one of these apps' standard build in dual in
    place of its dual build, pin the standard build for dual instead. A
    per-build exclusion is deferred until a real case needs it.
  - Delete `config/overlay.dual.json` and `config/settings.json`, both empty,
    together with every code path, test, fixture and document that reads or
    names them, including the frozen pre-migration fixture copies and the
    captured-baseline harness code that reads those copies. No check or
    compatibility handling for either path is added. One overlay file applies
    to both variants: a record patches every pack that selects its id-and-URL
    pair. Per-pack patches are retired with no replacement, so a patch can no
    longer target one pack only. The dual overlay holds no records, so nothing
    moves. The rendered settings block holds only the derived category colours.
  - Remove the 7 single-screen pins. Each names the only extra in its family,
    and extras always win single-screen selection, so for the current
    configuration the pins select nothing the precedence rule would not. They
    were also a guard: without them, `pack build` and offline verification no
    longer fail when single stops serving one of these curated extras. A
    regression test asserting that each is its family's single-screen winner
    under the committed configuration takes over that guard.
  - Build ingestion fetches upstream catalogs without credentials and no
    longer reads `config/http.json`. Exact-host credentials, redirect
    re-authentication and bounded reads stay with source generation, their only
    user.
  - The selection report records each winner, the candidates considered and a
    one-line reason. It no longer has per-alternative loss reasons, differing
    fields or a separate displacement list.
- **One check per command.** The build validates rendered bytes once, against
  the configuration bytes it composed with. It no longer re-reads README or the
  policy mid-build to detect concurrent edits. Offline verification keeps a
  minimal entry shape, the setting value checks, composition consistency and
  the catalog comparison. It drops the default-key completeness, pack settings
  and category colour checks, which render guarantees by construction, the
  GitLab URL check, which ingestion enforces, and the projected-eligibility
  check, since rules no longer declare eligibility. It keeps the known-setting
  type, HTML step, request header and `preferredApkIndex` checks. Upstream
  records and overlay patches supply those values and render copies them
  unchecked, so offline verification is their only gate before publication.
- **Report schemas.** Build reports move to schema 3, without `skipped`,
  `familyChanges` or `displacements`. Verification reports move to schema 3,
  whose fingerprints no longer cover the two deleted files. Older reports of
  either kind, including schemaless build reports, produce a diagnostic telling
  the user to regenerate them with `pack build` or `pack verify`.
- Delete the dead ingestion and offline-result fields left over from earlier
  changes.

### Retired and added

- Retires 1 requirement outright: historical family mappings.
- Adds 1 requirement: the dual-screen build model.
- Replaces 11 requirements with narrower ones under new names. OpenSpec refuses
  a MODIFIED block that drops a scenario, so each is removed and re-added
  rather than modified.
- Modifies 12 more requirements whose scenarios all survive, some reworded.
- Across the touched requirements, scenarios stay at 103: about 19 retired,
  about 19 new. The retired ones cover history classification, family and
  variant-scoped denials, dual-coverage exemptions, the dual overlay,
  configured pack settings, default-completeness and GitLab URL verification,
  alternative explanations, extras `variants` and mid-build README edits. The
  new ones mostly reject retired configuration fields or pin down the narrower
  scope. They include the dual-screen build model, a dual pin keeping a
  baseline build that shares its dual-screen build's package, extras
  `dualScreen`, the kept setting-value checks and the build-report
  regeneration diagnostic.
- Estimated implementation change: about 850 lines removed and 80 added. Most
  of the removals are in `offline.py` (about 355), `report.py` (about 150),
  `merge.py` (about 110) and `composition_policy.py` (about 100). The HTTP split
  mostly moves code, saving little.
- Estimated test change: about 1,000 lines removed and 200 added, mostly in
  offline, policy, report, source and composition tests.

None of the replacement requirements adds a guarantee about retries,
ownership, races or evidence; each is narrower than the one it replaces. The
new requirement states the model the sources already produce, with the one
preference change for dual-only extras. The only diagnostic-format change is
the build-report regeneration message, and it already is the
visible-failure-plus-rerun answer: an unreadable old report is replaced by
rerunning `pack build`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-composition`: the dual-screen build model, where each build's kind comes
  from its source and no rule changes eligibility or preference; remove
  historical mappings; package-only both-variant denials; pins ahead of
  dual-screen replacement, so a dual pin can keep a baseline build in dual in
  place of a dual-screen build; one overlay file; dual coverage without
  exemptions, so no app is published in single only; slimmer selection
  reporting.
- `pack-cli`: build report without family-change classification, displacement
  detail or `skipped`; build report schema 3 with a regeneration diagnostic;
  no mid-build README edit detection.
- `source-ingestion`: each source alone decides a build's kind, with no policy
  override; ingestion reads no policy, and codm2000 suppression uses source
  dual eligibility; extras `dualScreen` replaces `variants` and
  `dualPreferred`; build fetches without credentials.
- `pack-verification`: serialized entry shape that keeps the setting value
  checks and drops default completeness, category colours and GitLab URLs;
  composition checks without history, family denials, exemptions, the dual
  overlay or projected eligibility; fingerprints without the deleted files.
- `pack-rendering`: settings block without a settings configuration.
- `pack-curation`: curated extras win single-screen selection by precedence,
  guarded by a regression test instead of a pin, with pins only where dual
  preference competes.
- `readme-catalog`: drop the reference to historical mappings.

## Impact

- Code: `composition_policy.py`, `merge.py`, `report.py`, `offline.py`,
  `verify.py`, `build.py`, `cli.py`, `render.py`, `model.py`, `overlay.py`,
  `http.py`, `sources/`, `source_generation.py` and `package_id.py` (HTTP
  client moves to the generation side).
- Configuration: `config/composition.json` loses `history`, 7 pins and the
  MetroidArch rule's `eligible`. `config/extras.json` drops `variants` from its
  nine both-pack entries, and MetroidArch's `"variants": ["dual"]` becomes
  `"dualScreen": true`. `config/overlay.dual.json` and `config/settings.json`
  are deleted. `config/http.json` stays and is read only by source generation.
- Test fixtures: the frozen pre-migration configuration under
  `tests/fixtures/source-generation/codm/pre-migration-config/` gets the same
  `history`, `eligible` and extras edits, because current parsing reads it, and
  loses its `overlay.dual.json` and `settings.json` copies, which the
  captured-baseline harness in `tests/test_source_generation_fixtures.py`
  stops reading. Their entries leave the baseline index.
- Outputs: both packs and the README catalog remain byte-identical for the
  current configuration and the frozen fixture regression. An executable probe
  against the frozen captured baseline produced byte-identical packs with the
  MetroidArch rule's `eligible` removed and the MetroidArch extra
  dual-preferred, even with the Super Metroid dual pin removed; the pin stays.
- Local diagnostics: existing `.build/report.json` and `.build/verify.json`
  files must be regenerated. Nightly uploads both as diagnostics and consumes
  neither, and each run regenerates them.
- Docs: `docs/composition.md`, `docs/verification.md` and
  `docs/development.md`.
- No workflow, publication allowlist or dependency change.
