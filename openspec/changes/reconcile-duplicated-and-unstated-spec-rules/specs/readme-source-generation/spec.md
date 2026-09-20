## MODIFIED Requirements

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

Reviewed regexes SHALL be limited to constructs that mean the same to the engine
that validates them here and to the supported Obtainium client that applies
them. They SHALL therefore reject `\d`, `\D`, `\s`, `\S`, `\w`, `\W`, `\b` and
`\B`, whose character or boundary semantics differ between the two; every other
alphanumeric escape except the control-character escapes `\n`, `\r`, `\t`, `\f`
and `\v`, which excludes anchors such as `\A` and `\Z`, backreferences and octal
escapes; every group opening with `(?` other than the non-capturing `(?:`, the
lookahead `(?=` and the negative lookahead `(?!`, which excludes inline flags,
named groups, lookbehind and comments; and possessive quantifiers. Authors SHALL
use explicit character classes for the intended matching set. Escaped literal
backslashes SHALL be supported.

Only an explicit reviewed rule SHALL enable prereleases or classify a resource
as track-only. A 404, missing APK, download failure or package-ID conflict SHALL
NOT cause automatic classification, a fabricated package ID or a silent skip of
an otherwise eligible project. Effective discovery settings SHALL be retained
in generated Obtainium entries so a resolved prerelease remains discoverable
after import. Final-pack overlays SHALL NOT substitute for discovery policy.

A rule SHALL choose which release to resolve before making any request, from
its own settings alone, and generation SHALL perform exactly one release lookup
per project, against the endpoint that choice names: a rule enabling
prereleases or filtering release titles SHALL resolve from the bounded releases
list, and every other rule SHALL resolve from the stable latest release.
Neither endpoint SHALL be attempted as a fallback for the other, so a project
whose chosen endpoint fails SHALL fail resolution rather than be retried
against the other endpoint. A transport-level retry of that one lookup SHALL
reissue the same request to the same endpoint and SHALL NOT be a second lookup:
this requirement governs which endpoint is asked and how many times a release
is looked up, not how many HTTP attempts the shared transport makes.

The settings that select a release, namely prerelease admission, release-title
filtering and the consumer setting `fallbackToOlderReleases`, SHALL be
available to a rule of either kind, and the generated entry SHALL carry each
configured value. The settings that act on a release's APK assets, namely APK
filename filtering, version extraction and its group selector, SHALL be
available to an APK rule only, and a track-only rule carrying one SHALL fail
validation with the project and the setting identified, because a track-only
resource has no APK for them to act on. Consumer fallback SHALL NOT change which release the
generator resolves.

#### Scenario: Version extraction references an absent capture group

- **WHEN** a rule selects group `2` or includes `$2` but its version-extraction regex contains only one capturing group
- **THEN** policy validation fails before discovery or any network request, and no candidate catalog is emitted

#### Scenario: Policy JSON repeats a key

- **WHEN** policy JSON repeats an object key, including an identical project URL or discovery setting
- **THEN** generation fails before HTTP requests or candidate creation instead of silently accepting the last value

#### Scenario: Only prereleases exist

- **WHEN** a project explicitly enables prereleases and publishes a matching prerelease APK
- **THEN** generation resolves it from the bounded releases list, which its rule
  selected before any request was made, without requesting the stable latest
  release at all, and its exported settings permit Obtainium to find that
  release

#### Scenario: A track-only rule carries an APK-only setting

- **WHEN** a track-only rule carries APK filename filtering, version extraction or its group selector
- **THEN** policy validation fails with the project and that setting identified, before any network request

#### Scenario: A track-only rule carries a release-selection setting

- **WHEN** a track-only rule enables prereleases or consumer fallback
- **THEN** policy validation accepts it and the generated tracking entry carries the configured value

#### Scenario: Exported title filter and consumer fallback reach the client

- **WHEN** a rule's release-title filter excludes a mutable release channel and enables consumer fallback, and the newest matching versioned release resolves
- **THEN** the generated entry's title filter excludes the mutable channel and it carries `fallbackToOlderReleases` enabled, so Obtainium may later use an older matching release when a newer one has no eligible APK
- **AND** a rule that disables consumer fallback exports it disabled

#### Scenario: An unconfigured project has no stable APK

- **WHEN** a new APK project has no usable release under the default policy
- **THEN** it remains unresolved and blocks generation rather than becoming track-only

#### Scenario: A policy entry outlives a removed README row

- **WHEN** the README removes a project with a committed rule
- **THEN** generation reports the inactive rule and proposes removal of the catalog entry without rewriting the rule

#### Scenario: A regex uses a construct outside the shared subset

- **WHEN** a reviewed regex uses an inline flag, a named group, a lookbehind, a backreference, an anchor escape or a possessive quantifier
- **THEN** policy validation fails with the project identified, before any network request

### Requirement: Explicit track-only resources remain honest tracking entries

Track-only generation SHALL require, in reviewed policy, an explicit stable
numeric-string resource ID, a nonempty rationale and a documented manual
installation path. The installation path SHALL say in words where the resource
is installed from and SHALL name that place by an `https` URL carrying no
credentials, port, query or fragment, a github.com URL naming a repository and
nothing deeper; a rule lacking any of these SHALL fail policy validation with
the project identified. It SHALL
validate a published release under the selected channel policy without APK or
archive downloads or package-ID discovery. It SHALL emit `trackOnly: true`,
`versionDetection: false`, `includeZips: false` and disabled APK architecture
filtering. The record SHALL contain no observed installed or latest version,
fixed download URL or claim of an Android package identity. Tracking outcomes
SHALL be separate from APK resolution in diagnostics.

A track-only resource SHALL appear under its own synthetic identity and SHALL
NOT replace the entry of the app it extends in either pack. Its description SHALL carry
the rule's rationale and installation path, and with consumer guidance SHALL
explain that path, and that Obtainium
notifications and acknowledgement neither install it nor detect its installed
version. Enabling ZIP extraction SHALL NOT be presented as a way to install a
non-APK archive. The pack's own notification tracker is not one of these
resources; "Both packs include one shared omnipack notification tracker" in
pack-curation owns it.

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

#### Scenario: A track-only rule lacks a rationale or a usable installation path

- **WHEN** a track-only rule has no rationale, or its installation text holds no acceptable `https` URL or nothing beyond one
- **THEN** policy validation fails with the project identified, before any network request

### Requirement: Release APKs determine package IDs automatically

Generation SHALL resolve APK package IDs automatically, and its requests SHALL
be subject to the same host-scoped credential rules as every other
source-discovery request. Default APK policy SHALL use the GitHub latest stable
release endpoint. Explicit prerelease or release-title policy SHALL request a
single page of at most 100 releases, ignore drafts and disallowed prereleases, filter titles
(using the tag when the title is empty), and choose the newest matching release
by publication time with release ID as a deterministic tie-breaker.

Invalid selection metadata SHALL fail visibly. Two further outcomes SHALL fail
visibly and SHALL be distinguishable from each other, because they call for
different corrections. A releases response holding more entries than that bound
SHALL fail identifying the bound, because the host answered outside the page
that was requested. A response within the bound in which the rule permits no
release SHALL fail identifying that limitation. Neither SHALL be answered by an
unbounded scan or a broader release policy.

Every direct asset in that selected release whose filename ends in `.apk`,
case-insensitively, and matches the configured APK filename regex SHALL be
inspected on every run. No filename filter means all direct APKs. Filtered-out
asset names SHALL appear in diagnostics. Regex semantics SHALL be compatible
with the supported Obtainium client. APK package IDs SHALL NOT be invented or
supplied through a required manual-resolution step.

No eligible APK, disagreement between APK package IDs, or any unreadable eligible
APK SHALL fail that project's resolution without trying an older release.
Reading only a successful subset of the policy-selected APKs SHALL
NOT establish agreement. Resolution SHALL use bounded downloads, ranged
manifest extraction and manifest validation. APKs SHALL be treated as data and
SHALL NOT be executed. Non-APK archives and non-GitHub discovery are outside
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

#### Scenario: The releases response exceeds the bound

- **WHEN** the releases response holds more entries than the single requested page of at most 100 releases allows
- **THEN** resolution fails identifying the bound, distinguishably from a response within the bound in which the rule permits no release, and no release is selected from that response

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
outcome. The base revision SHALL appear in the PR body and in the run summary
of a run whose staging succeeds; a run whose staging fails SHALL summarize the
failing stage and its reason instead. The pack validation outcome SHALL be the reported results of the run's test,
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
