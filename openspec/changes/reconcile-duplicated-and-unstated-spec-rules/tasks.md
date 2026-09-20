Groups 1 to 3 add characterization tests for behavior that already ships, so
each new test is expected to pass when written; a test that fails there means a
delta misdescribes the code, and the delta is what gets corrected. Group 4 is
the only group that changes code and runs red then green.

## 1. Characterize ingestion behavior the specs now state

- [ ] 1.1 Add tests that an extras record and a committed codm2000 record carrying a top-level `meta` ingest successfully and render no `meta`, while another unmodeled field on the same record is retained; verify with `just test`
- [ ] 1.2 Add a test that a committed codm2000 record at a github.com URL declaring the HTML source type ingests as HTML, and one that a codm2000 record omitting `overrideSource` derives GitHub; verify with `just test`
- [ ] 1.3 Add tests that an RJNY record and a BBoi34 record carrying no `overrideSource` fail the build naming the entry as an unsupported source type; verify with `just test`
- [ ] 1.4 Add tests that an empty configured location fails naming the source for BBoi34 and for codm2000, beside the existing RJNY case; verify with `just test`
- [ ] 1.5 Add a build-level test that a committed track-only resource keeps its resource id, track-only flag and manual-installation description in dual while the app it extends keeps its own entry in both packs; verify with `just test`
- [ ] 1.6 Independent evidencing review of group 1: each new test maps to a named scenario in the `source-ingestion` delta, and none asserts behavior the delta does not state

## 2. Characterize composition behavior the specs now state

- [ ] 2.1 Add tests that a candidate rule and a pin whose selector `url` has no readable host, or contains whitespace, fail configuration identifying the field and the value before any candidate is matched; verify with `just test`
- [ ] 2.2 Confirm the existing test of a denial matching only never-eligible candidates asserts all three outcomes the delta states (nothing removed, no exclusion reported, not stale) and extend it where one is missing; verify with `just test`
- [ ] 2.3 Confirm the existing test of dual falling back among several baseline builds asserts `ordinary-fallback` for dual and `source` for single, and add a pin case asserting `pin`; verify with `just test`
- [ ] 2.4 Add a test that denying a designated curated extra's package id, with no pin naming it, makes the single-winner guard fail and name the family; verify the guard is shown failing, then passing on the committed configuration
- [ ] 2.5 Independent evidencing review of group 2: each test maps to a scenario in the `pack-composition` or `pack-curation` delta

## 3. Characterize generation behavior the specs now state

- [ ] 3.1 Add a test that an APK rule enabling `fallbackToOlderReleases` exports it enabled in the generated entry when the newest matching release resolves, and that a rule disabling it exports it disabled; verify with `just test`
- [ ] 3.2 Add a test that a track-only rule with a release-title filter is accepted and the generated tracking entry carries the filter; verify with `just test`
- [ ] 3.3 Confirm existing tests cover every construct the regex delta names (other alphanumeric escapes, non-permitted `(?` groups, possessive quantifiers) and a missing rationale and unusable installation text for a track-only rule; add any case that is absent; verify with `just test`
- [ ] 3.4 Add a test that a run whose staging fails summarizes the failing stage and reason, and that a run whose staging succeeds carries the base revision in its summary; verify with `just test`
- [ ] 3.5 Add an end-to-end test that a retained failure which reproduces main's catalog closes an open proposal rather than updating it; verify with `just test`
- [ ] 3.6 Independent evidencing review of group 3: each test maps to a scenario or sentence in the `readme-source-generation` delta

## 4. Remove the unreachable verification state and fix two report nits

- [ ] 4.1 Write failing tests: a verification report carrying `complete` or the `running` status is rejected as an unsupported shape, a report written before this change draws the `pack verify` regeneration diagnostic, and `pack report` output has no `Complete:` line; verify they fail for the expected reason
- [ ] 4.2 Remove the `complete` field from the written report, the `running` status, the `startedAt` fallback and the `Complete:` line from the reader, advance the verification schema version, and delete the test that keeps the incomplete state alive; verify 4.1 passes and `just test` is green
- [ ] 4.3 Write two failing tests, one per path that double-reports an unreadable verification input, then fix both. First, the five offline inputs (single, dual, deny, overlay, composition): an unreadable one yields exactly one `input_unreadable` error naming it and no `input_missing` error; test at least one pack file and one configuration file. Second, the README, which takes a separate path: an unreadable README yields exactly one `input_unreadable` error naming it and no `catalog_invalid` error saying it is missing or unreadable. A genuinely missing input of either kind is still reported as missing. Verify each test fails for the expected reason first, then with `just test`
- [ ] 4.4 Add tests for "Absent losing candidate cannot be assessed offline" (an unpinned policy candidate absent from the outputs leaves findings empty) and for an interrupted verification exiting nonzero through the command; verify with `just test`
- [ ] 4.5 Correct `pack report`'s help text to describe both reports; verify with `pack --help`
- [ ] 4.6 Update `docs/verification.md` so its description of the verification report no longer lists completion, and so the sentence stating which schema standalone verification writes to `.build/verify.json` gives the advanced verification schema version from 4.2; leave the statement that build reports must use schema 3 unchanged, since the build report's schema does not move; verify `just check-links` passes
- [ ] 4.7 Rerun `pack verify` then `pack report` locally and verify the evidence displays as current with no regeneration diagnostic
- [ ] 4.8 Independent evidencing review of group 4: no reader, writer, test or doc still mentions the removed state, and no spec described it; every mention of the verification schema version in `docs/` and `README.md` equals the writer's constant, and every mention of the build report schema is unchanged at 3

## 5. Bring the main specs into agreement

- [ ] 5.1 Synchronize the six delta specs into `openspec/specs/` without archiving the change; verify `openspec validate --specs --strict` passes 10 of 10 and the requirement count is still 70
- [ ] 5.2 Edit the Purposes of `pack-composition` (selection is per family; families, pins, dual preference, coverage and reporting), `source-ingestion` (credential rules govern source-generation requests; it owns URL comparison identity), `nightly-publishing` (README catalog, credential isolation, release synchronization) and `pack-cli` (source generation); verify each Purpose is true of every requirement below it
- [ ] 5.3 Replace "the helper" in `source-ingestion`'s credential requirement with a subject that has an antecedent; use "stale exclusion" throughout `pack-cli`; reword the WHEN of `pack-composition`'s "An overlay cannot move an entry onto a denylisted package id" so it names a patch field, not the selector; fix the missing blank line and the over-long lines noted in `pack-cli` and `nightly-publishing`; verify strict validation still passes
- [ ] 5.4 Retitle scenarios whose bodies moved on, editing main spec and delta together where the requirement is one this change modifies: `pack-composition` "Maintainer selects a standard build for dual" and "Overlay maps a package id to something other than an object"; `source-ingestion` "Existing generated family selector remains valid" and "Newly resolved prerelease apps are admitted"; `readme-source-generation` "Release scan reaches its bound"; `nightly-publishing` "Candidate verifies with warnings", "Resolver state or source catalog changes" and "App metadata is unavailable after a successful build"; verify `openspec validate reconcile-duplicated-and-unstated-spec-rules --strict` and `openspec validate --specs --strict` both pass
- [ ] 5.5 Grep specs, `README.md`, `docs/` and code comments for the renamed requirement title and every retitled scenario; verify no reference to an old name remains outside `openspec/changes/archive/`
- [ ] 5.6 Independent evidencing review of group 5: diff each synchronized requirement against its delta block, and confirm every pointer names a requirement that exists under that exact title

## 6. Validate and review

- [ ] 6.1 Run `just check-all`; verify it is green and record the test counts in `validation.md`
- [ ] 6.2 Verify captured-input pack bytes are unchanged by this change and record the comparison in `validation.md`
- [ ] 6.3 Parallel review wave over the whole branch: spec accuracy against code, test quality, and dead-code removal completeness; resolve or record every finding in `validation.md`
- [ ] 6.4 Completion audit: every checkbox above has evidence in `validation.md`, and every finding the proposal lists is either fixed or named under "Deliberately left alone"
