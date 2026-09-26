## MODIFIED Requirements

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

The automation-maintained codm2000 catalog SHALL be held to two things only:
that it is valid, and that it composes with the committed configuration, builds
and verifies. Which projects the catalog contains and how they resolved SHALL
NOT be grounds for blocking a source proposal, so a proposal whose catalog is
valid and which composes, builds and verifies SHALL need no other edit to the
repository to be accepted. Composition here means composition over upstream
records captured in the repository, while the source workflow builds from live
ones, so a catalog whose composition depends on upstream records newer than
those captures is outside this guarantee.

Catalog validity comprises the rules the pipeline enforces, each stated where it
is enforced, and two rules no pipeline stage checks, which this requirement
owns. A build rejects a malformed committed catalog, by "A failed fetch aborts
the build" in source-ingestion, and one that repeats an entry id, by "One package
id may resolve differently per variant" there. Generation, reading the accepted
catalog back, rejects a document whose shape is wrong or whose entries lack a
string id and url, a catalog that repeats an entry id, and a catalog that holds
one normalized project URL twice, by "Generation produces a deterministic
Obtainium source catalog" in readme-source-generation. Only the last of these is
checked by generation alone.

The two owned rules are these. Every catalog entry SHALL carry an id and
settings appropriate to its kind: a track-only entry a synthetic numeric id with
version detection, zip inclusion and architecture filtering all disabled, and an
APK entry a well-formed package id and no track-only flag. The committed catalog
file SHALL be byte-identical to the canonical rendering of the entries it holds,
so that a hand edit or a stale write is visible rather than silently carried.
Because generation neither compares the committed bytes against its own
rendering nor checks an entry's id and settings against its kind, each rule
SHALL be guarded by a check that fails when it drifts. Guarding any outcome in
this requirement SHALL NOT require maintaining another implementation of
Obtainium source resolution or regex semantics.

The same configuration-driven acceptance and canonical-rendering checks SHALL
cover the automation-maintained Quiver catalog. Its entries SHALL be installable
APK records with well-formed package IDs, supported settings and no track-only
flag; Quiver generation owns canonical-project and package uniqueness as defined
in quiver-source-generation. Accepted Quiver catalogs SHALL NOT be subject to a
hard-coded membership assertion. Reviewed Quiver exceptions and skip rules SHALL
be hand-maintained configuration, not automation-maintained catalog content.
Pruning an unwanted Quiver app uses the package deny list, as for any source.

#### Scenario: Upstream refresh changes a curated setting

- **WHEN** a source refresh changes a setting covered by a maintained override
- **THEN** composed and rendered output retains the intended curated value

#### Scenario: A designated curated extra stops winning single

- **WHEN** a curated extra's entry in `config/extras.json` is eligible for single and its family has no committed single pin, and a configuration change that composition accepts, such as a package denial of that extra's id when no pin names it, leaves it without its family's single-screen selection
- **THEN** a regression check fails and identifies that family

#### Scenario: A source proposal adds, removes or re-resolves projects

- **WHEN** a candidate codm2000 catalog is valid and composes with the committed configuration over the captured upstream records, builds and verifies
- **THEN** no check blocks the proposal because of which projects the catalog contains or how they resolved

#### Scenario: The committed catalog drifts from its canonical form

- **WHEN** the committed codm2000 catalog's bytes differ from the canonical rendering of its entries, or an entry's id or settings stop fitting its kind
- **THEN** a regression check fails and identifies the catalog

#### Scenario: Quiver proposal changes membership

- **WHEN** a Quiver candidate is canonical and valid and composes with reviewed configuration over captured upstream records, builds and verifies
- **THEN** no check blocks it solely because it adds or removes a project

#### Scenario: Quiver catalog is edited inconsistently

- **WHEN** committed Quiver bytes differ from canonical rendering or a record lacks a valid installable APK identity
- **THEN** a regression check fails identifying the catalog
