## MODIFIED Requirements

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

#### Scenario: Family conflict stops composition

- **WHEN** selection fails on tied candidates or a package collision
- **THEN** the report identifies the family, target and conflicting selectors and preserves prior diagnostics

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
