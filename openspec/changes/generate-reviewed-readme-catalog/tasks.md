## 1. Capture migration evidence and source boundaries

- [ ] 1.1 Inventory eligible README table projects, previously admitted generated candidates and higher-source coverage using captured inputs; record an explicit mapping to existing package-ID cache entries and confirm the baseline pack bytes and family winners are reproducible.
- [ ] 1.2 Define the accepted catalog/metadata/resolution-state fixtures and candidate output layout; verify fixtures cover a new project, accepted fallback, covered dual project, single-only coverage, removal and conflicting package IDs without modifying protected historical evidence.

## 2. Implement automatic source generation

- [ ] 2.1 Separate README table parsing from build ingestion, normalize and deduplicate repository links and render deterministic Obtainium source JSON; verify table-scoped parsing, unsupported links, malformed/empty tables, stable ordering, real IDs and duplicate-ID rejection.
- [ ] 2.2 Integrate the existing APK resolver with candidate state and accepted catalog membership; verify unchanged release reuse, changed host identifiers, all-APK agreement, bounded HTTP fallback, scoped credentials, accepted-entry retention and whole-attempt failure for unresolved new projects or inconsistent state.
- [ ] 2.3 Add the source URL/hash gate, catalog digest and manual force behavior; verify unchanged-source zero-resolution no-ops, metadata-only changes, release-only forced refresh, unchanged-content no-ops and retries while source content remains unaccepted.
- [ ] 2.4 Expose `pack generate-source codm [--force]` with current-run diagnostics and isolated `.build/` candidate outputs; verify exit statuses, stale-artifact rejection and that success/failure cannot mutate tracked catalogs, cache, pack outputs or git history.

## 3. Migrate routine builds to the accepted JSON source

- [ ] 3.1 Automatically generate the initial complete catalog and bound metadata/state, using the documented migration baseline only for previously admitted projects; verify every eligible project resolves or has permitted accepted fallback and no partial seed is marked accepted.
- [ ] 3.2 Replace codm build-time scraping with committed JSON normalization while preserving generated provenance, identity, dual coverage filtering and preference; verify fixture exports are byte-identical and tests cover higher-source eligibility overrides, normalized duplicate URLs, single-only coverage and existing selectors.
- [ ] 3.3 Remove the build's resolver/cache construction and move resolution-attempt diagnostics out of its report; verify normal builds make no README/APK requests, never mutate resolver state, fail on invalid local catalogs and preserve composition diagnostics and supported report compatibility.
- [ ] 3.4 Remove resolution state from nightly candidate capture, staging and commit allowlists; verify cache/source/metadata mutations are rejected while existing exact-byte, README-boundary, no-op, main-advancement and release synchronization tests pass.

## 4. Add checked catalog-update automation

- [ ] 4.1 Implement one candidate-check operation using the selected main base, source checks, composed pack build and structural verification; verify stale selectors, collisions, failed builds and changed checked bytes block publication, and only catalog/metadata/state enter the source commit while pack changes remain diagnostics.
- [ ] 4.2 Implement the dedicated owned branch/PR lifecycle with source-only writes and one attempt; verify with controlled git/remote transports initial creation, same-content no-op, updated content, main/branch races, foreign changes, previous merged/closed PRs and ambiguous-write discovery on a later run without duplicate creation.
- [ ] 4.3 Wire daily and manual forced runs, serialized execution, canonical-main gating, locked setup and scoped token permissions; verify workflow boundary tests and action linting cover fork/ref restrictions, explicit checks before PR writes, no main/release/issue operations and no implicit dependence on PR-triggered CI.
- [ ] 4.4 Add current-run summaries and 14-day diagnostic artifacts; verify generation, validation, PR and early setup failures remain visible without stale success, leaked credentials, executed source text or archived APK/HTTP bodies.

## 5. Documentation and integrated verification

- [ ] 5.1 Update development, ingestion, curation and publishing guidance for committed source inputs, automatic resolution, hash acceptance, forced refresh, fallback retry timing and PR permission/check prerequisites; verify active documentation no longer promises nightly APK discovery and durable text has no scratch references.
- [ ] 5.2 Run the project's required development checks, workflow linting and controlled two-run tests for unresolved-then-successful generation, open-PR updates and accepted-catalog nightly independence; record results, actual implementation/test changes and baseline export preservation without real remote writes.
- [ ] 5.3 Complete required implementation reviews and task-evidence audit, verify all capability deltas, and synchronize specs through the archive workflow; verify strict change/main-spec validation, preserve historical ledgers, and leave the implementation branch available without pushing or merging.
