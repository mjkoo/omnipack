# source-ingestion Specification

## Purpose

Turns each upstream catalog and the hand-written extras into a normalized set
of candidate app entries per pack variant, so that the rest of the pipeline
never has to know how any individual upstream encodes its data.

## Requirements

### Requirement: Upstream catalogs are read from their canonical locations

The system SHALL read each upstream from the location recorded in the source
configuration: the RJNY catalog from the configured path on the configured
branch, the BBoi34 catalog from the single-screen and dual-screen JSON assets
of the latest release of the configured repository, and the codm2000 catalog
from the configured README URL.

#### Scenario: BBoi34 assets come from the newest release

- **WHEN** ingestion runs and the newest BBoi34 release publishes assets named
  for a version later than any seen before
- **THEN** the entries are read from that release's assets rather than from a
  pinned or previously cached version

#### Scenario: Configured location is empty

- **WHEN** ingestion runs and a source's configured location is empty
- **THEN** the build fails with an error naming that source

### Requirement: HTTP credentials are optional and scoped to exact hosts

All pipeline HTTP requests SHALL use the shared standard-library HTTP helper,
including catalog fetches and the vendored package-id resolver's release
metadata requests, ranged APK reads and full asset downloads. GitHub latest
release metadata SHALL be requested from
`https://api.github.com/repos/OWNER/REPO/releases/latest`.

The system SHALL read host-to-environment-variable registrations from the
`credentials` object in dedicated `config/http.json`, whose committed default
content SHALL be `{"credentials": {"api.github.com": "GITHUB_TOKEN"}}`.
Registrations SHALL name exact hosts, compared case-insensitively against the
request hostname, without wildcard matching, subdomain inference or the
project-URL normalization rules. The configuration SHALL store variable names,
not token values.

The helper SHALL attach `Authorization: Bearer <token>` only when the request
host has a registered variable with a nonempty value. An unset or empty
variable SHALL leave the request unauthenticated. Unregistered hosts SHALL
receive no Authorization header even when tokens for other hosts are set.
Across a cross-host redirect, the helper SHALL strip the outgoing host's
credential; any destination credential SHALL be selected independently from
that destination's exact registration.

#### Scenario: Cold-cache GitHub resolution uses the API credential

- **WHEN** a generated GitHub project has no cached package id, the default
  HTTP configuration is loaded and `GITHUB_TOKEN` is nonempty
- **THEN** its latest-release metadata request to `api.github.com` carries the
  bearer token through the shared helper, and its ranged APK reads and full
  asset download fallback use that same helper
- **AND** requests to unregistered `github.com`, `raw.githubusercontent.com`,
  `codeberg.org` and release asset hosts carry no Authorization header

#### Scenario: Optional token is absent

- **WHEN** a registered variable is unset or empty
- **THEN** requests to its host proceed without Authorization, including
  cold-cache package-id resolution against public GitHub releases

#### Scenario: Host registration does not cover related names

- **WHEN** only `github.com` is registered and its token variable is nonempty
- **THEN** requests to `api.github.com` and `www.github.com` carry no
  Authorization header because neither exact host is registered

#### Scenario: Authenticated request redirects to an unregistered host

- **WHEN** a request bearing the token for `api.github.com` redirects to an
  unregistered host
- **THEN** the redirected request carries no Authorization header

### Requirement: URLs are compared in a normalized form

The same project is spelled differently by different hands across the upstream
catalogs and the resolved-id cache, so two spellings of one project must not be
treated as two projects. The system SHALL compare URLs in a normalized form
obtained by discarding the scheme, lowercasing the host, dropping a leading
`www.` from the host, dropping a trailing slash and a trailing `.git` from the
path, and reducing a GitHub project link to its owner and repository compared
without regard to case. The scheme SHALL NOT participate in the comparison, so
that `http` and `https` spellings of one project compare equal. Case SHALL be
folded only in the host and in a GitHub link's owner and repository; the case
of any other path SHALL be preserved, so that two URLs on another host
differing only in path case remain different projects. The pipeline SHALL use
this form wherever it compares URLs: deciding whether another source already
contributes a link, and keying the resolved package id cache.

#### Scenario: Two spellings of one project

- **WHEN** one source gives a project's URL as `https://github.com/Owner/Repo`
  and another gives it as `https://www.github.com/owner/repo.git/`
- **THEN** both normalize to the same URL and the two are treated as the same
  project, because a GitHub link's owner and repository are compared without
  regard to case

#### Scenario: Two spellings differ only in scheme

- **WHEN** one source gives a project's URL as `http://github.com/owner/repo`
  and another gives it as `https://github.com/owner/repo`
- **THEN** both normalize to the same URL and the two are treated as the same
  project

#### Scenario: A non-GitHub path differs only in case

- **WHEN** two URLs address the same non-GitHub host and differ only in the
  case of their path
- **THEN** they are treated as different projects, because case is folded only
  in the host and in a GitHub link's owner and repository

### Requirement: A failed fetch aborts the build

A pack that is silently missing a whole upstream is worse than no rebuild at
all, because it would drop every app that upstream contributes. The system
SHALL abort the build when any source cannot be fetched or parsed, and SHALL
NOT write either import file in that case. That restriction covers the two
import files only: the resolved package id cache keeps whatever it resolved
before the abort, and the build report is still written and records the
failure.

#### Scenario: One upstream is unreachable

- **WHEN** one upstream cannot be fetched
- **THEN** the build fails, and the previously written import files are left
  unmodified

#### Scenario: An upstream returns unparseable content

- **WHEN** an upstream is reachable but its content cannot be parsed as the
  expected catalog shape
- **THEN** the build fails with an error naming that source

### Requirement: RJNY export flags select entries per variant

The RJNY catalog carries per-entry export metadata that determines whether an
entry is exported at all and which variants it belongs to. The system SHALL
drop any entry marked as excluded from export, SHALL omit an entry from the
single-screen variant when it is marked as not included in the standard pack,
and SHALL omit an entry from the dual-screen variant when it is marked as not
included in the dual-screen pack. An entry carrying no such flag SHALL be a
candidate for both variants. Entries eligible for single SHALL be ordinary
candidates; entries eligible only for dual SHALL be dual-preferred. Explicit
composition policy SHALL be able to override eligibility and preference after
source normalization, but SHALL NOT revive an entry excluded from export.

#### Scenario: Entry excluded from export

- **WHEN** an RJNY entry is marked as excluded from export
- **THEN** it contributes to neither variant, regardless of its other flags

#### Scenario: Entry opted out of one variant

- **WHEN** an RJNY entry is marked as not included in the standard pack
- **THEN** it is a candidate for the dual-screen variant only

#### Scenario: Entry carries no export metadata

- **WHEN** an RJNY entry carries no export metadata
- **THEN** it is a candidate for both variants

### Requirement: RJNY presentation metadata does not reach the pack

The RJNY catalog carries name and URL overrides that its own rendered exports
do not apply; they exist to build its documentation table. Applying them would
change the app name and source URL that Obtainium sees. The system SHALL
ignore those overrides and SHALL carry through the entry's own name and URL.

#### Scenario: Entry carries a name override

- **WHEN** an RJNY entry carries a name override that differs from its name
- **THEN** the ingested entry keeps the entry's own name

### Requirement: One package id may resolve differently per variant

Upstreams deliberately point a single package id at different projects or
settings per variant, so that a dual-screen fork replaces its single-screen
counterpart. The system SHALL resolve each variant's candidates independently
and SHALL NOT require that a package id map to the same entry across variants.

#### Scenario: Same id, different project per variant

- **WHEN** an upstream contains two entries sharing a package id, one opted
  out of the single-screen variant and the other opted out of the dual-screen
  variant
- **THEN** the single-screen variant ingests one of them and the dual-screen
  variant ingests the other

#### Scenario: Duplicate ids remain within a variant

- **WHEN** ingesting one source leaves two candidate entries sharing a package
  id within the same variant
- **THEN** the duplicate is resolved during composition, not silently dropped
  during ingestion

### Requirement: BBoi34 entries map to variants by source file

The system SHALL retain each standard-asset record as an ordinary candidate
eligible for both targets, and each dual-asset record as a dual-preferred
candidate eligible only for dual. It SHALL preserve asset origin and retain both
records when a package id appears in both assets. Selection SHALL occur during
composition, where device preference precedes source ranking. Explicit policy
SHALL be able to override normalized eligibility and preference.

#### Scenario: Id present in both BBoi34 assets

- **WHEN** both assets contain different builds of an id and no override changes their suitability
- **THEN** ingestion retains both and composition selects the standard build for single and the dual build for dual, absent a higher-ranked eligible choice

#### Scenario: Standard alternative remains available

- **WHEN** explicit policy makes the dual candidate ineligible for dual
- **THEN** the retained standard candidate remains available for dual selection

### Requirement: codm2000 entries are generated from GitHub project links

The codm2000 catalog is a README of links rather than a machine-readable
catalog. The system SHALL extract its project links, SHALL keep only those
that address a GitHub repository, and SHALL skip the rest. Generated entries
SHALL be candidates for the dual-screen variant only, so the test for a project
another source already covers is scoped to that variant after explicit
eligibility rules have been applied to higher-source candidates: a link SHALL NOT
produce a generated entry when a higher-precedence source already contributes
that project as a candidate for the dual-screen variant, compared in the
pipeline's normalized URL form before exclusions and selection, and SHALL produce one otherwise. A project that
a higher-precedence source contributes to the single-screen variant alone
therefore still generates its dual-screen candidate, since nothing else would
supply that variant.

Generated builds SHALL be dual-preferred within their family unless explicit
policy overrides that preference. Merely listing a covered project in codm SHALL
NOT promote a higher-source ordinary build to dual-preferred. Generated rules
SHALL be applied after package resolution; all active candidate selectors SHALL then be
validated against the complete candidate set. Historical mappings SHALL be exempt from candidate-presence checks.
A missing rule or pinned candidate SHALL fail explicitly rather than be treated as an ordinary unresolved skip.

A README link supplies no display name and no grouping of its own, so a
generated entry SHALL carry as its name the repository name of its project URL,
and SHALL carry an empty category list. An entry with no category is already
governed: it sorts as though its primary category were the empty string and it
contributes nothing to the rendered settings block's category union.

#### Scenario: Generated entry takes its name from the repository

- **WHEN** a README row links to a GitHub repository that no other source
  contributes and whose package id resolves
- **THEN** the generated entry's name is that repository's name and its
  category list is empty

#### Scenario: Link is not a GitHub repository

- **WHEN** a README row links to a host with no APK release feed
- **THEN** no entry is generated for that row and the row is reported as
  skipped

#### Scenario: Link already covered as a dual-screen candidate

- **WHEN** a README row links to a repository that a higher-precedence source
  already contributes as a candidate for the dual-screen variant, spelled
  differently but equal once normalized
- **THEN** no entry is generated for that row

#### Scenario: Link covered in the single-screen variant only

- **WHEN** a README row links to a repository that a higher-precedence source
  contributes as a candidate for the single-screen variant only
- **THEN** a generated entry is produced for that row as a candidate for the
  dual-screen variant

#### Scenario: Policy removes higher-source dual eligibility

- **WHEN** a higher-source project would normally cover dual but policy restricts it to single
- **THEN** its codm link can generate a dual candidate

#### Scenario: Covered ordinary build is also listed by codm

- **WHEN** a higher-source ordinary candidate already covers that project's dual target
- **THEN** codm generates no duplicate and does not change that candidate's preference

### Requirement: A generated entry carries a real package id

Obtainium renames an app to its real package id on install, so an entry
carrying a placeholder id is re-added as a duplicate on the next import. The
system SHALL determine a generated entry's package id by reading the manifest
of every eligible APK asset of the project's latest release. An eligible APK
asset is every asset of that release whose filename ends in `.apk`, compared
without regard to case. When the latest release publishes no eligible APK
asset, when eligible assets declare different package ids, or when any
eligible asset cannot be read, including a size bound, fetch failure or
unreadable manifest, the resolution attempt SHALL fail. The system SHALL NOT
resolve an id from only the assets it could read, so that an unread asset cannot
mask a package id disagreement. Each of these failures SHALL use the cached id
and report the failure when a cached id exists; only a project with no cached
id SHALL be omitted and reported as unresolved. When every eligible asset
can be read and declares the same package id, the generated entry SHALL carry
that id. The system SHALL NOT emit a generated entry with an invented or
placeholder id. The cache requirement governs when the system reuses an id
without reading APK assets.

#### Scenario: Package id resolves

- **WHEN** a project's latest release publishes an APK whose manifest declares
  a package id
- **THEN** the generated entry carries that package id

#### Scenario: Several APKs declare the same package id

- **WHEN** a project's latest release publishes several eligible APK assets
  and each of their manifests declares the same package id
- **THEN** the generated entry carries that package id

#### Scenario: A release publishes no eligible APK asset without a cached id

- **WHEN** the latest release publishes no asset whose filename ends in `.apk`, compared
  without regard to case
  and the project has no cached id
- **THEN** no entry is generated for that project and it is reported as
  unresolved

#### Scenario: A release publishes no eligible APK asset with a cached id

- **WHEN** the latest release publishes no asset whose filename ends in `.apk`, compared
  without regard to case
  and the project has a cached id from a different release
- **THEN** the generated entry uses the cached id, the failure is reported, and
  both the cached id and its recorded release identifier remain unchanged

#### Scenario: APKs of one release declare different package ids without a cached id

- **WHEN** the latest release publishes eligible APK assets whose manifests declare
  different package ids
  and the project has no cached id
- **THEN** no entry is generated for that project and it is reported as
  unresolved

#### Scenario: APKs of one release declare different package ids with a cached id

- **WHEN** the latest release publishes eligible APK assets whose manifests declare
  different package ids
  and the project has a cached id from a different release
- **THEN** the generated entry uses the cached id, the failure is reported, and
  both the cached id and its recorded release identifier remain unchanged

#### Scenario: An eligible APK asset cannot be read without a cached id

- **WHEN** any eligible APK asset in the latest release cannot be read, including a
  size bound, fetch failure or unreadable manifest
  and the project has no cached id
- **THEN** no entry is generated for that project and it is reported as
  unresolved

#### Scenario: An eligible APK asset cannot be read with a cached id

- **WHEN** any eligible APK asset in the latest release cannot be read, including a
  size bound, fetch failure or unreadable manifest
  and the project has a cached id from a different release
- **THEN** the generated entry uses the cached id, the failure is reported, and
  both the cached id and its recorded release identifier remain unchanged

#### Scenario: Package id cannot be determined and no id is cached

- **WHEN** a project's package id cannot be determined and it has no cached id
- **THEN** no entry is generated for it, and it is reported as unresolved

### Requirement: Resolved package ids are cached across builds

Resolving a package id costs a network round trip against every eligible APK
asset of a release, and a transient failure must not drop an app from the pack.
The system SHALL persist each resolved package id keyed by the project's
normalized URL, and SHALL record alongside each cached id the host-assigned
identifier of the release that id was resolved from. A release's host-assigned
identifier is the stable identifier the release host assigns to that release,
not its tag name, and SHALL be compared verbatim, so that a project publishing
every build under one rolling tag is still recognized as having released again.

A build SHALL compare a project's latest release identifier with the identifier
recorded against its cached id: when the two are equal the system SHALL reuse
the cached id and SHALL NOT read any of the release's APK assets, and when they
differ the system SHALL resolve the
package id again and, only on successful resolution, replace both the cached
id and the recorded identifier with the result. Re-resolving on a new release
is what keeps a package id that changed upstream from staying frozen at its first resolution and what makes
that change visible in the cache. When an attempt to resolve a package id again
fails for a project that has a cached id, the system SHALL use the cached id
and SHALL report the failure. This includes a latest release with no eligible
APK, conflicting APK package ids, or any unreadable eligible APK. Any failed
resolution attempt, including a failure to read the release identifier, SHALL
leave both the cached id and its recorded release identifier unchanged, so a
later build retries the release that has not successfully resolved.

Reading a project's latest release identifier is itself a request against the
release host, so it can fail on its own before any comparison is possible. When
a project's latest release identifier cannot be read and the project has a
cached package id, the system SHALL use the cached id and SHALL report the
failure. When a project's latest release identifier cannot be read and the
project has no cached package id, the system SHALL NOT generate an entry for
that project and SHALL report the project as unresolved.

#### Scenario: Cached id is reused for an unchanged release

- **WHEN** a project URL has a cached package id under its normalized form and
  the project's latest release identifier equals the one recorded with that id
- **THEN** the build uses the cached id and reads none of the release's APK
  assets

#### Scenario: A new release re-resolves the package id

- **WHEN** a project URL has a cached package id and the project's latest
  release identifier differs from the one recorded with that id, and all
  eligible APKs are readable and declare the same package id
- **THEN** the build resolves the package id from that release's APK assets and
  records the resolved id together with the new release identifier

#### Scenario: Re-resolution fails with a cached id available

- **WHEN** a project's release identifier has changed and resolving its package
  id again fails
- **THEN** the cached id is used, the failure is reported, and both cached
  fields remain unchanged

#### Scenario: A failed release is retried on the next build

- **WHEN** resolution of a new release failed and a later build observes that
  same latest release identifier
- **THEN** the system retries resolution because the cache still records the
  identifier of the last successfully resolved release

#### Scenario: The release identifier cannot be read and an id is cached

- **WHEN** a project's latest release identifier cannot be read and the project
  has a cached package id
- **THEN** the build uses the cached id and reports the failure

#### Scenario: The release identifier cannot be read and no id is cached

- **WHEN** a project's latest release identifier cannot be read and the project
  has no cached package id
- **THEN** no entry is generated for that project and it is reported as
  unresolved

### Requirement: Hand-written extras are ingested as complete entries

The system SHALL ingest each entry in the extras configuration as a candidate
entry, and SHALL fail the build with an error naming the entry when an extras
entry is missing a package id, a URL or a name. An extras entry has no upstream
record to take a display name from, and a name is not optional downstream:
rendering orders entries by name and the import format displays it. An extras
entry SHALL be a candidate for both variants, unless it
carries a variants field naming the variants it applies to, in which case it
SHALL be a candidate for exactly the named variants. The system SHALL fail the
build when that field names anything other than the known variants, or names
an empty list. An optional boolean `dualPreferred` SHALL default to false and
SHALL be valid only with dual eligibility. Explicit composition policy SHALL be
able to override normalized eligibility and preference. Composition-only fields
SHALL NOT reach Obtainium app records.

#### Scenario: Extras entry lacks a package id

- **WHEN** an extras entry has no package id
- **THEN** the build fails with an error naming that entry

#### Scenario: Extras entry lacks a name

- **WHEN** an extras entry carries a package id and a URL but no name
- **THEN** the build fails with an error naming that entry

#### Scenario: Extras entry names no variants

- **WHEN** an extras entry carries a package id and a URL and no variants
  field
- **THEN** it is a candidate for both the single-screen and the dual-screen
  variant

#### Scenario: Extras entry names an unknown variant

- **WHEN** an extras entry's variants field names a variant the pack does not
  have
- **THEN** the build fails with an error naming that entry and the rejected
  value

#### Scenario: Ordinary extra competes with a dual fork

- **WHEN** an extra omits dualPreferred and a dual-preferred lower-source candidate shares its family
- **THEN** the extra is ordinary and does not win dual selection solely through source precedence

### Requirement: Every entry carries a supported source type

Obtainium reads a per-app source type that decides which settings keys an app
has, so every entry must carry one before it can be rendered. An entry ingested
from an upstream catalog SHALL take the source type that upstream's record
declares for it. An extras entry with an explicit `overrideSource` SHALL use
that declared source type before URL-based inference. Only when an extras entry
omits `overrideSource`, or for a generated entry, SHALL the system derive the
source type from the URL: a github.com repository takes GitHub and any other
URL takes HTML. The pack SHALL support GitHub, HTML and GitLab, and SHALL fail
the build with an error naming the entry and offending value for any other
source type, including a malformed explicit declaration rather than silently
falling back to URL inference.

Native GitLab entries SHALL follow the URL, identity and discovery boundary in
"Public GitLab entries retain native source identity". Explicit per-app settings
SHALL override hydrated defaults. Native GitLab selection SHALL NOT route through
HTML defaults.

#### Scenario: Upstream record declares a source type

- **WHEN** an upstream entry's record declares the HTML source type
- **THEN** the ingested entry carries the HTML source type

#### Scenario: An entry with no upstream record derives its source type

- **WHEN** a generated entry or an extras entry without `overrideSource` addresses a github.com
  repository
- **THEN** it carries the GitHub source type, while an entry addressing any
  other URL carries the HTML source type

#### Scenario: Unsupported source type

- **WHEN** an upstream or extras entry declares a source type other than GitHub, HTML or GitLab
- **THEN** the build fails with an error naming that entry and that source type

#### Scenario: Explicit GitLab declaration takes precedence over URL inference

- **WHEN** an Aurora extra declares `overrideSource: GitLab` and `https://gitlab.com/AuroraOSS/AuroraStore`
- **THEN** ingestion retains GitLab, and rendering uses GitLab defaults and preserves explicit settings in both variants instead of selecting HTML

#### Scenario: Native GitLab URL is outside the supported boundary

- **WHEN** an entry declares GitLab with a non-HTTPS URL, a host other than gitlab.com or no namespace/project path
- **THEN** the build fails with the entry and invalid URL identified

### Requirement: Per-app settings are normalized to a common form

Upstreams encode an entry's per-app settings inconsistently: some as a nested
object and some as a JSON-encoded string. The system SHALL normalize every
ingested entry's per-app settings to a single form so that later composition
compares and patches them uniformly.

#### Scenario: Upstream encodes settings as a string

- **WHEN** an upstream entry's per-app settings are a JSON-encoded string
- **THEN** the ingested entry exposes the same settings as structured data

#### Scenario: Settings string is malformed

- **WHEN** an upstream entry's per-app settings string cannot be decoded
- **THEN** the build fails with an error naming that entry

### Requirement: Public GitLab entries retain native source identity

The system SHALL accept explicit extras with source type `GitLab` and public HTTPS gitlab.com project URLs, preserve the full case-sensitive project path including subgroups (at most 21 path components in total), hydrate supported GitLab defaults, and render `overrideSource: GitLab`. Existing non-GitHub URL comparison semantics SHALL remain unchanged. Package ids for these explicit extras SHALL be supplied and backed by manifest evidence; adding GitLab SHALL NOT extend generated GitHub package discovery to arbitrary hosts.

#### Scenario: Aurora extra reaches both exports

- **WHEN** an explicit Aurora Store extra uses its canonical GitLab URL and both variants
- **THEN** both outputs and individual import links retain native GitLab identity and compatible settings
