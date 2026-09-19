## Context

See `proposal.md` for motivation and file scope. CI runs tests and verifies committed packs offline; it does not rebuild them. Offline verification checks pins, denials, overlay targets and the README catalog, but cannot prove that every configuration edit has been incorporated or that an overlay's values were applied. Tests compose against captured upstream inputs.

`pack build` fetches upstream JSON and reads the committed codm catalog. Only `pack generate-source codm` reads the upstream README and resolves APK identities. The source workflow checks generated packs but proposes only the catalog; nightly later publishes the pack outputs. This distinction is already specified and remains intact.

## Goals / Non-Goals

**Goals:** Make each common edit discoverable from one maintainer page, show how to inspect its effect, and accurately describe the limits of review and verification.

**Non-Goals:** No runtime, CI, schema, source policy or publication changes; no new catalog entries, device validation, general documentation rewrite or normative specification changes. Unrelated semantic audit findings require separate triage.

## Decisions

### Put the editing entry point in development documentation

Add a compact Common edits section to `docs/development.md`. Each recipe names the file to edit, a minimal record or selector shape where useful, and the reference owning its semantics:

- Extras: required `id`, `url`, `name`; strongly recommended `categories`, whose first entry, else `Other`, sets the catalog heading and sort; optional `dualScreen` for a dual-only build; ordinary extras are baseline candidates. Describe precedence as selection among eligible builds, not a promise that extras always win. Link to setup-note guidance for apps requiring user files or extra components.
- Codm: the upstream README supplies projects; `config/codm-projects.json` supplies reviewed per-project rules, not an independent list of additions. For a manual policy edit, generate, inspect the successful candidate and diagnostics, deliberately copy the candidate catalog into `config/catalogs/codm.json`, then build. Do not present automation's staging script as a manual acceptance command: it creates commits and assumes workflow context.
- Overlay: use the selected effective id plus project URL and a merge patch; explain null deletion and link to protected fields. The overlay example in `docs/composition.md`, which this recipe defers to, encodes `additionalSettings` as a JSON string. Repair it to a settings object: a patch merges keys into the settings object, and a patch value that is not an object replaces the whole value, after which rendering fails because the settings are no longer an object.
- Denial: use effective package id plus reason, affecting both packs and all sources. Note that removing a required curated extra may also require changing its reviewed extras configuration; do not recommend weakening its regression check.
- Identity and family rules: use original candidate selectors from the build report, a rationale, and manifest evidence for identity corrections. Distinguish original selector ids from effective output ids. Link to tracker identity restrictions.
- Pins: select an eligible candidate for a family and variant, including keeping a baseline build in dual. Explain that a pin is selection, not a per-build denial.

Existing semantics stay in `docs/composition.md` and source-generation details stay in `docs/source-generation.md`. A new standalone guide would add navigation and a second place to maintain the same rules.

### Use one manual review convention

Recommend that manual changes affecting pack contents run generation when applicable, `uv run pack build`, review the output diff and `.build/report.json`, then run `uv run pack verify` and the usual development checks. Include all changed `dist/single-screen.json`, `dist/dual-screen.json` and generated README bytes in the same PR as the input edit.

Make the `git diff` of `dist/` and the README against the PR's base the primary evidence of an edit's effect, with the build report's `changes`, `selections`, `denylistRemovals` and `staleExclusions` as supporting detail. State the limit that forces that ordering: `changes` lists only the package ids added or removed relative to the `dist/` files present immediately before that build, so it is empty for an overlay, settings, pin or identity edit that keeps the id set, and empty again on a second build of an already-built edit. Do not imply `pack report` prints added/removed ids.

If a file is unchanged, no artificial diff is needed, but a successful no-op build is a valid result only once the report shows that the edit took effect, or the edit was expected to be inert. For a denial, the new package id must appear among the report's `denylistRemovals` and must not appear among its `staleExclusions`: a mistyped id, or the original rather than the effective package id, records a stale exclusion while the build succeeds, offline verification and CI pass, and the app stays in both packs. For a pin or a rule, the selections must show the intended winner.

Explain that a green CI result is structural evidence rather than proof that every edited input reached the outputs. A failed live build leaves outputs unchanged and should be resolved or retried before describing the edit as built and reviewed.

Nightly publishing advances main's generated files while a manual PR is open, writing only `dist/single-screen.json`, `dist/dual-screen.json` and `README.md`. When those files move under the PR, rebase onto main, rerun generation where the edit requires it and `uv run pack build`, then re-review. Conflicts in the two pack files and in the region between the README's generated catalog markers are resolved by rebuilding, never by hand; a build replaces only that region and preserves the surrounding bytes, so a README conflict outside the markers is ordinary prose, merged by hand and re-read. A codm catalog conflict is different: nightly never writes that file, so the branch edited it too and the other side may be a manual policy PR rather than an automated source-catalog one. Take main's catalog as the base, re-run generation, re-inspect the candidate and diagnostics, re-copy it per the acceptance recipe above, then build. Never hand-resolve that file, whose conflict markers no generation run parses, and never keep main's catalog when the policy edit is the branch's purpose: that silently discards the reviewed edit.

This is a human convention, not a new CI gate. The alternative of prescribing different PR contents for each manual input type was rejected because it makes reviewers infer when an edit will actually take effect.

### Preserve the automated catalog-only exception

Link from the manual recipe to the source workflow explanation. Automated source PRs keep only the checked catalog; their packs and README remain diagnostics, with nightly rebuilding after merge. Manual policy changes include the reviewed generated catalog and changed outputs. Do not add generated packs to the automated workflow or require manually modifying its branch.

Correct the sentence in `docs/source-generation.md` claiming that its build step mirrors main CI. The workflow performs additional live building; main CI checks committed outputs offline.

### Repair stale claims

In `docs/curation.md`, explain that publishing a changed verified pair uploads both assets before editing the revision and digest record. Served digests are checked before deciding to leave, repair or advance the release. There is no post-upload readback, and repair does not advance the revision. Keep the non-atomic asset visibility limit to one line and add a link to `docs/publishing.md`, retaining the device-acceptance limits.

Also repair that page's rollback sentence by deletion, not replacement. Keep its true part, that a rollback restores the previous extras and overlay and rebuilds both files, and remove the stale clause that publication is a separate maintainer action, asserting nothing in its place about when or how a rollback reaches the release. `docs/publishing.md` already documents publication behavior and remains its owner.

In `docs/publishing.md`, repair the claim that the stable download URLs always serve the assets from the most recently completed edit. They serve whatever the most recent upload left in place: during a publication window an asset can be missing, or the pair can be mixed across revisions, and the raw-main links are the fallback until a later run completes or repairs the pair. This page owns the statement; the curation page links to it.

In `docs/development.md`, repair the claim that the report command shows whether verification matches the current local inputs. Link to `docs/verification.md`, which enumerates the fingerprinted set and owns the staleness rule, adding only what it omits: an edit outside that set - extras, sources, the codm catalog or the codm policy - leaves evidence reported as current until a rebuild changes the outputs.

`docs/composition.md` states the deferred flavor/identity migration, retained release selection and source-version policy. `docs/curation.md` states only the APK filter still selecting its current build, with the older-release fallback. Neither credits a past effort. Preserve the unresolved product decision.

### Validate the guidance without adding prose tests

Check every illustrated record against current parsers and every command against the local CLI, covering the examples the recipes link to as well as those this change inlines: a recipe that defers to a reference inherits that reference's example, so a wrong example there is a wrong recipe. Trace both an ordinary manual edit and a codm policy edit through the documented steps. Use existing fixtures or temporary inputs to check examples without changing committed configuration or fetching live APKs. Check links and run offline pack verification. Record results inside this change, not in durable consumer docs.

No new tests merely asserting headings or wording are warranted. Required implementation reviews and their completion audit remain part of apply; separate OpenSpec verification and archive are not implementation tasks.

## Risks / Trade-offs

- Live builds can include unrelated upstream refreshes. Review the full diff and explain incidental changes; do not promise a reproducible network snapshot or edit generated files to conceal changes.
- Copying a stale codm candidate could misrepresent a policy edit. Require successful generation and review of that invocation's report before acceptance; generation failure supplies no acceptable candidate.
- Recipes can duplicate reference material and drift. Keep them short, link to owning sections, and validate selector names and field boundaries during review.
- Offline verification does not establish APK identity, installation or device behavior. Preserve those limits and dated evidence rather than adding an assurance claim.

## Migration Plan

No data migration or deployment is needed. Apply the documentation edits together; reverting those edits restores the previous guidance without changing code, outputs or workflow behavior.
