## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Reviewed rules declare discovery and tracking treatment

**Reason**: Replaced by "Reviewed project rules declare discovery and tracking
treatment". The paragraph fixing the initial policy for EmuLnk, Showdown-DS,
Heimdall and Kanto Gear is dropped; those values live in the reviewed project
policy. Its generic rules remain: explicit fallback values are exported,
unconfigured projects keep their default, and consumer fallback never changes
which release the generator resolves. The Heimdall scenario is restated for any
rule with a release-title filter and consumer fallback.

**Migration**: None. `config/codm-projects.json` already carries these values.

### Requirement: Package IDs are resolved automatically from release APKs

**Reason**: Replaced by "Release APKs determine package IDs automatically",
which is identical except that its consumer-fallback scenario no longer names a
specific project.

**Migration**: None. Resolution behavior is unchanged.

### Requirement: Explicit track-only resources remain honest non-APK entries

**Reason**: Replaced by "Explicit track-only resources remain honest tracking
entries". The Kanto Gear paragraph and scenarios are restated as generic rules
for any track-only resource; Kanto Gear's resource ID, name, URL, release
channel and guidance live in the reviewed project policy. The sentence that
generation appends to every track-only description now says acknowledgement
does not install "the resource" rather than "the mod".

**Migration**: None for users. The committed Kanto Gear entry in
`config/catalogs/codm.json` is rewritten in the same change to what the
changed generator renders for its rule, so unchanged-source regeneration and
tracker retention keep reproducing it. The rendered dual-screen pack picks up
the wording on its next rebuild.
