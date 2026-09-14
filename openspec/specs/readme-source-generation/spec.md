# readme-source-generation Specification

## Purpose

Produces reviewed, committed Obtainium catalogs from README project links so
routine pack publication can consume accepted source data without APK discovery.

## Requirements

### Requirement: Reviewed project rules declare discovery and tracking treatment

The system SHALL read committed per-project policy keyed by normalized GitHub
repository URL. A project without a rule SHALL default to APK discovery using
stable releases. Rules SHALL explicitly distinguish APK projects from
track-only resources and support bounded prerelease, release-title, APK-filename
and source-version settings. Invalid types, unsupported fields, invalid regexes,
duplicate JSON object keys at any nesting level, duplicate normalized project
keys and inconsistent rule combinations SHALL fail before any network request.
Inactive rules whose project is absent from the README SHALL be reported without
introducing that project or blocking a source removal. Neither generation nor
its publisher SHALL write this policy.

Numeric version-extraction group selectors and `$N` references SHALL name
existing groups in the configured regex, with group zero denoting the full
match. Leading and trailing selector whitespace SHALL be ignored for validation.

Reviewed regexes SHALL reject `\d`, `\D`, `\s`, `\S`, `\w`, `\W`, `\b`, and
`\B`, whose character or boundary semantics differ between Python and Dart.
Authors SHALL use explicit character classes for the intended matching set.
Escaped literal backslashes SHALL remain supported.

Only an explicit reviewed rule SHALL enable prereleases or classify a resource
as track-only. A 404, missing APK, download failure or package-ID conflict SHALL
NOT cause automatic classification, a fabricated package ID or a silent skip of
an otherwise eligible project. Effective discovery settings SHALL be retained
in generated Obtainium entries so a resolved prerelease remains discoverable
after import. Final-pack overlays SHALL NOT substitute for discovery policy.

An APK rule SHALL be able to set the supported consumer setting
`fallbackToOlderReleases` explicitly, and the generated entry SHALL carry the
configured value. Unconfigured projects SHALL preserve their existing default
for that setting. Consumer fallback SHALL NOT change which release the
generator resolves.

#### Scenario: Version extraction references an absent capture group

- **WHEN** a rule selects group `2` or includes `$2` but its version-extraction regex contains only one capturing group
- **THEN** policy validation fails before discovery or any network request, and no candidate catalog is emitted

#### Scenario: Policy JSON repeats a key

- **WHEN** policy JSON repeats an object key, including an identical project URL or discovery setting
- **THEN** generation fails before HTTP requests or candidate creation instead of silently accepting the last value

#### Scenario: Only prereleases exist

- **WHEN** a project explicitly enables prereleases and publishes a matching prerelease APK
- **THEN** generation can resolve it through the releases list despite a 404 from the stable latest endpoint, and its exported settings permit Obtainium to find that release

#### Scenario: Exported title filter and consumer fallback reach the client

- **WHEN** a rule's release-title filter excludes a mutable release channel and enables consumer fallback, and the newest matching versioned release has no eligible APK while an older matching versioned release has one
- **THEN** the generated entry's title filter excludes the mutable channel and its enabled `fallbackToOlderReleases` setting permits Obtainium to use the older matching release
- **AND** a rule that disables consumer fallback exports it disabled

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

### Requirement: Release APKs determine package IDs automatically

Generation SHALL use the shared host-scoped HTTP helper to resolve APK package
IDs automatically. Default APK policy SHALL use the GitHub latest stable release
endpoint. Explicit prerelease or release-title policy SHALL use a bounded list
of at most 100 releases, ignore drafts and disallowed prereleases, filter titles
(using the tag when the title is empty), and choose the newest matching release
by publication time with release ID as a deterministic tie-breaker. Invalid
selection metadata or no matching release within the bound SHALL fail visibly.
Every direct asset in that selected release whose filename ends in `.apk`,
case-insensitively, and matches the configured APK filename regex SHALL be
inspected on every run. No filename filter means all direct APKs. Filtered-out
asset names SHALL appear in diagnostics. Regex semantics SHALL be compatible
with the supported Obtainium client. APK package IDs SHALL NOT be invented or
supplied through a required manual-resolution step.

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
- **THEN** generation records that ID and reports the host-assigned release identifier

#### Scenario: One APK differs or is unreadable

- **WHEN** an eligible APK disagrees with another or cannot be read within download limits
- **THEN** resolution fails rather than accepting IDs from the remaining subset

#### Scenario: No eligible APK

- **WHEN** an APK project's selected release contains only non-APK assets
- **THEN** resolution fails with an explicit unsupported-asset diagnostic

#### Scenario: Generator remains strict when consumer fallback is enabled

- **WHEN** a project's rule enables consumer fallback, its newest matching release has no eligible APK, and an older matching release is usable
- **THEN** resolution fails without inspecting the older release, and the project's committed entry is kept as a retained failure only if its effective policy is unchanged
- **AND** the generated consumer setting does not broaden generator release selection

#### Scenario: Explicit asset filter selects the supported APK family

- **WHEN** a reviewed filter excludes unrelated assets in the selected release
- **THEN** generation reports those exclusions and requires agreement across every remaining eligible APK

#### Scenario: Newest matching release has a broken APK

- **WHEN** the newest permitted release has an unreadable eligible APK but an older release is usable
- **THEN** resolution fails without treating the older release as a new successful resolution, and the project's committed entry is kept as a retained failure only if its effective policy is unchanged

#### Scenario: Release scan reaches its bound

- **WHEN** no permitted release occurs within the bounded list
- **THEN** the diagnostic identifies that limitation and no unbounded scan or broader release policy is attempted

### Requirement: Explicit track-only resources remain honest tracking entries

Track-only generation SHALL require an explicit stable numeric-string resource
ID and a documented manual installation path in reviewed policy. It SHALL
validate a published release under the selected channel policy without APK or
archive downloads or package-ID discovery. It SHALL emit `trackOnly: true`,
`versionDetection: false`, `includeZips: false` and disabled APK architecture
filtering. The record SHALL contain no observed installed or latest version,
fixed download URL or claim of an Android package identity. Tracking outcomes
SHALL be separate from APK resolution in diagnostics.

A track-only resource SHALL appear under its own synthetic identity and SHALL
NOT replace the entry of the app it extends in either pack. Its description and
consumer guidance SHALL explain its manual installation path, and that Obtainium
notifications and acknowledgement neither install it nor detect its installed
version. Enabling ZIP extraction SHALL NOT be presented as a way to install a
non-APK archive. The existing omnipack notification tracker SHALL retain its
distinct identity and behavior.

A new tracker whose selected release cannot be verified SHALL block the
complete proposal. A tracker with a committed entry SHALL keep that entry on a
lookup failure, with a visible warning, only under the same unchanged-policy
rule as any other project: the current rule, rendered with the rule's tracker ID
and the committed URL, SHALL reproduce the committed entry exactly, so a changed
tracker ID blocks retention. A change of kind SHALL require fresh validation for
the destination kind, with no cross-kind fallback, and an APK package ID SHALL
NOT be reused as a tracker ID.

#### Scenario: A tracked release contains only non-APK assets

- **WHEN** a track-only resource's published release is available and contains only non-APK archives
- **THEN** generation emits the tracking entry without seeking an APK or downloading an archive

#### Scenario: User acknowledges a tracking notification

- **WHEN** the user marks a tracked release as acknowledged in Obtainium
- **THEN** the documented update action remains the resource's manual installation path and no installation claim is made

#### Scenario: A new tracking resource is unavailable

- **WHEN** a new declared tracker has no verifiable permitted release
- **THEN** the source proposal fails with tracking diagnostics instead of accepting an unchecked partial catalog

#### Scenario: A tracker's resource ID changes and its lookup fails

- **WHEN** reviewed policy changes a committed tracker's resource ID and that tracker's release lookup fails
- **THEN** generation fails with no candidate catalog, and the committed entry is not retained under its old resource ID

### Requirement: Resolution failures keep only unchanged committed entries

Every generation SHALL resolve each eligible project from the README, the
reviewed policy and fresh release data, without reusing identities recorded by
earlier runs. A project that fails to resolve SHALL keep its entry from main's
committed catalog, reported as a retained failure, only when the current policy
would render that same entry for the committed APK package ID, or the rule's
tracker ID, and the committed URL. The current rule is the authority for a
tracker's identity, so a changed tracker ID is a changed effective policy. Any other failure,
including one for a project without a committed entry or for a project whose
effective policy changed, SHALL fail the whole generation, and no candidate
catalog SHALL be offered. Later runs SHALL retry every failure without
maintainer action. No package ID SHALL be invented, or taken from any entry
other than the project's own committed entry.

#### Scenario: Known project release cannot be fetched

- **WHEN** a project with a committed entry and unchanged effective policy fails release lookup or APK inspection
- **THEN** the candidate keeps its committed entry unchanged and the report lists a retained failure

#### Scenario: Policy formatting changes

- **WHEN** policy bytes change without changing what the policy renders for a project, and that project fails to resolve
- **THEN** its committed entry is retained as for any unchanged project

#### Scenario: New project fails

- **WHEN** a project without a committed entry cannot be resolved while others succeed
- **THEN** generation fails with no candidate catalog and no proposal

#### Scenario: Failed project later resolves

- **WHEN** a later run resolves a project that previously failed
- **THEN** its freshly resolved entry enters the candidate without maintainer action

#### Scenario: Changed policy fails to resolve

- **WHEN** a project's reviewed policy changes what would be rendered for it, and fresh resolution under that policy fails
- **THEN** generation fails with no candidate catalog, and the committed catalog stays in place until the policy resolves or is corrected

### Requirement: Catalog changes are checked before PR publication

Before pushing the source-update branch, creating a PR or editing a PR's body,
the source-maintenance workflow's read-only job SHALL validate the candidate
catalog's shape, IDs and deterministic rendering, run the project's full test
suite with the candidate catalog in place, and build and structurally verify
both pack variants with the candidate catalog and main's configuration. Any failure, including
stale selectors and package collisions, SHALL block those writes. When a
successful generation reproduces main's committed catalog, closing an open PR
from the source-update branch SHALL be the only permitted write, and it SHALL
require no tests, build or verification. Generated pack outputs and the pack README SHALL be diagnostics for this
run, not part of the proposal. The proposed catalog SHALL be byte-identical to
the checked candidate: the read-only job SHALL commit the candidate before the
checks and confirm afterwards that the workspace catalog still matches that
commit, and the write job SHALL push only that exact commit, identified by its
SHA, after confirming that its parent is the checked-out main revision and that
it changes only the committed source catalog, which SHALL be a regular file of
mode 100644 in both the base revision and the commit. The read-only job SHALL
likewise reject a generated candidate or a workspace catalog that is not a
regular file. The reviewed policy SHALL NOT be
modified or staged. Diagnostics SHALL
identify the base revision, catalog changes, skipped links, resolution results,
tracking outcomes, effective policy, retained failures and pack validation
outcome. The base revision SHALL appear in the run summary and in the PR body,
and the pack validation outcome SHALL be the reported results of the run's test,
build and verification steps.

#### Scenario: Candidate changes a pinned identity

- **WHEN** the proposed catalog makes an active composition selector stale
- **THEN** validation fails and the workflow does not publish the invalid source proposal

#### Scenario: Test suite fails with the candidate

- **WHEN** the full test suite fails with the candidate catalog in place
- **THEN** no branch or PR write occurs and the run fails visibly

#### Scenario: Candidate is valid

- **WHEN** the tests, source checks and composed-pack verification pass
- **THEN** only the checked source catalog is eligible for the proposal commit

#### Scenario: Bytes change after checking

- **WHEN** the workspace catalog no longer matches the checked commit after the checks ran
- **THEN** the read-only job fails before handing the commit off, and no branch or PR write occurs

#### Scenario: Policy changes after checking

- **WHEN** the reviewed policy file changes in the workspace during the run
- **THEN** the proposal commit still contains only the source catalog and never stages the policy

#### Scenario: Handed-off commit is not the checked commit

- **WHEN** the commit the write job receives differs from the checked SHA, its parent is not the checked-out main revision, or it changes a file other than the source catalog
- **THEN** the run fails before any branch push or PR write

#### Scenario: Catalog is replaced by a symlink or changes mode

- **WHEN** the generated candidate or the handed-off commit makes the source catalog a symbolic link, or changes its mode
- **THEN** the run fails before any branch push or PR write

### Requirement: One separate workflow maintains source update proposals

A daily scheduled workflow and manual dispatch SHALL operate from main in the
canonical repository, independently of nightly publication. Runs SHALL be
serialized without canceling active runs and have a bounded runtime. Ineligible
refs and forks SHALL perform no remote writes.

When the checked candidate differs from main's committed catalog, the workflow
SHALL rebuild one dedicated source-update branch from the main revision that
triggered the run as a single commit containing only the candidate catalog, replace the branch's
previous contents, and create or update the one open PR from that branch to
main. The source-update PR SHALL be an open PR whose head is that branch in the
canonical repository and whose base is main. A PR from another repository whose
branch has the same name SHALL be neither edited nor closed. If more than one
such source-update PR is open, the run SHALL fail before any remote write.
Content equality SHALL be judged on the branch's whole tree: a branch whose tree
equals the rebuilt proposal's tree SHALL be left as it is, even when its commits
differ from the rebuilt commit, and SHALL NOT be pushed again. Commits added to
that branch by hand SHALL be overwritten by the next push. When
the candidate equals main's committed catalog, the workflow SHALL make no
proposal and SHALL close an open source-update PR, without running the tests,
build or verification. README or policy edits that leave the generated catalog
unchanged SHALL NOT produce a proposal. No automatic merge, direct-main write,
failure issue lifecycle or release write SHALL be introduced.

Retention uses main's committed entry, not the open proposal's. A transient
resolution failure for a project whose update an open proposal carries can
therefore drop that update from the rebuilt proposal, or close the proposal
when that update was its only change. The next run that resolves the project
SHALL propose the update again, updating the open PR or opening a new one.

Each invocation SHALL make one generation and check attempt. A failed branch or
PR write SHALL fail the run visibly, and the next run SHALL rebuild the branch
and update the existing PR rather than open another. Before any branch push, PR
creation, PR edit or PR close, the write job SHALL confirm that main is still
the run's base revision. If main has advanced, the run SHALL fail visibly
without those writes, so a rerun of an earlier run cannot close or replace a
newer proposal, and a later run SHALL rebuild the proposal on the newer main.
Main advancing after that confirmation SHALL NOT be fenced: the PR SHALL show
as stale or conflicting until a later run rebuilds it.

#### Scenario: Candidate matches main

- **WHEN** a successful generation produces the committed catalog and main is still the run's base revision
- **THEN** no tests, build or verification are required, and no branch push, PR creation or PR edit occurs
- **AND** any open PR from the source-update branch is closed, which is the only write the run makes

#### Scenario: Existing PR has the same candidate

- **WHEN** the rebuilt proposal's tree equals the tree already on the source-update branch, whatever commits produced that tree
- **THEN** no push occurs, the branch is left as it is, and no duplicate PR is created

#### Scenario: README changes again before merge

- **WHEN** a later checked candidate differs from the open proposal
- **THEN** the workflow rebuilds the branch and updates that PR instead of opening another

#### Scenario: Main advances during checking

- **WHEN** main gains a commit after the run's checkout and before the write job's first write
- **THEN** the run fails visibly without a branch push or any PR write, and a later run rebuilds the proposal on the newer main

#### Scenario: Branch ownership is unexpected

- **WHEN** someone pushes a commit to the source-update branch, a later run has a changed candidate, and the branch's tree differs from the rebuilt proposal's tree
- **THEN** the rebuilt branch replaces that commit

#### Scenario: A fork PR shares the branch name

- **WHEN** an open PR from another repository uses the source-update branch name
- **THEN** the workflow neither edits nor closes it, and a changed candidate gets its own PR from the canonical repository's branch

#### Scenario: A retained failure reverts a proposed update

- **WHEN** an open proposal carries an update for a project with a committed entry, and a later run retains that entry after a transient resolution failure
- **THEN** the rebuilt proposal drops that update, and the PR is closed if no other change remains
- **AND** the next run that resolves the project proposes the update again, in the open PR or a new one

#### Scenario: Write job rerun after main advanced

- **WHEN** the write job of an earlier run is rerun after main has advanced past that run's base revision
- **THEN** it fails visibly without a branch push or any PR write, so a newer proposal is neither closed nor replaced by the earlier catalog

### Requirement: Generation diagnostics and credentials remain scoped

The workflow SHALL grant no permissions at workflow level and SHALL perform no
issue or release operations. Its read-only job SHALL run generation, staging,
tests, building and verification; every step of that job, including checkout
and runtime setup, SHALL run with a job token limited to reading repository
contents, and none SHALL receive the write credential. The write credential
SHALL be available only to the write job, which alone SHALL hold the contents
and pull-request write access needed for the source-update branch and PR. The
write job SHALL install no project dependencies and run no generation, tests,
build or verification: it SHALL check out afresh the main revision that
triggered the run, receive from the read-only job only the checked commit, as
git objects, and the escaped PR body, and run only a publication script that
imports nothing outside the standard library, on the runner's preinstalled
Python, with repository hooks disabled on every git command. The triggering
event SHALL fix the revision whose code the write job runs: no output of the
read-only job SHALL select it, and the write job SHALL fail before any write
unless the base revision the read-only job reports is that triggering revision.
Outputs of the read-only job SHALL reach the publication script only through
step environment variables, never interpolated into a command, and the script
SHALL reject any commit identifier that is not a full 40-character hexadecimal
SHA. No checkout SHALL persist a credential in the
repository configuration. Source text SHALL be handled as data:
upstream-derived text in the run summary and the PR body SHALL be HTML-escaped
inside a preformatted block, so it renders as literal text rather than markup.
Credentials, downloaded APKs and raw HTTP caches SHALL be excluded from
summaries and artifacts. The current run's generation report SHALL be retained
as an artifact for 14 days on success and failure when available, and the run
summary SHALL list retained failures. Missing reports after early failure SHALL
NOT imply successful validation. Actions SHALL expose failed generation, test,
validation and PR-operation stages.

Checks SHALL execute within the source-maintenance workflow, without relying on
PR events to run them. Each PR body SHALL link the workflow run that checked its
current content and SHALL be refreshed whenever the branch is updated.
Documentation SHALL explain that PRs opened by the workflow do not trigger the
project's PR checks, how a maintainer can run them when repository rules
require them, and the token and PR-creation prerequisites, without
automatically changing repository settings.

#### Scenario: PR event does not run checks automatically

- **WHEN** a proposal is opened or updated
- **THEN** its body links the run whose test, build and verification results cover its content, and no automatic merge occurs

#### Scenario: Retained failures are visible

- **WHEN** a run keeps a committed entry after a failed resolution
- **THEN** the run summary lists the project and its failure

#### Scenario: Checks run without the write credential

- **WHEN** generation, staging, tests, building and verification run
- **THEN** they run in the read-only job, whose token can only read repository contents, and the write credential is not present in their environment
- **AND** no checkout has persisted a credential in the repository configuration

#### Scenario: Check job names another revision

- **WHEN** the read-only job's outputs name a base other than the triggering revision, or a commit identifier that is not a full SHA
- **THEN** the write job fails before any branch push or PR write, having run only code from the triggering revision

#### Scenario: Discovery is unavailable

- **WHEN** README retrieval or APK generation fails
- **THEN** Actions reports failure while the committed catalog remains available to nightly
