## MODIFIED Requirements

### Requirement: Scheduled and manual refreshes use main

The system SHALL offer a daily refresh at 03:00 in America/New_York, following daylight saving time, and a manual workflow dispatch using the same publication policy. Write-capable refreshes SHALL run only for main in the canonical repository. The system SHALL serialize active publishers without canceling an executing publisher for a newer run. Each run SHALL have a 60-minute execution limit. Scheduling SHALL NOT promise exact delivery time or that every queued trigger executes.

#### Scenario: Nightly or manual refresh

- **WHEN** an eligible scheduled or manual run starts
- **THEN** it selects the current main revision and follows the same refresh gates

#### Scenario: Ineligible invocation

- **WHEN** the workflow is dispatched from another ref or runs in a fork
- **THEN** it skips publication and issue writes

#### Scenario: Overlapping triggers

- **WHEN** another refresh is triggered while a publisher is executing
- **THEN** the new trigger does not execute concurrently with or cancel that publisher

#### Scenario: Eastern time changes seasonally

- **WHEN** America/New_York changes between standard and daylight saving time
- **THEN** the daily scheduled local time remains 03:00
