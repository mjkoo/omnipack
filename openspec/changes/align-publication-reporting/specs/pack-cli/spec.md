## MODIFIED Requirements

### Requirement: The report command displays structural evidence and its freshness

The system SHALL implement `pack report` to display the available build and
verification reports as separate human-readable sections without network access
or file changes. It SHALL show recorded failures, verification mode and
observation time. It SHALL compare verification input
fingerprints and verifier identity against the current files/configuration and
label nonmatching evidence stale. A current local fingerprint SHALL NOT be
described as proof of current upstream health.

One missing report SHALL be acceptable if the other can be displayed. When both
are missing, or an existing report is unreadable, malformed or has an unsupported
schema, the command SHALL exit nonzero with a useful diagnostic. Successfully
displaying a recorded failed operation SHALL exit zero. Build reports SHALL also
display family selections with their reasons, and every non-blocking outcome the
build report records: the apps added and removed since the previous output, the
denylist entries that excluded a candidate, the denylist entries that matched no
candidate, and the admitted codm2000 candidates with their committed identities.
A diagnostic the report records SHALL NOT be withheld from display, and a
category the run recorded nothing in SHALL contribute nothing to the output. The
recorded admissions and exclusions SHALL be listed in full on each run rather
than summarized, sampled or elided, so a long diagnostics section is the
expected steady state. A null candidate comparison SHALL be displayed as
unavailable, never as a build that added and removed nothing, and a comparison
recorded by a build whose status is failed SHALL be displayed as candidates that
were not published rather than as apps added and removed since the previous
output. The composition policy SHALL
participate in freshness checks. An unsupported build report schema, including a
report without a schema field, SHALL produce a regeneration diagnostic directing
the user to `pack build`. An unsupported verification report schema SHALL
produce a regeneration diagnostic directing the user to `pack verify`, rather
than being interpreted as current structural evidence, which is the reporting
surface of the regeneration rule pack-verification states. Reports SHALL describe
structural scope without resolved versions or live-health claims. A supported
schema with a different verifier identity SHALL be stale.

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

#### Scenario: A build recorded non-blocking diagnostics

- **WHEN** a valid build report records apps added or removed, a denial that
  excluded a candidate, a denial that matched no candidate, or an admitted
  codm2000 candidate
- **THEN** `pack report` displays each of them with the variant, package id,
  family, reason, source, project URL, entry kind or committed identity the
  report holds for it, displays the candidate comparison with each package id
  identified as added or removed for its variant, and exits zero

#### Scenario: A build recorded no non-blocking diagnostics

- **WHEN** a valid build report records no candidate change, exclusion, stale
  denial or admission
- **THEN** `pack report` displays the build section without diagnostic output
  and exits zero

#### Scenario: The candidate comparison is unavailable

- **WHEN** a valid build report sets its candidate comparison to null because
  composition did not complete
- **THEN** `pack report` displays the comparison as unavailable rather than as a
  build that added and removed nothing
