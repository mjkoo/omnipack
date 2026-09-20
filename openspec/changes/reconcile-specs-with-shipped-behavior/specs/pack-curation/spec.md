## MODIFIED Requirements

### Requirement: Both packs include one shared omnipack notification tracker

Each export SHALL contain exactly one identical GitHub track-only entry for this project's own rolling release, whose synthetic id, name, repository and categorization come from reviewed configuration rather than from this requirement. It SHALL select release titles by a pattern matching the rolling release title format fixed by "One owned rolling release publishes both variants" in rolling-pack-release and no other release of that repository, so the pattern and that format SHALL change together. It SHALL extract the revision from the matched release title, allow prereleases and scanning past unrelated releases, disable latest-endpoint prioritization and asset-date versioning, and retain background notifications. The rendered tracker SHALL NOT embed the observed revision, installed version or asset URLs. Source revision changes SHALL NOT require an APK.

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

A maintained override SHALL survive a source refresh that changes the setting
it covers, and that outcome SHALL be guarded rather than left to review,
because it depends on how the pipeline combines reviewed configuration with
upstream records and no other check fails when it breaks.

A curated extra is designated to win the single-screen pack by source
precedence when its entry in `config/extras.json` is eligible for single,
meaning it is not a dual-screen build, and its family has no committed single
pin. A single pin is an explicit reviewed selection for its family, and
composition already fails when a pinned candidate is missing or ineligible, so
designation steps aside for a pinned family. Each designated curated extra
SHALL be guarded by a check that fails and identifies its family when it stops
being that family's single-screen winner, because no build or verification
check fails when single stops serving it. That coverage SHALL follow from the
reviewed configuration itself, so that curating a new extra covers it with no
further edit.

An automation-maintained codm2000 catalog SHALL fail the test suite only where
the catalog is not valid, or where composition with the committed configuration,
a build or a verification would fail. Composition here means composition over
the suite's captured upstream records while the source workflow builds from live
ones, so a catalog whose composition depends on upstream records newer than
those captures is outside this guarantee. Which projects the catalog contains
and how they resolved SHALL NOT decide whether the suite passes, so a source
proposal whose catalog is valid and which composes, builds and verifies SHALL
NOT fail the suite.

Validity is wider than what the pipeline rejects, so the suite MAY assert a
validity rule no pipeline stage enforces, and doing so SHALL NOT be read as
failing the catalog over which projects it contains or how they resolved. A rule
the pipeline does enforce SHALL be stated where it is enforced rather than
enumerated here, and no rule SHALL be attributed to a stage that does not check
it: a build rejects a catalog that repeats an entry id, by "One package id may
resolve differently per variant" in source-ingestion, while generation, reading
the accepted catalog back, rejects a document whose shape is wrong or whose
entries lack a string id and url, a catalog that repeats an entry id, and a
catalog that holds one normalized project URL twice, by "Generation produces a
deterministic Obtainium source catalog" in readme-source-generation.

Two further validity rules are owed by the test suite, no pipeline stage having
ever checked them, and are owned here alongside the other outcomes this
requirement protects. Every catalog entry SHALL carry an id and settings
appropriate to its kind: a track-only entry a synthetic numeric id with version
detection, zip inclusion and architecture filtering all disabled, and an APK
entry a well-formed package id and no track-only flag. The committed catalog
file SHALL be byte-identical to the canonical rendering of the entries it holds,
so that a hand edit or a stale write is visible rather than silently carried.
Generation neither compares the committed bytes against its own rendering nor
checks an entry's id and settings against its kind, so nothing fails when either
drifts unless the suite asserts it. Tests SHALL NOT require maintaining another
implementation of Obtainium source resolution or regex semantics.

#### Scenario: Upstream refresh changes a curated setting

- **WHEN** fixture source records change a setting covered by a maintained override
- **THEN** composed and rendered output retains the intended curated value

#### Scenario: A designated curated extra stops winning single

- **WHEN** a curated extra's entry in `config/extras.json` is eligible for single and its family has no committed single pin, and a configuration change that composition accepts, such as a package denial of that extra's id when no pin names it, leaves it without its family's single-screen selection
- **THEN** a regression check fails and identifies that family

#### Scenario: A source proposal adds, removes or re-resolves projects

- **WHEN** a candidate codm2000 catalog is valid and composes with the committed configuration over the suite's captured upstream records, builds and verifies
- **THEN** no test fails because of which projects the catalog contains or how they resolved
