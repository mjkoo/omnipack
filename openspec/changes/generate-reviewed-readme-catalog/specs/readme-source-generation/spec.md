## Purpose

Produces reviewed, committed Obtainium catalogs from README project links so
routine pack publication can consume accepted source data without APK discovery.

## ADDED Requirements

### Requirement: README changes gate automatic generation

The source-maintenance workflow SHALL compare the SHA-256 of fetched README
bytes with accepted metadata committed on main. Matching bytes SHALL skip
release lookup, APK inspection and PR writes unless a manual forced refresh was
requested. Metadata SHALL bind the configured source URL, README hash and
catalog digest. A different configured source URL SHALL require generation.
The accepted state SHALL advance only through merge of a reviewed catalog PR.
Missing initial state SHALL require successful generation before acceptance;
malformed existing state SHALL fail visibly rather than be silently ignored.

#### Scenario: Accepted README is unchanged

- **WHEN** the URL and fetched bytes match accepted source metadata without force
- **THEN** the workflow reports a no-op without resolution or PR writes

#### Scenario: Changed prose produces unchanged catalog

- **WHEN** changed README bytes yield identical catalog bytes
- **THEN** successful generation proposes the new source hash through a metadata update PR

#### Scenario: Unmerged proposal is not acceptance

- **WHEN** a prior catalog proposal is still open or was closed without merging
- **THEN** its source hash does not replace the hash accepted on main

### Requirement: Generation produces a deterministic Obtainium source catalog

Generation SHALL parse GitHub repository links from the configured README's
Project catalog tables, require recognizable table structure, normalize and
deduplicate project URLs, and report unsupported links as skipped. Links outside
those tables SHALL NOT introduce projects. Every supported GitHub repository
link in those tables SHALL be eligible independently of other catalogs, deny
rules or final pack selection. Missing or malformed table structure and an
unexpected empty eligible catalog SHALL fail generation rather than propose a
mass deletion.

The result SHALL be deterministic Obtainium-compatible JSON containing settings
and app records with real package IDs, GitHub source identity, repository-derived
names, owner-derived authors and empty app categories. It SHALL use existing
supported source defaults and serialization conventions, without final pack
family selection or curated overlays. Different projects with the same package
ID SHALL fail catalog validation with both URLs identified rather than silently
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

### Requirement: Package IDs are resolved automatically from release APKs

Generation SHALL use the shared host-scoped HTTP helper and the GitHub latest
release endpoint to resolve package IDs automatically. Every release asset whose
filename ends in `.apk`, case-insensitively, SHALL be inspected unless an accepted
ID can be reused for the same host-assigned release identifier. IDs SHALL NOT be
invented or supplied through a required manual-resolution step.

No eligible APK, disagreement between APK package IDs, or any unreadable eligible
APK SHALL fail that project's resolution. Reading only a successful subset SHALL
NOT establish agreement. Resolution SHALL retain bounded downloads, ranged
manifest extraction and manifest validation. APKs SHALL be treated as data and
SHALL NOT be executed. Non-APK archives and non-GitHub discovery remain outside
the supported resolution boundary.

#### Scenario: All APKs agree

- **WHEN** all eligible assets can be read and declare the same real package ID
- **THEN** generation records that ID and the host-assigned release identifier

#### Scenario: One APK differs or is unreadable

- **WHEN** an eligible APK disagrees with another or cannot be read within download limits
- **THEN** resolution fails rather than accepting IDs from the remaining subset

#### Scenario: No eligible APK

- **WHEN** a latest release contains only non-APK assets
- **THEN** resolution fails with an explicit unsupported-asset diagnostic

### Requirement: Accepted resolution state supports reuse without accepting partial catalogs

Resolution state SHALL be keyed by normalized project URL and bind a package ID
to its successfully inspected host-assigned release identifier, not its tag name.
An equal identifier SHALL reuse the accepted ID without APK reads; a different
identifier SHALL trigger resolution. Failed attempts SHALL leave the last
successful ID and release identifier unchanged.

For a project present in the accepted catalog, failed refresh SHALL retain its
accepted entry and report the failure. Accepted catalog and cache identities
SHALL agree; malformed or inconsistent state SHALL fail generation. A newly
eligible project without accepted catalog membership SHALL require successful
resolution, even if a transient or historical cache contains an ID. Any unresolved
new project SHALL fail the whole generation attempt, prohibit catalog PR writes
for that attempt and leave accepted state unchanged. Successful resolutions from
an incomplete attempt MAY be retained only as diagnostic work, not accepted
catalog or source metadata. Later invocations SHALL retry while README content
remains unaccepted. After merging a proposal with retained failures, unchanged
README runs SHALL skip resolution; another README change or forced refresh is
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

### Requirement: Catalog changes are checked before PR publication

The separate workflow SHALL validate source shape, IDs, deterministic rendering
and metadata/catalog/state consistency, then build and structurally verify both
pack variants with the proposed source catalog and the selected main revision's
configuration. Failures, including stale selectors and package collisions, SHALL
block PR writes. Generated pack outputs and the pack README SHALL be diagnostics
for this operation, not part of its source-update commit. The checked source bytes
SHALL be the bytes proposed in the PR. Diagnostics SHALL identify the selected
base revision and source revision, catalog changes, skipped links, resolution
results, retained failures and pack validation outcome.

#### Scenario: Candidate changes a pinned identity

- **WHEN** the proposed catalog makes an active composition selector stale
- **THEN** validation fails and the workflow does not publish the invalid source proposal

#### Scenario: Candidate is valid

- **WHEN** source checks and composed-pack verification pass
- **THEN** only the checked source catalog, source metadata and resolution state are eligible for a PR commit

#### Scenario: Bytes change after checking

- **WHEN** proposed source bytes differ from the validated candidate
- **THEN** PR publication is rejected

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
