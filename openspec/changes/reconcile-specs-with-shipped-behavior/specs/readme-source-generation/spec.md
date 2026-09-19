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

Reviewed regexes SHALL reject `\d`, `\D`, `\s`, `\S`, `\w`, `\W`, `\b`, and
`\B`, whose character or boundary semantics differ between the engine that
validates them here and the supported Obtainium client that applies them.
Authors SHALL use explicit character classes for the intended matching set.
Escaped literal backslashes SHALL remain supported.

Only an explicit reviewed rule SHALL enable prereleases or classify a resource
as track-only. A 404, missing APK, download failure or package-ID conflict SHALL
NOT cause automatic classification, a fabricated package ID or a silent skip of
an otherwise eligible project. Effective discovery settings SHALL be retained
in generated Obtainium entries so a resolved prerelease remains discoverable
after import. Final-pack overlays SHALL NOT substitute for discovery policy.

A rule SHALL choose which release to resolve before making any request, from
its own settings alone, and generation SHALL make exactly one release request
per project: a rule enabling prereleases or filtering release titles SHALL
resolve from the bounded releases list, and every other rule SHALL resolve from
the stable latest release. Neither SHALL be attempted as a fallback for the
other, so a project whose chosen endpoint fails SHALL fail resolution rather
than be retried against the other endpoint.

The settings that select a release, namely prerelease admission, release-title
filtering and the consumer setting `fallbackToOlderReleases`, SHALL be
available to a rule of either kind, and the generated entry SHALL carry each
configured value. The settings that act on a release's APK assets, namely APK
filename filtering, version extraction and its group selector, SHALL be
available to an APK rule only, and a track-only rule carrying one SHALL fail
validation with the project and the setting identified, because a track-only
resource has no APK for them to act on. Unconfigured projects SHALL preserve
their existing defaults. Consumer fallback SHALL NOT change which release the
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

Generation SHALL resolve APK package IDs automatically, and its requests SHALL
be subject to the same host-scoped credential rules as every other
source-discovery request. Default APK policy SHALL use the GitHub latest stable
release endpoint. Explicit prerelease or release-title policy SHALL use a bounded list
of at most 100 releases, ignore drafts and disallowed prereleases, filter titles
(using the tag when the title is empty), and choose the newest matching release
by publication time with release ID as a deterministic tie-breaker.

Invalid selection metadata SHALL fail visibly. Two further outcomes SHALL fail
visibly and SHALL be distinguishable from each other, because they call for
different corrections. A releases response holding more entries than the bound
SHALL fail identifying the bound, rather than being filtered as though it were
the project's whole history, since the project's history is larger than the
supported scan. A response within the bound holding no release the rule permits
SHALL fail identifying that limitation, since the project's history is within
the scan and its policy matches nothing in it. Neither SHALL be answered by an
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

#### Scenario: The releases response exceeds the bound

- **WHEN** the releases response holds more entries than the bound allows
- **THEN** resolution fails identifying the bound, distinguishably from a bounded response holding no permitted release, and no release is selected from the truncated view
