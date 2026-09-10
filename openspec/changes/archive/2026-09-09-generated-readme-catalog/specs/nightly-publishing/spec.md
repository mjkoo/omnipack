## MODIFIED Requirements

### Requirement: Publish only the verified output and cache

The publisher SHALL limit commits to `dist/single-screen.json`,
`dist/dual-screen.json`, `README.md`, and `config/package-ids.json`.
README changes SHALL be restricted to the interior of exactly one valid catalog
marker pair; prefix and suffix bytes, including markers, SHALL match the selected
base revision. This restriction SHALL be rechecked at candidate capture and
when staging finishes. It SHALL reject missing
candidate files, symlink replacements, unexpected tracked modifications, and
changes to candidate bytes after verification. Both packs, the README and the cache SHALL
be published in one commit when any allowed bytes differ from the base.
Unchanged files need not appear in the commit diff. Reports and transient
caches SHALL NOT be committed. A byte-identical candidate SHALL create no commit, even if file modes changed.
Publication SHALL preserve base file modes. The publisher SHALL recheck the
full tracked-change allowlist when staging finishes.

Publication SHALL use a conventional commit identifying the UTC date, run, and
base revision, and a normal fast-forward push to main. It SHALL NOT force-push
or alter repository protection settings to bypass a rejection.

#### Scenario: Pack and cache changes

- **WHEN** the verified candidate changes an output and the package-id cache
- **THEN** one commit publishes their verified bytes and no unrelated files

#### Scenario: Cache-only refresh

- **WHEN** both packs are unchanged but the verified package-id cache differs
- **THEN** one commit preserves the cache change

#### Scenario: Successful no-op

- **WHEN** all allowed bytes match the base and main is confirmed unchanged
- **THEN** the run records a successful no-op without creating a commit

#### Scenario: Unexpected mutation

- **WHEN** an unrelated tracked file changes or verified candidate bytes change
  before staging completes
- **THEN** publication is rejected

#### Scenario: Generated catalog refresh

- **WHEN** verified generated catalog bytes differ from the base
- **THEN** the README change is published with any changed packs and cache in one commit

#### Scenario: Handwritten README mutation

- **WHEN** a candidate changes README content outside the generated section
- **THEN** publication fails even if standalone verification succeeds
