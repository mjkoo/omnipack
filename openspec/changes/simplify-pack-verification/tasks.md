## 1. Structural verification and evidence

- [x] 1.1 Retain pure serialized-pair, local composition, settings and catalog validation while removing live dispatch and both retired CLI flags; verify valid outputs pass with network access forbidden, missing HTTP config is irrelevant, and retired flags fail before report writes.
- [x] 1.2 Implement structural schema 2, updated verifier identity and fingerprints limited to structural inputs; verify exact-input freshness, independent errors, interrupted records, atomic completion and report-write failure behavior.
- [x] 1.3 Adapt report parsing and formatting to structural evidence and explicit old-schema regeneration diagnostics; verify stale supported reports, unsupported historical verification reports, missing reports and recorded failures while preserving build-report behavior.

## 2. Publication consumers

- [x] 2.1 Replace the post-build live command and evidence checks with fresh structural verification in each selected revision's runtime; verify obsolete, missing, incomplete, stale and changed-byte candidates are rejected and valid candidates retain publication/no-op behavior.
- [x] 2.2 Preserve the tracker bootstrap prerequisite with existing release discovery before main publication, separate from pack verification; verify missing or unowned seed prevents main/release writes, offline verification does not query releases, and synchronization retains its ownership/digest checks.
- [x] 2.3 Update summaries and fallback reporting to distinguish pre-build checks from candidate structural evidence; verify handled failures, uncertainty, cleanup, issue and artifact outcomes remain accurate without retired live fields.
- [x] 2.4 Verify selected-build structural failure blocks publication without reselection, while unavailable app release metadata after successful ingestion and building neither blocks an otherwise eligible candidate nor selects a standard alternative; retain coverage for source-fetch failure, deliberate ordinary fallback, pin constraints and configured release fallback within a selected project.

## 3. Remove compatibility implementation and preserve curation

- [x] 3.1 Convert resolver-dependent curation tests into fixture-driven composition/render assertions for maintained identities, variants and override values; verify upstream changes cannot overwrite curated settings and fixture output bytes remain unchanged.
- [x] 3.2 Delete live.py, live_http.py, resolution/ and tests exclusively covering retired guarantees; verify no remaining runtime or test imports depend on them and no test-only resolver replacement was introduced.
- [x] 3.3 Remove unused verification-only HTTP helpers and cache/probe code after auditing callers; verify source ingestion, package-ID discovery and shared credential/redirect protections retain their existing tests and behavior.

## 4. Documentation and integrated validation

- [x] 4.1 Update current development, verification, publishing, curation and version-detection guidance for structural scope, removed flags and old-report regeneration; verify active instructions no longer require live verification while dated evidence, archived changes and protected review records remain intact.
- [x] 4.2 Run required project checks, the retained suite, structural verification and publication boundary tests; record results and implementation/test line reductions, and verify no export/configuration changes or external publication writes occurred.
- [x] 4.3 Verify and synchronize the reviewed spec deltas through the project workflow, updating the main verification Purpose to structural guarantees at synchronization; validate specs and check that current requirements no longer promise automated live app resolution.
