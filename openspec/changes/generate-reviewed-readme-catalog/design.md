## Context

See proposal.md for motivation and scope. `sources/codm.py` currently takes a
resolver and higher-precedence candidates, scrapes README links and emits dual
candidates. `ingest_all` applies eligibility policy early to determine dual
coverage. `package_id.py` contains the automatic resolver, accepted-ID cache,
range/ZIP extraction and binary manifest parser. The build constructs that
resolver and nightly can commit `config/package-ids.json`.

Source selection depends on provenance and original identity as well as rendered
Obtainium fields. Existing codm selectors use source `codm2000` and origin
`codm-generated`; changing those during migration would invalidate curation.
The current renderer rejects duplicate package IDs in an import document.

## Goals / Non-Goals

**Goals:** Put accepted source data between discovery and composition; preserve
export behavior for captured upstream inputs; make generation reusable locally
without granting it PR or main publication powers.

**Non-Goals:** A generic source crawler, a replacement APK parser, multi-host
package discovery, automatic conflict resolution, a durable failed-run recovery
protocol, or a complete composition-policy refactor. This change isolates the
existing resolver rather than promising substantial line-count reduction.

## Decisions

### Separate candidate generation from source acceptance

Add `pack generate-source codm [--force]`. It writes its result under
`.build/source-generation/codm/`, including catalog, source metadata, candidate
resolution state and a report. It never edits the committed inputs or git.
Reset current-run diagnostic availability at invocation start so an old result
cannot be offered after failure. Reuse shared normalization, HTTP and rendering
utilities where appropriate without calling final composition to create the
source catalog.

Use `config/catalogs/codm.json` for the accepted Obtainium document and
`config/catalogs/codm.source.json` for schema version, source URL, exact README
SHA-256 and catalog SHA-256. Retain `config/package-ids.json` as generation-owned
resolution state to avoid an unnecessary format migration. Configure the source
with both its local catalog path and its README URL; build uses only the former.
The metadata has no wall-clock field that would manufacture changes on reruns.

A metadata change on the proposal branch is pending, even though it uses the
same file format as accepted state. Main is the authority for acceptance. The
command reads accepted catalog/state from its main-based checkout, not from an
open PR. This prevents an unmerged resolution from silently becoming accepted.
Missing initial state allows bootstrap generation; inconsistent existing state
fails with an actionable diagnostic.

Alternative: have generation directly overwrite tracked files. Keeping candidate
outputs separate makes incomplete results harder to confuse with accepted input
and keeps local invocation free of repository writes.

### Gate by README bytes, with a manual force escape hatch

Compare exact fetched bytes and the configured URL to accepted metadata. On a
match, stop before release requests. A README prose-only change proposes a
metadata-only update so later runs can recognize acceptance. Forced runs perform
normal resolution even if the README is unchanged, but unchanged generated
content still produces no PR commit. Failed new-project resolution leaves main's
hash unchanged, so scheduled runs retry naturally.

Accepted-entry fallback is different: after a warning-bearing proposal merges,
unchanged README runs skip again. Resolving its newer release requires another
README change or forced run. This deliberately accepts the trigger limitation
instead of adding a second release-polling system.

### Generate a complete independent source; preserve coverage at ingestion

Parse only Project catalog tables, deduplicate normalized repository links and
resolve all eligible projects regardless of current upstream coverage. Reject
missing/malformed table structure and empty eligible input. Keep unsupported
links in diagnostics. Generate repository names, owner authors and empty
categories using supported GitHub import defaults. Do not apply overlays or
family selection to this source file.

The ingestion adapter reads this Obtainium JSON through shared record
normalization and supplies the established codm provenance, origin, dual-only
eligibility and preference. Preserve the early higher-source eligibility check
and normalized-URL coverage suppression before applying final candidate policy.
This still differs from ordinary JSON adapters in source-specific semantics;
forcing identical semantics would change current pack selections. The broader
repeated-policy cleanup remains separate.

A complete source may expose ID collisions between links formerly hidden by
upstream coverage. Fail with both project URLs rather than invent a winner or
weaken the Obtainium document's unique-ID constraint. This is a validation
failure, not a request to enter package IDs manually.

### Keep the automatic resolver and narrow accepted fallback

Retain latest-release API lookup, host-assigned release identifiers, agreement
across all eligible APKs, ranged extraction, bounded full fallback and
credential scoping. Resolve fresh projects automatically. For entries already
in the accepted catalog, a failed refresh retains the full accepted entry and
unchanged successful cache fields with a warning. Catalog/cache inconsistencies
fail before generation.

A historical cache entry for a project absent from the accepted source is not
sufficient fallback evidence for a new addition. It needs a successful current
resolution. Build candidate cache state separately from accepted state; on a
failed overall attempt, partial resolutions can appear in diagnostics but do
not become tracked changes. No cross-run persistence of failed attempts is
required. This deliberately gives up paid-work recovery to keep acceptance clear.

Alternative: delete the parser or require manually provided IDs. Both defeat the
approved automatic onboarding requirement. Replacing the parser with an SDK is
not needed to isolate it from nightly.

### Validate within the generation workflow before updating a PR

Use a daily UTC schedule distinct from nightly and manual dispatch, main-only
canonical-repository writes, one serialized source workflow and a bounded run.
Use the project's locked runtime. Validate the source candidate, overlay it into
the clean selected-base checkout for a normal pack build and structural verify,
and retain a pack diff as diagnostics. Capture the three checked source/state
files; reset generated pack/README changes before the PR commit and enforce the
source-only path allowlist. Test exact-byte correspondence with the checked
candidate. No runtime-generated pack output enters this PR.

Perform these checks explicitly in this workflow. Do not rely on the PR event
as the only check path. GitHub documents that PR events produced by
`GITHUB_TOKEN` can require approval before their workflows run; repository rules
still govern those additional checks and merging. Use the built-in token with
contents and pull-request write permissions for publication; do not add a PAT
or GitHub App dependency merely to bypass that approval. Operators must enable
PR creation if repository policy requires it; implementation does not alter
settings. See [GitHub workflow triggering documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)
for token event behavior. Generation/check execution uses repository read access;
write credentials are scoped to the publication step.

### Keep one proposal without recreating nightly recovery machinery

Use a dedicated `automation/codm-catalog` branch, main as PR base, and an owned
PR marker `<!-- omnipack:codm-catalog -->`. Verify the expected head/base/repository
and source-only changes before adopting or updating it. Use normal branch
commits and pushes, incorporating current main into the owned branch when
necessary without rewriting unrelated work; conflicts or unexpected edits fail
for a later maintainer action. Compare main and the remote source-branch head to
the captured values before publishing. A race or rejection ends this attempt.
An open branch with identical proposed files receives no new commit simply
because main advanced. Validation still uses the selected current main.

After an earlier PR merges, a new source revision can reuse the branch only when
its old content is integrated into main and ownership is unambiguous. A closed,
unmerged PR does not blacklist the source. A subsequent run can propose it
again, while still respecting branch ownership. Preserve merged/closed PRs as
history; no issue or duplicate-cleanup subsystem is introduced.

A remote operation can succeed without acknowledgement. Report that uncertainty
and let the next invocation look up the owned branch/PR before creating another;
do not add an immediate retry loop. The source workflow never writes main or
rolling releases. Normal nightly main-advancement safeguards continue to handle
catalog merges racing with nightly builds.

## Risks / Trade-offs

- Automatic inspection retains roughly 434 resolver lines and associated tests.
  Isolation improves failure boundaries; new workflow code may increase total size.
- A newly eligible project without a supported APK blocks a complete update.
  Keep precise diagnostics and the last committed catalog available; do not hide
  the blockage with placeholder IDs or a partial proposal.
- Independent generation inspects more projects than coverage-filtered builds.
  Measure this during migration and retain bounded downloads and unchanged-source
  gating. First generation can expose existing unsupported projects or collisions.
- Source removals or package changes can invalidate pins and overlays. Candidate
  pack validation blocks those proposals until the relevant curation is revised
  through normal reviewed changes; automation does not guess replacement rules.
- README-only scheduling misses release-only ID changes. Provide documented
  forced refresh and explicitly describe retained-failure retry timing.
- Main or the owned proposal branch can advance. Fail and rerun instead of adding
  automatic generation retries, branch rewriting or merge-conflict resolution.

## Migration Plan

1. Capture existing source fixtures, selected identities and export bytes. Build
   an inventory of all eligible README projects and mark which were previously
   suppressed by dual coverage. Resolve the initial full source automatically;
   use existing accepted entries/cache as the initial fallback baseline only for
   previously admitted generated projects. Do not treat every historical cache
   entry as an accepted catalog member.
2. Add the generator, committed source and bound metadata/state in the same
   implementation change as the adapter switch. Validate automatic bootstrap
   against the supported complete-catalog contract; do not claim a partial seed
   represents an accepted full README revision.
3. Switch build ingestion and reporting, retain generated source identities,
   and prove byte-identical fixture exports. Add previously suppressed project
   cases to prove that local source completeness does not change coverage rules.
4. Remove cache from nightly's candidate capture/staging/commit paths. Preserve
   its exact-byte, README-boundary and release contracts. Add the separate
   generation workflow and source-only PR boundary checks.
5. Update operator and curation documentation, run required development checks
   and controlled two-run generation/PR tests, and record verification evidence.
   Do not perform real remote PRs, pushes or release writes as test execution.

Deploy code and accepted source files together. Rollback is a reviewed revert
of the adapter/workflow/source migration as a unit, retaining the previous
exports and generation evidence; do not automatically modify published releases.
