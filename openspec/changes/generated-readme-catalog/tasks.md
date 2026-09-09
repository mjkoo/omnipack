## 1. Catalog generation and consumer guide

- [ ] 1.1 Implement deterministic family tables, collapsible categories and exact per-app redirect payloads; verify shared/different builds, dual-only entries, ordering, escaping and decoded payload fidelity in unit tests, including a fixture for the redirect's actual decoding behavior.
- [ ] 1.2 Implement strict byte-preserving marker replacement and add consumer instructions, pack links and credits to README; verify malformed markers and preserved surrounding bytes in tests, generate the initial catalog from committed exports, and inspect a rendered preview.

## 2. Build and verification integration

- [ ] 2.1 Generate and gate the catalog in pack build and recoverably replace README with both exports; verify failure before publication, concurrent README edits, replacement failures, first-build rollback and temporary-file cleanup with injected failures.
- [ ] 2.2 Extend standalone verification and report compatibility with README consistency and fingerprints; verify stale/missing/malformed catalogs fail without writes or live requests, concurrent mutations fail, handwritten edits permit fresh verification and historical evidence remains readable but stale.

## 3. Publication and delivery

- [ ] 3.1 Publish only verified catalog-interior changes alongside the packs and cache; verify candidate/staged byte checks, handwritten-content rejection, mode preservation, no-op and fresh-attempt behavior in nightly integration tests.
- [ ] 3.2 Update durable build/verification/publishing documentation and sync the delta specs; verify strict OpenSpec validation, all project checks and offline pack verification, and document representative Android handoff acceptance as tested or explicitly pending if no device is available.
