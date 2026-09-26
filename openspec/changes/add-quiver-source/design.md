## Context

See proposal.md for motivation. BBoi supplies Obtainium records directly;
Quiver supplies cross-platform project rows without Android package IDs. The
existing codm generator already selects GitHub releases, inspects bounded APK
manifests, renders deterministic catalogs and retains unchanged accepted entries
when resolution fails. Its README discovery, dual-only source eligibility and
hard-coded proposal paths cannot simply be reused for Quiver.

The September 21, 2026 survey found 165 rows across 162 repositories, with 15
indexed APK entries: five same-project overlaps, one alternate Minish Cap port
and nine additional games. These are dated leads, not a fixed catalog roster.
The [catalog](https://github.com/tgeorgiadis/quiver-community-app-catalog) documents
that its optional platform metadata may retain older successful checks.

## Goals / Non-Goals

**Goals:** isolate Quiver discovery from reusable release/manifest/catalog
operations; support ongoing default admission after initial vetting; preserve
existing selections and codm behavior; keep ordinary builds free of APK reads.

**Non-Goals:** GitLab generated resolution, ZIP extraction, source builds,
track-only generation, mod management, automatic installs, universal game-family
inference, Minish Cap replacement, or device validation. Existing manual GitLab
extras remain supported. No device access is authorized by this change.

## Decisions

### Generate an accepted local source

Add a Quiver section to config/sources.json with index URL, optional platform
metadata location from the index, catalog path and exception-policy path.
Use config/catalogs/quiver.json and config/quiver-projects.json. The latter is
versioned and holds per-project APK settings and name/category overrides keyed
by canonical GitHub project URL, plus a skip list. A skip rule carries a reason
and names a row's listed normalized GitHub URL or, for an unsupported row, its
literal repository values; it is matched before any request for that row, so a
persistently failing or unsupported row is silenced. A discovery skip pauses
inspection, not admission: an accepted entry matching the skipped listed URL
is retained unchanged and reported as skipped, without claiming a fresh check.
Other sources are unaffected. Pruning an app is not
Quiver policy: the package deny list matches by package ID across every
source, so a denied app stays out under any repository name. Omitted rules
mean stable APK discovery. Do not add an include allowlist or silently convert
no-APK projects into trackers. Validate policy before requests.

Extract only the common resolver/rendering/retention functions needed from
source_generation.py; keep codm policy semantics and its public command stable.
A separate Quiver orchestration module handles list parsing and skip outcomes.
Building directly from Quiver would put unreliable metadata/APK availability
on the nightly critical path. Manual extras alone would lose ongoing discovery.

### Complete discovery with advisory platform hints

Fetch and validate the index and every listed JSON document, preserving list
IDs and URLs in the generation report. A row names its repository by a
`repository` field holding a bare `owner/name` string, mapped to
https://github.com/owner/name before normalization; an absent
`repositorySource`, or `github` in any case, means GitHub. Upstream already
carries `"repositorySource": "gitlab"` (sonicdcer/Starfox64Recomp). A row with any
other `repositorySource`, or a `repository` that is not a valid owner/name
pair, is a reported unsupported row that is never looked up on GitHub and
blocks nothing. A list whose overall shape is malformed fails. Of the remaining row fields (`name`, `folderName`,
`appIconUrl`, `tags`, `catalogId`, `mods`, `filesToAdd` and so on), generation
uses only `project` for naming and `releaseAssetFilter` for diagnostics.
Resolve supported GitHub repositories through repository metadata, retain canonical identity and alias provenance,
and collapse duplicate canonical projects. Treat upstream text as data; ignore
mod/install directives. Confining list and platform-metadata locations to the
configured catalog host and path prefix keeps an upstream index from steering
requests elsewhere; reuse bounded HTTP and exact-host credential handling.

Repeated rows for one canonical repository always collapse into one project.
Quiver's releaseAssetFilter never becomes an Obtainium filter, so rows that
differ only in upstream asset filters are reported as a diagnostic and do not
fail generation (upstream already lists mstan/FireRedLeafGreenRecomp twice with
different filters). A repository shipping several package IDs is caught by the
all-eligible-APKs-agree rule; a reviewed APK filter or skip is the remedy.
Display-only disagreement uses a stable deterministic name unless overridden.
Never translate foreign regex syntax implicitly. Track alias-to-canonical policy matches; fail if two
rules become ambiguous after canonicalization. A fork remains a separate project.

Resolve each unskipped supported repository's release under the existing
stable/latest or bounded filtered-list policy. Repository metadata distinguishes
an existing project with no permitted release from a missing/private project.
A default latest-release absence can be a skip after repository identification;
network/auth/rate-limit errors cannot. A conclusive repository absence (HTTP
404 or 451) is a reported unavailable-repository skip for a project with no
committed entry and removes a committed entry. Any other persistent lookup
failure, such as a repository GitHub blocks with 403, blocks every run visibly
until a reviewed skip names its row. No fallback scan broadens selection.
Platform metadata is advisory and never authorizes skipping fresh discovery.
A valid list of desktop-only projects can yield an empty APK candidate; an empty
project discovery result or missing list fails instead. Missing/malformed optional
platform data is reported and ignored.

### Deterministic candidate and conservative failure behavior

For new projects, no permitted release or eligible direct APK is a reported
skip. Eligible APKs must all be readable and agree on identity. For accepted
projects whose discovered rows still match by canonical or listed URL, those
same outcomes and transient lookup failures trigger unchanged-policy retention.
Other unresolved projects and changed-policy failures block candidate emission.
Generation regenerates the catalog from the lists: a row matches an entry by
its canonical or listed URL, never by package ID, and an entry no row matches, or whose repository returns 404 or 451, is removed in the reviewed
PR. A renamed repository surfaces there as a changed URL or as a removal plus
an addition. If discovery lists only a new repository name and its release has
no eligible APK, the unmatched old entry is removed without a replacement;
package IDs and titles do not establish rename identity. Retention uses the
committed catalog, not the contents of an open automated proposal. Clear stale
candidate output on rerun.

Render ordinary GitHub Obtainium records with no observed release pin. Name an
entry by the row's `project` (the port name, such as "Sonic 3 A.I.R."), falling
back to the repository name; a reviewed name override wins. The row's `name` is
the game title, which several repositories can share, so it never names an
entry. Collapsed rows whose `project` values disagree use the stable
deterministic choice described above. Default the category to Decomps/Recomps, with reviewed overrides for other
kinds of game ports. Retention re-renders with the same inputs as a fresh
render: current effective policy and the current discovery-derived name and
category, plus the accepted entry's package ID and URL. An upstream `project`
change that coincides with a resolution failure therefore blocks
generation visibly instead of retaining stale text; a later rerun resolves it.
Freshly rendered entries carry canonical URLs; retained entries keep their
accepted bytes. Report skips, canonical aliases, unsupported
rows, filtered assets, release/package observations, retained failures and
added/changed/removed catalog entries. No exact diagnostic wording is required.

### Preserve composition boundaries

Add source quiver and origin quiver-generated to source validation and reports.
Ingest the catalog as baseline entries eligible for both packs. Place Quiver
below codm2000, BBoi, RJNY and extras in source rank, preserving existing dual
preference, pins and package denials.

Retain Quiver candidates for composition, including package-ID overlaps. Catalog-only
proposals cannot carry composition rules, so Quiver candidates go through the
existing family formation and selection unchanged: a Quiver candidate sharing
an effective package ID with an existing candidate, including an explicit
family member such as app:gen1recomp or app:ghostship, joins that family, and
an ordinary Quiver baseline loses whole to an existing member at the same tier.
Families never join by project URL. Every Quiver candidate reaches composition,
including one at another source's project URL. Its baseline eligibility remains
both packs; codm candidates remain dual-only and dual-preferred. Ordinary family
selection, source rank and pins resolve conflicts, and the owner's package deny
list prunes apps from the final packs. A denied app may remain in a source
candidate catalog. Compare against current main to keep unrelated pack choices
and settings unchanged. Do not guess by title. Initial vetting must classify overlaps against existing sources,
including current Minish Cap, so this change alone never replaces an existing
preferred fork. New package IDs and source URLs appear in proposal diffs and
must pass current selector checks.

### Admit the initial source, then keep proposals ordinary

Vet every Android candidate found by the initial refreshed discovery, including
these nine original leads:

| Game | GitHub repository |
| --- | --- |
| Automobili Lamborghini | alondero/automobililamborghini-recomp |
| Star Fox Enhanced | kandowontu/starfox-enhanced |
| Super Smash Bros. Melee | 999sian/melee-pc |
| Pikmin | SSunnKing/Open-Nectar---Pikmin-Native-PC-Mobile-Port |
| Resident Evil Gaiden | sergiomanzur/regaiden-recomp |
| Mario Kart Wii | chrissotraidis/kartpad |
| Silent Hill | SlickAmogus/silent-hill-decomp |
| Eternal Sonata | birabittoh/EternalSonataReprise |
| Sonic 3 A.I.R. | Eukaryot/sonic3air |

Use the established lineage/community-use/basic-APK-vetting standard. Record
observations and dispositions in validation.md in this change directory when
implementation performs them. Record hashes, identities, permissions, SDK/ABI,
signing observations, required data and material limitations. Consumer setup
instructions and maintained rationale belong in ordinary documentation, without
turning it into a validation log. Unofficial or AI-assisted work is not by itself
a rejection reason. No fixed membership test or perpetual allowlist is added.

### Reuse the proposal publisher through fixed source descriptors

Parameterize scripts/source_proposal.py with a fixed supported-source choice,
not arbitrary paths. Keep codm's automation/codm-catalog branch and path defaults
intact. Give Quiver branch automation/quiver-catalog, catalog/candidate/report
paths, its own concurrency group and distinct artifact names. The
readme-source-generation workflow requirements are generalized per source: each
source has its own branch, one open PR, serialization group and catalog path;
the more-than-one-open-PR failure, closure and base-revision checks are scoped
to that source's PR; and a source's run never stages or publishes another
source's catalog. Extend the daily/manual source workflow with
source-specific jobs or an equivalent matrix; isolate each source's result.
Generation/staging/tests/build/structural verification run with read-only access.
The generation step of that read-only check job receives
`GITHUB_TOKEN: ${{ github.token }}` for Quiver and, for parity, codm; the job's
contents-read permission keeps it consistent with the rule that only a
read-only job token reaches generation.
The publisher uses the existing exact checked-commit handoff, base-revision check,
path/mode checks and no-dependency write job. Only that source's catalog can be
proposed. No policy, export or README files enter automated proposal commits.

Reuse unchanged-candidate closure, tree equality and visible failure/rerun
behavior. Do not add locks, race fencing, issue lifecycles or auto-merge. Include
skip and retained-failure diagnostics even when no catalog change occurs. Docs
must cover the existing bot-PR check limitations.

## Risks / Trade-offs

- Fresh lookup across the complete catalog costs requests: repository metadata
  plus release lookups for roughly 160 repositories exceed the unauthenticated
  limit, and rate-limit errors are unresolved failures. The token is optional
  for the CLI but required in practice for a full run, so the workflow's
  generation step supplies one (see the workflow decision); expose rate-limit
  failure rather than trusting stale platform metadata.
- One new broken APK can block a proposal. A reviewed skip or selection
  correction resolves persistent cases; accepted entries retain unchanged data.
- Multiple apps in one repository can require different APK IDs. Initial scope
  is one identity per repository, so use a reviewed single selection or skip.
- Two listed projects resolving to one package ID, such as a newly listed fork,
  fail generation naming both until a reviewed skip or selection picks one;
  one source's catalog never carries a package ID twice.
- Duplicate game entries under different package IDs are an accepted outcome.
  Initial overlap vetting and explicit families cover known cases; proposal
  review catches new ones without a similarity classifier or diagnostics.
- A listed repository that disappears before admission is only a reported
  unavailable-repository skip, so review must read skip reports to notice it;
  transient lookup errors still fail the run rather than being mistaken for it.
- Shared helper changes can regress codm. Preserve its fixtures and run its
  command, generation and publisher regression suites.

## Migration Plan

Ship source configuration, accepted catalog, adapters, precedence changes and
matching exports together after initial vetting. Keep source automation proposals
catalog-only; the initial manual implementation includes policy and pack outputs.
Record every rejected initial Android candidate's known package ID and reason
in the package deny list. A Quiver skip may additionally silence its discovery
row to avoid resolution; it does not record permanent rejection of the app.
Roll back by restoring the source integration/configuration and rebuilding both outputs; never remove an
already installed app as a side effect. The Minish Cap selection of Picori for
single-screen has already landed, so initial overlap vetting classifies Quiver's
alternate Minish Cap port against that selection.
