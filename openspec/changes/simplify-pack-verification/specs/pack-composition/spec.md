## MODIFIED Requirements

### Requirement: Selected build verification does not change composition

A selected build failing structural verification SHALL prevent publication
without causing composition to select another project or family alternative.
After successful source ingestion and building, publication eligibility SHALL NOT
depend on a separate lookup of the selected project's release metadata.
Unavailable release metadata SHALL NOT trigger reselection or block an otherwise
eligible candidate. Standard fallback SHALL occur when no eligible preferred
dual candidate remains after successful ingestion and deliberate exclusions,
unless a pin requires one. An entire source fetch failure SHALL still abort the
build. Existing configured release fallback within one selected project SHALL
remain separate and unchanged.

#### Scenario: Preferred dual project fails metadata verification

- **WHEN** a selected dual build fails structural verification and a standard candidate exists
- **THEN** publication fails and the previously published pair remains intact
- **AND** the pipeline does not replace the selected project with the standard candidate

#### Scenario: Selected project release metadata is unavailable after a successful build

- **WHEN** source ingestion, building, checks and fresh structural verification succeed but the selected project's release metadata is unavailable
- **THEN** the otherwise eligible candidate remains eligible for publication without a separate release metadata lookup
- **AND** the pipeline does not replace the selected project with a standard candidate or another family alternative

#### Scenario: Preferred build is absent from a valid source snapshot

- **WHEN** all source acquisition succeeds, no preferred candidate exists, and no pin requires one
- **THEN** dual selection uses an eligible ordinary candidate if available
