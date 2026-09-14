# pack-cli Specification

## Purpose

The command-line surface through which the pack is built and inspected, both
by a person working on the configuration and by the automation that rebuilds
the pack on a schedule.

## Requirements

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

### Requirement: Build diagnostics include the offline verification verdict

The build report SHALL include an offline-verification section with status and
findings. Failure before this stage SHALL mark verification as not run. Failure
during verification SHALL preserve the existing build diagnostics and candidate
diff. Building SHALL NOT replace `.build/verify.json` or claim live health.

#### Scenario: Build fails before verification

- **WHEN** source ingestion fails
- **THEN** the build report identifies ingestion failure and verification as not run

#### Scenario: Build fails after successful verification

- **WHEN** offline verification passes and report writing or publication fails
- **THEN** the failure report retains the successful offline verdict and identifies
  the later failing stage

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

### Requirement: The report command displays structural evidence and its freshness

The system SHALL implement `pack report` to display the available build and
verification reports as separate human-readable sections without network access
or file changes. It SHALL show recorded failures, warnings, incomplete attempts,
verification mode and observation time. It SHALL compare verification input
fingerprints and verifier identity against the current files/configuration and
label nonmatching evidence stale. A current local fingerprint SHALL NOT be
described as proof of current upstream health.

One missing report SHALL be acceptable if the other can be displayed. When both
are missing, or an existing report is unreadable, malformed or has an unsupported
schema, the command SHALL exit nonzero with a useful diagnostic. Successfully
displaying a recorded failed operation SHALL exit zero. Build reports SHALL also
display family selections with their reasons. The composition policy SHALL
participate in freshness checks. An unsupported build report schema, including a
report without a schema field, SHALL produce a regeneration diagnostic directing
the user to `pack build`. Unsupported old verification schemas SHALL produce a
regeneration diagnostic directing the user to `pack verify`, rather than being
interpreted as current structural evidence. Reports SHALL describe structural
scope without resolved versions or live-health claims. A supported schema with a
different verifier identity SHALL be stale.

#### Scenario: Configuration changed after successful structural verification

- **WHEN** an overlay changes after the recorded run
- **THEN** `pack report` displays the recorded results as stale

#### Scenario: A report describes failure

- **WHEN** a valid available report records a failed build or failed verification
- **THEN** `pack report` displays its failure details and exits zero

#### Scenario: Only a build report exists

- **WHEN** a valid build report exists and no verification report exists
- **THEN** the report command displays the build and says standalone verification
  has not been recorded, without treating it as a successful verification

#### Scenario: Only composition policy changed

- **WHEN** config/composition.json changes while both pack files remain identical
- **THEN** recorded verification is displayed as stale

#### Scenario: Build report predates the current format

- **WHEN** `.build/report.json` has no schema field or an older schema
- **THEN** `pack report` exits nonzero and directs the user to regenerate it with `pack build`

### Requirement: A failed build leaves published outputs unchanged

Automation commits whatever the distribution directory holds, so a partially
written pack would be published. The system SHALL leave the existing output
files unchanged when a build fails at any stage, and SHALL exit with a
non-zero status. The two import files and README SHALL be published as a
recoverable unit. A handled failure during replacement SHALL restore every
replaced file to its previous bytes or absence. Successful replacement and
recovery SHALL preserve existing file permission modes; new outputs SHALL use
normal file creation permissions subject to the process umask. The handwritten
README content published SHALL be the content the build read when it started.
Recovery covers handled exceptions, not process termination, runner loss or
rollback storage failure. The build SHALL leave committed source catalogs
unchanged on success and failure.

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

### Requirement: The build report records composition and source outcomes

The scheduled rebuild needs to explain a change or a failure without rerunning
the build. The system SHALL write a build report recording:

- the apps added and removed since the previous output;
- each family's per-target selection, with the winner's original and effective
  package ids, project URL, source and origin, the other candidates considered
  and the selection reason;
- the candidate exclusions, and the denylist entries that matched no candidate
  and are therefore stale exclusions;
- source ingestion failures.

Resolution-attempt diagnostics SHALL belong to source generation, not routine
build reports. Build reports SHALL identify admitted codm2000 candidates and
their committed identities, distinguishing APK package IDs from track-only
resource IDs, without claiming that they were freshly resolved or their
releases checked. Conflicts and stale policy selectors SHALL be actionable.

The report SHALL be written on a successful build and on a failed one alike,
and a failed build's report SHALL record the stage that was running and the
error that stopped it. If composition has not completed, the report SHALL set
`changes` to null because no complete candidate output exists to compare;
this SHALL NOT be interpreted as an empty pack. The report SHALL preserve the
selections, denylist removals and stale exclusions collected before a
composition failure. Once composition completes, the report SHALL compare its
candidate apps with the previous output even if a later stage fails. The
previous output a report compares against is the contents of the import files
as they stood before the build, so the system SHALL read them before it
replaces either import file; when a variant's import file does not yet exist,
every app in that variant SHALL be reported as added. The report SHALL be
written as a machine-readable JSON document to `.build/report.json`, a path
outside the distribution directory that is not committed, so that a report
differing between runs never makes an otherwise unchanged rebuild look like a
change.

#### Scenario: An app appears for the first time

- **WHEN** a build adds an app that the previous output did not contain
- **THEN** the report lists that app as added

#### Scenario: A family switches to another package

- **WHEN** the selected build of a family moves to a different package id
- **THEN** the report lists the old package as removed and the new one as added,
  and that family's selection names the new winner

#### Scenario: Committed generated entry is ingested

- **WHEN** a build admits an entry from the committed codm2000 catalog
- **THEN** its source, entry kind and committed package or resource ID are available in build diagnostics without a fresh-resolution claim

#### Scenario: The build fails before it writes output

- **WHEN** a build aborts because an upstream is unreachable
- **THEN** the report is still written and names the stage that was running and
  the error that stopped the build

#### Scenario: An early failure cannot compute output changes

- **WHEN** a build fails before composition completes and previous import files exist
- **THEN** the report sets `changes` to null instead of listing existing apps as removed
- **AND** the previous import files remain unchanged

#### Scenario: Composition diagnostics survive invalid overlays

- **WHEN** selection and denylist processing collect diagnostics and an overlay
  subsequently fails validation
- **THEN** the failed report preserves the collected selections, denylist removals,
  and stale exclusions, and sets `changes` to null

#### Scenario: The first build has no previous output

- **WHEN** a build runs and a variant's import file does not yet exist
- **THEN** the report lists every app in that variant as added and lists none
  as removed

#### Scenario: Report stays out of the distribution directory

- **WHEN** a build completes
- **THEN** the report is a JSON document at `.build/report.json` and no report
  file is written into the distribution directory

#### Scenario: Family conflict stops composition

- **WHEN** selection fails on tied candidates or a package collision
- **THEN** the report identifies the family, target and conflicting selectors and preserves prior diagnostics

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
