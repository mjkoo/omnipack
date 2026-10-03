## ADDED Requirements

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
another source's build of the same app.

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
`www.` from the host, dropping a trailing slash and a trailing `.git` from the
path, and reducing a GitHub project link to its owner and repository compared
without regard to case. The scheme SHALL NOT participate in the comparison, so
that `http` and `https` spellings of one project compare equal. Case SHALL be
folded only in the host and in a GitHub link's owner and repository; the case
of any other path SHALL be preserved, so that two URLs on another host
differing only in path case remain different projects.

Reducing a GitHub link to its owner and repository SHALL discard the rest of
its path, its query and its fragment, because a GitHub project is identified by
owner and repository alone. An explicit port SHALL be retained on every host,
github.com included, so two links that differ only in an explicit port SHALL be
different projects. On any other host the normalized form SHALL also retain a
query and a fragment, so two links to one host and path that differ in any of
them SHALL be different projects: the system cannot know which parts of another
host's link identify the project. The pipeline SHALL use this form wherever it
compares URLs: deciding whether another source already contributes a link,
collapsing a generated source's listings of one project into one entry, forming
default families, matching a denial or an overlay record to the candidates or
selected entries it governs, and matching a composition policy selector to the
candidates it governs.

This normalized form is the system's comparison identity, and it SHALL decide
only whether two spellings mean one project. It SHALL NOT decide whether a URL
is acceptable to a source adapter: an adapter that reads a URL as written does
so at an earlier stage, before normalization, so a URL that compares equal to
an acceptable one MAY still be rejected there. The two notions of "the same
host" are therefore distinct stages, and neither follows from the other.

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
  and repository, and different projects on any other host, whose query and
  fragment are retained

#### Scenario: Links differ only in an explicit port

- **WHEN** two URLs address the same host and path and one of them carries an
  explicit port
- **THEN** they are different projects on every host, github.com included,
  because the normalized form retains an explicit port wherever it appears

### Requirement: Public GitLab entries keep native source identity

The system SHALL accept explicit extras and generated catalog entries with source type `GitLab` whose URL identifies exactly one public gitlab.com project, preserve the full case-sensitive project path including subgroups, hydrate supported GitLab defaults, and render `overrideSource: GitLab`. A URL SHALL identify one public gitlab.com project only when its scheme is `https` and its host is `gitlab.com`, each compared without regard to case, with no `www.` prefix and no port, carrying no credentials, and whose path holds between two and twenty-one nonempty components naming a project and its namespaces, each read with its case and encoding exactly as written while empty components and a trailing slash are ignored, no component of which is the separator `-` that gitlab.com reserves for its own routes, and which carries no query and no fragment. Any other URL SHALL fail the build with the entry and the URL identified, because the pipeline cannot tell which part of it names the project.

This acceptance boundary is an earlier and separate stage from normalized
comparison: the native adapter reads the project path out of the URL as the
entry spells it, before any normalization is applied, so a URL that compares
equal to an acceptable one MAY still be rejected here. A `www.gitlab.com`
spelling compares equal to the canonical one, because comparison drops a leading
`www.`, and is nonetheless not a native GitLab project URL; an explicit port is
rejected here and, being retained in the normalized form, also makes a different
project under comparison. Acceptance SHALL therefore be decided on the URL as
written rather than on its comparison identity.

#### Scenario: A GitLab extra reaches both exports

- **WHEN** an explicit GitLab extra uses its canonical gitlab.com project URL and is selected in both variants
- **THEN** both outputs and individual import links retain native GitLab identity and compatible settings

#### Scenario: A GitLab URL carries more than a project path

- **WHEN** an entry declares GitLab with a gitlab.com URL whose host is spelled with a `www.` prefix, or that carries a query, a fragment, credentials, an explicit port, a reserved `-` path component or more path components than a project and its namespaces
- **THEN** the build fails with the entry and the invalid URL identified, rather than reading a project path out of it

### Requirement: Committed Quiver entries are baseline builds with generated provenance

Routine ingestion SHALL read Quiver entries from its configured committed
Obtainium catalog without requesting Quiver lists, repository hosts or APKs.
A missing, unreadable or malformed catalog or repeated entry ID SHALL fail the
build while preserving previous outputs. Valid entries SHALL carry source
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

- **WHEN** the configured catalog is missing, malformed or repeats an entry ID
- **THEN** the build fails naming Quiver and leaves published outputs unchanged

#### Scenario: Quiver record carries policy fields

- **WHEN** a committed Quiver record includes a top-level family or variant field
- **THEN** ingestion rejects it under the source-record policy-field prohibition

## REMOVED Requirements

## REMOVED Requirements

### Requirement: HTTP credentials are optional and scoped to exact hosts

**Reason**: Generation no longer queries repository APIs or downloads APKs, so no request needs a credential.

**Migration**: Replaced by "Source fetches carry no credentials"; `config/http.json` is deleted.

### Requirement: Every committed codm2000 entry is a dual-screen candidate with its generated identity

**Reason**: Generated codm entries no longer carry manifest package ids, track-only resource ids or reviewed discovery settings.

**Migration**: Replaced by "Committed codm entries are dual-screen candidates".
