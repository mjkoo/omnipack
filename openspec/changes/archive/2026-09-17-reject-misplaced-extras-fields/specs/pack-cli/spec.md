## ADDED Requirements

### Requirement: The verify command runs offline structural checks only

The system SHALL implement `pack verify` to check both current distribution files,
local configuration and generated catalog offline without network requests.
An unsupported argument SHALL fail argument parsing with nonzero exit before
verification runs. The command SHALL record
structural evidence and exit zero only on a complete, error-free run. Report
write failure SHALL cause nonzero exit with a concise stderr diagnostic.
Verification SHALL NOT rebuild, resolve package IDs, alter distribution or
configuration files, or overwrite the build report.

#### Scenario: No build report is available

- **WHEN** the current exports, configuration and catalog pass local checks without a previous build report
- **THEN** `pack verify` succeeds and writes structural evidence without network access

#### Scenario: An unsupported argument is supplied

- **WHEN** `pack verify` is invoked with a flag it does not define
- **THEN** argument parsing fails with nonzero exit without network requests or replacement verification evidence

#### Scenario: Report persistence fails

- **WHEN** verification cannot write its report
- **THEN** it exits nonzero with a concise diagnostic

### Requirement: The generate-source command builds the reviewed README source catalog

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
or track it. Only artifacts produced by the current invocation SHALL be offered
as its result.

#### Scenario: Unchanged source

- **WHEN** the README, the policy and every project's resolved identity match the committed catalog
- **THEN** the command succeeds with a candidate catalog byte-identical to the committed catalog

#### Scenario: Incomplete generation

- **WHEN** a new APK project cannot be resolved or a new declared tracker cannot be validated
- **THEN** the command fails with current diagnostics and offers no complete candidate for publication

#### Scenario: Policy update needs generation

- **WHEN** project policy changes while README bytes remain identical
- **THEN** the next invocation generates under the new policy

#### Scenario: A track-only rule needs no APK resolution

- **WHEN** a project's explicit track-only rule and its permitted release validate
- **THEN** the report records a tracking resource with its synthetic ID, not a resolved Android package

## MODIFIED Requirements

### Requirement: The report command displays structural evidence and its freshness

The system SHALL implement `pack report` to display the available build and
verification reports as separate human-readable sections without network access
or file changes. It SHALL show recorded failures, warnings, incomplete attempts,
verification mode and observation time. It SHALL compare verification input
fingerprints and verifier identity against the current files/configuration and
label nonmatching evidence stale. A current local fingerprint SHALL NOT be
described as proof of current upstream health.

One missing report SHALL be acceptable if the other can be displayed. When both
are missing, or an existing report is unreadable, malformed or has an unsupported
schema, the command SHALL exit nonzero with a useful diagnostic. Successfully
displaying a recorded failed operation SHALL exit zero. Build reports SHALL also
display family selections with their reasons. The composition policy SHALL
participate in freshness checks. An unsupported build report schema, including a
report without a schema field, SHALL produce a regeneration diagnostic directing
the user to `pack build`. An unsupported verification report schema SHALL
produce a regeneration diagnostic directing the user to `pack verify`, rather
than being interpreted as current structural evidence. Reports SHALL describe
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

## REMOVED Requirements

### Requirement: The verify command performs structural checks only

**Reason**: Replaced by "The verify command runs offline structural checks only", which keeps every verify command rule and states rejection of unsupported arguments generically instead of naming the retired `--live` and `--probe-assets` flags.

**Migration**: None. Those flags are still rejected as unsupported arguments; run `pack verify` without them.

### Requirement: A separate command generates the reviewed README source catalog

**Reason**: Replaced by "The generate-source command builds the reviewed README source catalog", which keeps every generation rule and drops the rejection of the retired `--force` flag and its scenario, since every invocation already resolves every project.

**Migration**: None. Argument parsing still rejects `--force` as an unsupported argument; run `pack generate-source codm` without it.
