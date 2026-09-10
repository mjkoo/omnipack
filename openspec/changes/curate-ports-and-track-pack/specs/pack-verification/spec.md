## MODIFIED Requirements

### Requirement: Offline verification checks the serialized pair

The system SHALL validate both rendered import documents without fetching,
hydrating, repairing or rewriting them. It SHALL reject missing/unreadable files,
invalid JSON including non-finite numbers, non-object roots, non-list `apps`,
non-object `settings`, malformed app records, duplicate ids within a variant,
and unsupported source types. Each app SHALL have nonempty string `id`, `name`
and absolute HTTP(S) `url`, string `author`, string-list `categories`, and
`overrideSource` equal to GitHub, HTML or GitLab. GitLab entries SHALL use
public HTTPS gitlab.com project URLs with a namespace and project, optionally
including subgroups (at most 21 path components in total), with the full case-sensitive project path preserved. Track-only ids SHALL NOT be required
to follow Android package-name syntax.

`additionalSettings` SHALL be a string decoding to an object with every key
defined by the committed defaults for its source type, with correctly typed
known settings. Nested HTML steps and header records SHALL be checked. Optional
`preferredApkIndex`, when present, SHALL be an integer, not a boolean. Unknown
fields SHALL NOT be removed or rejected solely for being unknown offline.
`settings.categories` SHALL decode from a string to a mapping of the exact
observed category names to unsigned 32-bit integer ARGB colours, consistent with
the configured colours and existing deterministic fallback rule. Other configured
pack settings SHALL agree with the rendered settings block.

#### Scenario: A rendered settings object is not string encoded

- **WHEN** an entry carries an object directly as `additionalSettings`
- **THEN** verification fails with its variant, id and field identified
- **AND** no repair or network request occurs

#### Scenario: Invalid entries in both variants

- **WHEN** one variant contains duplicate ids and the other contains a setting
  of the wrong type
- **THEN** both independently discoverable errors are reported

#### Scenario: Unknown fields are structurally valid

- **WHEN** a structurally valid entry includes an unknown extra setting
- **THEN** offline verification preserves the input and does not claim that the
  setting is supported by live resolution

#### Scenario: Ordinary offline verification accepts the rendered Aurora pair

- **WHEN** both normally rendered packs contain Aurora with `overrideSource: GitLab`, its canonical public HTTPS gitlab.com project URL and correctly typed complete GitLab settings, and all other offline checks pass
- **THEN** ordinary offline verification succeeds for both variants without network access, hydration, repair or rewriting

#### Scenario: Unsupported source remains an offline error

- **WHEN** either rendered pack contains an `overrideSource` other than GitHub, HTML or GitLab
- **THEN** offline verification fails with the variant, id and offending source identified and no live requests occur

#### Scenario: GitLab defaults are incomplete or mistyped

- **WHEN** a rendered GitLab entry lacks a committed default key or supplies a known setting with the wrong type
- **THEN** offline verification fails without hydrating or repairing the entry

### Requirement: Live checks honor a declared compatibility boundary

The system SHALL retain live GitHub and HTML resolution against the repository's
Obtainium v1.6.14 compatibility baseline and add native public GitLab resolution
against the bounded Obtainium v1.6.15 GitLab adapter behavior. It SHALL document supported settings
and explicit device-independent limitations. It SHALL support the release and
HTML behavior specified below and the native public GitLab requirements and SHALL reject active unsupported resolution
features with the setting and entry identified, rather than ignoring them.

Unsupported features SHALL include archive downloads, non-date/non-none GitHub
sorting, request proxies, embedded credentials, disabled TLS
verification, device-dependent HTML intermediate filtering, and HTML
pseudo-versioning without explicit version extraction. Inactive defaults SHALL
not activate unsupported features. Unknown additional settings SHALL produce a
live compatibility error unless explicitly classified as harmless presentation
or device controls. Final device architecture filtering and preferred APK
selection SHALL be outside the guarantee and SHALL be identified as such.

GitLab support SHALL be limited to explicit installable public gitlab.com project
entries with release-tag versions, APK filtering, optional version extraction
and older-release fallback. GitLab resolution SHALL include named asset links
and project-upload APK links in release descriptions, and inspect at most 100
releases in API order. Active GitLab options outside this boundary SHALL fail
before HTTP; inactive defaults SHALL be classified explicitly. Public GitLab
requests SHALL work without a token under the shared exact-host credential,
request-bound, evidence and optional-probe guarantees. Adding GitLab SHALL NOT
relax the existing GitHub credential requirement or HTML compatibility checks.


#### Scenario: Unsupported feature is enabled

- **WHEN** an entry enables ZIP downloads
- **THEN** live verification reports unsupported resolution behavior
- **AND** it does not pass the entry by checking only a direct APK

#### Scenario: Inactive HTML pseudo-version default

- **WHEN** an HTML entry successfully extracts an explicit version and retains
  its default pseudo-versioning setting
- **THEN** that unused default does not cause a compatibility error

#### Scenario: Supported native GitLab entry dispatches to GitLab resolution

- **WHEN** offline verification passes for an installable GitLab entry using supported settings
- **THEN** live verification uses native GitLab release resolution and retains separate per-variant evidence without requiring a public GitLab token
