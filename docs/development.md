# Development

Run `direnv allow` (or `nix develop`) to get every tool the `justfile`
targets need, then `just --list` for the available commands. `just
check-all` runs everything CI runs.

## Common edits

Edit maintained inputs, then follow [manual review](#manual-review-and-pr-contents)
for generation, acceptance and output review.

- **Add an extra:** append a record to `config/extras.json`, for example:

  ```json
  {"id": "org.example.app", "url": "https://github.com/example/app", "name": "Example", "categories": ["PC Ports"]}
  ```

  `id`, `url` and `name` are required. `categories` is strongly recommended.
  Only [taxonomy](composition.md#categories) values other than Track Only pass
  through from an extra's categories, and any other value is dropped; a
  track-only extra always carries Track Only, and a family in the category map
  takes the mapped category instead. The README catalog files each row under
  the first category of its presenting entry, the single-screen one when the
  app has one, or under `Other` when that entry has none; see
  [categories](composition.md#categories). Ordinary extras are baseline
  candidates for both packs; optional `"dualScreen": true` makes one dual-only.
  Selection compares eligible builds, so an extra does not always win. See
  [build eligibility and precedence](composition.md#baseline-and-dual-screen-builds)
  and add a [setup note](curation.md#port-setup) for required user files or components.
- **Refresh a generated source:** the codm and Quiver catalogs come from
  their upstream lists alone; there is no per-project generation policy. Give
  a generated app its name and settings with an overlay record and its
  category with a category map key, as for any other source. To refresh a
  catalog by hand, generate and accept a candidate as described below before
  building; see [inputs](source-generation.md#inputs) and
  [rendered entries](source-generation.md#rendered-entries).
- **Patch selected settings:** add a `{url, patch}` record to
  `config/overlay.json`, using the selected entry's project URL. The record
  patches every selected entry at that URL. `patch.additionalSettings` is an
  object whose keys merge into existing settings, not a JSON-encoded string.
  Null deletes allowed fields. Follow the
  [overlay example and protected-field rules](composition.md#denials-and-patches).
- **Fix a wrong package id:** when Obtainium shows a never-installed duplicate
  of an installed app after re-import, or an id error, set `patch.id` to the
  installed APK's package id in that app's overlay record, as
  [wrong package ids](curation.md#wrong-package-ids) describes.
- **Set an app's category:** add a `categories` key for its family to
  `config/composition.json`: its `app:` name, or otherwise its normalized
  project URL, such as `"github.com/example/app": "PC Ports"`.
  Overlays cannot patch categories. A build report entry under
  `uncategorizedFamilies` names the family key to add, and one under
  `staleCategoryAssignments` names a key to remove or correct. See
  [categories](composition.md#categories).
- **Deny a project:** append `{"url": "https://github.com/example/retired", "reason": "No supported build"}`
  to `config/deny.json`. This removes every build at that project URL from both
  packs across all sources, not just one build, and leaves builds at other URLs
  selectable; see [denials](composition.md#denials-and-patches). Removing a
  required curated extra may also require changing its reviewed extras
  configuration; do not weaken its regression check to hide a contradictory
  configuration.
- **Group or split a family:** add a candidate rule to
  `config/composition.json`, with `match`, `rationale` and an `app:` `family`.
  Take the `source`, `origin`, `id` and `url` selectors from the build report's
  selections or considered candidates. A rule claims every build at its URL,
  so joining two repositories takes one rule at each; giving two builds at one
  URL different families splits that URL by package id. Follow the
  [complete policy example](composition.md#candidate-policy). The build
  report's `repeatedIds`, `singleOnlyFamilies` and `sameRankTies` name the
  families that usually need such a rule.
- **Pin a winner:** add a pin with `family`, `variant` (`single` or `dual`),
  original candidate `match` and `rationale` in `config/composition.json`.
  The [candidate must be eligible](composition.md#candidate-policy) and survive
  denials. A dual pin can keep a baseline build over a dual-screen build.
  A pin selects a winner; it is not a per-build denial.

## Manual review and PR contents

For every manual edit affecting pack contents:

1. For a manual codm or Quiver catalog refresh, run
   `uv run pack generate-source <source>` with `codm` or `quiver`. Inspect that
   invocation's `.build/source-generation/<source>/report.json` and candidate
   `catalog.json`, including skipped listings and intended project changes.
   Accept only a successful, reviewed candidate; a failed run has none to accept.
   Copy it deliberately:

   ```sh
   cp .build/source-generation/<source>/catalog.json config/catalogs/<source>.json
   ```

   Ordinary extras, overlay, denial, family and pin edits skip generation.
   Do not use `python -m scripts.source_proposal stage` for manual acceptance:
   it creates commits and assumes workflow context.
2. Run `uv run pack build`. Resolve or retry a failed live build before calling
   the edit built and reviewed; failure preserves the previous outputs.
3. Review `git diff main...HEAD -- dist/ README.md` against the PR base, plus
   `git diff HEAD -- dist/ README.md` for uncommitted build results. This output
   diff is the primary evidence, including for overlay-only edits. Review the
   full diff for incidental upstream refreshes rather than hiding them by editing
   generated files. Use `uv run pack report` for supporting `selections`,
   `denylistRemovals`, `staleExclusions`, `sourceAdmissions`,
   `uncategorizedFamilies`, `staleCategoryAssignments` and `changes`,
   recorded in `.build/report.json`. `changes` holds the entries, each a package
   id and normalized project URL, added or removed relative to files present
   immediately before the build: settings edits that keep every entry's id and
   URL produce no entries, and a second build can empty it. The command lists
   all recorded entries, including admitted committed candidates with their
   source, project URL and committed id. A diagnostic kind with
   nothing recorded prints nothing; an unavailable comparison is labeled
   unavailable, and a failed build's comparison describes candidates that were
   not published.
4. An unchanged output needs no artificial diff, but accept a successful no-op
   only when the report shows the edit took effect or it was expected to be inert.
   A new denial's normalized URL must appear in `denylistRemovals` and be absent
   from `staleExclusions`; a mistyped URL can pass build, verification and CI
   while leaving the app selected. For a pin or rule, check the intended
   winner in `selections`.
5. Run `uv run pack verify` and the usual development checks (`just check-all`).
   Include every changed `dist/single-screen.json`, `dist/dual-screen.json` and
   generated README in the same PR as the input edit, plus the accepted source
   catalog when applicable. Green CI is structural evidence, not proof that
   every edited input reached the outputs or that overlay values were applied.

If main's generated files move while the PR is open, rebase onto main, rerun
source generation where applicable and `uv run pack build`, then re-review.
Resolve conflicts in the two pack files and between README's
`<!-- omnipack:catalog:start -->` and `<!-- omnipack:catalog:end -->` markers
by rebuilding, never by hand. Merge README prose outside those markers by hand
and re-read it; the build preserves those bytes. For a source catalog conflict,
take main's catalog as the base, rerun generation, inspect the new candidate and
diagnostics, copy it using the acceptance recipe above, then build. Never
hand-resolve the catalog. Nightly writes only the packs and README, never a source catalog.

The [automated source proposal](source-generation.md#proposal-workflow) is the
catalog-only exception: its builds are checks, and nightly rebuilds outputs
after merge. Do not add packs to its branch. This manual review convention
adds no CI gate.

## Build the packs

Run `uv run pack build` from the repository root. It fetches the configured
pack sources, including the committed codm and Quiver catalogs, and writes both
import files to `dist/` and regenerates the README catalog after validating their
serialized bytes offline. It does not fetch the codm README, the Quiver index or
release APKs. Keep exactly one standalone pair of catalog markers in README; the
build preserves all bytes outside them. The build and source generation fetch public inputs without
credentials.

The JSON diagnostics are in `.build/report.json`, including each
family's selection with the candidates it was chosen over and the selection
reason, denylist removals and stale exclusions, uncategorized families and stale
category assignments, repeated package ids, single-only families, same-rank
ties, admitted committed candidates with their identities, and the entries
(package id and project URL) added and removed since the previous output. A
failed build returns a nonzero status and preserves the previous packs and
README.

## Verify and inspect

Run `uv run pack verify` (or `just verify`) to validate the committed packs,
README catalog and local configuration without network access.
Verification does not consult HTTP configuration or credentials. Unsupported
arguments fail before verification and leave prior evidence intact. Use Obtainium
to investigate source selection and version behavior.
Verification leaves distribution files, README, configuration, and the build
report unchanged. Standalone evidence is written to `.build/verify.json`.

Run `uv run pack report` to display build and verification results, recorded
non-blocking build diagnostics,
observation times, and whether verification matches its fingerprinted inputs.
Edits outside that set, such as extras, sources or source catalogs,
leave evidence reported as current until a rebuild changes the outputs.
A matching fingerprint does not establish current upstream health.

See [verification](verification.md#commands-and-evidence) for the fingerprinted
set, structural checks, failure policy, and the limits of a successful check.
CI verifies committed files offline; nightly publication builds and verifies
once, in a read-only job, then hands the exact verified commit to a separate
write job that pushes it. Formatting, lint, types and the full suite remain
development CI responsibilities. Main advancing past a run's base fails that
run without another attempt; release synchronization is checked separately,
after the main outcome. A verification or build report with any schema other
than the current one requires regeneration with `uv run pack verify` or
`uv run pack build` respectively.

See [pack composition](composition.md) for family selection, policy,
exclusion, overlay, migration, and rollback behavior.

See [source generation](source-generation.md) for upstream inputs and
screening, generating isolated candidates, accepting source data, and operating the
separate source proposal workflow. See [source generation validation](../openspec/changes/archive/2026-09-11-generate-reviewed-readme-catalog/source-generation-validation.md)
for the dated controlled, live-build, and device evidence.

See [maintained app curation](curation.md) for version policies and known
identity findings, and [curation validation](../openspec/changes/archive/2026-09-09-curate-app-version-policies/curation-validation.md) for
fixture, metadata and device acceptance results.

See [nightly publishing](publishing.md) for scheduled refreshes, permissions,
the one-time release bootstrap, failure and rerun behavior, diagnostics, and
rollback.

See [onboarding validation](../openspec/changes/archive/2026-09-10-simplify-pack-onboarding/onboarding-validation.md) for the latest README,
schedule, tracker-exclusion, and pack verification evidence.
