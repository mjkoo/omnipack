# Spec Delta

## MODIFIED Requirements

### Requirement: Bucket credentials reach only the archive job

The bucket endpoint, bucket name and access keys SHALL come from the
secrets of a deployment environment that only the archive job uses. No job
other than the archive job SHALL receive them. The archive job SHALL hold
read-only repository contents access, SHALL NOT persist a checkout credential,
SHALL use no caches and SHALL pin every action by commit SHA. The job that holds
the secrets SHALL install only the project and the `archive` dependency group.

#### Scenario: Publishing runs without the bucket credential

- **WHEN** a nightly publishing job runs
- **THEN** none of the archive secrets is available to it
