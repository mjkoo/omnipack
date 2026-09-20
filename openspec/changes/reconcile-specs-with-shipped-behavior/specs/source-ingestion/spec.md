## MODIFIED Requirements

### Requirement: Upstream catalogs are read from their canonical locations

The system SHALL read each upstream from the location recorded in the source
configuration: the RJNY catalog from the configured path on the configured
branch, the BBoi34 catalog from the single-screen and dual-screen JSON assets
of the latest release of the configured repository, and the codm2000 catalog
from its configured committed Obtainium JSON file. The latest release SHALL be
the one the upstream itself publishes as latest, so ingestion SHALL NOT rank
releases by a version read from an asset name, and SHALL NOT reuse a release it
read on an earlier run. Each configured asset pattern SHALL match exactly one
asset of that release; any other number of matching assets SHALL fail the build
naming BBoi34 and the pattern that matched wrongly, rather than choosing one of
them. Routine ingestion SHALL NOT fetch the source README, inspect APKs or
resolve package IDs.

#### Scenario: BBoi34 assets come from the newest release

- **WHEN** ingestion runs and BBoi34 has published a release since the previous
  run, so that the release the upstream reports as latest is not the one the
  previous run read
- **THEN** the entries are read from the assets of the release the upstream
  reports as latest, without pinning a release or reusing the previous run's

#### Scenario: A configured asset pattern matches the wrong number of assets

- **WHEN** the latest release contains no asset matching a configured pattern,
  or more than one
- **THEN** the build fails naming BBoi34 and that pattern, without selecting
  one of the matching assets or continuing with the other pattern's entries

#### Scenario: Configured location is empty

- **WHEN** ingestion runs and a source's configured location is empty
- **THEN** the build fails with an error naming that source

#### Scenario: README or APK hosting is unavailable

- **WHEN** committed codm2000 JSON is valid and other catalog sources are available
- **THEN** ingestion succeeds without requesting README or APK data

### Requirement: URLs are compared in a normalized form

The same project is spelled differently by different hands across the upstream
catalogs, the source README, the reviewed project policy and the committed
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
matching a generated project to its reviewed rule and to its entry in the
committed source catalog, matching an overlay record's key to the selected
entries it patches, and matching a composition policy selector to the candidates
it governs.

This normalized form is the system's comparison identity, and it SHALL decide
only whether two spellings mean one project. It SHALL NOT decide whether a URL
is acceptable to a source adapter: an adapter that reads a URL as written does
so at an earlier stage, before normalization, so a URL that compares equal to
an acceptable one MAY still be rejected there. The two notions of "the same
host" are therefore distinct stages, and a reader SHALL NOT infer either from
the other.

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

### Requirement: One package id may resolve differently per variant

Upstreams deliberately point a single package id at different projects or
settings per variant, so that a dual-screen fork replaces its single-screen
counterpart. The system SHALL resolve each variant's candidates independently
and SHALL NOT require that a package id map to the same entry across variants.

An upstream catalog contributing two entries that share a package id SHALL have
both retained for composition to resolve, because ingestion cannot know which
of them a family rule, a pin or a denial will select. The committed codm2000
catalog SHALL instead fail ingestion when it repeats an entry id, naming the id
and both project URLs, because it is reviewed before it is committed and a
repeated id there is an error in the catalog rather than a choice for
composition.

#### Scenario: Same id, different project per variant

- **WHEN** an upstream contains two entries sharing a package id, one opted
  out of the single-screen variant and the other opted out of the dual-screen
  variant
- **THEN** the single-screen variant ingests one of them and the dual-screen
  variant ingests the other

#### Scenario: Duplicate ids remain within a variant

- **WHEN** ingesting one upstream catalog leaves two candidate entries sharing
  a package id within the same variant
- **THEN** the duplicate is resolved during composition, not silently dropped
  during ingestion

#### Scenario: The committed catalog repeats an entry id

- **WHEN** the committed codm2000 catalog contains two entries carrying the
  same id
- **THEN** ingestion fails naming that id and both entries' project URLs,
  rather than retaining both or keeping whichever appears first

### Requirement: Public GitLab entries keep native source identity

The system SHALL accept explicit extras with source type `GitLab` whose URL identifies exactly one public gitlab.com project, preserve the full case-sensitive project path including subgroups, hydrate supported GitLab defaults, and render `overrideSource: GitLab`. A URL SHALL identify one public gitlab.com project only when its scheme is `https` and its host is `gitlab.com`, each compared without regard to case, with no `www.` prefix and no port, carrying no credentials, and whose path, read exactly as written, is between two and twenty-one components naming a project and its namespaces, no component of which is the separator `-` that gitlab.com reserves for its own routes, and which carries no query and no fragment. Any other URL SHALL fail the build with the entry and the URL identified, because the pipeline cannot tell which part of it names the project. Existing non-GitHub URL comparison semantics SHALL remain unchanged.

This acceptance boundary is an earlier and separate stage from normalized
comparison: the native adapter reads the project path out of the URL as the
entry spells it, before any normalization is applied, so a URL that compares
equal to an acceptable one MAY still be rejected here. A `www.gitlab.com`
spelling compares equal to the canonical one, because comparison drops a leading
`www.`, and is nonetheless not a native GitLab project URL; an explicit port is
rejected here and, being retained in the normalized form, also makes a different
project under comparison. Acceptance SHALL therefore be decided on the URL's own
scheme, host and path rather than on its comparison identity, which additionally
drops a leading `www.` and folds a GitHub link to owner and repository.

Package ids for these explicit extras SHALL be supplied by the maintainer who adds the entry, from recorded primary APK manifest evidence as any other identity decision is; the pipeline SHALL NOT verify them, because adding GitLab SHALL NOT extend generated GitHub package discovery to arbitrary hosts.

#### Scenario: A GitLab extra reaches both exports

- **WHEN** an explicit GitLab extra uses its canonical gitlab.com project URL and is selected in both variants
- **THEN** both outputs and individual import links retain native GitLab identity and compatible settings

#### Scenario: A GitLab URL carries more than a project path

- **WHEN** an entry declares GitLab with a gitlab.com URL whose host is spelled with a `www.` prefix, or that carries a query, a fragment, credentials, an explicit port, a reserved `-` path component or more path components than a project and its namespaces
- **THEN** the build fails with the entry and the invalid URL identified, rather than reading a project path out of it

## RENAMED Requirements

- FROM: `### Requirement: Committed codm2000 entries keep device-aware source semantics`
- TO: `### Requirement: Committed codm2000 entries are dual-screen builds that keep their generated identity`
