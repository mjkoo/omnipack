## Context

See proposal.md for motivation. The build already composes each variant
independently, renders both files in memory and replaces the pair with rollback
on publication failure. It writes `.build/report.json`, including failures.
`verify.py`, `pack verify` and `pack report` are unimplemented.

The committed files contain 87 single-screen and 107 dual-screen entries. Each
contains seven HTML sources and four track-only resources. Shared ids can have
different URLs or settings per variant. The existing package-id resolver only
serves generated GitHub entries and has deliberately different cache semantics
from a live health check.

The compatibility baseline is Obtainium v1.6.14, already used by the renderer.
The upstream [GitHub resolver](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/app_sources/github.dart),
[HTML resolver](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/app_sources/html.dart)
and [shared version handling](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/providers/source_provider.dart)
are the behavioral references. RJNY's
[test script](https://github.com/RJNY/Obtainium-Emulation-Pack/blob/main/scripts/test-apps.py)
is a useful implementation starting point, but its version handling cannot be
adopted unchanged. In particular, successful extraction must not be replaced by
a placeholder or a raw value when an explicit regex fails.

## Goals / Non-Goals

**Goals:** validate the serialized artifact at the build boundary; separate pure
validation, source resolution, network probing and diagnostics; report enough
evidence to distinguish a broken configuration from an unavailable upstream.

**Non-goals:** reproducing Obtainium's entire source provider, running Android
during ordinary verification, claiming that numeric version syntax proves a
match with installed versionName, and adding persistent live-success caching.
The live guarantee is evaluated before device-specific architecture selection.
Ordinary live verification resolves metadata and versions without fetching asset
bodies. An explicit `--probe-assets` diagnostic adds bounded reachability checks.

## Decisions

### Validate bytes, not a repaired model

Introduce a pure offline validation boundary accepting both output byte strings
and a snapshot of `deny.json`, both overlays and `settings.json`. Standalone
verification supplies existing files; build supplies newly rendered bytes before
either file is replaced. Decode without hydrating or silently repairing input:
otherwise an omitted setting or serialization mistake could be hidden.

Validate required app fields, the supported source discriminator, string-encoded
settings and categories, default-key completeness, known setting types and
nested HTML structures, finite JSON values, ids, and category mappings. Unknown
fields are retained; structural validity does not imply live support. Validate
the overlay/deny configuration under existing composition rules, check targets
against the rendered pair, reject denied ids still present, and check dual
coverage with its existing dual-only exclusion exception. This cannot prove
freshness against upstream sources or that every overlay value was applied.

Reuse small configuration/coverage predicates where appropriate, without
re-running source ingestion or composition. Testing serialized input is more
useful than feeding the same normalized objects back through renderer helpers.

### Isolate live resolution from package-id discovery

Use `resolution/github.py`, `resolution/html.py` and shared version/link helpers,
or equivalent focused modules. Each resolver accepts a validated entry and an
injected shared HTTP client, and returns selected source evidence, raw/effective
version, version origin and ordered download candidates. It never mutates apps
or the package-id cache. Adapt RJNY helpers selectively; record an immutable
upstream revision, original path and licence attribution when copying code.
Keep the current standard-library runtime policy.

GitHub support covers the first 100 releases, matching the pinned provider's
request window, `date` and `none` sorting, draft/prerelease handling, title and
notes filters, `fallbackToOlderReleases`, direct APK assets, APK name filters and
inversion, title versions and release/asset date versions. Match the baseline's
fallback boundary: excluded drafts/prereleases do not consume the first eligible
release, but a title/notes/APK mismatch does when older-release fallback is off.
Select based on metadata before probing. Report the inspected window and chosen
release; failure inside the window does not prove no older usable release exists.
Track-only entries use the same filtering, without an APK requirement, and use
the provider's tags fallback when no release qualifies. Network errors do not
trigger tags fallback or acceptance of a cached version.

HTML support covers all seven committed configurations: anchor URLs and link
text, relative URL resolution, JSON/raw-text links outside anchors, custom
headers, intermediate steps, alphanumeric sorting, last-segment sorting,
skip/reverse sorting, custom link and APK filters, and URL/whole-page version
extraction. Use response URLs after redirects as relative-link bases. The last
link after the configured sort/filter operations is selected, including at each
intermediate step. Installable entries require a final download candidate; an
older HTML link cannot rescue an unreachable selected one. Track-only entries
using whole-page version extraction may succeed with a nonempty effective
version and no final download link. They still follow every configured active
intermediate step; an empty intermediate selection fails. URL-based version
extraction requires a usable final selected URL even for track-only entries.
Enforce a maximum of ten nonempty intermediate steps and reject excess rather
than silently skip instructions. Whole-page normalization, URL decoding and
group selection follow the pinned provider.

Provide an explicit support table in `docs/verification.md`. Unsupported active
features include non-date/non-none GitHub sorting, `verifyLatestTag`, archive
downloads, request proxies, embedded credentials, disabled TLS verification,
device-dependent intermediate filtering, and HTML pseudo-versioning when no
explicit extraction is configured. These are live errors, not successful skips.
The current HTML entries all configure version extraction, so their inactive
pseudo-version defaults do not fail. Unknown additional-setting keys are live
errors unless classified as harmless presentation/device controls; false/empty
values for known unsupported features remain acceptable when inactive. Unknown
values are not presumed harmless merely because they are false. Document the
accepted cosmetic/device controls, including `autoApkFilterByArch` being outside
this check's device-independent guarantee. Validate `preferredApkIndex` as an
integer offline but do not interpret a device's selection in live verification.

This bounded implementation is preferable to a generic Obtainium clone. New
upstream behavior becomes a named compatibility failure requiring an intentional
extension, instead of silently changing the meaning of success.

### Extract versions before classifying them

Use shared extraction semantics: the last regex match, the baseline's default
group, numeric and `$N` group references, concatenation and unmatched optional
groups. Reject malformed patterns, invalid groups, no match and empty output.
Support the compatible subset used by the pack and explicitly reject constructs
whose Dart semantics cannot be reproduced. Do not equate Python regex compilation
with compatibility. Translate default ECMAScript whitespace, dot line terminators
and strict end anchors with a small class-aware scanner. Retain ASCII digit,
word and boundary semantics; reject pattern backreferences, numeric/octal escapes,
unknown identity escapes, class-contained `\S`, character-class escapes beside
hyphens and repeated groups containing captures. These conservative guards avoid
Python-specific ranges and retained captures. The supported subset operates
on BMP text, without modeling UTF-16 surrogate-pair matching. HTML's active
release-date override is rejected before fetching because no date is available.
GitHub uses the tag or configured title, then extraction,
then an intentional release-date override in microseconds since the Unix epoch.
Date selection follows the baseline, including asset-date selection. A requested
date with no usable date is a verification error rather than a fallback to a tag.

Lint effective GitHub versions with a documented, anchored heuristic: optional
`v`/`V`, two or more dot-separated numeric components, and optional `-` prerelease
or `+` build suffixes containing ASCII letters, digits, dots or hyphens. Track-only,
disabled version detection and date-version entries are separately classified
and do not receive the numeric-shape warning. Title or regex use alone does not
suppress it. This intentionally avoids claiming full Obtainium reconciliation
parity or an APK versionName comparison. Failed resolution has no successful
effective version to lint.

### Keep routine verification on metadata

`pack verify` remains offline. `pack verify --live` adds source metadata, version
extraction and eligible-candidate selection, without any download probes.
`pack verify --live --probe-assets` adds the reachability diagnostic below;
`--probe-assets` without `--live` is invalid. Reports distinguish `offline`,
`live` and `live-probe`, so a metadata success cannot imply a download was checked.

Resolve a repository response once per invocation and apply each variant's
settings locally. Probes consume the selected candidate URLs directly and never
resolve latest again. If a future publishing pipeline downloads a selected asset,
it should use that download as evidence rather than issue a separate probe.
Connecting that pipeline remains outside this change.

### Probe downloads only when explicitly requested

Add a shared-client operation for reading a response prefix, distinct from the
existing maximum-size operation that rejects oversized metadata. Request
`Range: bytes=0-1023`, read at most 1024 bytes, then close the stream even when
the server returns 200 and ignores Range. Accept 200 or 206 with a nonempty
prefix; reject errors and empty responses. Do not trust HEAD alone. A successful
probe establishes HTTP reachability, not that those bytes are an APK.

For a GitHub release try eligible candidates in returned order until one works;
record attempted failures as warnings if another succeeds, otherwise fail the
entry. HTML has one selected candidate. Never use network probe failure as
grounds to fall back to an older release. Preserve candidate and final response
URLs internally while redacting credentials/query tokens from reports.

Use the existing 30-second request timeout, at most two transient retries and
host-scoped credentials. Enforce at most ten redirects and a 10 MiB metadata
response limit. Preserve HTML non-secret headers, including User-Agent, and
reject pack Authorization/Cookie headers and embedded credentials. Redirects
rebuild credentials for the destination host.

Live requests use a minimum two-second interval per host, including retries and
redirects. Require a configured, nonempty exact-host GitHub API credential before
contacting that API; do not consume the unauthenticated quota for the pack.
Honor server retry delays within a bounded wait, and suppress a rate-limited host
for the rest of the invocation instead of repeatedly requesting each entry.
Unrelated hosts continue. Network errors remain errors, not stale passes.

Persist only a bounded GitHub metadata response/validator cache under `.build/`
for conditional requests. Each invocation still contacts the API; a cached body
is usable only after a fresh authenticated 304. Never cache verification success,
probe success across runs, credentials or credential-derived identities. Invalid
cache data is discarded and falls back to normal acquisition. A missing or failed
live response cannot use cached metadata as evidence.

Reuse identical metadata responses and failures within the invocation, and reuse
identical probe responses and failures only in diagnostic mode. Resolution keys
include source, exact configured request URL and complete settings. For HTML,
preserve scheme, authority, path, trailing slash and query; project normalization
is not a resolution identity. Keep each variant's result even when work is reused.
No concurrency framework or persistent probe cache is needed.

### Separate build history from verification evidence

Build continues to own `.build/report.json` and adds an offline-verification
section with status and findings. Before that stage it is `not-run`; failure at
that stage records `offline verification` and preserves previous output. A build
does not touch the standalone verification report.

Standalone verification atomically replaces `.build/verify.json`, on success or
failure. Include schema version, Obtainium baseline, verifier version, mode,
start/completion times, completion flag, status, SHA-256 input fingerprints and
per-entry findings keyed by variant and id (or input index for malformed ids).
Fingerprint the exact two files plus denylist, overlays, pack settings and HTTP
configuration; represent missing/unreadable inputs explicitly. Never fingerprint
or serialize environment token values. Record errors with stage and a stable
code, warnings, effective version/origin, selected release/page and probe evidence.
Write an initial `running`/incomplete report before network work so an interrupted
attempt cannot leave the previous success looking like the latest attempt.
Resolve from the captured input snapshot and compare file fingerprints again
before completion. If any input changed, record an input-changed error and exit
nonzero, preserving the fingerprints of what was actually checked.

Offline errors prevent the live phase. Once offline passes, collect independent
entry failures and finish the rest. A run is successful only when complete and
error-free; warning-only runs succeed. Reporting failure makes the command fail
and produces a concise stderr diagnostic even if the normal report is unavailable.

`pack report` reads both available reports without fetching or changing files.
Print build and verification sections separately. Compare fingerprints and
verifier identity with current inputs to label verification current or stale;
display mode and observation time because an old live pass does not prove current
upstream health even if local inputs match. Missing one report is acceptable;
missing both, unreadable JSON or unsupported report schemas exit nonzero. A
successfully displayed failed operation still gives the report command exit 0.

### Test behavior and leave network checks opt-in

Fixture tests intercept transport beneath the actual HTTP client and resolver,
exercising the full path through source parsing, selection, extraction and probe.
Use every current HTML configuration and discriminating fixtures where the wrong
sort order, regex match or intermediate page yields a different outcome. Add
release/title/date and track-only fixtures, credential redirect checks, a server
ignoring Range, and distinct per-variant configurations for the same id.

CLI integration proves no-network offline execution, no standalone writes to
dist/cache/config, report freshness and failure collection, and rollback on a
failed build gate. CI runs unit/integration fixtures plus `pack verify` against
committed dist, never a live upstream build. A manual live verification records
actual failures and warnings in durable validation documentation. It does not
require all third-party sources to be healthy to establish correct diagnostics.
Document any remaining metadata/configuration failures as blockers for subsequent
nightly publishing. Diagnostic probe failures describe reachability at their
observation time; routine metadata verification does not claim that reachability.

## Risks / Trade-offs

- Upstream semantics and regex dialects can drift. Mitigate with a pinned
  compatibility baseline, explicit support table and discriminating fixtures.
- A 200 response can be a challenge page. Reachability deliberately does not
  establish binary identity; state the limitation in reports and documentation.
- One reachable candidate says nothing about every architecture. Preserve this
  limit explicitly and defer device selection/manifest checks.
- Strict failures may initially expose broken sources or unsupported new keys.
  Report all of them; do not add silent exceptions to make the first run green.
- Full live checks consume network requests. Bound requests, reuse metadata
  and conditional validators, skip routine asset probes, and keep ordinary CI
  offline. The historical full runs motivate this smaller nightly contract.

## Migration Plan

Implement behind the existing command names, add the offline build gate after
fixture coverage passes, and add standalone offline verification to CI. No pack
schema or configuration migration is intended. Update README and version-detection
documentation to describe implemented behavior and remove claims that every
numeric-version re-import necessarily shows an update. Record a manual live run
and its limitations. Keep nightly automation for a subsequent change. Rollback
removes the gate and new commands' implementation without rewriting pack data.
