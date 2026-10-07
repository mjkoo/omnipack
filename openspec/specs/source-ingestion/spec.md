# source-ingestion Specification

## Purpose

Turns upstream catalogs and hand-written extras into normalized candidate app
entries per pack variant. It owns each source's admission, kind, eligibility
and source identity, the URL comparison identity shared by the pipeline, and
the host-scoped credential rules used by source-generation requests.

## Requirements

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
catalogs, the source README, the Quiver lists, the overlay and the committed
source catalog, so two spellings of one project must not be treated as two
projects. The system SHALL compare URLs in a normalized form
obtained by discarding the scheme, lowercasing the host, dropping a leading
`www.` from the host, dropping a port equal to the scheme's default (443 for
`https`, 80 for `http`, and 443 for a URL written without a scheme), dropping a trailing slash and a trailing `.git` from
the path, reducing a GitHub project link to its owner and repository compared
without regard to case, and reducing a gitlab.com project link to the
project path before any `/-/` segment, the route marker GitLab reserves inside
a project. A gitlab.com link whose path holds fewer than two nonempty
segments before any `-` segment, or whose first nonempty segment is one of GitLab's site routes (`-`,
`groups`, `users`, `explore`, `dashboard`, `search`, `help` or `admin`), names
no project and SHALL NOT be reduced; it is a site page, compared like another
host's link.
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

#### Scenario: A gitlab.com group link points inside the group

- **WHEN** a source gives `https://gitlab.com/group/-/epics`
- **THEN** it is not reduced to `gitlab.com/group`, because only one nonempty
  segment precedes its `-` segment, so it names a group rather than a project,
  and it derives no source type

### Requirement: A failed fetch aborts the build

A pack that is silently missing a whole upstream is worse than no rebuild at
all, because it would drop every app that upstream contributes. The system
SHALL abort the build when any source cannot be fetched or parsed, and SHALL
NOT write either import file in that case. The build report SHALL still record the failure. The committed codm2000
catalog is a required local source: missing, malformed or unreadable content
SHALL fail the build without falling back to README generation. Builds SHALL
NOT modify that catalog.

#### Scenario: One upstream is unreachable

- **WHEN** one upstream cannot be fetched
- **THEN** the build fails, and the previously written import files are left
  unmodified

#### Scenario: An upstream returns unparseable content

- **WHEN** an upstream is reachable but its content cannot be parsed as the
  expected catalog shape
- **THEN** the build fails with an error naming that source

#### Scenario: Committed source catalog is missing

- **WHEN** the configured codm2000 JSON file is missing or malformed
- **THEN** the build fails naming codm2000 and preserves previous outputs

### Requirement: RJNY export flags select entries per variant

The RJNY catalog carries per-entry export metadata that determines whether an
entry is exported at all and which variants it belongs to. The system SHALL
drop any entry marked as excluded from export, SHALL omit an entry from the
single-screen variant when it is marked as not included in the standard pack,
and SHALL omit an entry from the dual-screen variant when it is marked as not
included in the dual-screen pack. An entry carrying no such flag SHALL be a
candidate for both variants. An entry in both exports SHALL be a baseline
build. An entry only in the dual-screen export SHALL be a dual-screen build,
preferred in dual. An entry only in the standard export SHALL be a baseline
build that upstream keeps out of dual. An entry marked out of both packs SHALL
contribute to neither. These flags SHALL alone decide an entry's kind and
eligibility. "Builds are baseline or dual-screen and each pack selects its kind" in
pack-composition states, once for every source, that no composition setting
changes either, which is also why none restores an entry to a pack its flags
leave it out of or revives an entry excluded from export.

#### Scenario: Entry excluded from export

- **WHEN** an RJNY entry is marked as excluded from export
- **THEN** it contributes to neither variant, regardless of its other flags

#### Scenario: Entry opted out of one variant

- **WHEN** an RJNY entry is marked as not included in the standard pack
- **THEN** it is a candidate for the dual-screen variant only

#### Scenario: Entry carries no export metadata

- **WHEN** an RJNY entry carries no export metadata
- **THEN** it is a candidate for both variants

#### Scenario: Entry kept out of dual by upstream

- **WHEN** an RJNY entry is marked as not included in the dual-screen pack
- **THEN** it is a baseline build for single only, and its family's dual
  selection, if any, comes from another build in that family

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
counterpart in their own packs. The system SHALL resolve each variant's
candidates independently and SHALL NOT require that a package id map to the
same entry across variants. A shared package id does not join candidates at
different project URLs into one family, so such a replacement across URLs
holds in these packs only when a family rule joins the URLs into one explicit
family, as "Composition policy assigns app families by project URL" in
pack-composition defines; without one, the single-screen build's family is
published in single and reported as a single-only coverage finding.

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

#### Scenario: A cross-URL replacement needs a family rule

- **WHEN** the two entries sharing a package id, one single-only and one
  dual-only, carry different project URLs
- **THEN** ingestion retains both, and the dual-only entry replaces the
  single-only one in dual only when a family rule joins their URLs

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

### Requirement: BBoi34 entries map to variants by source file

The system SHALL retain each standard-asset record as a baseline build eligible
for both targets, and each dual-asset record as a dual-screen build eligible
only for dual and therefore preferred there. It SHALL preserve asset origin and
retain both records when one project appears in both assets. Selection SHALL
occur during composition: what a pin, a dual-screen build and a project denial
each do to a project present in both assets is defined by "Builds are baseline
or dual-screen and each pack selects its kind", "Pins select an eligible
candidate of their family" and "Project denials exclude candidates from both
variants" in pack-composition. The asset a record comes from SHALL alone decide
its kind.

#### Scenario: Id present in both BBoi34 assets

- **WHEN** both assets contain different builds of an id
- **THEN** ingestion retains both as separate candidates, a baseline build from
  the standard asset and a dual-screen build from the dual asset, and leaves
  the choice between them to composition

#### Scenario: Standard alternative remains available

- **WHEN** a family's standard-asset build is eligible for both targets and the
  family has no available dual-screen build, because the dual asset lacks one
  or a denial removed one at a project URL the standard build does not share
- **THEN** the retained standard build remains available for dual selection

### Requirement: Hand-written extras are baseline or dual-screen builds

The system SHALL ingest each entry in the extras configuration as a candidate
entry, and SHALL fail the build with an error naming the entry when an extras
entry is missing a package id, a URL or a name. An extras entry has no upstream
record to take a display name from, and a name is not optional downstream:
rendering orders entries by name and the import format displays it. An extras
entry SHALL be a baseline build, a candidate for both variants, unless it
carries an optional boolean `dualScreen` set to true, which makes it a
dual-screen build: a candidate for the dual-screen variant only, preferred
there. `dualScreen` SHALL default to false, and a non-boolean value SHALL fail
the build with an error naming the entry. Ingestion SHALL consume an extras
entry's `dualScreen` field so it does not reach that entry's Obtainium app
record.

#### Scenario: Extras entry lacks a package id

- **WHEN** an extras entry has no package id
- **THEN** the build fails with an error naming that entry

#### Scenario: Extras entry lacks a name

- **WHEN** an extras entry carries a package id and a URL but no name
- **THEN** the build fails with an error naming that entry

#### Scenario: Extras entry is a baseline build

- **WHEN** an extras entry carries a package id, a URL and a name and no
  `dualScreen` field
- **THEN** it is a candidate for both the single-screen and the dual-screen
  variant and is not preferred in dual

#### Scenario: Extras entry is a dual-screen build

- **WHEN** an extras entry sets `dualScreen` to true, a dual-screen
  lower-source candidate shares its family and no pin applies
- **THEN** the extra is a candidate for the dual-screen variant only and wins
  dual selection over that candidate by source precedence

#### Scenario: Extras dual-screen flag is not a boolean

- **WHEN** an extras entry's `dualScreen` field holds a value other than true
  or false
- **THEN** the build fails with an error naming that entry

#### Scenario: Ordinary extra competes with a dual fork

- **WHEN** a baseline extra and a dual-screen lower-source candidate share a
  family and no pin applies
- **THEN** ingestion offers the extra as a baseline build, eligible for both
  variants and not preferred in dual, so composition rather than source
  precedence alone decides dual selection

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

### Requirement: Source records carry no composition policy fields

This requirement SHALL apply to every record a source normalizes,
and SHALL NOT apply to an RJNY entry marked as excluded from export, which is
dropped before normalization. Every such record, from each upstream catalog, the
committed codm2000 catalog and the hand-written extras, SHALL be
an Obtainium app object as its source publishes it, and the extras
`dualScreen` field SHALL be the only field defined by this system that
ingestion reads from a source record. A source record carrying `family` or
`variant` at its top level SHALL fail ingestion regardless of
the field's value, including null, with an error naming the source, the entry
and the field, stating that the field cannot come from a source record, and
stating that composition policy in `config/composition.json` owns app
families and per-pack selection. The error SHALL NOT
direct or imply that the failure can be corrected by editing composition
policy. The failure SHALL persist while the configured source location serves
a record carrying the field, and the system SHALL provide no override for an
individual record or field; an extras entry or a committed codm2000 record is
corrected by editing it. The one other field name
ingestion reserves is `meta`, which the RJNY catalog uses for its export flags
and presentation overrides and which is not part of an Obtainium app object:
ingestion SHALL drop a top-level `meta` from a record of any source, so it never
reaches a pack. Every other field ingestion does not model SHALL be retained
unchanged for rendering, from every source.

#### Scenario: Upstream entry carries a variant field

- **WHEN** an otherwise valid upstream catalog entry carries a top-level
  `variant`
- **THEN** ingestion fails naming that source, the entry and `variant`,
  stating that the field cannot come from a source record and that
  composition policy in `config/composition.json` owns per-pack selection,
  without directing the correction to composition policy, and later builds
  from that source location fail the same way while the record carries the
  field

#### Scenario: Extras entry carries a null family

- **WHEN** an otherwise valid extras entry carries a top-level `family` whose
  value is null
- **THEN** ingestion fails naming extras, the entry and `family`

#### Scenario: Entry excluded from export is not checked

- **WHEN** an RJNY entry marked as excluded from export carries a top-level
  `family`
- **THEN** ingestion does not fail and the entry is dropped

#### Scenario: Unrelated unmodeled field passes through

- **WHEN** an otherwise valid entry from any source carries a top-level field
  that ingestion does not model and that is not `family`, `variant` or `meta`,
  including `packageId`
- **THEN** ingestion retains the field unchanged for rendering rather than
  rejecting or removing it

#### Scenario: A record outside RJNY carries catalog metadata

- **WHEN** an otherwise valid extras or committed codm2000 record carries a
  top-level `meta`
- **THEN** ingestion accepts the record and the rendered entry carries no `meta`

### Requirement: Committed Quiver entries are baseline builds with generated provenance

Routine ingestion SHALL read Quiver entries from its configured committed
Obtainium catalog without requesting Quiver lists, repository hosts or APKs.
A missing, unreadable or malformed catalog, a repeated entry ID or two entries
at one normalized project URL SHALL fail the build while preserving previous
outputs. Valid entries SHALL carry source
`quiver`, generated origin `quiver-generated`, their committed ids and the
source type each declares. They SHALL be
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
value identified. An empty or whitespace-only declaration SHALL count as no
declaration, so the entry derives its source type or carries none.

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

#### Scenario: A record declares an empty source type

- **WHEN** an upstream record declares `overrideSource: ""`
- **THEN** an entry addressing a github.com repository carries the GitHub
  source type, an entry addressing an itch.io page carries no source type, and
  no entry carries an empty source type

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
