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
build SHALL NOT perform live verification. Existing ingestion network requests
and generated package-id discovery SHALL remain part of building.

#### Scenario: Successful build

- **WHEN** the build command runs, every source is reachable, and the rendered
  pair passes offline verification
- **THEN** the single-screen and dual-screen import files and README catalog are written and the
  command exits successfully

#### Scenario: Offline verification rejects newly rendered output

- **WHEN** either newly rendered variant fails offline verification
- **THEN** neither distribution file nor the README is replaced, the command exits nonzero,
  and the build report identifies the offline verification stage and findings

### Requirement: A failed build leaves previous output intact

Automation commits whatever the distribution directory holds, so a partially
written pack would be published. The system SHALL leave the existing output
files unchanged when a build fails at any stage, and SHALL exit with a
non-zero status. The two import files and README SHALL be published as a recoverable unit.
A handled failure during replacement SHALL restore every replaced file to its
previous bytes or absence. Before publication, a README changed since capture
SHALL cause failure without overwriting that edit. Recovery covers handled
exceptions, not process termination, runner loss or rollback storage failure. The resolved package id cache is exempt: a newly
resolved id SHALL be written to the cache as soon as it resolves, so that a
build failing later keeps the resolution work it already paid for.

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

#### Scenario: Build fails after resolving a new package id

- **WHEN** a build resolves a package id that was not previously cached and
  then fails before the output is written
- **THEN** the import files are unchanged and the cache retains the newly
  resolved id

#### Scenario: README replacement fails

- **WHEN** the JSON replacements succeed but replacing README fails
- **THEN** both JSON files are restored and README retains its previous bytes

#### Scenario: README is edited during building

- **WHEN** README differs from the bytes captured for catalog generation
- **THEN** publication fails before replacing outputs and preserves the edit

### Requirement: The build writes a report of what it did

The scheduled rebuild needs to explain a change or a failure without rerunning
the build. The system SHALL write a build report recording the apps added and
removed since the previous output, the families and package ids where candidates were displaced by
pins, device preference or source precedence, the candidate exclusions, and the
denylist entries that matched no candidate in scope and are therefore stale exclusions, the source rows that
were skipped or left unresolved, and every project that produced a generated
entry together with its resolved or reused package id. The report SHALL also
record each failed resolution attempt that retained a cached id. Listing a resolved
generated project is what lets a maintainer write a denylist entry for it,
since a project link names no package id of its own and a project that resolved
and was already in the previous output appears in none of the other lists.

The report SHALL additionally record each family's per-target winner and
alternatives, source/origin, original and effective identity, eligibility,
preference tier, fallback and selection reason. It SHALL distinguish family
coverage from package coverage, and family additions/removals from project or
package replacements. Conflicts and stale policy selectors SHALL be actionable.

Previous-output family classification SHALL use only committed historical
effective-id-and-normalized-URL mappings, without requiring a prior build report
or retaining obsolete active candidate rules. Current family membership SHALL
come from composition. A known previous family present in the current target
SHALL be retained, with package/project changes reported as transitions; a known
previous family absent now SHALL be removed. An unmapped previous entry SHALL
have unknown family history and SHALL NOT be assigned an inferred package family
or reported as a family removal. If any previous entries in a target are unmapped,
current families without a known previous match SHALL have unknown addition
status rather than definite additions or replacements. The report SHALL identify
unmapped keys and the missing-history reason while preserving known matches and
raw app/package diffs. Missing previous output SHALL mean all current families
are additions. Missing history SHALL NOT fail otherwise valid composition.

The report SHALL be written on a successful build and on a failed one alike,
and a failed build's report SHALL record the stage that was running and the
error that stopped it. If composition has not completed, the report SHALL set
`changes` to null because no complete candidate output exists to compare;
this SHALL NOT be interpreted as an empty pack. The report SHALL preserve
precedence displacements, denylist removals, and stale exclusions collected
before a composition failure. Once composition completes, the report SHALL
compare its candidate apps with the previous output even if a later stage fails.
The previous output a report compares against is the
contents of the import files as they stood before the build, so the system
SHALL read them before it replaces either import file; when a variant's import
file does not yet exist, every app in that variant SHALL be reported as added.
The report SHALL be written as a machine-readable JSON document to
`.build/report.json`, a path outside the distribution directory that is not
committed, so that a report differing between runs never makes an otherwise
unchanged rebuild look like a change.

#### Scenario: An app appears for the first time

- **WHEN** a build adds an app that the previous output did not contain
- **THEN** the report lists that app as added

#### Scenario: A generated project resolved its package id

- **WHEN** a build generates an entry for a project link and the project's
  package id resolves
- **THEN** the report lists that project together with the package id resolved
  for it, whether or not the previous output already contained that app

#### Scenario: A generated entry could not be resolved

- **WHEN** a project's package id could not be determined and no id is cached
- **THEN** the report lists that project as unresolved

#### Scenario: A failed resolution retains a cached generated entry

- **WHEN** a project's resolution attempt fails and a cached id is available
- **THEN** the report records the failure and lists the generated project with
  its retained cached package id

#### Scenario: The build fails before it writes output

- **WHEN** a build aborts because an upstream is unreachable
- **THEN** the report is still written and names the stage that was running and
  the error that stopped the build

#### Scenario: An early failure cannot compute output changes

- **WHEN** a build fails before composition completes and previous import files exist
- **THEN** the report sets `changes` to null instead of listing existing apps as removed
- **AND** the previous import files remain unchanged

#### Scenario: Composition diagnostics survive invalid overlays

- **WHEN** precedence and denylist processing collect diagnostics and an overlay
  subsequently fails validation
- **THEN** the failed report preserves the collected displacements, denylist removals,
  and stale exclusions, and sets `changes` to null

#### Scenario: The first build has no previous output

- **WHEN** a build runs and a variant's import file does not yet exist
- **THEN** the report lists every app in that variant as added and lists none
  as removed

#### Scenario: Report stays out of the distribution directory

- **WHEN** a build completes
- **THEN** the report is a JSON document at `.build/report.json` and no report
  file is written into the distribution directory

#### Scenario: Family stays while the package changes

- **WHEN** the selected build moves to another package in the same declared family
- **THEN** the report records the package transition and retained family separately

#### Scenario: Old candidate disappears in a fresh scheduled checkout

- **WHEN** previous import files contain an old package, its candidate has disappeared, its obsolete active rule has been removed, a historical mapping retains its family, and no prior build report exists
- **AND** composition selects a different package in that family for the same target
- **THEN** the report records a retained family and the old-to-new package transition without requiring the retired candidate or a prior report

#### Scenario: Previous entry has no historical mapping

- **WHEN** a previous entry has no historical mapping and a current family has no known previous match
- **THEN** the report identifies that entry as unknown family history and the current family as unknown addition status, without asserting a family removal, addition or replacement for them
- **AND** raw app/package changes remain available and missing history alone does not fail the build

#### Scenario: Family conflict stops composition

- **WHEN** selection fails on tied candidates or a package collision
- **THEN** the report identifies the family, target and conflicting selectors and preserves prior diagnostics

### Requirement: The build persists newly resolved package ids

The system SHALL write back each package id as it is resolved during a build,
together with the host-assigned identifier of the release it was resolved from,
rather than
only once the build succeeds, so that a later build can reuse it and can tell
whether the project has published a new release since.

#### Scenario: A new project is resolved

- **WHEN** a build resolves a package id that was not previously cached
- **THEN** the cache records that id, and the host-assigned identifier of the
  release it was resolved from, against the project URL after the build

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

### Requirement: The verify command inspects existing output

The system SHALL implement `pack verify` to check both current distribution
files and local configuration offline without network requests. It SHALL
implement `pack verify --live` to add metadata resolution and version checks only
after offline success, without download probes. `pack verify --live --probe-assets`
SHALL add explicit bounded reachability diagnostics. `--probe-assets` without
`--live` SHALL be rejected. All modes SHALL record verification evidence and exit zero only on a complete,
error-free run; warnings alone SHALL not fail the command. Report write failure
SHALL cause a nonzero exit with a concise stderr diagnostic. Verification SHALL
not rebuild, update package ids, alter distribution/configuration files or
overwrite the last build report.

#### Scenario: Offline verification is invoked without a build report

- **WHEN** both distribution files and the local configuration are valid but no
  build report exists
- **THEN** `pack verify` succeeds, records offline evidence and makes no network call

#### Scenario: Invalid output is passed to live verification

- **WHEN** `pack verify --live` finds malformed output
- **THEN** it reports offline errors, performs no live request and exits nonzero

#### Scenario: Live check has warnings only

- **WHEN** every entry resolves a version and any required eligible candidates,
  but some versions receive lint warnings
- **THEN** `pack verify --live` records the warnings and exits zero

#### Scenario: Routine live verification avoids asset traffic

- **WHEN** `pack verify --live` succeeds
- **THEN** no selected download is requested and the report identifies metadata-only
  mode without claiming reachability

#### Scenario: Asset diagnostics require explicit selection

- **WHEN** `pack verify --live --probe-assets` runs
- **THEN** selected download candidates are probed and evidence identifies
  `live-probe` mode separately from ordinary `live` mode

### Requirement: The report command displays available evidence and its freshness

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
displaying a recorded failed operation SHALL exit zero. The existing build-report
format without a schema field SHALL remain readable. New build reports SHALL
also display family selections, fallback reasons, identity transitions and
candidate conflicts. The composition policy SHALL participate in freshness
checks; evidence predating that input or the new verifier identity SHALL be stale.

#### Scenario: Configuration changed after successful live verification

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
