## 1. Foundations

- [x] 1.1 Extend the normalized entry model to carry the variant a candidate
  applies to, its name, its source type, its category list and its provenance,
  replacing the variant-set field; verify by a unit test constructing candidates for one
  package id in each variant and asserting they stay distinct.
- [x] 1.2 Add the standard-library HTTP helper with timeout, user agent and
  bounded retries with backoff, used by all pipeline HTTP. Add dedicated
  `config/http.json` with default content
  `{"credentials": {"api.github.com": "GITHUB_TOKEN"}}`, mapping exact hosts
  to environment-variable names. Attach a bearer token only for a registered
  host with a nonempty variable; match hostnames case-insensitively without
  wildcard, subdomain inference or project-URL normalization. Strip the source
  host's credential across a cross-host redirect and select any destination
  credential independently from its registration. Verify retries and exhausted
  retries, exact-host authentication, unset and empty variables, no header on
  unregistered hosts despite other tokens being set, no inferred subdomain or
  `www.` registration, and no source token forwarded across a cross-host
  redirect.
- [x] 1.3 Capture trimmed fixture snapshots of the RJNY source catalog, both
  RJNY rendered exports, both BBoi34 release assets, the Codeberg release
  listing and the codm2000 README; verify the fixtures load and each carries
  the entries the later tests reference, including the duplicate ids and the
  non-GitHub README rows.
- [x] 1.4 Add the shared URL normalization used by the pipeline's two URL
  comparison sites, the already-contributed check on codm2000 links and the
  resolved-id cache key - discard the scheme, lowercase the host, drop a
  leading `www.`, drop a trailing slash and a trailing `.git`, and compare a
  GitHub link's owner and repository without regard to case; verify by unit
  tests covering each rule and asserting that two spellings of one GitHub
  project compare equal including when they differ only in owner or repository
  case and when they differ only in scheme, that a non-GitHub path differing
  only in case is not folded, and that two different projects do not compare
  equal.

## 2. Package-id resolution

- [x] 2.1 Vendor the upstream package-id resolver as a module, dropping its
  command-line entry point and dotenv handling and recording its public-domain
  origin in the file. Route all its release metadata requests, ranged APK
  reads and full asset downloads through the shared HTTP helper; verify by a
  unit test resolving a package id from a
  fixture APK tail and by the lint and type checks passing on the vendored
  module.
- [x] 2.2 Implement the cache read and write over the resolved-id file, keyed
  by the normalized project URL and recording alongside each id the
  host-assigned identifier of the release it was resolved from - the stable
  identifier the release host assigns to a release, not its tag name, compared
  verbatim - written as soon as an id resolves rather than at the end of the
  build, and falling back to the cached id when the latest release identifier
  itself cannot be read; verify by unit tests that a cached id whose recorded
  release identifier equals the project's latest one is returned without reading
  any APK asset, that a cached id whose recorded release identifier differs from
  the project's latest one is resolved again and the cache updated with both the
  new id and the new identifier, that a project republishing under one rolling
  tag with a new host-assigned identifier is resolved again, that a differently
  spelled URL for the same project hits the same cache entry, including one
  differing only in the case of its GitHub owner and repository and one
  differing only in scheme, that a newly resolved id is written back together
  with its release identifier, that a failure to resolve again with a cached
  id available returns the cached value, reports the failure and preserves both
  cached fields so a later build observing the same failed release retries
  resolution, that a failure
  to read the latest release identifier with a cached id available returns the
  cached value, reports the failure and preserves both cached fields, and that
  a failure to read the latest
  release identifier with no cached id leaves the project unresolved with no
  entry produced.
- [x] 2.3 Resolve a project's package id from every eligible APK asset of its
  latest release - every release asset whose filename ends in `.apk` compared
  case-insensitively - using the id only when every eligible asset is readable
  and all declare the same id. Treat no eligible APK, disagreement between
  package ids, and any unreadable APK as failed resolution attempts, each using
  the cached id and reporting the failure when available, and omitting the entry
  as unresolved only without a cached id. Verify successful resolution over a
  release with one APK, several APKs sharing an id, and mixed `.apk`, `.APK` and
  non-APK filenames. Test each failure with and without a cached id: a release
  with no APK assets, APKs declaring different ids, and an unreadable APK,
  covering a size bound, fetch failure and unreadable manifest while other APKs
  agree. Assert a cached id produces an entry and a failure report while both
  cached fields remain unchanged; assert no cached id produces no entry and an
  unresolved report. For each cached failure, run a later build against the same
  release and assert it retries resolution.
- [x] 2.4 Ensure generated entries never use a placeholder id: verify the
  generated-entry path for no eligible APK, disagreeing APK ids and an
  unreadable APK, each with and without a cached id, asserting it retains an
  entry with the cached id and reports the failure when available, and otherwise
  omits the entry and reports the project as unresolved.

- [x] 2.5 Add a fixture-backed cold-cache generated-project integration test
  through the actual resolver and shared HTTP helper, intercepting only network
  transport. Load the default `config/http.json` mapping and set a fake
  `GITHUB_TOKEN`; assert the latest-release request to
  `https://api.github.com/repos/OWNER/REPO/releases/latest` carries
  `Authorization: Bearer <token>` and the generated entry resolves. Assert no
  token reaches unregistered `github.com`, `raw.githubusercontent.com`,
  `codeberg.org` or asset hosts on catalog and resolver requests, including
  ranged reads, full-download fallback and a cross-host redirect from the
  authenticated API host to an unregistered host. Repeat resolution with the
  variable unset and empty, asserting unauthenticated requests still resolve
  against public fixtures. Do not replace the resolver or helper with mocks.

## 3. Source ingestion

- [x] 3.1 Implement RJNY ingestion: fetch the configured path on the
  configured branch, drop entries excluded from export, apply the per-variant
  opt-outs, ignore the presentation-only name and URL overrides, and normalize
  per-app settings to structured data; verify by unit tests over the fixture
  covering each flag and a test asserting the name override is not applied.
- [x] 3.2 Add the differential test asserting RJNY ingestion reproduces the id
  set and per-id URL of both committed upstream exports, including the id that
  resolves to a different project per variant.
- [x] 3.3 Implement BBoi34 ingestion: resolve the newest release, match both
  asset patterns, map the single-screen asset to both variants and the
  dual-screen asset to the dual-screen variant, and decode the string-encoded
  per-app settings; verify by unit tests over the fixtures covering the four
  ids present in both assets and a test asserting a malformed settings string
  fails the build.
- [x] 3.4 Implement codm2000 ingestion: extract README project links, keep
  GitHub repository links, skip other hosts, skip a link only when a
  higher-precedence source already contributes that project as a candidate for
  the dual-screen variant - the variant generated entries supply - with the two
  URLs equal in normalized form, and emit the rest as dual-screen-only generated
  entries named for the repository in their project URL and carrying an empty
  category list; verify by a unit test over the fixture asserting the GitHub
  links are kept, the non-GitHub rows are reported as skipped, a link a
  higher-precedence source already contributes as a dual-screen candidate under
  a different spelling produces no entry, covering a spelling that differs only
  in the case of the GitHub owner and repository and one that differs only in
  scheme, that a link a higher-precedence source contributes to the
  single-screen variant only still produces a generated dual-screen entry, and
  that a generated entry's name is its repository name and its category list is
  empty.
- [x] 3.5 Implement extras ingestion from configuration: fail the build with an
  error naming the entry on an entry missing a package id, a URL or a name, make
  an entry a candidate for both variants by default, honour an optional
  per-entry variants field naming the subset it applies to, and fail the build
  on a variants value that is not a known variant; verify by unit tests
  asserting an entry with no variants field reaches both variants, an entry
  naming one variant reaches only that variant, and that a missing package id, a
  missing URL, a missing name and an unknown variant each fail the build with an
  error naming the entry.
- [x] 3.6 Establish every ingested entry's source type: take it from the
  upstream record's source field, derive it from the URL for generated and
  extras entries with a github.com repository taking the GitHub type and any
  other URL the HTML type, and fail the build with an error naming the entry
  and the value for any type other than GitHub or HTML; verify by unit tests
  over an upstream entry of each type, a generated entry and an extras entry
  deriving GitHub from a github.com URL, an extras entry deriving HTML from
  another host, and an upstream entry declaring an unsupported type.
- [x] 3.7 Make any fetch or parse failure abort the build before anything is
  rendered, naming the failing source; verify by unit tests that simulate an
  unreachable source and an unparseable response, and assert existing output
  files are untouched.

## 4. Composition

- [x] 4.1 Drive the composition stages in a fixed order - union by precedence,
  denylist removal, overlay target validation, overlay application, then the
  dual-screen coverage check - with the denylist observing entries as their
  sources contributed them and never re-applied afterwards, which is safe
  because an overlay's patch may not contain the package-id field at all;
  verify by a test asserting an overlay whose patch carries the package-id
  field set to an id the denylist names fails the build, and a test asserting
  an overlay naming an id the denylist just removed fails the build.
- [x] 4.2 Implement the per-variant union keyed by package id with the
  precedence order extras, RJNY, BBoi34, generated, keeping the winning
  candidate whole, collapsing identical candidates that come from one source,
  and failing the build with the source, the variant and the package id when
  one source contributes differing candidates for the same id in one variant;
  verify by unit tests covering a two-source collision, an extras collision,
  an identical same-source duplicate, and a differing same-source duplicate.
- [x] 4.3 Report displaced candidates with the winning and losing source and
  the differing fields; verify by a unit test asserting a settings difference
  between a winner and a loser appears in the report.
- [x] 4.4 Implement denylist removal by package id, with an optional variant
  on an entry scoping both the removal and the match test to that variant alone,
  reporting each removal with the recorded reason, treating an entry whose
  package id matches nothing in the variants it applies to as a no-op recorded
  in the build report as a stale exclusion whatever another variant holds, and
  failing the
  build with an error naming the entry and the rejected value when an entry
  names a variant the pack does not have; verify by unit tests for an entry
  naming an id and no variant removing it from both variants, an entry naming
  an id and one variant removing it from that variant only, an entry naming an
  id no variant carries asserting the build succeeds, nothing is removed and
  the report records that entry as a stale exclusion, an entry naming the
  dual-screen variant and an id only the single-screen variant carries
  asserting nothing is removed and the report records it as a stale exclusion,
  and an entry naming an
  unknown variant asserting the build fails with an error naming the entry and
  the value.
- [x] 4.5 Validate overlay targets before applying them: the common overlay
  must name a package id present in at least one composed variant, and the
  dual-screen overlay one present in the composed dual-screen variant; verify
  by unit tests for a common overlay naming an id present in neither variant
  and a dual-screen overlay naming an id absent from the dual-screen variant,
  and by a test asserting a common overlay naming an id present in one variant
  only succeeds and patches that variant.
- [x] 4.6 Implement overlay application as a JSON Merge Patch keyed by package
  id, applying the common overlay to whichever composed variants contain the
  named id and the dual-screen overlay to the dual-screen variant on top of it,
  requiring each patch to be an object and rejecting with an error naming the
  package id both a package id mapped to anything else and a patch that contains
  the source-type field or the package-id field with any value, null included,
  since presence of either field rather than assignment to it is what the guard
  is on; verify by unit tests covering a changed setting, a dual overlay
  refining the common overlay, a null deleting a key that is neither the source
  type nor the package id, a patch containing the source-type field failing the
  build with an error naming the package id, a patch containing the package-id
  field failing the same way, a patch mapping the source-type field to null and
  one mapping the package-id field to null each failing the same way, and a
  package id mapped directly to null - and to a non-object value - failing the
  build with an error naming that package id rather than removing the entry.
- [x] 4.7 Fail the build when a package id in the composed single-screen
  variant is absent from the dual-screen variant, exempting an id a denylist
  entry names for the dual-screen variant whether or not that entry actually
  removed anything; verify by a unit test for the failing case, one asserting a
  dual-screen-scoped denial of an id the single-screen variant still carries
  leaves the build passing, and one where a dual-screen-scoped denial names an
  id no composed dual-screen entry carries while the single-screen variant does,
  asserting the build succeeds and the report records that entry as a stale
  exclusion.

## 5. Rendering

- [x] 5.1 Commit the per-source-type settings defaults table for the GitHub
  and HTML source types, seeded from the values upstream exports carry, and
  record in it the Obtainium version its key set was seeded from - the release
  current when the table is committed; verify by a test asserting each type's
  key set matches the fixture exports and that the recorded version is
  present.
- [x] 5.2 Implement settings hydration filling every key defined for the source
  type the entry carries from ingestion, preserving entry-set and overlaid
  values and emitting unknown keys after the known ones; verify by unit tests
  covering a sparse entry of each source type, an overlaid value that also has
  a default, and an unknown key.
- [x] 5.3 Add the differential test asserting hydration of an entry shared
  with RJNY reproduces the settings its rendered export carries.
- [x] 5.4 Encode per-app settings as a JSON string in the rendered output;
  verify by a unit test asserting the field is a string that decodes to the
  structured settings.
- [x] 5.5 Implement deterministic ordering by primary category - the first
  category in an entry's category list, taken as the empty string when the list
  is empty - then name, then package id, with pinned serialization; verify by
  unit tests asserting two renderings of the same composed input are
  byte-identical, that entries tying on category and name order by id, that an
  entry carrying no category sorts ahead of every entry with a named primary
  category, and by a test over a fixture spanning two distinct named categories
  whose package ids deliberately contradict both the category order and the
  name order within a category, and one of whose entries lists a first category
  that is not its alphabetically smallest, asserting the exact expected
  sequence of package ids from several permutations of the input order so that
  all three sort keys and the first-category rule are proven rather than only
  the tie-break.
- [x] 5.6 Render the settings block from configuration with the category list
  as a JSON-encoded string mapping each category used in that variant to an
  ARGB integer, taking a configured category's colour from configuration and
  deriving any other category's colour from the first three bytes of the
  SHA-256 digest of its name with a fully opaque alpha; verify by unit tests
  asserting the exact rendered value for a category absent from configuration
  and its stability across runs, that a configured category renders the
  configured value, that a configured category no entry uses is omitted, and
  that an entry carrying no category adds nothing to the category list.
- [x] 5.7 Fail the build rather than render a variant containing two apps
  with the same package id; verify by a unit test.

## 6. Build command

- [x] 6.1 Implement the build command driving ingestion, composition,
  rendering and writing for both variants; verify by an end-to-end test over
  the fixtures asserting both files are written and the command exits zero.
- [x] 6.2 Narrow the existing command-registration test to the commands that
  remain unimplemented, `verify` and `report`, replacing its build case with
  the end-to-end assertion that the build command runs; verify by the test
  module passing with no expectation that building raises a not-implemented
  error.
- [x] 6.3 Publish both output files as a unit once both variants render, using
  a strategy that restores the previous pair when publication fails partway -
  the previous contents of both files, or the absence of both on a first run -
  so a failure at any stage leaves existing output unchanged, while leaving the
  resolved package id cache outside that guarantee; verify by tests that fail
  the build after the first variant renders and assert both files are
  untouched, that a failure injected between the two file replacements leaves
  both files at their pre-build contents, that the same failure injected on a
  first run leaves neither file present, that a first-run failure before the
  write phase creates no files, and that a build failing after a new package id
  resolved leaves the output untouched but keeps the newly cached id.
- [x] 6.4 Write the build report as a JSON document to `.build/report.json`,
  outside the distribution directory, adding `.build/` to the repository's
  version-control ignore file so the report is never committed, on a failed
  build as well as a successful one, recording
  apps added and removed against the import files as they stood before the
  build - read before either file is replaced, and with every app counted as
  added when a variant's file does not yet exist - precedence displacements,
  denylist removals, denylist entries that matched nothing as stale exclusions,
  skipped or unresolved source rows, every project that produced a generated
  entry together with its resolved or reused package id, failed resolution
  attempts that retained a cached id, and on a failure the
  stage that was running and the error that stopped it; verify by an end-to-end
  test asserting the file is written at that path, parses as JSON, lists a
  newly added app, an unresolved project and a resolved generated project with
  its package id including one whose app the previous output already contained,
  a cached generated project whose resolution failed with its retained id and
  the resolution failure, and that no report file appears
  in the distribution directory, by a test over a first build with no existing
  output asserting every app is listed as added, by a test asserting the diff
  is computed against the pre-build contents rather than the newly written
  ones, by a test that aborts the build on an unreachable upstream and
  asserts the report exists and names the failing stage and error, and by a
  check asserting the report path is ignored by version control.
- [x] 6.5 Persist newly resolved package ids as part of the build; verify by
  an end-to-end test asserting the cache file gains an entry.

## 7. Integration

- [x] 7.1 Run a live build against the real upstreams and review the two
  rendered files and the report by hand, confirming the entry counts and the
  per-variant resolution of the id that differs between variants.
- [x] 7.2 Import the rendered single-screen file into Obtainium on a device
  and confirm every app is added and its settings UI shows the full set of
  switches.
- [x] 7.3 Confirm the whole check suite passes and that a second build with no
  upstream change rewrites both files byte-identically.
