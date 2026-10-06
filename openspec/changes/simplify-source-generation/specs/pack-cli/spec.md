## ADDED Requirements

### Requirement: The generate-source command writes a candidate catalog and its report

The system SHALL provide `pack generate-source <source>` for each generated
source. Each invocation SHALL run that source's discovery, write a candidate
catalog and a report under `.build/source-generation/<source>/`, and exit zero
when generation succeeds and nonzero when it fails. A failed invocation SHALL
leave no candidate catalog, so an earlier run's candidate is never offered as
current. The report SHALL be written on success and failure alike, unless its
output directory cannot be created, and SHALL record the source, its inputs, the error when generation failed, the
skipped listings each with its reason, including listed projects discovery
screened out for publishing no APK asset, and, on success, the entries added to
and removed from the committed catalog and the entries changed in place: an
entry the candidate keeps at a normalized URL the committed catalog holds whose
rendered bytes differ from the committed entry's, such as one with a new name. The command SHALL NOT write committed files, pack
outputs, git history or PRs, and SHALL keep no state between invocations.

#### Scenario: Unchanged source

- **WHEN** the upstream inputs produce the committed catalog
- **THEN** the command succeeds with a candidate byte-identical to the
  committed catalog and a report listing no additions, removals or changed
  entries

#### Scenario: An entry changes in place

- **WHEN** the upstream renames a project the committed catalog holds at the
  same normalized URL
- **THEN** the command succeeds and its report lists that entry as changed,
  not as removed and added

#### Scenario: A failed rerun follows success

- **WHEN** an invocation succeeds and the next one cannot read its discovery
  input
- **THEN** the second exits nonzero, its report records the error, and no
  candidate catalog remains under the build directory

#### Scenario: Skipped listings are reported

- **WHEN** a Quiver row names a forge generation cannot form a URL for
- **THEN** the command succeeds and its report lists that row as skipped

#### Scenario: Screened-out projects are reported

- **WHEN** a listed Quiver project that the committed catalog does not hold
  has an asset-name entry naming no APK asset
- **THEN** the command succeeds and its report lists that project as skipped
  for publishing no APK asset

## MODIFIED Requirements

### Requirement: The report command displays structural evidence and its freshness

The system SHALL implement `pack report` to display the available build and
verification reports as separate human-readable sections without network access
or file changes. It SHALL show recorded failures, the nonfatal findings
recorded by standalone verification and by the build's offline verdict, listed
in full, verification mode and observation time. One missing report SHALL be acceptable if the other can be
displayed. When both are missing, or an existing report is unreadable, malformed
or has an unsupported schema, the command SHALL exit nonzero with a useful
diagnostic. Successfully displaying a recorded failed operation SHALL exit zero.

Recorded verification evidence SHALL be labelled current or stale. It SHALL be
current only when every input fingerprint it records equals the current bytes of
that input, over the input set that "Structural verification evidence belongs to
an exact input snapshot" in pack-verification defines, composition policy
included, and its verifier identity equals the running verifier's; otherwise it
SHALL be labelled stale, including a supported schema with a different verifier
identity. A current local fingerprint SHALL NOT be described as proof of current
upstream health. What a stored report may contain is pack-verification's rule;
the display SHALL add no resolved version or live-health claim to it.

An unsupported build report schema, including a report without a schema field,
SHALL produce a regeneration diagnostic directing the user to `pack build`. An
unsupported verification report schema SHALL produce a regeneration diagnostic
directing the user to `pack verify`, rather than being interpreted as current
structural evidence, which is the reporting surface of the regeneration rule
pack-verification states.

Build reports SHALL also display family selections with their reasons, and every
non-blocking outcome the build report records: the apps added and removed since
the previous output, the denylist entries that excluded a candidate, the
denylist entries that matched no candidate, the package ids repeated within a
variant, the single-only coverage findings, the same-rank tie findings, the admitted generated candidates
with their committed ids and project URLs, the families with a selected entry left
without a category together with the variants concerned, and the stale
category assignments. A non-blocking outcome the build report records
SHALL NOT be withheld from display, a diagnostic kind the run recorded nothing in SHALL
contribute nothing to the output, and every recorded entry SHALL be listed in
full on each run rather than summarized, sampled or elided, so a long
diagnostics section is the expected steady state. A null candidate comparison
SHALL be displayed as unavailable, never as a build that added and removed
nothing, and a comparison recorded by a build whose status is failed SHALL be
displayed as candidates that were not published rather than as apps added and
removed since the previous output.

#### Scenario: Configuration changed after successful structural verification

- **WHEN** an overlay changes after the recorded run
- **THEN** `pack report` displays the recorded results as stale

#### Scenario: A report describes failure

- **WHEN** a valid available report records a failed build or failed verification
- **THEN** `pack report` displays its failure details and exits zero

#### Scenario: Verification recorded nonfatal findings

- **WHEN** a valid verification report or a build report's offline verdict
  records success with a single-only coverage finding and a repeated package id
- **THEN** `pack report` displays the successful status and each nonfatal
  finding with the variant, label, package id and project URL it records, and
  exits zero

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

#### Scenario: A build recorded non-blocking diagnostics

- **WHEN** a valid build report records apps added or removed, a denial that
  excluded a candidate, a denial that matched no candidate, a package id
  repeated within a variant, a single-only coverage finding, a same-rank tie
  finding, an admitted generated candidate, an uncategorized family, or a stale
  category assignment
- **THEN** `pack report` displays each of them with the variant, package id,
  families, reason, source, project URLs, tied selectors, chosen winner or
  committed id the report holds for it, displays the candidate
  comparison with each entry's package id and project URL identified as added
  or removed for its variant, and exits zero

#### Scenario: A build recorded no non-blocking diagnostics

- **WHEN** a valid build report records no candidate change, exclusion, stale
  exclusion, repeated package id, single-only coverage finding, same-rank tie
  finding, admission, uncategorized family or stale category assignment
- **THEN** `pack report` displays the build section without diagnostic output
  and exits zero

#### Scenario: Category lists are the only recorded diagnostics

- **WHEN** a valid build report records an uncategorized family or a stale
  category assignment and records no candidate change, exclusion, stale
  exclusion, repeated package id, single-only coverage finding, same-rank tie
  finding or admission
- **THEN** `pack report` displays each uncategorized family with its variants
  and each stale category map key, and exits zero

#### Scenario: A repeated package id is the only recorded diagnostic

- **WHEN** a valid build report records a package id repeated within a variant
  and no other non-blocking outcome
- **THEN** `pack report` displays the variant, the package id, and each
  entry's family and project URL, and exits zero

#### Scenario: A single-only coverage finding is the only recorded diagnostic

- **WHEN** a valid build report records a family selected in single without a
  dual build and no other non-blocking outcome
- **THEN** `pack report` displays the family with its single selection's
  package id and project URL, and exits zero

#### Scenario: A same-rank tie is the only recorded diagnostic

- **WHEN** a valid build report records a same-rank tie finding and no other
  non-blocking outcome
- **THEN** `pack report` displays the family, the variant, the tied selectors
  and the chosen winner, and exits zero

#### Scenario: The candidate comparison is unavailable

- **WHEN** a valid build report sets its candidate comparison to null because
  composition did not complete
- **THEN** `pack report` displays the comparison as unavailable rather than as a
  build that added and removed nothing

#### Scenario: Neither report exists

- **WHEN** neither a build report nor a verification report exists
- **THEN** `pack report` exits nonzero with a diagnostic saying so

#### Scenario: The verifier changed after verification

- **WHEN** a verification report with the current schema records a verifier
  identity other than the running verifier's
- **THEN** `pack report` displays the recorded results as stale

#### Scenario: A failed build recorded a candidate comparison

- **WHEN** a build report whose status is failed records a candidate comparison
- **THEN** `pack report` displays it as candidates that were not published, not
  as apps added and removed since the previous output

### Requirement: The build report records composition and source outcomes

The scheduled rebuild needs to explain a change or a failure without rerunning
the build. The system SHALL write a build report recording:

- the apps added and removed since the previous output, compared on package
  id and normalized project URL and each recorded with both;
- each family's per-target selection, with the winner's package id, project
  URL, source and origin, the other candidates considered
  and the selection reason;
- the candidate exclusions, each denial's under its denied project URL with
  the families it removed, and the denylist entries that matched no candidate
  and are therefore stale exclusions, each identified by its project URL;
- for each variant, every package id more than one selected entry carries,
  with those entries' families and project URLs;
- the single-only coverage findings: each family selected in single with no
  selected build in dual, with its single selection's package id and project
  URL;
- the same-rank tie findings: each family and variant whose winner was chosen
  among different candidates tied at the winning rank, with the tied
  candidates' selectors and the chosen winner;
- the families with a selected entry left without a category, each recorded
  with exactly the variants whose selected entry ended with an empty final
  category list, and the stale category assignments: the category map keys
  that set no selected entry's category, whether the key names no selected
  family or a family whose selected entries are all track-only;
- source ingestion failures.

Resolution-attempt diagnostics SHALL belong to source generation, not routine
build reports. Build reports SHALL identify the admitted generated candidates
of each generated source by their committed ids and project URLs, without
claiming that their projects were inspected. Conflicts and stale policy selectors SHALL be actionable.

The report SHALL be written on a successful build and on a failed one alike,
and a failed build's report SHALL record the stage that was running and the
error that stopped it. If composition has not completed, the report SHALL set
`changes` to null because no complete candidate output exists to compare;
this SHALL NOT be interpreted as an empty pack. The report SHALL preserve the
selections, denylist removals, stale exclusions and category lists collected
before a later failure, and the same-rank tie findings recorded during
selection. When composition fails before category assignment
runs, only the uncategorized families and stale category assignments, and the
later single-only coverage findings and repeated package ids, SHALL be
recorded empty, because those checks have not run, while stale exclusions and
other diagnostics collected before the failure SHALL remain preserved, and the
recorded failure and stage SHALL tell the reader that the check did not
complete. Once composition completes, the report SHALL compare its
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

- **WHEN** the selected build of a family moves to a different package id or
  project URL
- **THEN** the report lists the old entry as removed and the new one as added,
  and that family's selection names the new winner

#### Scenario: A family moves to another repository with the same package id

- **WHEN** the selected build of a family moves to another project URL whose
  build carries the same package id
- **THEN** the report lists the old entry as removed and the new one as added,
  each with that package id and its own project URL, and `pack report`
  displays both URLs so the two entries are distinguishable

#### Scenario: Committed generated entry is ingested

- **WHEN** a build admits an entry from a committed generated catalog
- **THEN** its source, committed id and project URL are available in build
  diagnostics without a claim that its project was inspected

#### Scenario: An app is left without a category

- **WHEN** a build's selected entry for a family ends category assignment with
  an empty final category list in one or more variants
- **THEN** the report lists that family as uncategorized with exactly those
  variants, and the build succeeds

#### Scenario: A track-only entry without source categories is not uncategorized

- **WHEN** a build selects an entry of a family the category map does not name,
  whose final settings carry `trackOnly: true` and whose source supplies no
  category
- **THEN** the entry carries Track Only and the report does not list its family
  as uncategorized

#### Scenario: A category map key sets no category

- **WHEN** the category map names a family that no variant selects, or a family
  whose selected entries are all track-only
- **THEN** the report lists that key as a stale category assignment

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

#### Scenario: A same-rank tie is resolved and recorded

- **WHEN** different candidates of one family tie at the winning rank for a
  target and no pin applies
- **THEN** the build succeeds and the report lists a same-rank tie finding
  identifying the family, target, tied selectors and chosen winner

#### Scenario: Family conflict stops composition

- **WHEN** composition fails on a pin that is missing, excluded,
  wrong-family, target-ineligible or one of several pins for one family and
  target
- **THEN** the report identifies the pin by its family and target
- **AND** the report preserves prior diagnostics

#### Scenario: A single-screen family has no dual build

- **WHEN** a build selects a family in single and no build of that family in
  dual
- **THEN** the build succeeds and the report lists that family as a
  single-only coverage finding with its single selection's package id and
  project URL

#### Scenario: A pack repeats a package id

- **WHEN** a build selects two entries carrying one package id in one variant
- **THEN** the build succeeds and the report lists that package id for that
  variant with both entries' families and project URLs

## REMOVED Requirements

### Requirement: The generate-source command builds the reviewed README source catalog

**Reason**: One generator serves every source and resolves nothing, so its report no longer carries policy, resolution, tracking or retention outcomes.

**Migration**: Replaced by "The generate-source command writes a candidate catalog and its report".

### Requirement: The generate-source command builds a reviewed Quiver candidate

**Reason**: One generator serves every source and resolves nothing, so its report no longer carries policy, resolution, tracking or retention outcomes.

**Migration**: Replaced by "The generate-source command writes a candidate catalog and its report".

