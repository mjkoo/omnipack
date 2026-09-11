# readme-source-generation Specification

## Purpose

Produces reviewed, committed Obtainium catalogs from README project links so
routine pack publication can consume accepted source data without APK discovery.

## Requirements

### Requirement: README and reviewed project policy gate automatic generation

The source-maintenance workflow SHALL compare the SHA-256 of fetched README
bytes and the reviewed project-policy bytes with accepted metadata committed
on main. Matching README, policy and configured URL SHALL skip
release lookup, APK inspection and PR writes unless a manual forced refresh was
requested. Metadata SHALL bind the configured source URL, README hash,
project-policy hash and catalog digest. A different configured source URL or
changed policy SHALL require generation even when the README is unchanged.
The accepted state SHALL advance only through merge of a reviewed catalog PR.
Missing initial state SHALL require successful generation before acceptance;
malformed existing state SHALL fail visibly rather than be silently ignored.

#### Scenario: Accepted README is unchanged

- **WHEN** the URL, fetched README and valid policy match accepted source metadata without force
- **THEN** the workflow reports a no-op without resolution or PR writes

#### Scenario: Changed prose produces unchanged catalog

- **WHEN** changed README bytes yield identical catalog bytes
- **THEN** successful generation proposes the new source hash through a metadata update PR

#### Scenario: Unmerged proposal is not acceptance

- **WHEN** a prior catalog proposal is still open or was closed without merging
- **THEN** its source hash does not replace the hash accepted on main

#### Scenario: Discovery policy changes without a README edit

- **WHEN** reviewed policy enables prereleases or changes a project's treatment while README bytes stay unchanged
- **THEN** generation runs under that policy and proposes its hash only after successful complete validation

#### Scenario: Policy formatting changes

- **WHEN** policy bytes change without changing any effective project rule
- **THEN** generation can reuse valid unchanged-release resolutions and propose the changed input hash without manufacturing catalog changes

### Requirement: Reviewed rules declare discovery and tracking treatment

The system SHALL read committed per-project policy keyed by normalized GitHub
repository URL. A project without a rule SHALL default to APK discovery using
stable releases. Rules SHALL explicitly distinguish APK projects from
track-only resources and support bounded prerelease, release-title, APK-filename
and source-version settings. Invalid types, unsupported fields, invalid regexes,
duplicate normalized keys and inconsistent rule combinations SHALL fail before
the unchanged-input gate. Inactive rules whose project is absent from the
README SHALL be reported without introducing that project or blocking a source
removal. Neither generation nor its publisher SHALL write this policy.

Numeric version-extraction group selectors and `$N` references SHALL name
existing groups in the configured regex, with group zero denoting the full
match. Leading and trailing selector whitespace SHALL be ignored for validation.

Only an explicit reviewed rule SHALL enable prereleases or classify a resource
as track-only. A 404, missing APK, download failure or package-ID conflict SHALL
NOT cause automatic classification, a fabricated package ID or a silent skip of
an otherwise eligible project. Effective discovery settings SHALL be retained
in generated Obtainium entries so a resolved prerelease remains discoverable
after import. Final-pack overlays SHALL NOT substitute for discovery policy.

The initial policy SHALL enable prerelease APK discovery for EmuLnk/emulnk,
castdrian/showdown-ds and mastercook777/Heimdall-AYN-Thor-Assistant, and classify
AverageConsumer/kanto-gear as track-only. Showdown and Heimdall SHALL select
their versioned APK filenames and retain prerelease suffixes in version
extraction. Heimdall SHALL exclude the mutable debug-latest release channel.
The initial APK rules SHALL set the supported consumer setting
`fallbackToOlderReleases` to true for Heimdall and false for Showdown and
EmuLnk. Unconfigured projects SHALL preserve their existing default for that
setting. Consumer fallback SHALL NOT change which release the generator
resolves.

#### Scenario: Version extraction references an absent capture group

- **WHEN** a rule selects group `2` or includes `$2` but its version-extraction regex contains only one capturing group
- **THEN** policy validation fails before discovery or the unchanged-input gate, and no candidate catalog is emitted

#### Scenario: Only prereleases exist

- **WHEN** a project explicitly enables prereleases and publishes a matching prerelease APK
- **THEN** generation can resolve it through the releases list despite a 404 from the stable latest endpoint, and its exported settings permit Obtainium to find that release

#### Scenario: Heimdall client skips debug and falls back for asset availability

- **WHEN** a newer Heimdall release title is `debug-latest`, the newest matching versioned release has no eligible APK, and an older matching versioned release has an eligible APK
- **THEN** the generated entry's title filter excludes the debug release and its enabled `fallbackToOlderReleases` setting permits Obtainium to use the older matching release
- **AND** Showdown and EmuLnk retain explicit disabled fallback settings

#### Scenario: An unconfigured project has no stable APK

- **WHEN** a new APK project has no usable release under the default policy
- **THEN** it remains unresolved and blocks generation rather than becoming track-only

#### Scenario: A policy entry outlives a removed README row

- **WHEN** the README removes a project with a committed rule
- **THEN** generation reports the inactive rule and proposes removal of the catalog entry without rewriting the rule

### Requirement: Generation produces a deterministic Obtainium source catalog

Generation SHALL parse GitHub repository links from the configured README's
Project catalog tables, require recognizable table structure, normalize and
deduplicate project URLs, and report unsupported links as skipped. Links outside
those tables SHALL NOT introduce projects. Every supported GitHub repository
link in those tables SHALL be accounted for under its explicit or default
APK/track-only treatment independently of other catalogs, deny rules or final
pack selection. Missing or malformed table structure and an
unexpected empty eligible catalog SHALL fail generation rather than propose a
mass deletion.

The result SHALL be deterministic Obtainium-compatible JSON containing settings
and records with GitHub source identity, repository-derived names unless a
reviewed name is supplied, owner-derived authors and empty app categories.
APK records SHALL have manifest-backed package IDs; explicitly declared
track-only records SHALL have stable synthetic resource IDs. It SHALL use
existing supported defaults and serialization conventions plus reviewed
project settings, without final pack family selection or final-pack overlays.
Different projects with the same entry ID, including tracker/APK collisions,
SHALL fail catalog validation with both URLs identified rather than silently
choose a project or emit an invalid import. Source removals SHALL be reflected
as proposed deletions only after otherwise complete successful generation.

#### Scenario: Duplicate URL spellings

- **WHEN** two eligible links normalize to the same project
- **THEN** one entry is generated with stable output for equivalent input orderings

#### Scenario: Other catalogs already include the project

- **WHEN** an eligible README project is also available in another upstream catalog
- **THEN** source generation still includes it and leaves pack coverage filtering to ingestion

#### Scenario: Table disappears

- **WHEN** fetched content lacks the expected project table or has no eligible projects
- **THEN** generation fails without offering a replacement catalog

#### Scenario: A project is removed

- **WHEN** a valid nonempty README revision removes a previously accepted project
- **THEN** the complete candidate catalog omits it and diagnostics identify the deletion

#### Scenario: One of multiple Project tables is malformed

- **WHEN** a README contains a valid Project table and another Project header with a missing or invalid delimiter
- **THEN** generation fails without proposing removals from the malformed table or emitting a candidate catalog

### Requirement: Package IDs are resolved automatically from release APKs

Generation SHALL use the shared host-scoped HTTP helper to resolve APK package
IDs automatically. Default APK policy SHALL use the GitHub latest stable release
endpoint. Explicit prerelease or release-title policy SHALL use a bounded list
of at most 100 releases, ignore drafts and disallowed prereleases, filter titles
(using the tag when the title is empty), and choose the newest matching release
by publication time with release ID as a deterministic tie-breaker. Invalid
selection metadata or no matching release within the bound SHALL fail visibly.
Every direct asset in that selected release whose filename ends in `.apk`,
case-insensitively, and matches the configured APK filename regex SHALL be
inspected unless accepted state permits reuse. No filename filter means all
direct APKs. Filtered-out asset names SHALL appear in diagnostics. Regex
semantics SHALL be compatible with the supported Obtainium client.
APK package IDs SHALL NOT be
invented or supplied through a required manual-resolution step.

No eligible APK, disagreement between APK package IDs, or any unreadable eligible
APK SHALL fail that project's resolution without trying an older release.
Reading only a successful subset of the policy-selected APKs SHALL
NOT establish agreement. Resolution SHALL retain bounded downloads, ranged
manifest extraction and manifest validation. APKs SHALL be treated as data and
SHALL NOT be executed. Non-APK archives and non-GitHub discovery remain outside
the supported APK-resolution boundary. An explicit track-only resource SHALL
follow its separate metadata-only contract.

#### Scenario: All APKs agree

- **WHEN** all policy-selected APK assets can be read and declare the same real package ID
- **THEN** generation records that ID and the host-assigned release identifier

#### Scenario: One APK differs or is unreadable

- **WHEN** an eligible APK disagrees with another or cannot be read within download limits
- **THEN** resolution fails rather than accepting IDs from the remaining subset

#### Scenario: No eligible APK

- **WHEN** an APK project's selected release contains only non-APK assets
- **THEN** resolution fails with an explicit unsupported-asset diagnostic

#### Scenario: Generator remains strict when Heimdall consumer fallback is enabled

- **WHEN** Heimdall's newest matching release has no eligible APK and an older matching release is usable
- **THEN** generation fails or uses permitted accepted-entry fallback without inspecting the older release as a new successful resolution
- **AND** the generated consumer setting does not broaden generator release selection

#### Scenario: Explicit asset filter selects the supported APK family

- **WHEN** a reviewed filter excludes unrelated assets in the selected release
- **THEN** generation reports those exclusions and requires agreement across every remaining eligible APK

#### Scenario: Newest matching release has a broken APK

- **WHEN** the newest permitted release has an unreadable eligible APK but an older release is usable
- **THEN** resolution fails or uses permitted accepted-entry fallback, without treating the older release as a new successful resolution

#### Scenario: Release scan reaches its bound

- **WHEN** no permitted release occurs within the bounded list
- **THEN** the diagnostic identifies that limitation and no unbounded scan or broader release policy is attempted

### Requirement: Explicit track-only resources remain honest non-APK entries

Track-only generation SHALL require an explicit stable numeric-string resource
ID and a documented manual installation path in reviewed policy. It SHALL
validate a published release under the selected channel policy without APK or
archive downloads, package-ID discovery or package-cache writes. It SHALL emit
`trackOnly: true`, `versionDetection: false`, `includeZips: false` and disabled
APK architecture filtering. The record SHALL contain no observed installed or
latest version, fixed download URL or claim of an Android package identity.
Tracking outcomes SHALL be separate from APK resolution in diagnostics.

Kanto Gear SHALL use resource ID `1845280017`, name `Kanto Gear (mod updates)`,
its existing AverageConsumer/kanto-gear URL and stable release tags. It SHALL
appear as a dual-only tracking entry while the official Gen1Recomp host remains
in both packs. Its description and consumer guidance SHALL explain installation
and updates through Gen1Recomp's Mod Index or ZIP import, and that Obtainium
notifications and acknowledgement do not install the mod or detect its actual
installed version. Enabling ZIP extraction SHALL NOT be presented as a way to
install this Lua archive. The existing omnipack notification tracker SHALL
retain its distinct identity and behavior.

A new tracker whose selected release cannot be verified SHALL block the
complete proposal. An accepted tracker may retain its complete entry on a
lookup failure only with unchanged effective policy and a visible warning.
Changing a project's kind SHALL require fresh validation for the destination
kind with no cross-kind fallback or reuse of an APK package ID as a tracker ID.

#### Scenario: Kanto release contains only a mod ZIP

- **WHEN** Kanto's published release is available and the reviewed rule is track-only
- **THEN** generation emits the tracking entry without seeking an APK, downloading the ZIP or writing package-ID cache state

#### Scenario: User acknowledges a Kanto notification

- **WHEN** the user marks a tracked Kanto release as acknowledged in Obtainium
- **THEN** the documented update action remains installation through Gen1Recomp and no mod-installation claim is made

#### Scenario: A new tracking resource is unavailable

- **WHEN** a new declared tracker has no verifiable permitted release
- **THEN** the source proposal fails with tracking diagnostics instead of accepting an unchecked partial catalog

### Requirement: Accepted resolution state supports reuse without accepting partial catalogs

Resolution state SHALL be keyed by normalized project URL and bind a package ID
to its successfully inspected host-assigned release identifier and effective
project-policy fingerprint, not its tag name alone. Equal release and policy
identifiers SHALL reuse the accepted ID without APK reads; a different release
or effective policy SHALL trigger resolution. Failed attempts SHALL leave the last
successful ID and release identifier unchanged.

For a project present in the accepted catalog, failed refresh SHALL retain its
accepted entry and report the failure only when its effective project policy
is unchanged. A policy change that fails fresh validation SHALL block the
proposal, even for an accepted project. Accepted APK catalog and cache identities
and effective-policy fingerprints SHALL agree; malformed or inconsistent state
SHALL fail generation. Trackers SHALL NOT require package-cache entries. A newly
eligible project without accepted catalog membership SHALL require successful
resolution, even if a transient or historical cache contains an ID. Any unresolved
new APK project SHALL fail the whole generation attempt, prohibit catalog PR writes
for that attempt and leave accepted state unchanged. Successful resolutions from
an incomplete attempt MAY be retained only as diagnostic work, not accepted
catalog or source metadata. Later invocations SHALL retry while README content
remains unaccepted. After merging a proposal with retained failures, unchanged
README/policy runs SHALL skip resolution; another README or policy change or forced refresh is
required to retry those failures.

#### Scenario: Known project release cannot be fetched

- **WHEN** an accepted project's release lookup or APK refresh fails
- **THEN** its accepted entry and successful cache fields are retained with a visible warning

#### Scenario: New project fails

- **WHEN** one newly eligible project cannot be resolved while others succeed
- **THEN** generation fails with no partial catalog PR and no accepted-hash update

#### Scenario: Failed new project later becomes resolvable

- **WHEN** a later run sees the same unaccepted README and resolution now succeeds
- **THEN** it can validate and propose the complete catalog

#### Scenario: Rolling tag gets a new release identifier

- **WHEN** the tag name is unchanged but the host-assigned identifier changes
- **THEN** generation inspects the new release before replacing accepted resolution fields

#### Scenario: Asset policy changes at the same release

- **WHEN** an accepted project's effective policy changes but the host-assigned release ID is unchanged
- **THEN** generation freshly validates under the new policy and cannot reuse or retain the prior-policy identity on failure

### Requirement: Catalog changes are checked before PR publication

The separate workflow SHALL validate source shape, IDs, deterministic rendering
and metadata/catalog/state/policy consistency, then build and structurally verify both
pack variants with the proposed source catalog and the selected main revision's
configuration. Failures, including stale selectors and package collisions, SHALL
block PR writes. Generated pack outputs and the pack README SHALL be diagnostics
for this operation, not part of its source-update commit. The checked source bytes
SHALL be the bytes proposed in the PR. Diagnostics SHALL identify the selected
base revision and source revision, catalog changes, skipped links, resolution
results, tracking-only outcomes, effective policy, retained failures and pack
validation outcome. The selected-base policy SHALL be read-only and its exact
bytes SHALL be bound into checked evidence; changed policy after checking SHALL
block publication. Only catalog, metadata and resolution state SHALL enter the
automated source commit.

#### Scenario: Candidate changes a pinned identity

- **WHEN** the proposed catalog makes an active composition selector stale
- **THEN** validation fails and the workflow does not publish the invalid source proposal

#### Scenario: Candidate is valid

- **WHEN** source checks and composed-pack verification pass
- **THEN** only the checked source catalog, source metadata and resolution state are eligible for a PR commit

#### Scenario: Bytes change after checking

- **WHEN** proposed source bytes differ from the validated candidate
- **THEN** PR publication is rejected

#### Scenario: Policy changes after checking

- **WHEN** the reviewed policy bytes differ from those used to validate the candidate
- **THEN** publication is rejected and the automation does not stage the policy file

### Requirement: One separate workflow maintains source update proposals

A daily scheduled workflow and manual dispatch SHALL operate from main in the
canonical repository, independently of nightly publication. Runs for this
source SHALL be serialized without canceling active runs and have a bounded
runtime. A manually dispatched force option SHALL bypass only the unchanged
README gate. Ineligible refs and forks SHALL perform no remote writes.

The workflow SHALL create or update at most one automation-owned source PR with
base main and a dedicated source-update branch. It SHALL verify repository, base,
head and ownership before updating an existing proposal, reject unrelated branch
changes, and restrict commits to the source catalog and its metadata/resolution
state. Identical candidate content already proposed SHALL cause no new commit or
PR. Changed valid content SHALL update the existing proposal. A closed unmerged
proposal SHALL NOT suppress a later proposal of still-unaccepted source content.
No rejection ledger, automatic merge, direct-main write, failure issue lifecycle
or release write SHALL be introduced.

Each invocation SHALL use one generation/check attempt. Main or source-branch
advancement that invalidates the checked base SHALL cause visible failure and a
later rerun, without automatic regeneration. Failed or ambiguous remote writes
SHALL be reported honestly; a later invocation SHALL discover any existing owned
proposal before creating another. No success SHALL be claimed for an unknown
external result.

#### Scenario: Existing PR has the same candidate

- **WHEN** successful generation matches the content already proposed by the owned PR
- **THEN** no duplicate PR or incidental commit is created

#### Scenario: README changes again before merge

- **WHEN** another successful checked source revision differs from the open proposal
- **THEN** the workflow updates that owned proposal instead of opening another

#### Scenario: Main advances during checking

- **WHEN** main no longer equals the selected validation base before PR publication
- **THEN** the run fails without publishing its stale candidate and a later run starts fresh

#### Scenario: Branch ownership is unexpected

- **WHEN** the expected source branch or PR contains unrelated changes or lacks expected ownership
- **THEN** automation fails without overwriting it

### Requirement: Generation diagnostics and credentials remain scoped

The workflow SHALL use only permissions needed for source-branch and PR writes,
with repository read access for generation and checks and no issue or release
operations. Source text SHALL be handled as data; credentials, downloaded APKs
and raw HTTP caches SHALL be excluded from summaries and artifacts. Current-run
reports SHALL be retained for 14 days on success and failure when available.
Missing reports after early failure SHALL NOT imply successful validation.
Actions SHALL expose failed generation, validation and PR-operation stages.

Catalog checks SHALL execute explicitly within the source-maintenance workflow,
without relying on a PR-created event to run them. Documentation SHALL explain
any additional approval needed for repository-required PR checks and token/PR
creation prerequisites, without automatically changing repository settings.

#### Scenario: PR event does not run checks automatically

- **WHEN** token or repository policy delays downstream PR checks
- **THEN** source generation and pack validation already have explicit workflow results and no automatic merge occurs

#### Scenario: Discovery is unavailable

- **WHEN** README retrieval or APK generation fails
- **THEN** Actions reports failure while the committed catalog remains available to nightly
