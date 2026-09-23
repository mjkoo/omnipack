## MODIFIED Requirements

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

#### Scenario: Resolved APK declares another package id

- **WHEN** an inspected APK declares a package id other than the id its upstream catalog uses
- **THEN** documentation records the original identity and the manifest-backed correction
- **AND** the maintained identity policy exports the manifest-backed id

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
