## MODIFIED Requirements

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
and its no-Android skip, as "Resolution failures keep only unchanged committed
entries" there defines it for every generated source.

For a project without a committed entry, a conclusive repository-metadata
absence (HTTP 404 or 451 on the repository lookup) SHALL produce a reported
unavailable-repository skip, distinct from the no-Android skip. No-release SHALL
require successful repository identification. Any other failed lookup SHALL be
an unresolved failure, not a no-Android conclusion. For a project with a
committed entry, no permitted release or no eligible APK SHALL instead follow
the retention rule. Generation SHALL NOT execute downloaded APKs or generate
track-only entries.

A skip rule SHALL be keyed by a row's listed normalized GitHub URL or, for an
unsupported row, by its literal `repository` value together with its
`repositorySource` when present, and SHALL carry a reason. It SHALL be matched
before any request for that row, so a skipped row makes no repository, release
or APK request and a persistently failing or unsupported row is silenced.
A discovery skip pauses inspection of that row; it does not reject the app.
If the skipped row's listed URL matches an accepted entry, generation SHALL
retain that entry unchanged and report it as skipped without claiming a fresh
check. A skip SHALL NOT affect entries supplied by other sources. Pruning an
app from the packs is done by project denial, not by a skip rule.

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

### Requirement: Quiver admission preserves reviewed choices without freezing source membership

Initial source admission SHALL account for every discovered Android candidate
under the existing curation standard. Every rejected Android candidate SHALL
have its project URL and rejection reason recorded in the deny list. A skip MAY additionally silence its discovery row to avoid resolution;
it SHALL NOT substitute for that denial. A denied app MAY remain in a source
candidate catalog because final composition applies project denials.
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
- **THEN** its project URL and rejection reason are maintained in the deny list, and a skip rule may additionally avoid resolving its discovery row
- **AND** if a later catalog lists the app under a renamed repository, the new URL is a different project until the maintainer denies it too

#### Scenario: Future project passes default resolution

- **WHEN** a new project resolves and its candidate catalog is valid and composes with reviewed configuration
- **THEN** no fixed-membership regression assertion rejects it merely because it is new
