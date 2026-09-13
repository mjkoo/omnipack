## Context

See proposal.md for why. The current shape that the decisions below change:

- `ingest_all` applies the composition policy to the higher-precedence
  candidates only to find codm2000's dual-covered URLs, then applies it again
  to every candidate. `compose` applies it a third time to candidates that
  already carry it, without pin checks.
- A build's eligibility and dual preference can come from three places: its
  source, a candidate rule's `eligible` and `dualPreferred`, and an extras
  entry's `variants` and `dualPreferred`.
- `pack build` reads configuration from disk several times. The CLI reads the
  policy, denylist and overlays for composition. `publish_build` re-reads them
  for the offline gate, then re-reads the policy and README up to three more
  times to detect edits.
- `offline.py` (769 lines) checks entry shape, every setting against
  `SETTINGS_DEFAULTS`, HTML steps, request headers, category colours against
  `config/settings.json`, projected eligibility, and composition consistency.
- `http.py` serves two callers. The build makes plain GETs to
  `raw.githubusercontent.com` and `codeberg.org`, neither of which has a
  registered credential. Source generation calls `api.github.com` with a token
  and makes ranged and size-bounded APK reads.
- Committed configuration today:
  - `config/overlay.dual.json` is `[]` and `config/settings.json` is `{}`.
  - The 4 denials are id-only with no variant.
  - No candidate rule or extra sets `dualPreferred`. One rule sets `eligible`:
    MetroidArch's `["dual"]`, which restates its extras entry's
    `"variants": ["dual"]`. The other nine extras entries set
    `"variants": ["single", "dual"]`, which is the default.
  - Of the 15 pins, 7 are single-screen. Each names an extras candidate that is
    single-eligible and the only extra in its family. The 8 dual pins each name
    a curated extra: the same 7 baseline extras, and MetroidArch, a dual-only
    extra.
  - There are 113 history records.
- The frozen pre-migration configuration under
  `tests/fixtures/source-generation/codm/pre-migration-config/` carries the
  same `history`, `eligible` rule and extras `variants`, plus its own
  `overlay.dual.json` and `settings.json` copies. The captured baseline
  regression in `tests/test_source_generation_fixtures.py` parses it with
  current code and reads both copies.

## Goals / Non-Goals

**Goals:**

- Both packs and the README catalog stay byte-identical for the current
  configuration and for the frozen captured baseline.
- Each command reads each local input once and checks it once.
- A build's kind, baseline or dual-screen, comes from one place: its source.

**Non-Goals:**

- Changing source precedence, dual pins, identity corrections or overlay patch
  semantics, other than retiring per-pack patches (decision 4).
- Changing source-derived eligibility. Dual preference is now derived from it,
  and no composition rule can change either. The only preference change is
  that a dual-only extra becomes preferred in dual.
- A per-build exclusion keyed by the candidate selector. It is deferred until a
  real case needs it (decision 3).
- Adding a "changed" diff to the build report, or printing the added and
  removed diff in `pack report`. The diff stays in `.build/report.json` as it
  is.
- Moving per-app wording out of the source-generation specs.
- Any publication, workflow or source-generation behavior.

## Decisions

### 1. Apply the policy once, in composition

`ingest_all` takes no policy and returns unmodified candidates. codm2000
suppression needs one fact about each higher-precedence candidate: whether it
is eligible for dual. Only its source decides that (decision 2), so ingestion
reads it from the candidate itself. There is no early policy application or
lookup, and no identity or family change is applied early.

`compose` then calls `apply_composition_policy` once, and the `require_all` and
`validate_pins` switches go. That pass applies identity and family rules and
validates every candidate-rule selector. `compose` receives only admitted
candidates, so selectors are still validated against the admitted set. The
pass no longer validates pins.

Package exclusions are processed and recorded next. Pin validation follows
them, before any family is selected. A pin must match exactly one admitted
candidate after identity and family rules. That candidate must belong to the
pin's family, be eligible for the pin's target by its source and not be denied
there. These are the same candidates a pin is checked against today. A missing
or target-ineligible pin therefore fails only after exclusions, and the failed
build report keeps the denial removals and stale exclusions already recorded,
as the fixed stage order requires.

Alternative considered: move codm2000 suppression into composition, after the
single pass. Rejected, because selectors must be validated against the admitted
set. Suppression would then have to sit between rule application and selector
validation inside that pass, putting a source rule into composition. It needs
only source eligibility, so it stays in ingestion.

### 2. Each build is a baseline build or a dual-screen build

The policy:

- Every build is a baseline build or a dual-screen build. An app's baseline
  build, when it has one, is what the single-screen pack uses.
- Absent a pin, a dual-screen build, when one exists, replaces the baseline in
  the dual-screen pack. With no dual-screen build, the dual pack uses the
  baseline. Source precedence decides among builds of one kind.
- An app may instead have only a dual-screen build, which appears only in the
  dual pack. An app only codm2000 supplies, such as Showdown-DS, is one.
- A valid pin comes first. It selects the one candidate it names for its
  family and pack, ahead of dual-screen replacement and source precedence, and
  a dual pin may name a dual-eligible baseline build even when a dual-screen
  build is available. Nothing other than a pin naming a specific candidate
  makes the dual pack select a baseline build over an available dual-screen
  build.

Only a build's source decides its kind:

| Source | Baseline build | Dual-screen build |
| --- | --- | --- |
| BBoi | standard asset, in both packs | dual asset |
| codm2000 | none | every generated entry |
| RJNY | in both exports; or in the standard export only, kept out of dual by upstream | in the dual-screen export only |
| Extras | by default, in both packs | `"dualScreen": true` |

RJNY's `excludeFromExport` still drops an entry, and an entry marked out of
both exports contributes to neither pack. The captured RJNY catalog has one
single-only entry, Cemu 0.5, whose family also has the dual-only Cemu 0.5.2.

Rules:

1. A build is dual-screen exactly when it is eligible for dual only. Dual
   preference is derived from that, with no separate flag. BBoi, codm2000 and
   RJNY already mark exactly these builds preferred. The only change is that a
   dual-only extra becomes preferred in dual. MetroidArch is the only one, and
   its family's dual pin already selects it.
2. Candidate rules no longer change eligibility or preference. `CandidateRule`
   loses `eligibility` and `dual_preferred`. `eligible` and `dualPreferred`
   fail as unknown candidate-rule fields, naming the rule and field. Rules keep
   `match`, `family`, `packageId` and `rationale`. The only `eligible` rule
   today, MetroidArch's `["dual"]`, restates what its extras entry declares.
3. Extras replace the `variants` array with an optional boolean `dualScreen`,
   default false. A non-boolean value fails naming the entry. `variants` and
   `dualPreferred` fail naming the entry and field. A single-only extra can no
   longer be written; none exists.
4. Pins stay and keep their precedence, which `merge._select` already applies
   before the dual-preferred tier. A valid pin selects the one candidate it
   names, ahead of dual-screen replacement and source precedence. It can
   choose between two dual-screen builds, or keep a dual-eligible baseline
   build in dual in place of an available dual-screen build, including one
   that shares the baseline's package id (decision 3). Of the 8 committed dual
   pins, 7 name curated baseline extras, which therefore win dual even when an
   upstream such as BBoi ships a dual-screen build of the same project, and
   one names MetroidArch, the dual-only extra.

Consequences:

- Ingestion no longer applies the policy at all (decision 1). Composition
  applies it once.
- Policy parsing loses eligibility validation and `_eligibility`. A
  rendered-key projection carries the family only, so eligibility projection
  conflicts disappear, and offline verification loses `ineligible_output`
  (decision 6).
- The "dual preference requires dual eligibility" checks in policy application
  and extras parsing go, because preference can no longer disagree with
  eligibility.
- No rule can move a dual-only build into single. So a dual asset cannot be
  restricted to single, where it would tie with its standard sibling for the
  single winner. Nor can a family's only dual build be restricted to single to
  open a coverage gap. Neither configuration can be written, so neither needs a
  rule or a test.
- Selection itself is unchanged: a valid pin selects its candidate outright;
  otherwise single considers single-eligible candidates, dual considers
  dual-preferred candidates when any remain and all dual-eligible candidates
  otherwise, and source precedence decides within that tier.

Alternative considered: keep `eligible` rules and drop only `dualPreferred`.
Rejected. An `eligible: ["single"]` rule on a dual-only build makes it a
single contender. When its family's single-eligible build shares its source
rank, as a BBoi dual asset and its standard sibling do, composition then fails
with an ambiguous single winner instead of keeping the standard build in dual.
Keeping the rules means specifying and testing configurations nothing needs.

### 3. Denials are package-only and cover both variants

`parse_exclusions` accepts exactly `id` and `reason`; any other field fails,
naming the entry and the field. Removal records keep the variant a candidate
was removed from. Stale exclusions carry only id and reason.

Build coverage and offline coverage both lose their exemption branch. A denial
of the single winner's package now removes it from single as well, so no
exemption can arise. A family selected in single must have a dual build, so an
app can no longer be published in single only. To publish an app in neither
pack, deny every package id its family's builds carry.

A package denial removes every build carrying that package id from both packs.
The family's builds carrying other package ids stay selectable, so the app is
absent from a pack only when no selectable build of its family remains there.
For Zelda 3, Minish Cap and Harvest Moon 64 the standard and dual builds share
a package id and those families have no other build, so a denial of that id
removes each of those apps from both packs. To keep a family's
baseline build in the dual pack in place of its dual-screen build, pin the
baseline build for dual (decision 2). A BBoi standard build is eligible for
both packs, so the pin is valid, and it works whether or not the two builds
share a package id: the dual-screen build stays admitted but is selected in
neither pack.

Deferred: a per-build exclusion keyed by the candidate selector (`source`,
`origin`, `id`, `url`, as pins use), which could drop one build while a
sibling sharing its package stays, leaving the dual choice among the remaining
builds to precedence instead of fixing it with a pin. No current configuration
needs it. It is added when a real case does.

### 4. One overlay file and no pack settings file

`compose` takes one overlay. `render(apps)` emits a settings block holding only
`categories`. `config/overlay.dual.json` and `config/settings.json` are
deleted, together with every code path, test, fixture and document that reads
or names them. That includes the frozen copies under
`tests/fixtures/source-generation/codm/pre-migration-config/`, their entries in
the baseline index, and the captured-baseline harness in
`tests/test_source_generation_fixtures.py`, which reads those copies and from
then on composes with one overlay and renders without settings. The change
adds no check or compatibility handling for either path.

Per-pack overlay patches are retired with no replacement. One overlay record
applies in every pack that selects its id-and-URL pair, so a patch can no
longer target one pack only. Where both packs select the same pair, as they do
for the Zelda 3, Minish Cap and Harvest Moon 64 standard and dual builds, one
record patches both. `config/overlay.dual.json` holds no records, so nothing
moves.

### 5. The build reads its local inputs once

At the start of `pack build`, the CLI reads these into one immutable snapshot:

- `sources.json` and `extras.json`;
- `deny.json`, `overlay.json` and `composition.json`;
- `README.md`.

Composition parses from the snapshot. The offline gate validates the rendered
bytes against the same snapshot bytes. Catalog generation replaces the catalog
inside the captured README bytes.

`require_current_inputs`, its three call sites and `IngestionResult.policy`
and `.policy_bytes` go. `previous_ids` still reads the old outputs before
replacement, and `_replace_outputs` still snapshots outputs so it can roll
back. That snapshot serves recovery, not edit detection.

Trade-off accepted: README or configuration edited during a build is
overwritten by, or missing from, that build's outputs.

### 6. Offline verification keeps shape, setting values, composition consistency and the catalog

Kept:

- decoding with non-finite rejection;
- the document shape;
- per-entry required fields, URL scheme, categories and a supported
  `overrideSource`;
- `additionalSettings` as a string decoding to a finite object;
- in a narrowed `_validate_additional`, the setting value-type check against
  the source's known defaults (`wrong_setting_type`), the HTML
  `intermediateLink` step check (`invalid_html_step`) and the request header
  check (`invalid_request_header`);
- the `preferredApkIndex` integer check (`invalid_preferred_apk_index`);
- duplicate ids;
- the composition checks: duplicate family, pin mismatch, denied package
  present, stale overlay and coverage gap.

Kept checks keep their finding codes. The setting value checks stay because
nothing else checks those values before publication:

- render's `hydrate_settings` copies an entry-supplied value for a known key
  without checking its type;
- ingestion only requires `additionalSettings` to decode to an object;
- `preferredApkIndex` passes through normalization and rendering unchecked;
- overlay patches can set both.

`publish_build` refuses to replace outputs when the offline gate has
findings, so these checks gate what nightly publishes.

Removed:

- `_validate_additional`'s default-key completeness check
  (`missing_setting_default`), since render's hydration fills every default
  key;
- `_validate_pack_settings`, which compared the rendered settings block and
  category colours with `config/settings.json`. Render derives the colours from
  the entries it renders;
- the GitLab URL check, which ingestion enforces;
- the `ineligible_output` composition check, which compared rendered entries
  with eligibility declared by candidate rules. Rules no longer declare
  eligibility and projections carry the family only, so it has nothing left to
  check;
- `ValidatedEntry` and `OfflineResult`. `validate_offline` returns a tuple of
  findings.

`OfflineInputs` drops `dual_overlay` and `settings`. `SETTINGS_DEFAULTS`
remains render's hydration source and offline verification's reference for
known setting types.

### 7. Slim selection records

`FamilySelection` keeps:

- the family and variant;
- the winner's original and effective ids, URL, source and origin;
- the reason: `pin`, `dual-preferred`, `ordinary-fallback` or `source`;
- `considered`, a list of `{source, origin, original_id, url}` for the family's
  other candidates that were eligible for that variant and not excluded.
  Excluded candidates are already listed in `denylistRemovals`.

`Displacement`, `SelectionAlternative`, `_alternative`, `_differing_fields`,
the six loss reasons and the displacement list go. `_import_data` stays,
because it builds the winner's data.

### 8. Both report schemas move to 3, with no tolerant readers

A schema 3 build report holds `schemaVersion`, `status`, `changes`,
`sourceAdmissions`, `denylistRemovals`, `staleExclusions`, `selections` and
`offlineVerification`, plus `stage` and `error` on failure.

`format_reports` accepts only schema 3. Anything else, including a missing
schema, raises `unsupported build report schema <value>; regenerate with
`pack build``.

The verification report's `INPUT_PATHS` become `single`, `dual`, `deny`,
`overlay`, `composition` and `readme`. `SCHEMA_VERSION` becomes 3,
`VERIFIER_VERSION` becomes `2.0.0` because the checks narrowed, and the reader
requires schema 3 with exactly those inputs.

Alternative considered: keep both schema numbers and tolerate the missing
keys. Rejected: the reports are disposable diagnostics, regenerating one is a
single command, and tolerant readers are part of what this change removes.

### 9. The build's HTTP client carries no credential code

`http.py` keeps what both callers need:

- a retrying `get` with transient-error classification, which reads whole
  bodies and follows redirects with urllib's defaults;
- `redact_url`.

It sends no credentials. A new `omnipack/source_http.py` holds the
generation-only client:

- exact-host `HttpConfig`;
- the credential-stripping redirect handler;
- `max_bytes`, plus `method` and `headers` for HEAD and Range requests.

`source_generation.py` and `package_id.py` use `source_http.py`. `pack build`
constructs the plain client and never reads `config/http.json`.

Alternative considered: keep one client and give the build an empty credential
map. The diff is smaller and the observable result is the same, but the build
path would still carry the credential and bounded-read code. The split saves
only 20 to 40 lines; what it buys is a build path with no credential logic.

### 10. Finish the app model

`App` drops `variant`, and `eligibility` becomes a required field.
`dual_preferred` becomes a property derived from eligibility, true exactly when
the build is eligible for dual only, rather than a stored field. `origin` and
`original_id` keep their defaults only where a constructor relies on them.
`normalize_record` loses its `variant` and `dual_preferred` parameters and
requires `eligibility`.

`ComposedApp` becomes a family plus a data dict. Overlay application,
rendering and `source_generation._render_catalog` construct it with a family;
catalog rendering there uses `package:<id>`. Provenance and original id stay on
`App`, where selection reporting reads them.

### 11. Configuration edits land with the code that needs them

`history` leaves `config/composition.json` in the same commit that makes it an
unknown field. The 7 single-screen pins leave in their own commit, which also
updates any test that expects their reason to be `pin` and adds the regression
test described below.

The dual-screen model's configuration edits land with the parsing that needs
them:

- `config/composition.json` drops the MetroidArch rule's `eligible` in the
  commit that makes `eligible` an unknown candidate-rule field.
- `config/extras.json` drops `"variants": ["single", "dual"]` from its nine
  both-pack entries, and MetroidArch's `"variants": ["dual"]` becomes
  `"dualScreen": true`, in the commit that changes extras parsing.

The frozen pre-migration fixture configuration under
`tests/fixtures/source-generation/codm/pre-migration-config/` is migrated the
same way, in the same commits as `history`, `eligible` and the extras fields,
because the captured baseline regression parses it with current code. Its
`overlay.dual.json` and `settings.json` copies and their baseline index entries
are deleted in the commits that delete the live files, where the harness stops
reading them.

Readers and validators change no later than their writers, so `pack build`,
`pack verify` and `pack report` agree at every commit on the branch:

- Offline verification, the build's offline gate and the verification report
  stop reading `config/overlay.dual.json` and `config/settings.json` before
  either file is deleted. That commit also makes the verification schema and
  verifier version change.
- `pack report` reads the slimmer selection records in the same commit that
  starts writing them.

Why the dual-screen model changes no output: an executable probe against the
frozen captured baseline produced byte-identical packs with the MetroidArch
rule's `eligible` removed and the MetroidArch extra dual-preferred. They stayed
byte-identical even with the Super Metroid dual pin removed, where MetroidArch
wins dual as a preferred extra instead of by pin. The pin stays. The frozen
baseline regression and the live comparison in tasks.md confirm it on the
branch.

Why removing the single pins changes no selection for the current
configuration: extras rank highest and single has no preference tier, and each
pinned extra is its family's only extra and single-eligible. The frozen
baseline regression and the live comparison confirm it. Those families' single
reason in the build report goes from `pin` to `source`.

Selection is not all those pins did. A single pin fails the build when its
extra is not single-eligible, and offline verification reports `pin_mismatch`
when the rendered single entry is not the pinned id and URL. Without them,
`pack build` and `pack verify` no longer fail when a later extras or policy
edit stops single from serving Aurora Store, idTech4A++, VCMI, Julius, Xash3D
FWGS, Ghostship or Gen1Recomp. The dual pins still fail the build if one of
these extras disappears altogether. The pin-removal commit therefore adds a
regression test asserting that, for the committed configuration, each of the 7
extras is its family's single-screen winner. That test is the guard that
replaces the single pins.

## Risks / Trade-offs

- [One-pass policy, the dual-screen model or deleted configuration changes
  output unintentionally] → The frozen captured-baseline regression must stay
  byte-identical. Back-to-back live builds of the base commit and the branch
  are compared byte for byte, and the result is recorded in the change's
  validation record.
- [A hand-edited `dist/` passes weaker offline checks] → The dropped checks
  cover only what render guarantees by construction, every default key and the
  derived category colours, plus GitLab URLs, which ingestion enforces, and
  projected eligibility, which no rule declares any more. Setting value types,
  HTML steps, request headers and `preferredApkIndex` stay checked, because
  upstream records and overlay patches supply them and render does not check
  them. Only `pack build` writes `dist/`, and only in nightly, whose allowlist
  and bundle checks bound what lands.
- [A README edit during a local build is overwritten] → Accepted, since a build
  takes seconds. Recover the edit from the editor or git and rerun.
- [Old local reports stop displaying] → The regeneration diagnostic names the
  command to run.
- [Variant-scoped denials and eligibility rules are gone] → Accepted. No
  committed denial is variant-scoped, and the only `eligible` rule restated its
  extras entry. An app selected in single can no longer be kept out of dual,
  and an app that must leave dual leaves both packs by a denial of every
  package id its family's builds carry.
- [A dual-screen build that shares its baseline's package cannot be denied
  alone] → A package denial removes every build of that package from both
  packs. To keep the baseline build in dual instead, pin it for dual; this
  works for Zelda 3, Minish Cap and Harvest Moon 64, whose standard and dual
  builds share a package id. A pin fixes one candidate and fails the build if
  that candidate disappears, so dropping one build while leaving the dual
  choice to precedence waits for the deferred per-build exclusion keyed by the
  candidate selector.
- [Single-screen pins no longer guard the curated extras] → For the current
  configuration the 7 removed pins select nothing precedence would not, but
  they also made `pack build` fail, and offline verification report
  `pin_mismatch`, when single stopped serving the pinned extra. A regression
  test asserting that each of the 7 extras is its family's single-screen winner
  under the committed configuration replaces that guard. The remaining dual
  pins still fail the build if one of these extras disappears altogether.
- [The HTTP split churns tests for little line saving] → The tests move with
  the code, and the generation credential tests keep their assertions.
- [A patch for one pack only, or configured colours, are needed later] →
  Reintroduce them when a real use appears. Until then, a record patching an
  id-and-URL pair that both packs select patches both. The dual overlay and
  settings files hold nothing, so there is nothing to migrate now.

## Migration Plan

The project has no external users. Configuration and frozen-fixture edits land
with the code on the change branch:

- `history` and the 7 single-screen pins leave `config/composition.json`;
- the MetroidArch rule loses `eligible`;
- extras lose `variants`, and MetroidArch's entry gains `"dualScreen": true`;
- the two empty files and their frozen fixture copies are deleted.

Local `.build/` reports regenerate on the next command. To roll back, revert
the branch: the deleted configuration files were empty, and history records,
the rule field and the extras fields can be restored from git.
