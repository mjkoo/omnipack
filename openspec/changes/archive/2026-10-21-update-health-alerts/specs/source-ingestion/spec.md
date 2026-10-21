# Spec Delta

## MODIFIED Requirements

### Requirement: Source fetches carry no credentials

Every upstream request the build and source generation make SHALL carry no
credentials, and the build and source generation SHALL keep no HTTP
credential configuration. The live check's GitHub API credential is outside
this rule: it follows the `pack check-live` requirement, which scopes the
`GITHUB_TOKEN` environment variable to GitHub API requests. Publication
operations are outside this rule: release, pull-request and branch-push
operations follow the publication credential rules of the workflows that make
them.

#### Scenario: A token is present in the environment

- **WHEN** `GITHUB_TOKEN` is set while a build or a source generation runs
- **THEN** no upstream request carries an Authorization header
