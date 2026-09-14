# pack-curation Specification

## Purpose

Defines how curated app decisions are recorded, protected and documented, plus
the pack's own notification tracker and the exclusion of upstream pack
trackers.

## Requirements

### Requirement: Curation evidence states its limits

Durable curation documentation SHALL state each maintained policy and its
rationale, the observed release/APK versions and package identities behind it, the
observation date and primary upstream references. It SHALL distinguish current
structural validation from dated metadata/APK observations and from device
validation, and SHALL NOT claim device validation that was not performed. Where
a curated entry, meaning an entry maintained in `config/extras.json`, needs
user action beyond installing it, such as supplying game files, installing a
separate component or configuring the app by hand, consumer documentation
SHALL describe that action. It SHALL explain that
explicit source-version tracking keeps update checks enabled but cannot
guarantee eliminating a one-time spurious update after re-import or detecting
an in-place asset replacement that leaves the source version unchanged.

Known upstream package-id mismatches SHALL be recorded without claiming that a
version policy repairs them. A successful structural result SHALL NOT be
described as proof of safe identity, installation, re-import, or update
behavior for those entries.

#### Scenario: Resolved APK declares another package id

- **WHEN** an inspected APK declares a package id other than the id its upstream catalog uses
- **THEN** documentation records the original identity and the manifest-backed correction
- **AND** the maintained identity policy exports the manifest-backed id

#### Scenario: A curated entry needs user-supplied files

- **WHEN** a curated entry cannot run until the user supplies game files or installs a separate component
- **THEN** consumer documentation describes that step
- **AND** it does not claim the step was validated on a device unless it was

### Requirement: Upstream pack trackers are excluded from both packs

Both published variants SHALL exclude an upstream catalog's own pack-update
tracker entry through a maintained package denial, including after upstream
refreshes. The exclusion SHALL keep that upstream as an app catalog source,
with its attribution and provenance.

#### Scenario: Upstream refresh contains its pack tracker

- **WHEN** an upstream source's refreshed records include its own track-only pack tracker, and a maintained denial names that tracker's id
- **THEN** neither generated pack nor the generated README catalog includes that tracker
- **AND** the upstream's other eligible apps remain available to composition

### Requirement: Both packs include one shared omnipack notification tracker

Each export SHALL contain exactly one identical GitHub track-only entry with stable synthetic id `809443320`, name `omnipack updates`, repository `https://github.com/mjkoo/omnipack`, and Utilities categorization. It SHALL select titles matching `^omnipack revision [0-9]+$`, extract the trailing integer from the release title, allow prereleases and scanning past unrelated releases, disable latest-endpoint prioritization and asset-date versioning, and retain background notifications. The rendered tracker SHALL NOT embed the observed revision, installed version or asset URLs. Source revision changes SHALL NOT require an APK.

Consumer documentation SHALL explain that either variant changing can notify everyone, that acknowledgement is not synchronization, and that updating the pack requires downloading the appropriate JSON and re-importing. Existing raw-main links and the exclusion of upstream pack trackers SHALL remain in force.

#### Scenario: Only one variant changes

- **WHEN** a complete release publication increments the shared revision
- **THEN** either variant's tracker can report that revision as an update

#### Scenario: Rebuild observes a newer release revision

- **WHEN** the curated configuration and other build inputs are unchanged
- **THEN** observing the tracker revision alone does not change either generated pack

### Requirement: Curated decisions are protected by outcome checks over reviewed configuration

Maintained source-selection, version, asset and identity decisions SHALL be
expressed as reviewed configuration, meaning the configuration maintainers
edit by hand rather than the automation-maintained codm2000 catalog, and SHALL
be preserved across source refreshes. That configuration SHALL be the record of
each curated app's intended values. Its selection settings describe intended
Obtainium behavior; the pack builder SHALL NOT independently execute them as a
live compatibility guarantee. Known observed versions and asset identities
SHALL remain dated evidence, not assertions of current upstream health.

Regression checks SHALL exercise composition and rendering and assert the
outcomes that depend on how the pipeline combines reviewed configuration with
upstream records, including that a maintained override survives an upstream
refresh that changes the setting it covers. A curated extra is designated to
win the single-screen pack by source precedence when its entry in
`config/extras.json` is eligible for single, meaning it is not a dual-screen
build, and its family has no committed single pin. A single pin is an explicit
reviewed selection for its family, and composition already fails when a pinned
candidate is missing or ineligible, so the check steps aside for a pinned
family. Each designated curated extra SHALL have a check that it is its
family's single-screen winner under the committed configuration, because no
build or verification check fails when single stops serving it. That check
SHALL derive its expected set from `config/extras.json` and the committed
single pins rather than from a hand-kept list, so a newly curated extra is
covered without editing the check.

A test that reads the automation-maintained codm2000 catalog SHALL fail only
where composition, build or verification with the committed configuration, or
catalog validation, would also reject that catalog. The test suite composes
over frozen captured upstream records while the source workflow builds from
live ones. Composition here means composition over the suite's captured
records; a catalog whose composition depends on upstream records newer than
those captures is outside this guarantee. Catalog validation
consists of these checks on the catalog's content: the catalog is an object
with an apps list; entry ids are unique; no two entries share a normalized
project URL; each entry's id and flags suit its kind, meaning an APK entry carries a syntactically valid Android manifest
package id and is not track-only, and a track-only entry carries a
numeric-string resource id with `trackOnly` true and version detection, ZIP
extraction and APK architecture filtering disabled; and the file's bytes are
the canonical rendering of its entries. These checks never depend on which
projects the catalog contains or how they resolved, so a test asserting
particular committed ids or projects is not part of catalog validation, and a
source proposal whose catalog passes catalog validation, composes over the
captured records, builds and verifies cannot fail the test suite. Tests SHALL NOT require maintaining
another implementation of Obtainium source resolution or regex semantics.

#### Scenario: Upstream refresh changes a curated setting

- **WHEN** fixture source records change a setting covered by a maintained override
- **THEN** composed and rendered output retains the intended curated value

#### Scenario: A designated curated extra stops winning single

- **WHEN** a curated extra's entry in `config/extras.json` is eligible for single and its family has no committed single pin, and a configuration change that composition accepts, such as a package denial of that extra's id when no pin names it, leaves it without its family's single-screen selection
- **THEN** a regression check fails and identifies that family

#### Scenario: A source proposal adds, removes or re-resolves projects

- **WHEN** a candidate codm2000 catalog passes catalog validation, meaning it is an object with an apps list, its entry ids are unique, no two entries share a normalized project URL, each entry's id and flags suit its kind and its bytes are the canonical rendering of its entries, and it composes with the committed configuration over the suite's captured upstream records, builds and verifies
- **THEN** no test fails because of which projects the catalog contains or how they resolved
