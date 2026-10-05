## ADDED Requirements

### Requirement: Curation records state their evidence and limits

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

A successful structural result SHALL NOT be described as proof of safe
identity, installation, re-import, or update behavior.

These are obligations on documentation, so document review, not an automated
test, checks the scenarios of this requirement.

When a pack's selection for a family moves to another publisher's build,
curation SHALL distinguish package identity from update compatibility. An
in-place upgrade claim SHALL be supported by dated observations of released APK
signing identity and Android version ordering; matching package IDs or
comparable-looking release tags SHALL NOT establish compatibility. Consumer
guidance SHALL state any required backup, save transfer or fresh-install
action, distinguish source inspection from tested device behavior, and identify
unresolved compatibility. While the save-preservation route for that family
remains unresolved, the move SHALL NOT be presented as a supported migration,
and durable curation documentation SHALL record the family, the dated
observations and the unresolved route. The pipeline SHALL NOT install,
uninstall or migrate apps as part of changing a pack's source selection.

#### Scenario: A structural pass is not an install claim

- **WHEN** both packs pass offline verification
- **THEN** curation documentation does not describe that result as proof that
  every entry installs, re-imports or updates correctly

#### Scenario: A curated entry needs user-supplied files

- **WHEN** a curated entry cannot run until the user supplies game files or installs a separate component
- **THEN** consumer documentation describes that step
- **AND** it does not claim the step was validated on a device unless it was

#### Scenario: Equal package IDs with incompatible signing

- **WHEN** selected replacement APKs share a package ID but lack compatible signing identity
- **THEN** guidance does not claim an in-place upgrade
- **AND** it describes the established save-preserving route, or states that the route is unresolved without presenting the move as a supported migration

#### Scenario: Release labels imply the wrong ordering

- **WHEN** replacement release tags appear newer but APK version codes do not support a normal upgrade
- **THEN** the curation record states the observed Android ordering and consumer guidance does not promise an ordinary upgrade

## MODIFIED Requirements

### Requirement: Upstream pack trackers are excluded from both packs

Both published variants SHALL exclude an upstream catalog's own pack-update
tracker entry through a maintained project denial, including after upstream
refreshes. The exclusion SHALL keep that upstream as an app catalog source,
with its attribution and provenance.

#### Scenario: Upstream refresh contains its pack tracker

- **WHEN** an upstream source's refreshed records include its own track-only pack tracker, and a maintained denial names that tracker's project URL
- **THEN** neither generated pack nor the generated README catalog includes that tracker
- **AND** the upstream's other eligible apps remain available to composition

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
Pruning an unwanted Quiver app uses the project deny list, as for any source.

#### Scenario: Upstream refresh changes a curated setting

- **WHEN** a source refresh changes a setting covered by a maintained override
- **THEN** composed and rendered output retains the intended curated value

#### Scenario: A designated curated extra stops winning single

- **WHEN** a curated extra's entry in `config/extras.json` is eligible for single and its family has no committed single pin, and a configuration change that composition accepts, such as a denial of that extra's project URL when no pin names it, leaves it without its family's single-screen selection
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

## REMOVED Requirements

### Requirement: Curation evidence states its limits

**Reason**: Curation evidence no longer corrects composition ids. Package-id corrections are no longer composition rules backed by recorded APK evidence; the owner fixes a wrong source id by hand with an overlay `id` patch when Obtainium shows a duplicate or an id error. Dated manifest evidence remains, as the package identities behind a maintained policy that the replacement requirement records.

**Migration**: Replaced by "Curation records state their evidence and limits".
