## ADDED Requirements

### Requirement: A separate command generates the reviewed README source catalog

The system SHALL provide `pack generate-source codm`. Each invocation SHALL
fetch the configured README, validate the reviewed project policy, resolve every
eligible project, and on success write a complete candidate catalog and a
diagnostic report under `.build/`. It SHALL NOT write committed source files,
pack outputs, git history or PRs, and it SHALL NOT persist resolution state
between invocations. It SHALL exit zero for successful generation and nonzero
for failed generation. The report SHALL identify unsupported links, inactive
project rules, effective policy, resolved APK IDs, successful track-only
resources, retained failures, unresolved projects and catalog changes relative
to the committed catalog. It SHALL NOT modify the reviewed project policy. A
complete catalog SHALL account for every eligible project as an APK or an
explicitly declared tracker; lack of an APK SHALL NOT imply permission to skip
or track it. The retired `--force` flag SHALL be rejected as an unsupported
argument. Only artifacts produced by the current invocation SHALL be offered as
its result.

#### Scenario: Unchanged source

- **WHEN** the README, the policy and every project's resolved identity match the committed catalog
- **THEN** the command succeeds with a candidate catalog byte-identical to the committed catalog

#### Scenario: Forced refresh

- **WHEN** `--force` is supplied
- **THEN** argument parsing fails before any network request, since every invocation already resolves every project

#### Scenario: Incomplete generation

- **WHEN** a new APK project cannot be resolved or a new declared tracker cannot be validated
- **THEN** the command fails with current diagnostics and offers no complete candidate for publication

#### Scenario: Policy update needs generation

- **WHEN** project policy changes while README bytes remain identical
- **THEN** the next invocation generates under the new policy

#### Scenario: A track-only rule needs no APK resolution

- **WHEN** a project's explicit track-only rule and its permitted release validate
- **THEN** the report records a tracking resource with its synthetic ID, not a resolved Android package

## REMOVED Requirements

### Requirement: A separate command generates the README source catalog

**Reason**: Replaced by "A separate command generates the reviewed README
source catalog", which is identical except that its track-only scenario no
longer names a specific project.

**Migration**: None. The command's behavior is unchanged, apart from the
generated track-only description wording that readme-source-generation
states.
