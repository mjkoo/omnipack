## ADDED Requirements

### Requirement: The generate-source command builds a reviewed Quiver candidate

The system SHALL provide `pack generate-source quiver`, applying the Quiver
source-generation contract and writing its current candidate and diagnostic
report under `.build/source-generation/quiver/`. It SHALL exit zero only for
complete successful generation, including reported unchanged-entry retention,
and nonzero otherwise. Failed invocations SHALL offer no current candidate.
It SHALL leave committed source data, policy, packs, README and git history
unchanged and SHALL perform no PR operations. The report SHALL identify source
coverage, skipped rows, unsupported rows, no-release/no-APK skips,
unavailable-repository skips, resolved identities, retained failures,
unresolved projects and proposed catalog changes.
Reports SHALL distinguish unavailable results from successful empty outcomes.
This command SHALL NOT change `pack generate-source codm` semantics.

#### Scenario: Generation produces a new candidate

- **WHEN** Quiver generation succeeds with a new APK project
- **THEN** the candidate and report appear under its build directory and committed inputs and published outputs remain unchanged

#### Scenario: A failed rerun follows success

- **WHEN** the next invocation cannot complete discovery
- **THEN** it exits nonzero with current failure diagnostics and does not offer the earlier candidate as current output
