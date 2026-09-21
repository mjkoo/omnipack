## MODIFIED Requirements

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
eligibility. "Each build is a baseline build or a dual-screen build" in
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

### Requirement: BBoi34 entries map to variants by source file

The system SHALL retain each standard-asset record as a baseline build eligible
for both targets, and each dual-asset record as a dual-screen build eligible
only for dual and therefore preferred there. It SHALL preserve asset origin and
retain both records when a package id appears in both assets. Selection SHALL
occur during composition: what a pin, a dual-screen build and a package denial
each do to a package id present in both assets is defined by "Each build is a
baseline build or a dual-screen build", "Explicit selections identify an
eligible candidate" and "Package denials exclude candidates from both
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
  or a denial removed one whose package the standard build does not carry
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

### Requirement: Every entry carries a supported source type

Obtainium reads a per-app source type that decides which settings keys an app
has, so every entry must carry one before it can be rendered. An entry ingested
from the RJNY or BBoi34 catalog SHALL take the source type its record declares,
and a record declaring none SHALL fail as an unsupported source type. An extras
entry or a committed codm2000 entry with an explicit `overrideSource` SHALL use
that declared source type before URL-based inference. Only when such an entry
omits `overrideSource` SHALL the system derive the source type from the URL: a
github.com repository takes GitHub and any other URL takes HTML. The pack SHALL
support GitHub, HTML and GitLab, and SHALL fail the build with an error naming
the entry and offending value for any other source type, including a malformed
explicit declaration rather than silently falling back to URL inference.

Native GitLab entries SHALL follow the URL, identity and discovery boundary in
"Public GitLab entries keep native source identity". Explicit per-app settings
SHALL override hydrated defaults. A native GitLab entry SHALL be hydrated with
the defaults defined for GitLab, never those defined for HTML.

#### Scenario: Upstream record declares a source type

- **WHEN** an upstream entry's record declares the HTML source type
- **THEN** the ingested entry carries the HTML source type

#### Scenario: An entry with no upstream record derives its source type

- **WHEN** an extras entry or a committed codm2000 entry that omits
  `overrideSource` addresses a github.com repository
- **THEN** it carries the GitHub source type, while an entry addressing any
  other URL carries the HTML source type

#### Scenario: Unsupported source type

- **WHEN** an upstream or extras entry declares a source type other than GitHub, HTML or GitLab
- **THEN** the build fails with an error naming that entry and that source type

#### Scenario: Explicit GitLab declaration takes precedence over URL inference

- **WHEN** an extras entry declares `overrideSource: GitLab` with a public gitlab.com project URL
- **THEN** ingestion retains GitLab, and rendering uses GitLab defaults and preserves explicit settings in both variants instead of selecting HTML

#### Scenario: Native GitLab URL is outside the supported boundary

- **WHEN** an entry declares GitLab with a non-HTTPS URL, a host other than gitlab.com or no namespace/project path
- **THEN** the build fails with the entry and invalid URL identified

#### Scenario: A committed codm2000 entry declares its source type

- **WHEN** a committed codm2000 entry addressing a github.com repository declares
  the HTML source type
- **THEN** the ingested entry carries the HTML source type rather than the type
  its URL would derive

#### Scenario: An upstream record declares no source type

- **WHEN** an RJNY or BBoi34 record carries no `overrideSource`
- **THEN** the build fails naming that entry as having an unsupported source
  type, rather than deriving one from its URL

### Requirement: Public GitLab entries keep native source identity

The system SHALL accept explicit extras with source type `GitLab` whose URL identifies exactly one public gitlab.com project, preserve the full case-sensitive project path including subgroups, hydrate supported GitLab defaults, and render `overrideSource: GitLab`. A URL SHALL identify one public gitlab.com project only when its scheme is `https` and its host is `gitlab.com`, each compared without regard to case, with no `www.` prefix and no port, carrying no credentials, and whose path holds between two and twenty-one nonempty components naming a project and its namespaces, each read with its case and encoding exactly as written while empty components and a trailing slash are ignored, no component of which is the separator `-` that gitlab.com reserves for its own routes, and which carries no query and no fragment. Any other URL SHALL fail the build with the entry and the URL identified, because the pipeline cannot tell which part of it names the project.

This acceptance boundary is an earlier and separate stage from normalized
comparison: the native adapter reads the project path out of the URL as the
entry spells it, before any normalization is applied, so a URL that compares
equal to an acceptable one MAY still be rejected here. A `www.gitlab.com`
spelling compares equal to the canonical one, because comparison drops a leading
`www.`, and is nonetheless not a native GitLab project URL; an explicit port is
rejected here and, being retained in the normalized form, also makes a different
project under comparison. Acceptance SHALL therefore be decided on the URL as
written rather than on its comparison identity.

Package ids for these explicit extras SHALL be supplied by the maintainer who adds the entry, from recorded primary APK manifest evidence as any other identity decision is; the pipeline SHALL NOT verify them, because generated package discovery covers GitHub projects only.

#### Scenario: A GitLab extra reaches both exports

- **WHEN** an explicit GitLab extra uses its canonical gitlab.com project URL and is selected in both variants
- **THEN** both outputs and individual import links retain native GitLab identity and compatible settings

#### Scenario: A GitLab URL carries more than a project path

- **WHEN** an entry declares GitLab with a gitlab.com URL whose host is spelled with a `www.` prefix, or that carries a query, a fragment, credentials, an explicit port, a reserved `-` path component or more path components than a project and its namespaces
- **THEN** the build fails with the entry and the invalid URL identified, rather than reading a project path out of it

### Requirement: Committed codm2000 entries are dual-screen builds that keep their generated identity

The system SHALL ingest accepted codm2000 entries from committed Obtainium JSON.
README parsing and package-ID resolution SHALL occur only in the separate
source-generation operation. The source catalog SHALL contain generated GitHub
project entries independently of other upstream coverage, including APKs and
explicit track-only resources. It SHALL retain discovery settings such as
prerelease enablement and filename filters, and SHALL NOT reinterpret a
track-only resource ID as an Android package ID.

During routine ingestion, codm2000 entries SHALL be dual-screen builds, eligible
for dual only and preferred there. A normalized project URL already supplied by
a higher-precedence candidate that its source makes eligible for dual SHALL
suppress the corresponding codm2000 candidate before exclusions and selection.
Single-only coverage SHALL NOT suppress it. Suppression SHALL use source
eligibility alone, and ingestion SHALL NOT read or apply the composition policy.
Merely appearing in codm2000 SHALL NOT promote an ordinary higher-source build.

Retained entries SHALL preserve codm2000 provenance, generated origin, original
package identity and source settings, so family rules and fork-specific overlays
that select a generated entry match it. How a policy selector is validated
against the admitted candidates, and what a missing rule target or pinned
candidate does, is defined by "Composition policy separates app families from
package identities" and "Explicit selections identify an eligible candidate" in
pack-composition.

#### Scenario: Dual coverage suppresses a local catalog candidate

- **WHEN** a higher-source candidate covers dual with a normalized URL equal to a committed codm2000 entry
- **THEN** the codm2000 candidate is suppressed without promoting the higher-source candidate

#### Scenario: Single-only coverage leaves a dual candidate

- **WHEN** the higher-precedence candidate for that URL is eligible for single only, as an RJNY entry left out of the dual-screen export is
- **THEN** the committed entry remains a dual-screen codm2000 candidate, preferred in dual

#### Scenario: Retained generated selectors keep matching

- **WHEN** a retained committed entry has a generated-origin rule or overlay selector
- **THEN** its source identity is preserved and the same family and override behavior applies

#### Scenario: A selected project is removed

- **WHEN** an accepted source update removes a candidate required by an active rule or pin
- **THEN** pack composition fails explicitly rather than silently ignoring the stale selector

#### Scenario: Committed prerelease entries retain their settings

- **WHEN** the committed catalog includes manifest-verified APK entries with explicit prerelease settings and no higher-source coverage
- **THEN** they enter dual as installable APK entries, retaining those settings and their original identities without entering single

#### Scenario: A tracking resource keeps its identity

- **WHEN** the committed catalog includes an explicit track-only resource
- **THEN** dual retains its stable resource identity, track-only flag and manual-installation description
- **AND** neither pack's entry for the app the resource extends is replaced

### Requirement: Source records carry no composition policy fields

This requirement SHALL apply to every record a source normalizes, including a
committed codm2000 record later suppressed by higher-precedence dual coverage,
and SHALL NOT apply to an RJNY entry marked as excluded from export, which is
dropped before normalization. Every such record, from each upstream catalog, the
committed codm2000 catalog and the hand-written extras, SHALL be
an Obtainium app object as its source publishes it, and the extras
`dualScreen` field SHALL be the only field defined by this system that
ingestion reads from a source record. A source record carrying `family`,
`packageId` or `variant` at its top level SHALL fail ingestion regardless of
the field's value, including null, with an error naming the source, the entry
and the field, stating that the field cannot come from a source record, and
stating that composition policy in `config/composition.json` owns app
families, package identities and per-pack selection. The error SHALL NOT
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

#### Scenario: Upstream entry carries a package identity field

- **WHEN** an otherwise valid upstream catalog entry carries a top-level
  `packageId`
- **THEN** ingestion fails naming that source, the entry and `packageId`,
  stating that the field cannot come from a source record and that
  composition policy in `config/composition.json` owns package identities,
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

#### Scenario: Suppressed codm2000 entry is checked

- **WHEN** a committed codm2000 entry whose normalized URL is covered by a
  higher-precedence dual candidate carries a top-level `variant`
- **THEN** ingestion fails naming codm2000, the entry and `variant`

#### Scenario: Unrelated unmodeled field passes through

- **WHEN** an otherwise valid entry from any source carries a top-level field
  that ingestion does not model and that is not `family`, `packageId`,
  `variant` or `meta`
- **THEN** ingestion retains the field unchanged for rendering rather than
  rejecting or removing it

#### Scenario: A record outside RJNY carries catalog metadata

- **WHEN** an otherwise valid extras or committed codm2000 record carries a
  top-level `meta`
- **THEN** ingestion accepts the record and the rendered entry carries no `meta`
