## 1. Capture candidates and establish the migration baseline

- [x] 1.1 Capture the current two outputs and representative source candidates as committed test fixtures; verify the baseline records selected ids, URLs, settings and source origins without requiring live access in tests.
- [x] 1.2 Inventory competing standard/dual builds and known identity conflicts, especially CTR; deliver a durable table of explicit family decisions, required manifest-backed corrections and unresolved issues, preserving unrelated forks and Ludashi's current release selection.

## 2. Implement the candidate model and composition policy

- [x] 2.1 Extend normalized candidates with eligibility, dual preference, origin and original/effective identity; verify identical duplicates collapse while ambiguous original identities fail and internal metadata does not reach rendered apps.
- [x] 2.2 Add strict versioned composition-policy parsing, candidate selectors, corrections, family namespaces and pins; verify malformed rules, duplicate selectors, unknown fields/targets, invalid eligibility and pin conflicts fail through focused tests.
- [x] 2.3 Implement shared rendered-family projections and original-selector matching without recursive rewrites; verify different-package family mapping, ambiguous projection rejection and offline interpretation without a build report. Add separate historical effective-id-and-normalized-URL family mappings, rejecting malformed records, duplicate normalized keys and conflicts with active projections; verify history neither requires candidate presence nor affects current selection or offline coverage.

## 3. Preserve device intent through ingestion

- [x] 3.1 Map RJNY flags to eligibility and preference and retain both BBoi asset origins; verify standard fallback remains available and dual preference survives cross-source ingestion.
- [x] 3.2 Add extras dual preference and apply higher-source policy before codm coverage checks, then generated rules after resolution; verify URL normalization, no promotion by duplicate codm links, generated dual candidates for single-only coverage, cached-id behavior and missing required selector failures.

## 4. Select families and apply build-bound patches

- [x] 4.1 Extend exclusions to exactly one package or family selector and apply them to candidates before selection; verify target scoping, different-package alternatives, stale exclusions and pin-versus-denial errors.
- [x] 4.2 Implement pin-first and suitability-first selection with existing source precedence inside each tier; verify standard-only, dual-only, standard-plus-dual, ordinary extras versus dual forks, same-rank ambiguity and input-order invariance.
- [x] 4.3 Enforce unique output packages and single-to-dual family coverage with exact denial exemptions; verify cross-package replacements pass, distinct-family package collisions fail and upstream ineligibility does not silently waive coverage.
- [x] 4.4 Migrate overlay parsing to id-and-URL selectors with common-then-dual application; verify fork isolation, stale losing targets, duplicate selectors, forbidden identity/URL fields, null semantics and actionable legacy-schema rejection.

## 5. Verify and explain the new composition

- [x] 5.1 Include composition bytes in build and standalone offline input snapshots and enforce rendered family, projected pin/eligibility, denial and overlay constraints; verify build/verify agreement without source fetches or output repair.
- [x] 5.2 Include composition policy in fingerprints and update verifier identity and freshness handling; verify policy-only changes, mid-run mutations and older evidence cannot produce a current success while supported historical reports remain readable.
- [x] 5.3 Extend JSON and human-readable reports with family selections, origins, preference/pin/source reasons, alternatives and identity transitions; verify diagnostics survive partial failure and existing changes-null and uncommitted-report behavior remain intact. Regress a disappeared old candidate with its stale active rule removed, preserved history and no prior report in a fresh scheduled checkout; require a retained-family package transition. Test unknown previous history, conservatively unknown additions, known removals, normalized URL matching and first-build additions without inventing family changes.
- [x] 5.4 Exercise the build-to-nightly boundary with simulated selected-build failures; verify no project fallback or publication occurs, while existing same-project release fallback and the publication allowlist remain unchanged.

## 6. Migrate maintained configuration and validate outputs

- [ ] 6.1 Add the initial committed composition policy using the evidenced family decisions, seed historical mappings for baseline rendered identities including default package families, retain history when retiring active candidate rules, and migrate every overlay to explicit repository selectors; verify fixtures preserve existing intended version settings, Cinderbox inclusion and Ludashi's current filter/source-version policy.
- [ ] 6.2 Rebuild both packs and inspect the complete selection diff; deliver an explanation for every policy-driven package/project transition, family addition/removal and explicit exclusion, separating unrelated upstream drift.
- [ ] 6.3 Run focused regression suites followed by just check-all, pack verify and authenticated pack verify --live; record exact outcomes and output fingerprints, with no unresolved selection or serialized coverage errors.
- [ ] 6.4 Document any device migration steps and validate import/re-import and installation on an available Android device; record actual observations or explicitly outstanding device acceptance without substituting metadata success.

## 7. Complete review and durable documentation

- [ ] 7.1 Update README and durable composition/curation/verification docs with the selection order, configuration schemas, report interpretation, rollback and deferred Ludashi migration; verify the examples match parser tests and all references work from a fresh clone.
- [ ] 7.2 Complete the implementation review and task-evidence audit required by the project workflow; verify each checkbox is supported by passing checks or an explicitly recorded acceptance limitation and resolve implementation findings before completion.
- [ ] 7.3 Verify implementation against the change and sync approved spec deltas with behavior before archive; verify OpenSpec validation passes and the branch contains code, configuration, generated outputs, durable docs and corresponding spec changes together.
