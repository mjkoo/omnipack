# Structural verification validation

Validation date: 2026-09-10 UTC, macOS aarch64, Python 3.14.7.
These are local automated checks and controlled publication tests, not device
acceptance or an operational publication run.

## Results

`just check-all` passed, including lock validation, Ruff formatting/lint, Ty,
dependency audit, Python sdist/wheel builds, all 639 retained tests, structural
verification, workflow lint, Nix formatting and host flake checks. The test run
completed in 30.61 seconds with 92% package coverage. The dependency audit found
no known vulnerabilities or adverse project statuses in 10 packages.

Workflow lint reported no findings using zizmor's default offline mode. Nix
reported the expected uncommitted-tree notice and omitted incompatible systems;
the flake checks ran for aarch64-darwin. This does not claim Linux or device
acceptance.

The standalone verification report used schema 2, verifier 1.0.0 with structural
scope, and offline mode. It completed successfully with no errors from
23:53:06.695322 to 23:53:06.727122 UTC. Both reports and fingerprints are local
observations, not evidence of current app release availability.

All nine main specs passed `openspec validate --specs`; the change artifacts
passed strict validation. The six affected capabilities now describe structural
verification, report regeneration, publication evidence, preserved curation and
the separate release-seed prerequisite.

## Behavioral evidence

- [Verification tests](../tests/test_verify.py) and
  [CLI integration tests](../tests/test_verification_integration.py) cover exact
  fingerprints, HTTP-configuration independence, interrupted evidence, retired
  flag rejection and report-write failures.
- [Report tests](../tests/test_report.py) cover unsupported-schema regeneration,
  current/stale evidence and retained build-report behavior.
- [Publication tests](../tests/test_nightly_publish.py) run real fixture ingestion,
  composition, build and verification. A preferred dual candidate remains selected
  with its standard alternative present. Structural failure blocks publication;
  successful candidates need no post-build app HTTP requests. Both configured
  release-fallback values survive in exact candidate bytes.
- [Git publication tests](../tests/test_nightly_git.py) cover seed ownership before
  writes, selected-revision evidence, byte boundaries, no-op and recovery.
  [Reporting tests](../tests/test_nightly_reporting.py) distinguish retained
  pre-build evidence from successful and failed candidate evidence.
- [Curation tests](../tests/test_curation.py) and
  [reconciliation tests](../tests/test_reconciliation_curation.py) preserve fixture
  render hashes and explicit policies through source refreshes. Shared
  [HTTP](../tests/test_http.py), [source](../tests/test_sources.py) and
  [package-ID](../tests/test_package_id.py) behavior remains covered.

## Preservation and size

All 54 tracked export, configuration and fixture files matched their pre-change
SHA-256 hashes. The curated fixture map and both reconciliation render hashes
also matched exactly. All 537 protected review records were unchanged. Historical
validation results and archived changes remain intact; the old verification
validation page only gains a notice identifying its retired contract.

Python physical lines, counting `src/` plus `scripts/` as implementation and
`tests/` separately, changed from 9,760 to 7,467 implementation lines and from
14,613 to 10,890 test lines: reductions of 2,293 and 3,723. Tests decreased from
999 to 639 because live-resolution guarantees were retired, not replaced.

No export/configuration changes or external publication writes occurred. Live
app resolution, asset probing and effective-version lint are no longer automated;
Obtainium behavior and dated APK observations remain separate from structural
validation.
