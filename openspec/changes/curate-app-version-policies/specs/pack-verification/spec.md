## MODIFIED Requirements

### Requirement: Version lint evaluates effective GitHub versions

The system SHALL warn when a successfully resolved GitHub effective version does
not match the documented numeric-shape heuristic: optional `v` or `V`, followed by either
a bare unsigned integer or at least two dot-separated numeric components. Only
the dotted form permits optional prerelease/build suffixes introduced by `-`
or `+` with ASCII letters, digits, dots or hyphens. The heuristic
SHALL match the entire value and SHALL NOT be described as a comparison with
the installed APK version. Track-only, disabled version detection and intentional
date versioning SHALL be recorded as distinct classifications without that warning.
Release-title or extraction-regex settings alone SHALL NOT suppress warnings.
Warnings SHALL NOT cause a nonzero verification result.

#### Scenario: A regex leaves a rolling tag unchanged

- **WHEN** extraction succeeds but the effective version is `continuous`
- **AND** numeric version detection is enabled without intentional date versioning
- **THEN** the report includes a version-format warning

#### Scenario: Effective version is numeric

- **WHEN** extraction turns a release title into `v1.2.3-beta1`
- **THEN** the effective version passes the numeric-shape lint
- **AND** the result does not claim agreement with Android versionName

#### Scenario: Single-component numeric versions are valid shapes

- **WHEN** effective versions are `4093`, `20250425`, or `v20250425` with
  standard version detection enabled
- **THEN** they pass the numeric-shape lint
- **AND** the result does not claim agreement with Android versionName

#### Scenario: Opaque identifiers still warn

- **WHEN** effective versions are `Android-Build4`, `2026-04-27`, or
  `XenDroid-0b11201` with standard version detection enabled and no date override
- **THEN** the report still includes a version-format warning

