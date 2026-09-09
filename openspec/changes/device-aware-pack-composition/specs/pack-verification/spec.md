## MODIFIED Requirements

### Requirement: Offline verification checks local composition constraints

The system SHALL validate the composition policy, denylist and build-bound
overlays without fetching source catalogs. It SHALL interpret rendered families
using effective id and normalized project URL projections from the policy,
falling back to package families where no rule applies. Ambiguous projections,
invalid configuration and forbidden overlay fields SHALL fail.

It SHALL reject duplicate selected families within a variant, a denied package
or family remaining in scope, violations of projected eligibility or candidate
pins, stale id-and-URL overlay targets, and single families absent from dual
without the explicit composition exemptions. A common patch matching either
variant SHALL be valid; stale exclusions SHALL remain nonfatal. A different
package in the same declared family SHALL satisfy coverage. Unique output package
ids SHALL still be required independently.

These checks SHALL NOT claim to verify source provenance, optimal winner ranking,
rule presence in unfetched catalogs or actual patch values. Those candidate-level
checks remain build responsibilities. Offline verification SHALL not rewrite
outputs or require previous build reports to interpret family coverage.

#### Scenario: Dual-only overlay has no target

- **WHEN** the named id-and-URL pair exists only in single
- **THEN** verification reports a stale dual overlay

#### Scenario: An explicit exclusion permits different coverage

- **WHEN** a single family's dual output is absent and its family or single winner's package is denied for dual
- **THEN** coverage passes even if the denial removed no candidate

#### Scenario: Different-package family replacement is present

- **WHEN** policy maps single and dual output entries with different ids to one family
- **THEN** offline coverage passes without requiring the single package in dual

#### Scenario: Pinned output is another repository

- **WHEN** the rendered family winner differs from the pin's effective id-and-URL projection
- **THEN** offline verification fails with the family and target identified

#### Scenario: Absent losing candidate cannot be assessed offline

- **WHEN** a policy selector refers to a candidate not represented in the outputs
- **THEN** offline verification does not claim whether that source candidate exists
- **AND** build must still enforce selector presence against fetched candidates

### Requirement: Verification evidence belongs to an exact input snapshot

Standalone verification SHALL write `.build/verify.json` separately from the
build report. It SHALL include schema and verifier versions, the compatibility
baseline, mode (`offline`, `live`, or `live-probe`), observation times, completion
and status, input fingerprints,
errors, warnings, and per-variant entry results with resolution and probe evidence.
Fingerprints SHALL cover exact bytes of both output files, the denylist, both
overlays, composition policy, pack settings and HTTP configuration, identifying missing/unreadable
inputs explicitly and excluding token values. Input changes during a run SHALL
prevent a successful result for the current files.

The system SHALL write an incomplete running record before live requests and
atomically replace it on completion, including failed completion. Offline errors
SHALL prevent live requests. After offline success, independent live failures
SHALL be collected across both variants instead of stopping at the first entry.
Equivalent resolution inputs SHALL share requests within a run, but each variant
and id SHALL retain its own result. HTML resolution identity SHALL preserve the
exact configured request URL, including scheme, authority, path, trailing slash
and query, unless request equivalence is established; project URL normalization
SHALL NOT establish this equivalence. Success SHALL require completion and no
errors, regardless of any cached package id or prior verification report.

#### Scenario: Same package id has different variant settings

- **WHEN** single-screen and dual-screen entries share an id but differ in URL or
  resolution settings
- **THEN** each is resolved with its own configuration and reported separately

#### Scenario: Trailing-slash HTML endpoints have different results

- **WHEN** two HTML entries have identical settings and configured URLs differing
  only by a trailing slash, but the endpoints serve different versions and
  relative download links
- **THEN** each entry resolves its own version and download URL using its own
  final response URL as the relative base
- **AND** project-normalized URL equality does not permit sharing their results

#### Scenario: A live attempt is interrupted

- **WHEN** verification stops after writing its running record but before completion
- **THEN** the stored report is incomplete and cannot be presented as a success

#### Scenario: A second entry fails independently

- **WHEN** two entries fail at different live stages after offline validation passes
- **THEN** the completed report contains both failures and the run fails

#### Scenario: Policy changes during verification

- **WHEN** the composition policy bytes change during a run
- **THEN** the result cannot be successful for the current input snapshot

#### Scenario: Old evidence lacks composition policy

- **WHEN** recorded evidence predates the policy fingerprint or current verifier identity
- **THEN** it is stale rather than proof that current family constraints passed
