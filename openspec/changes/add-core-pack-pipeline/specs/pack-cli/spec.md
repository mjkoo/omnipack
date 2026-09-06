## Purpose

The command-line surface through which the pack is built and inspected, both
by a person working on the configuration and by the automation that rebuilds
the pack on a schedule.

## ADDED Requirements

### Requirement: The build command produces both variants

The system SHALL provide a build command that ingests every source, composes
and renders both variants, and writes them to the distribution directory.

#### Scenario: Successful build

- **WHEN** the build command runs and every source is reachable
- **THEN** the single-screen and dual-screen import files are written and the
  command exits successfully

### Requirement: A failed build leaves previous output intact

Automation commits whatever the distribution directory holds, so a partially
written pack would be published. The system SHALL leave the existing output
files unchanged when a build fails at any stage, and SHALL exit with a
non-zero status. The two import files SHALL be published as a unit, so that a
failure while the second file is being replaced leaves both files at the
contents they had before the build, or leaves neither file present when the
distribution directory held no output before the build. This guarantee covers
the two import files only. The resolved package id cache is exempt: a newly
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

### Requirement: The build writes a report of what it did

The scheduled rebuild needs to explain a change or a failure without rerunning
the build. The system SHALL write a build report recording the apps added and
removed since the previous output, the ids where a candidate was displaced by
precedence, the denylist removals, the denylist entries that matched no
composed entry and are therefore stale exclusions, the source rows that
were skipped or left unresolved, and every project that produced a generated
entry together with its resolved or reused package id. The report SHALL also
record each failed resolution attempt that retained a cached id. Listing a resolved
generated project is what lets a maintainer write a denylist entry for it,
since a project link names no package id of its own and a project that resolved
and was already in the previous output appears in none of the other lists.

The report SHALL be written on a successful build and on a failed one alike,
and a failed build's report SHALL record the stage that was running and the
error that stopped it. The previous output a report compares against is the
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

#### Scenario: The first build has no previous output

- **WHEN** a build runs and a variant's import file does not yet exist
- **THEN** the report lists every app in that variant as added and lists none
  as removed

#### Scenario: Report stays out of the distribution directory

- **WHEN** a build completes
- **THEN** the report is a JSON document at `.build/report.json` and no report
  file is written into the distribution directory

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
