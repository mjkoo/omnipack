## MODIFIED Requirements

### Requirement: The build command produces both variants

The system SHALL provide a build command that ingests every source, composes
and renders both variants, generates the README catalog, verifies the rendered
pair and catalog offline, and publishes all three files only after verification
succeeds. Handwritten README content SHALL be preserved byte-for-byte. Missing
or malformed catalog markers SHALL fail the build. The
build SHALL NOT perform live verification. Network requests for upstream JSON catalogs SHALL remain part of building.
The codm2000 source SHALL be read from committed JSON; README scraping, APK
discovery and package-ID resolution SHALL NOT occur during building.

#### Scenario: Successful build

- **WHEN** the build command runs, every source is reachable, and the rendered
  pair passes offline verification
- **THEN** the single-screen and dual-screen import files and README catalog are written and the
  command exits successfully

#### Scenario: Offline verification rejects newly rendered output

- **WHEN** either newly rendered variant fails offline verification
- **THEN** neither distribution file nor the README is replaced, the command exits nonzero,
  and the build report identifies the offline verification stage and findings

### Requirement: The verify command performs structural checks only

The system SHALL implement `pack verify` to check both current distribution files,
local configuration and generated catalog offline without network requests.
The retired `--live` and `--probe-assets` flags SHALL be rejected as unsupported
arguments with nonzero exit before verification runs. The command SHALL record
structural evidence and exit zero only on a complete, error-free run. Report
write failure SHALL cause nonzero exit with a concise stderr diagnostic.
Verification SHALL NOT rebuild, resolve package IDs, alter distribution or
configuration files, or overwrite the build report.

#### Scenario: No build report is available

- **WHEN** the current exports, configuration and catalog pass local checks without a previous build report
- **THEN** `pack verify` succeeds and writes structural evidence without network access

#### Scenario: A retired flag is supplied

- **WHEN** either `--live` or `--probe-assets` is supplied, alone or together
- **THEN** argument parsing fails without network requests or replacement verification evidence

#### Scenario: Report persistence fails

- **WHEN** verification cannot write its report
- **THEN** it exits nonzero with a concise diagnostic

### Requirement: Build failure preserves published outputs without source mutation

Automation commits whatever the distribution directory holds, so a partially
written pack would be published. The system SHALL leave the existing output
files unchanged when a build fails at any stage, and SHALL exit with a
non-zero status. The two import files and README SHALL be published as a recoverable unit.
A handled failure during replacement SHALL restore every replaced file to its
previous bytes or absence. Successful replacement and recovery SHALL preserve
existing file permission modes; new outputs SHALL use normal file creation
permissions subject to the process umask. Before publication, a README changed
since capture SHALL cause failure without overwriting that edit. Recovery covers handled
exceptions, not process termination, runner loss or rollback storage failure. The build SHALL leave committed source catalogs unchanged on success and failure.

#### Scenario: Build fails after some output was rendered

- **WHEN** rendering succeeds for one variant and the build then fails
- **THEN** neither output file is modified and the command exits non-zero

#### Scenario: Build fails on the first run

- **WHEN** the build fails and no output files exist yet
- **THEN** no output files are created

#### Scenario: Build fails between replacing the two output files

- **WHEN** one import file has been replaced with its newly rendered contents
  and the build then fails before the other is replaced
- **THEN** both import files hold the contents they had before the build, and
  neither is present if the distribution directory held no output before it

#### Scenario: README replacement fails

- **WHEN** the JSON replacements succeed but replacing README fails
- **THEN** both JSON files are restored and README retains its previous bytes

#### Scenario: README is edited during building

- **WHEN** README differs from the bytes captured for catalog generation
- **THEN** publication fails before replacing outputs and preserves the edit

### Requirement: A separate command generates the README source catalog

The system SHALL provide `pack generate-source codm`. Each invocation SHALL
fetch the configured README, validate the reviewed project policy, resolve every
eligible project, and on success write a complete candidate catalog and a
diagnostic report under `.build/`. It SHALL NOT write committed source files,
pack outputs, git history or PRs, and it SHALL NOT persist resolution state
between invocations. It SHALL exit zero for successful generation and nonzero
for failed generation. The report SHALL identify unsupported links, inactive
project rules, effective policy, resolved APK IDs, successful track-only
resources, retained failures, unresolved projects and catalog changes relative
to the committed catalog. It SHALL NOT modify the reviewed project policy. A
complete catalog SHALL account for every eligible project as an APK or an
explicitly declared tracker; lack of an APK SHALL NOT imply permission to skip
or track it. The retired `--force` flag SHALL be rejected as an unsupported
argument. Only artifacts produced by the current invocation SHALL be offered as
its result.

#### Scenario: Unchanged source

- **WHEN** the README, the policy and every project's resolved identity match the committed catalog
- **THEN** the command succeeds with a candidate catalog byte-identical to the committed catalog

#### Scenario: Forced refresh

- **WHEN** `--force` is supplied
- **THEN** argument parsing fails before any network request, since every invocation already resolves every project

#### Scenario: Incomplete generation

- **WHEN** a new APK project cannot be resolved or a new declared tracker cannot be validated
- **THEN** the command fails with current diagnostics and offers no complete candidate for publication

#### Scenario: Policy update needs generation

- **WHEN** project policy changes while README bytes remain identical
- **THEN** the next invocation generates under the new policy

#### Scenario: Kanto needs no APK resolution

- **WHEN** Kanto's explicit track-only rule and permitted release validate
- **THEN** the report records a tracking resource with its synthetic ID, not a resolved Android package
