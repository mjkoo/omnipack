## Purpose

Discovers Android APK projects from Quiver's cross-platform community lists and
produces complete, reviewed Obtainium catalog candidates independently of pack
building and device validation.

## ADDED Requirements

### Requirement: Quiver discovery accounts for the complete configured catalog

Generation SHALL read the configured Quiver index and all lists it references,
validate their shapes, and preserve project/list provenance in diagnostics.
Malformed or unavailable required lists and an empty discovered project set
SHALL fail generation without proposing deletions. Every list location SHALL
lie within the configured catalog host and path prefix: a list location
outside it SHALL fail generation as a malformed index. A row's repository SHALL
be its `repository` value, an `owner/name` pair mapped to
https://github.com/owner/name (the row's listed URL), and a `repositorySource`
that is absent or equals `github` case-insensitively SHALL mean GitHub; of the other row fields, only
`project` (naming) and `releaseAssetFilter` (diagnostics) SHALL be used.
Supported public GitHub repositories SHALL be normalized and repository renames
resolved to a canonical URL before canonical project deduplication. A row whose
`repositorySource` has any other value, or whose `repository` is not a valid
GitHub `owner/name` pair, SHALL be reported as an unsupported row, SHALL never
be looked up on GitHub and SHALL NOT block anything. Duplicate references
SHALL NOT create duplicate generated entries: rows for one canonical repository SHALL
collapse into one project. Differing upstream asset filters among those rows
SHALL be reported as diagnostics and SHALL NOT fail generation; a repository
whose eligible APKs carry several package IDs is governed by the APK agreement
rule below. Optional platform metadata SHALL NOT decide admission or absence:
missing, stale or failed metadata SHALL NOT prevent fresh release discovery.

#### Scenario: One required list fails

- **WHEN** one referenced list cannot be fetched or parsed while other lists succeed
- **THEN** generation fails and offers no replacement catalog or deletions

#### Scenario: List location outside the configured catalog

- **WHEN** the index references a list outside the configured catalog host and path prefix
- **THEN** generation fails as a malformed index without fetching that list

#### Scenario: Repository rename overlaps another row

- **WHEN** two rows resolve to the same canonical GitHub repository
- **THEN** discovery accounts for one project while preserving both list references

#### Scenario: Duplicate rows carry different upstream asset filters

- **WHEN** two rows for one canonical repository carry different upstream asset filters
- **THEN** discovery accounts for one project, reports the differing filters as a diagnostic and does not fail generation

#### Scenario: Android support outpaces metadata

- **WHEN** optional metadata is absent or lists no APK but the fresh selected release has an eligible APK
- **THEN** the project is evaluated for APK admission using that release

#### Scenario: Unsupported provider

- **WHEN** a row's `repositorySource` is `gitlab`
- **THEN** it is reported as an unsupported row and never looked up on GitHub, without blocking other projects or creating an unchecked entry

#### Scenario: GitHub named in another case

- **WHEN** a row's `repositorySource` is `GitHub`
- **THEN** the row is a supported GitHub row

### Requirement: Quiver projects default to fresh stable APK discovery

Supported projects SHALL default to stable APK discovery without an admission
allowlist. Reviewed project policy SHALL support naming/category overrides,
skip rules with reasons and the existing bounded prerelease, release-title,
APK-filename and version settings. Invalid policy SHALL fail before network
requests. Quiver's own asset-filter syntax SHALL NOT implicitly become an
Obtainium filter. Generation SHALL independently resolve each unskipped
project from current release data on each invocation under its effective policy.
Release selection and APK inspection SHALL use the supported GitHub selection,
bounds, portable settings and all-selected-APK agreement rules defined by
"Release APKs determine package IDs automatically" in readme-source-generation,
except for the Quiver-specific no-release and no-APK outcomes below.

For a project without a committed entry, a successful check finding no permitted
release or no eligible direct APK SHALL produce a reported skip, not a tracker.
For such a project, a conclusive repository-metadata absence (HTTP 404 or 451
on the repository lookup) SHALL produce a reported unavailable-repository skip,
distinct from the no-Android skip. Any other failed lookup, including network,
authentication and rate-limit errors, or an unreadable/ambiguous selected APK
SHALL be an unresolved failure, not a no-Android conclusion. No-release SHALL
require successful repository identification and a conclusive release absence
under the supported selection policy. For a project with a committed entry, no
permitted release or no eligible APK SHALL instead follow the retention rule.
Generation SHALL NOT execute downloaded APKs or generate track-only entries.

A skip rule SHALL be keyed by a row's listed normalized GitHub URL or, for an
unsupported row, by its literal `repository` value together with its
`repositorySource` when present, and SHALL carry a reason. It SHALL be matched
before any request for that row, so a skipped row makes no repository, release
or APK request and a persistently failing or unsupported row is silenced.
A discovery skip pauses inspection of that row; it does not reject the app.
If the skipped row's listed URL matches an accepted entry, generation SHALL
retain that entry unchanged and report it as skipped without claiming a fresh
check. A skip SHALL NOT affect entries supplied by other sources. Pruning an
app from the packs is done by package denial, not by a skip rule.

#### Scenario: Newly discovered stable Android project

- **WHEN** a previously unseen GitHub project has readable eligible stable APKs agreeing on package identity and no explicit rule
- **THEN** it enters the candidate catalog without adding an admission rule

#### Scenario: Desktop-only release

- **WHEN** a new project's fresh selected release has desktop assets but no eligible direct APK
- **THEN** it is reported as skipped and is neither an installable entry nor a tracker

#### Scenario: Release absence differs from lookup failure

- **WHEN** a new project's release lookup fails without establishing permitted-release absence
- **THEN** generation reports an unresolved failure and emits no complete catalog

#### Scenario: Listed repository no longer exists

- **WHEN** the repository lookup for a project without a committed entry returns HTTP 404 or 451
- **THEN** the project is reported as an unavailable-repository skip, separately from no-Android skips, and generation continues

#### Scenario: Explicit prerelease selection

- **WHEN** reviewed policy permits prereleases and the newest matching release contains readable agreeing APKs
- **THEN** its package identity and compatible prerelease settings enter the candidate

#### Scenario: Multiple APK identities

- **WHEN** the selected APK assets disagree on package ID
- **THEN** resolution fails without accepting a successful subset or inventing an identity

#### Scenario: Reviewed skip

- **WHEN** a skip rule names a row's listed URL with a reason and that repository's lookup would fail, for example with HTTP 403
- **THEN** fresh resolution is omitted and reported with that reason, no request is made for the row, and generation continues

#### Scenario: Discovery skip matches an accepted entry

- **WHEN** a reviewed discovery skip names a listed row whose URL matches an accepted Quiver entry
- **THEN** generation retains that entry byte-for-byte and reports the skipped refresh, without requesting the repository, release or APK
- **AND** entries from other sources remain unaffected

### Requirement: Quiver candidates are deterministic and preserve unchanged entries on resolution failure

Generation SHALL produce deterministic Obtainium JSON with one entry per
canonical project and unique manifest-backed package IDs, compatible GitHub
settings, names and categories. A freshly rendered entry's `url` SHALL be the
canonical post-rename `https://github.com/owner/name`. Two projects resolving to one
package ID SHALL fail generation naming both projects; a reviewed skip or
selection is the remedy. Source-generated entries SHALL be independent
of final composition, other source coverage and final-pack overlays. Reading
accepted data and emitting candidate data SHALL reject malformed records,
duplicate IDs or duplicate normalized project URLs. Canonical generation SHALL
NOT embed observed release versions or asset URLs as fixed update targets.
An entry's name SHALL be the row's `project` (the port name) when present,
otherwise the repository name, and a reviewed name override SHALL win; the
row's `name` (the game title) SHALL NOT name an entry. When collapsed rows for
one canonical repository disagree on `project`, the name SHALL be a stable
deterministic choice independent of row order.

A row SHALL match a committed entry when the entry's normalized URL equals
either the row's canonical URL or the row's listed normalized URL; package IDs
SHALL NOT match entries to rows. A committed entry that no row matches, or
whose row's repository lookup returns HTTP 404 or 451, SHALL be removed from the
candidate, and the removal SHALL appear in the candidate comparison.

A project's resolution failure SHALL retain only its own accepted entry when
rendering it with the same inputs as a fresh render, meaning current effective
policy and the current discovery-derived name and category, together with that
entry's package ID and URL, would reproduce the accepted entry exactly. Retention SHALL be reported separately
from successful fresh resolution. Any unresolved project without such a
retainable entry SHALL fail the complete generation. Later invocations SHALL
retry resolution without reusing previous run state. A required discovery
failure SHALL never be answered by partial source removals. Generation SHALL
never overwrite committed catalogs or policy.

#### Scenario: Existing APK disappears

- **WHEN** an admitted project with unchanged effective policy no longer has a permitted APK
- **THEN** its accepted entry is retained and reported as a failure rather than proposed for deletion

#### Scenario: Upstream name changes while resolution fails

- **WHEN** an accepted entry's name came from the row's `project`, that `project` changes, and the project's resolution fails
- **THEN** the re-render does not reproduce the accepted entry, so generation fails visibly rather than retaining it

#### Scenario: Two ports share one game title

- **WHEN** two repositories' rows carry the same game title in `name` but different `project` values and neither has a reviewed name override
- **THEN** each entry is named by its own `project`, so the two entries have distinct names

#### Scenario: Changed policy cannot resolve

- **WHEN** a project's effective policy changes and resolution fails
- **THEN** no complete candidate catalog is emitted and accepted data remains unchanged

#### Scenario: Confirmed source removal

- **WHEN** successful discovery no longer lists an accepted project, or its repository lookup returns HTTP 404 or 451
- **THEN** its deletion appears in the candidate comparison

#### Scenario: Entry committed under a repository's old name

- **WHEN** an entry was committed under a repository's then-canonical URL, the repository was later renamed, a row still lists the old name, and the selected release has no eligible APK
- **THEN** the row matches the entry by its listed URL and the entry follows retention

#### Scenario: Newly listed fork reuses a package ID

- **WHEN** a newly listed fork resolves to the package ID of another listed project
- **THEN** generation fails naming both projects

#### Scenario: Stable input order independence

- **WHEN** equivalent project rows arrive in a different order with identical effective policy and resolved identities
- **THEN** candidate catalog bytes are identical

#### Scenario: Other source already covers a project

- **WHEN** a resolved Quiver project also appears in another pack source
- **THEN** generation still records it and leaves final selection to ingestion and composition

### Requirement: Quiver admission preserves reviewed choices without freezing source membership

Initial source admission SHALL account for every discovered Android candidate
under the existing curation standard. Every rejected Android candidate SHALL
have its known package ID and rejection reason recorded in the package deny
list. A skip MAY additionally silence its discovery row to avoid resolution;
it SHALL NOT substitute for that denial. A denied app MAY remain in a source
candidate catalog because final composition applies package denials.
Maintained skips, denials and selection exceptions SHALL
survive later source refreshes. Subsequent generation SHALL admit newly resolvable default
projects to candidate catalogs without requiring an admission-list edit.
Candidate acceptance SHALL depend on catalog validity and compatibility with
reviewed configuration and both pack outputs, not a fixed list of project names
or previously observed package IDs. A same-project identity change SHALL remain
visible in the candidate comparison, and conflicts with maintained selectors
SHALL fail the existing composition checks rather than silently rewrite policy.

#### Scenario: Initial candidate is unsuitable

- **WHEN** initial vetting rejects a discovered Android project
- **THEN** its known package ID and rejection reason are maintained in the package deny list, and a skip rule may additionally avoid resolving its discovery row
- **AND** if a later catalog lists the same package under a renamed repository, final composition still excludes it by package denial

#### Scenario: Future project passes default resolution

- **WHEN** a new project resolves and its candidate catalog is valid and composes with reviewed configuration
- **THEN** no fixed-membership regression assertion rejects it merely because it is new
