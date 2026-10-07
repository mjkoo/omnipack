## ADDED Requirements

### Requirement: GitLab entries keep their declared source type

An entry from any source that declares `overrideSource: GitLab`, or whose URL
is a gitlab.com project and that declares nothing, SHALL keep the GitLab
source type, its URL as written and its explicit settings, and SHALL be
hydrated with the defaults defined for GitLab, never those defined for HTML.
The system SHALL NOT restrict a GitLab entry's host, path, port or query.

#### Scenario: A GitLab extra reaches both exports

- **WHEN** an explicit GitLab extra is selected in both variants
- **THEN** both outputs and individual import links retain native GitLab
  identity and compatible settings

#### Scenario: A self-hosted GitLab project is declared

- **WHEN** an extras entry declares GitLab with the URL of a project on a
  self-hosted GitLab instance
- **THEN** the build keeps the entry with the GitLab source type and its URL
  unchanged

### Requirement: An entry's source type is declared, derived or left to Obtainium

Obtainium reads a per-app source type, and detects one from the URL when an
app declares none. An entry SHALL keep the source type its record declares,
whatever its source. When a record declares none, the system SHALL derive one
only for URLs whose type is unambiguous: a github.com repository takes GitHub
and a gitlab.com project takes GitLab. Any other entry without a declaration
SHALL carry no source type, leaving detection to Obtainium. The system SHALL
NOT fail an entry for the source type it declares or lacks; a malformed
declaration, one that is not a string, SHALL fail the build with the entry and
value identified.

An entry declaring GitLab SHALL keep the URL as written, so a project on any
GitLab instance, gitlab.com or self-hosted, reaches the pack as Obtainium's
GitLab source reads it. Explicit per-app settings
SHALL override hydrated defaults. A native GitLab entry SHALL be hydrated with
the defaults defined for GitLab, never those defined for HTML.

#### Scenario: Upstream record declares a source type

- **WHEN** an upstream entry's record declares the HTML source type
- **THEN** the ingested entry carries the HTML source type

#### Scenario: An entry with no upstream record derives its source type

- **WHEN** an extras entry or a committed codm2000 entry that omits
  `overrideSource` addresses a github.com repository
- **THEN** it carries the GitHub source type, while an entry addressing an
  itch.io page carries no source type

#### Scenario: Explicit GitLab declaration takes precedence over URL inference

- **WHEN** an extras entry declares `overrideSource: GitLab` with a public gitlab.com project URL
- **THEN** ingestion retains GitLab, and rendering uses GitLab defaults and preserves explicit settings in both variants instead of selecting HTML

#### Scenario: A committed codm2000 entry declares its source type

- **WHEN** a committed codm2000 entry addressing a github.com repository declares
  the HTML source type
- **THEN** the ingested entry carries the HTML source type rather than the type
  its URL would derive


#### Scenario: A record declares a source type the pack has no defaults for

- **WHEN** an upstream record declares `overrideSource: Codeberg`
- **THEN** the build keeps the entry with that source type and does not fail

#### Scenario: An upstream record declares no source type

- **WHEN** an RJNY or BBoi34 record carries no `overrideSource` and its URL is
  not a github.com repository or a gitlab.com project
- **THEN** the entry carries no source type and the build does not fail

### Requirement: Committed codm entries are dual-screen candidates

The system SHALL ingest the committed codm2000 catalog as Obtainium JSON,
without fetching the codm README; generation from the README is the separate
source-generation operation. Each entry SHALL keep codm2000 provenance, the
generated origin, its committed id, URL, name and settings, so composition
rules and overlays that select it match it. During routine ingestion, codm2000
entries SHALL be dual-screen builds, eligible for dual only and preferred
there. Every committed entry SHALL become a candidate whether or not another
source lists the same project, and ingestion SHALL NOT read or apply the
composition policy: family formation, dual preference, precedence, pins and
project denials in pack-composition decide between a codm2000 build and
another source's build of the same app. A missing, unreadable or malformed
catalog, a repeated entry ID or two entries at one normalized project URL
SHALL fail the build while preserving previous outputs.

#### Scenario: Broken committed codm catalog

- **WHEN** the configured catalog is missing, malformed, repeats an entry ID or
  holds two entries at one normalized project URL
- **THEN** the build fails naming codm and leaves published outputs unchanged

#### Scenario: Another source lists the same project

- **WHEN** a higher-precedence source supplies a candidate with a normalized
  URL equal to a committed codm2000 entry's
- **THEN** the committed entry still enters composition as a dual-screen
  codm2000 candidate, and pack-composition selects between the two builds

#### Scenario: A selected project is removed

- **WHEN** an accepted source update removes a candidate required by an active
  rule or pin
- **THEN** pack composition fails explicitly rather than silently ignoring the
  stale selector

### Requirement: Source fetches carry no credentials

Every upstream request the build and source generation make SHALL carry no
credentials, and the system SHALL keep no HTTP credential configuration.
Publication operations are outside this rule: release, pull-request and
branch-push operations follow the publication credential rules of the
workflows that make them.

#### Scenario: A token is present in the environment

- **WHEN** `GITHUB_TOKEN` is set while a build or a source generation runs
- **THEN** no upstream request carries an Authorization header

## MODIFIED Requirements

### Requirement: URLs are compared in a normalized form

The same project is spelled differently by different hands across the upstream
catalogs, the source README, the Quiver lists, the overlay and the committed
source catalog, so two spellings of one project must not be treated as two
projects. The system SHALL compare URLs in a normalized form
obtained by discarding the scheme, lowercasing the host, dropping a leading
`www.` from the host, dropping a port equal to the scheme's default (443 for
`https`, 80 for `http`, and 443 for a URL written without a scheme), dropping a trailing slash and a trailing `.git` from
the path, reducing a GitHub project link to its owner and repository compared
without regard to case, and reducing a gitlab.com project link to the
project path before any `/-/` segment, the route marker GitLab reserves inside
a project. A gitlab.com link whose first path segment is one of GitLab's site
routes (`-`, `groups`, `users`, `explore`, `dashboard`, `search`, `help` or
`admin`) names no project and SHALL NOT be reduced.
A trailing `.git` SHALL be matched without regard to case only on github.com,
where path case is folded, and exactly elsewhere. The scheme SHALL NOT participate in the comparison, so
that `http` and `https` spellings of one project compare equal. Case SHALL be
folded only in the host and in a GitHub link's owner and repository; the case
of any other path SHALL be preserved, so that two URLs on another host
differing only in path case remain different projects.

Reducing a GitHub link to its owner and repository SHALL discard the rest of
its path, its query and its fragment, because a GitHub project is identified by
owner and repository alone, and reducing a gitlab.com project link SHALL
likewise discard its query and fragment. Any port other than the scheme's default SHALL
be retained on every host, github.com included, so two links that differ only
in such a port SHALL be different projects. On any other host, and for a
gitlab.com site route, the normalized form SHALL also retain a query and a
fragment, so two links to one host and path that differ in any of them SHALL
be different projects: the system cannot know which parts of another
host's link identify the project. The pipeline SHALL use this form wherever it
compares URLs: deciding whether another source already contributes a link,
collapsing a generated source's listings of one project into one entry, forming
default families, matching a denial or an overlay record to the candidates or
selected entries it governs, and matching a composition policy selector to the
candidates it governs.

This normalized form is the system's comparison identity, and it SHALL decide
only whether two spellings mean one project. It SHALL NOT decide whether a URL
is acceptable: no stage rejects an entry for its URL's host or path.

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

#### Scenario: Links differ only in a query or fragment

- **WHEN** two URLs address the same host and path and differ only in a query
  or a fragment
- **THEN** they are the same project on github.com, whose links reduce to owner
  and repository, and on gitlab.com, whose links reduce to the project path,
  and different projects on any other host, whose query and fragment are
  retained

#### Scenario: Links differ only in an explicit port

- **WHEN** two URLs address the same host and path and one of them carries an
  explicit port other than its scheme's default
- **THEN** they are different projects on every host, github.com included,
  because the normalized form retains such a port wherever it appears

#### Scenario: A link names its scheme's default port

- **WHEN** one source gives `https://github.com:443/owner/repo` and another
  gives `https://github.com/owner/repo`
- **THEN** both normalize to the same URL, because a scheme's default port is
  dropped

#### Scenario: A gitlab.com link points inside a project

- **WHEN** one source gives `https://gitlab.com/group/app/-/releases#v1` and
  another gives `https://gitlab.com/group/app`
- **THEN** both normalize to the same URL, because a gitlab.com link is
  reduced to the project path before its `/-/` segment

#### Scenario: A gitlab.com link is a site page

- **WHEN** a source gives `https://gitlab.com/groups/team/-/epics`
- **THEN** it is not reduced to `gitlab.com/groups/team`, because `groups` is
  a GitLab site route rather than a project's namespace, and it derives no
  source type

### Requirement: Committed Quiver entries are baseline builds with generated provenance

Routine ingestion SHALL read Quiver entries from its configured committed
Obtainium catalog without requesting Quiver lists, repository hosts or APKs.
A missing, unreadable or malformed catalog, a repeated entry ID or two entries
at one normalized project URL SHALL fail the build while preserving previous
outputs. Valid entries SHALL carry source
`quiver`, generated origin `quiver-generated`, their committed ids and their
GitHub or GitLab source type. They SHALL be
baseline candidates eligible for both packs, subject to ordinary normalization,
composition policy, denials and overlays. Every valid entry SHALL reach
composition, including entries sharing another source's project URL. Routine
ingestion SHALL NOT modify the catalog or generate missing entries. Source
records SHALL obey the existing prohibition on composition fields and preserve
generated provenance in reports without claiming a fresh APK check.

#### Scenario: Quiver hosting is unavailable during build

- **WHEN** the committed Quiver catalog and the other build inputs are valid
- **THEN** building succeeds without requesting Quiver hosting or APK data

#### Scenario: Broken committed Quiver catalog

- **WHEN** the configured catalog is missing, malformed, repeats an entry ID or
  holds two entries at one normalized project URL
- **THEN** the build fails naming Quiver and leaves published outputs unchanged

#### Scenario: Quiver record carries policy fields

- **WHEN** a committed Quiver record includes a top-level family or variant field
- **THEN** ingestion rejects it under the source-record policy-field prohibition

## REMOVED Requirements

### Requirement: HTTP credentials are optional and scoped to exact hosts

**Reason**: Generation no longer queries repository APIs or downloads APKs, so no request needs a credential.

**Migration**: Replaced by "Source fetches carry no credentials"; `config/http.json` is deleted.

### Requirement: Every committed codm2000 entry is a dual-screen candidate with its generated identity

**Reason**: Generated codm entries no longer carry manifest package ids, track-only resource ids or reviewed discovery settings.

**Migration**: Replaced by "Committed codm entries are dual-screen candidates".

### Requirement: Every entry carries a supported source type

**Reason**: The pack no longer limits entries to the source types it holds default settings for; Obtainium supports and detects many more.

**Migration**: Replaced by "An entry's source type is declared, derived or left to Obtainium".

### Requirement: Public GitLab entries keep native source identity

**Reason**: Obtainium's GitLab source also reads self-hosted instances and URLs beyond a bare gitlab.com project path; the pack no longer rejects them.

**Migration**: Replaced by "GitLab entries keep their declared source type".
