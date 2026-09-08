## 1. Compatibility boundary and fixtures

- [x] 1.1 Record the immutable RJNY revision and licence for any adapted helpers,
  and document the Obtainium v1.6.14 source references and supported-setting table
  in `docs/verification.md`. Verify every setting in both committed packs is
  classified as implemented, harmless/device-specific, inactive unsupported, or
  an explicit live error; test that an unknown key cannot silently pass live checks.
- [x] 1.2 Capture trimmed release/page fixtures for each distinct configured
  resolution pattern, including all seven HTML entries and track-only resources.
  Verify fixtures have recorded provenance and expected selections/versions that
  can be checked independently against the pinned source behavior.

## 2. Offline artifact validation

- [ ] 2.1 Implement validation of both serialized documents, required app fields,
  finite JSON values, source types, unique ids and string-encoded settings. Test
  missing files, malformed roots/entries, object-valued additional settings,
  duplicate ids, missing defaults, wrong known types, unknown retained fields,
  and track-only ids that are not Android package names.
- [x] 2.2 Validate nested HTML step/header shapes, category mappings and configured
  settings agreement. Test invalid nested values, booleans used as integers,
  invalid ARGB range, missing/extra categories, configured and derived colours,
  and the committed output pair passing without hydration or rewriting.
- [x] 2.3 Add local overlay/deny validation and coverage checks using existing
  composition semantics. Test forbidden overlay edits, stale common/dual targets,
  a common target in only one variant, a denied id still present, stale denials,
  and both allowed and disallowed dual-coverage gaps. Assert no source fetch occurs.

## 3. Shared HTTP and bounded probing

- [x] 3.1 Add a prefix-read probe operation separate from metadata size limits.
  Test real transport stream consumption and closure for 200 ignoring Range,
  206 honoring Range, empty bodies, errors and redirect limits. Assert at most
  1024 body bytes are read per probe, no HEAD dependency and no full download.
- [x] 3.2 Preserve caller-provided non-secret User-Agent and enforce credential
  boundaries for live headers and redirects. Test exact-host tokens, cross-host
  redirect stripping, rejected Authorization/Cookie pack headers, no credentials
  in diagnostics, and existing package-id resolver HTTP tests remaining green.
- [x] 3.3 Apply the live metadata size limit, request timeout and bounded retry
  policy. Verify transient success, retry exhaustion, rate limits, nontransient
  failures and oversized metadata with transport-backed tests and bounded attempts.

## 4. Version extraction and GitHub resolution

- [ ] 4.1 Implement compatible version extraction and unsupported-pattern
  diagnostics. Test last-match selection, default group, numeric and `$N` group
  templates, concatenation, optional and escaped groups, invalid groups, no match,
  empty output and incompatible regex constructs. Include the actual PPSSPP and
  Cocoon extraction templates as discriminating fixtures.
- [x] 4.2 Implement GitHub release-window acquisition, date/API ordering,
  draft/prerelease handling, title/notes filters and older-release fallback.
  Test the 100-release boundary, date ties under baseline behavior, skipped
  drafts/prereleases and title/notes mismatches with fallback both enabled and off.
- [x] 4.3 Add direct APK asset selection, filename filters and inversion, and
  track-only release/tags behavior. Test mixed APK/non-APK assets, filtered-empty
  releases, no-APK track-only success, filtered tags fallback and network failures
  not triggering fallback. Verify unsupported active features fail by name.
- [x] 4.4 Compute tag/title, extracted and release/asset-date versions in the
  correct order. Test title fallback, raw versus effective reporting, exact epoch
  microseconds, asset-date selection and missing dates. Assert no regex failure
  becomes a raw-version success.

## 5. HTML resolution

- [x] 5.1 Adapt link extraction, filtering and sorting with URL/link-text pairs,
  relative URLs, JSON/raw-text extraction, decoding and configured headers. Test
  redirected relative bases, text-vs-URL filters, escaped JSON URLs, alphanumeric
  order, last-segment order and independent skip/reverse behavior.
- [ ] 5.2 Implement intermediate traversal and final candidate selection. Test
  the Play! and RetroArch step chains, last-link selection at each stage, empty
  intermediate matches, installable empty final matches, excessive depth and
  ignored empty step filters under the pinned baseline. Assert no alternate older link rescues a failed probe.
- [x] 5.3 Add URL and normalized whole-page version extraction. Run all seven
  committed HTML configurations through resolver-plus-HTTP fixture tests with
  asserted final URL and effective version. Verify no-match/empty output fails,
  unused pseudo defaults are allowed and active unsupported pseudo-versioning
  is reported without placeholders. Add a track-only whole-page fixture with
  successful traversal and a valid version but no eligible final download links;
  assert success without a probe and failure for its installable counterpart.
  Assert track-only failure for empty active intermediate selection and for
  URL-based extraction without a usable final selected URL.

## 6. Live orchestration and version lint

- [ ] 6.1 Orchestrate metadata-only live resolution and opt-in bounded candidate probes, with
  track-only exemption and per-variant findings. Test first-candidate failure
  followed by success, every candidate failing, no older-release rescue,
  same-id different-variant configurations and equivalent-input request reuse
  without suppressing either variant's result. Key resolution reuse by source,
  exact configured request URL and complete settings, excluding project URL
  normalization. Add same-settings HTML fixtures at slash-distinct endpoints
  with different versions and relative download bases; assert separate requests,
  versions and resolved download URLs while identical inputs still reuse work.
- [x] 6.2 Implement the documented numeric-shape lint on effective GitHub
  versions. Test numeric/prerelease/build forms, rolling/date/raw strings,
  regex/title values that remain nonnumeric, and separate classifications for
  track-only, disabled detection and intentional date versions. Assert warnings
  alone leave verification successful.
- [ ] 6.3 Collect independent live failures and avoid persistent success reuse.
  Test two entries failing at different stages while later entries still run,
  a cached package id not masking a dead source, and a second invocation making
  fresh requests despite a successful prior report.

## 7. Evidence and command integration

- [ ] 7.1 Implement versioned verification evidence, exact-byte input fingerprints,
  running/incomplete records, atomic completion and redaction. Test missing inputs,
  interrupted attempts, successful and failed completions, report write errors,
  changed inputs during a run, and absence of secret values in serialized reports.
- [ ] 7.2 Implement `pack verify`, metadata-only `pack verify --live`, and explicit
  `pack verify --live --probe-assets`; reject probing without live mode. Test exit codes,
  warning-only success, absent build report, offline errors preventing all live
  requests, no-network offline operation, concise stderr on report failure, and
  byte-identical dist/config/cache/build-report files after standalone checks.
- [x] 7.3 Gate build publication on offline validation of the newly rendered
  bytes and include the verdict in build diagnostics. Test invalid second-variant
  bytes preserving both old files, first-run rejection leaving no files,
  candidate diff and earlier diagnostics surviving failure, `not-run` on early
  failure, retained package-id work and untouched standalone verification evidence.
- [ ] 7.4 Implement human-readable `pack report`. Distinguish offline, metadata-only
  live and live-probe evidence. Test current and stale
  fingerprints, changed verifier identity, incomplete runs, observation time and
  mode, build-only/verification-only reports, missing-both and corrupt/unsupported
  schemas, legacy build reports, failure-report display exiting zero, and no
  network or writes during display.

## 8. Integration and documentation

- [x] 8.1 Add offline verification of committed dist to ordinary CI using the
  existing uv/just conventions. Verify the workflow does not run upstream builds
  or live checks and passes actionlint plus the project's normal check suite.
- [ ] 8.2 Update README, version-detection documentation and verification usage
  docs. Verify they describe implemented commands, supported settings, warning
  policy, report freshness and the reachability/device limits without claiming
  all numeric-version re-imports necessarily cause an update.
- [ ] 8.3 Run the complete fixture integration and repository checks. Verify both
  committed variants pass offline validation, all supported resolution patterns
  have end-to-end fixture evidence, and previous ingestion/cache/publication
  behavior has not regressed.
- [ ] 8.4 Preserve the completed full live observations and inspected error/warning
  evidence, clearly labeled as historical comprehensive-probe behavior.
  Record timestamp, compatibility/verifier identity, input hashes, aggregate
  results and unresolved blockers in durable validation documentation. Verify
  diagnostics distinguish configuration failures, unsupported behavior and
  network failures; any remaining external failure is explicitly a blocker for
  future nightly publishing under the applicable mode, not a reason to silently
  modify overlays. Confirm dist/config/package-id cache were unchanged by verification.
  Validate the narrowed request contract with deterministic transport fixtures;
  do not repeat full upstream runs solely to re-prove code changes.

## 9. Polite metadata verification

- [ ] 9.1 Add live-specific per-host pacing through retries and redirects, require
  configured GitHub authentication, honor bounded server retry delays, and stop
  contacting rate-limited hosts within a run. Test with injected time/transport,
  including unrelated hosts continuing, without adding delays to ordinary builds.
- [ ] 9.2 Add bounded GitHub conditional metadata caching with fresh authenticated
  304 revalidation, malformed-cache fallback and no stale success on failures.
  Test no credential persistence and no persistent probe or verification-success cache.
- [ ] 9.3 Prove metadata-only commands send no asset requests; shared repository
  metadata is selected independently per variant; duplicate metadata/probe failures
  are reused; probes use selected URLs without another latest-release lookup.
  Record fixture request counts and the guarantee's limits in durable docs.
