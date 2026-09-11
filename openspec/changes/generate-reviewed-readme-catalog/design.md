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
The current renderer rejects duplicate entry IDs in an import document.

Manual inspection on 2026-09-11 established why the old discovery path omitted
projects. EmuLnk, Showdown-DS and Heimdall publish prerelease APKs; GitHub's
stable-only `/releases/latest` returns 404 for those repositories. Downloaded
manifests identify `com.emulnk` (v0.5.10), `dev.adrian.showdown`
(v0.1.2-alpha.25) and `com.mastercook777.heimdall` (v0.2.1-alpha.1).
RJNY already supplies EmuLnk with `includePrereleases: true`, matching the
author's [Obtainium configuration](https://github.com/EmuLnk/emulnk/blob/master/obtainium.json).
Its existing source URL and final entry are correct.

Kanto Gear v3.2.8 is a Lua mod archive with no APK. Its
[installation instructions](https://github.com/AverageConsumer/kanto-gear#install)
use official Gen1Recomp and its Mod Index or ZIP import. Both packs already
include that host as `com.theboisclub.pokemonred`. Kanto itself has no current
pack entry. Obtainium supports release notifications through
[track-only entries](https://wiki.obtainium.imranr.dev/sources/), but cannot
install the mod or detect its installed version inside Gen1Recomp.

## Goals / Non-Goals

**Goals:** Put accepted source data between discovery and composition; preserve
existing export behavior while adding the explicitly requested APKs and tracker;
make generation reusable locally
without granting it PR or main publication powers.

**Non-Goals:** A generic source crawler, a replacement APK parser, multi-host
package discovery, automatic conflict resolution, a durable failed-run recovery
protocol, a mod installation/update engine, automatic conversion of failed APK
projects to trackers, or a complete composition-policy refactor. This change isolates the
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
SHA-256, reviewed project-policy SHA-256 and catalog SHA-256. Retain
`config/package-ids.json` as generation-owned APK resolution state, adding a
per-entry effective-policy fingerprint to its successful identity fields. Configure the source
with its local catalog path, README URL and project-policy path; build ingestion
uses only the catalog, while generation reads all three.
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

### Gate by README and policy bytes, with a manual force escape hatch

Compare exact fetched README bytes, the configured URL and exact bytes of
`config/codm-projects.json` to accepted metadata. Only a match on all inputs
stops before release requests. Parse and validate policy before this gate, even
on a no-op. A README prose-only or policy-formatting-only change proposes a
metadata-only update so later runs can recognize acceptance. Forced runs perform
normal resolution even if the README is unchanged, but unchanged generated
content still produces no PR commit. Failed new-project resolution leaves main's
hash unchanged, so scheduled runs retry naturally.

Accepted-entry fallback is different: after a warning-bearing proposal merges,
unchanged README/policy runs skip again. Resolving its newer release requires
another README or policy-file change or a forced run. This deliberately accepts the trigger limitation
instead of adding a second release-polling system.

### Declare project treatment before discovery

Add `config/codm-projects.json`, referenced by the codm source configuration.
It has `schemaVersion: 1` and a `projects` object keyed by normalized GitHub
repository URL. An absent rule means an APK project with the existing stable,
all-direct-APK discovery behavior. A rule declares `kind: apk` or
`kind: track-only`, an optional display `name`, and an `additionalSettings`
object limited to `includePrereleases`, `filterReleaseTitlesByRegEx`,
`apkFilterRegEx`, `versionExtractionRegEx` and `matchGroupToUse`. Track-only
rules additionally require a stable numeric-string `trackerId`, `rationale`
and an `installation` instruction naming the host and its canonical URL. APK rules
cannot supply an ID; identities still come from manifests.

Reject malformed types, duplicate normalized keys, unsupported fields, invalid
regular expressions, and inconsistent rule combinations. Report rules absent
from a valid README revision as inactive without introducing their projects or
blocking genuine source removals. Rules are human-reviewed input, never learned
from HTTP errors or written by the source PR automation. The normal overlay
remains a post-composition curation layer; it cannot repair failed discovery.

Use these initial explicit rules:

| Project | Treatment |
| --- | --- |
| `github.com/emulnk/emulnk` | APK, `includePrereleases: true`; preserve the higher-source entry at ingestion |
| `github.com/castdrian/showdown-ds` | APK, prereleases enabled, name `Showdown!`, asset filter `^showdown-v[0-9].*\.apk$` |
| `github.com/mastercook777/heimdall-ayn-thor-assistant` | APK, prereleases enabled, name `Heimdall`, release-title filter `^Heimdall v[0-9]+\.[0-9]+\.[0-9]+(?:-(?:alpha|beta)\.[0-9]+)?$`, asset filter `^heimdall-v[0-9].*\.apk$` |
| `github.com/averageconsumer/kanto-gear` | Track-only, stable releases, name `Kanto Gear (mod updates)`, tracker ID `1845280017`; install/update through official `https://github.com/bryanthaboi/gen1recomp` using its Mod Index or ZIP import |

For Showdown and Heimdall, source-version extraction `^v?(.+)$` with group `1`
retains alpha/beta suffixes and matches the inspected manifests. The observations
above are regression evidence, not fixed versions or IDs supplied to discovery.
Kanto's tracker ID is an explicitly assigned resource identity, not an Android
package ID; it stays fixed across title, settings and release changes.

Emit the effective discovery settings into generated entries. Keep
`verifyLatestTag: false` and `sortMethodChoice: date`. For explicit APK rules,
set `fallbackToOlderReleases: false` so Obtainium follows the declared release
selection without hiding a broken newest APK behind an older release. Preserve
unconfigured legacy entries' existing defaults, including their consumer-side
older-release fallback setting, for byte compatibility. This does not add
older-release discovery to the generator. Explicitly classified APK entries set
`trackOnly: false`; track-only entries set `trackOnly: true`,
`versionDetection: false`, `includeZips: false` and
`autoApkFilterByArch: false`. Do not embed observed releases, APK URLs or
installed-version state. Include the manual installation instruction in the
tracker's `about` setting and user documentation. Trackers keep the existing
codm dual-only eligibility; Kanto's host remains available in both packs.

Alternative: add hand-maintained extras for the two APKs and exempt covered
projects from generation. Extras are a viable immediate curation path, but
would make independent source completeness depend on another catalog and
duplicate discovery policy. Explicit rules keep APK IDs automatically derived and
allow the complete catalog to stand alone. A generic ZIP fallback would not
solve Kanto: its archive contains no Android application.

### Generate a complete independent source; preserve coverage at ingestion

Parse only Project catalog tables, deduplicate normalized repository links and
account for every eligible project under its declared APK or track-only rule,
regardless of current upstream coverage. Reject
missing/malformed table structure and empty eligible input. Keep unsupported
links in diagnostics. Generate repository names, owner authors and empty
categories using supported GitHub import defaults, with explicit policy names
and settings where present. Do not apply final-pack overlays or
family selection to this source file.

The ingestion adapter reads this Obtainium JSON through shared record
normalization and supplies the established codm provenance, origin, dual-only
eligibility and preference. Preserve the early higher-source eligibility check
and normalized-URL coverage suppression before applying final candidate policy.
This still differs from ordinary JSON adapters in source-specific semantics;
forcing identical semantics would change current pack selections. The broader
repeated-policy cleanup remains separate.

A complete source may expose entry-ID collisions between links formerly hidden by
upstream coverage, including tracker/APK collisions. Fail with both project URLs rather than invent a winner or
weaken the Obtainium document's unique-ID constraint. This is a validation
failure, not a request to enter package IDs manually.

### Resolve the declared release channel and eligible APK set

Default APK projects retain GitHub's latest stable release endpoint. Projects
opting into prereleases or release-title filtering use the releases-list
endpoint, bounded to 100 releases in one response. Ignore drafts, apply the
configured prerelease/title rules (title, or tag if title is empty), then select
the newest by `published_at`, with numeric release ID as a deterministic
tie-breaker. Missing/malformed release identifiers or dates fail visibly.
No eligible release within the bound fails with a diagnostic; do not silently
broaden the channel or drop the filter. The Heimdall title rule excludes its
mutable private-development `debug-latest` channel.

Within that one selected release, inspect every direct `.apk` asset matching
the configured filename regex, case-insensitively for the extension and with
case-sensitive regex matching. An empty filter means all direct APKs. Record
filtered-out asset names. No eligible asset, disagreement or an unreadable
eligible APK fails resolution; never fall back to an older release or silently
use one successful ABI. Scoped filters are deliberate policy, not guesses made
after observing a failure. Keep regex syntax to the shared Python/Dart subset
and verify the selected assets with Obtainium during migration.

Track-only projects require a selected published release under the same channel
rules, but no APK, package-ID resolution or archive download. A tracker receives
its explicit resource ID and has no package-cache entry. Reports distinguish
successful tracking from package resolution. A failed new tracker lookup blocks
the complete proposal; an accepted tracker can retain its full entry with a
warning only when it equals the deterministic record rendered from the current
rule. This establishes unchanged treatment without adding tracker data to the
APK cache. A release or README changing never
automatically changes a project's declared kind.

### Keep successful state separate and narrow accepted fallback

Retain host-assigned release identifiers, agreement across all eligible APKs,
ranged extraction, bounded full fallback and
credential scoping. Resolve fresh projects automatically. For entries already
in the accepted catalog, a failed refresh retains the full accepted entry and
unchanged successful cache fields with a warning only when its effective
project policy is unchanged. Catalog/cache inconsistencies fail before generation.

Bind each successful APK cache entry to the SHA-256 of canonical effective
project policy, after defaults. Include the declared kind, name and supported
settings in this fingerprint; policy formatting changes do not invalidate
reuse. Reuse requires accepted membership, an equal host-assigned release ID
and an equal effective-policy fingerprint. A changed rule forces fresh APK
inspection even at the same release, and failure blocks acceptance rather than
retaining an entry with incompatible settings. The source metadata binds exact
policy-file bytes separately for the input gate. Validation checks accepted
entry settings against their cache fingerprints; the current desired policy
may differ from the accepted entry while a policy change awaits generation.

For bootstrap only, derive the legacy default-policy fingerprint for previously
admitted generated APK entries from captured migration evidence. Historical
cache entries outside that set cannot acquire accepted membership this way.
Trackers cannot consume or overwrite APK cache evidence. Any reviewed kind
transition requires fresh validation of the destination kind, with no fallback
across kinds, and retires the old entry atomically in the candidate.

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
source-only path allowlist. Treat project policy as a read-only selected-base
input: bind its exact bytes in validation evidence, reject changes after checks,
and never include it in the automation's three-file commit allowlist.
Test exact-byte correspondence with the checked
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
- A newly eligible APK project without a supported APK blocks a complete update.
  Keep precise diagnostics and the last committed catalog available; do not hide
  the blockage with placeholder IDs, implicit tracking conversion or a partial
  proposal. Explicit prerelease rules fix known discovery gaps; the Kanto rule
  represents a real non-APK resource with honest installation semantics.
- Independent generation inspects more projects than coverage-filtered builds.
  Measure this during migration and retain bounded downloads and unchanged-source
  gating. First generation can expose existing unsupported projects or collisions.
- Source removals or package changes can invalidate pins and overlays. Candidate
  pack validation blocks those proposals until the relevant curation is revised
  through normal reviewed changes; automation does not guess replacement rules.
- README/policy gating misses release-only ID changes. Provide documented
  forced refresh and explicitly describe retained-failure retry timing.
- Main or the owned proposal branch can advance. Fail and rerun instead of adding
  automatic generation retries, branch rewriting or merge-conflict resolution.
- Track-only notifications cannot verify the installed mod. Label Kanto and
  explain that acknowledging a notification does not install/update it.
- A bounded prerelease listing can miss older matching releases. Report the
  bound explicitly; do not conceal it with unbounded scans or fallback channels.

## Migration Plan

1. Capture existing source fixtures, selected identities and export bytes. Build
   an inventory of all eligible README projects and mark which were previously
   suppressed by dual coverage. Resolve the initial full source automatically;
   use existing accepted entries/cache as the initial fallback baseline only for
   previously admitted generated projects. Do not treat every historical cache
   entry as an accepted catalog member.
2. Add and test the four explicit project rules, preserving the already captured
   baseline and adding separate prerelease/tracker evidence. Automatically
   inspect Showdown and Heimdall rather than seeding their IDs from the manual
   investigation. Verify EmuLnk's generated entry resolves but remains suppressed
   by its correct higher-source entry. Validate Kanto as tracking-only, with no
   claim that its ZIP is installable by Obtainium.
3. Add the generator, committed source and bound metadata/state in the same
   implementation change as the adapter switch. Validate automatic bootstrap
   against the supported complete-catalog contract; do not claim a partial seed
   represents an accepted full README revision.
4. Switch build ingestion and reporting, retain generated source identities,
   and prove byte-identical fixture exports for the pre-existing baseline when
   the three requested additions are absent. In the expanded case, prove that
   only Showdown, Heimdall and the Kanto tracker are added to dual, existing app
   bytes/settings and family winners are unchanged, and single is unchanged.
   Freeze the 92/109 captured baseline; do not regenerate it to bless additions.
   Live upstream growth is reported separately from this controlled regression.
5. Remove cache from nightly's candidate capture/staging/commit paths. Preserve
   its exact-byte, README-boundary and release contracts. Add the separate
   generation workflow and source-only PR boundary checks.
6. Update operator and curation documentation, run required development checks
   and controlled two-run generation/PR tests, and record verification evidence.
   Do not perform real remote PRs, pushes or release writes as test execution.

Deploy code and accepted source files together. Rollback is a reviewed revert
of the adapter/workflow/source migration as a unit, retaining the previous
exports and generation evidence; do not automatically modify published releases.
