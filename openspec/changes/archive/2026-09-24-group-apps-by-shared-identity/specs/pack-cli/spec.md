## MODIFIED Requirements

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

- **WHEN** composition fails on tied candidates, on two explicit families joined through shared identity, or on a family whose selected entries do not pair
- **THEN** for tied candidates the report identifies the family, target and conflicting selectors; for joined explicit families it identifies both families and the joining candidates, with no target; for entries that do not pair it identifies the family and both entries
- **AND** in each case the report preserves prior diagnostics
