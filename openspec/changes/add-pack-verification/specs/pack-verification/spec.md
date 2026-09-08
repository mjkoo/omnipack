## Purpose

Establishes whether the rendered packs are structurally valid and whether their
configured update sources resolve, with reproducible diagnostics and an explicit
distinction between download reachability and binary or device compatibility.

## ADDED Requirements

### Requirement: Offline verification checks the serialized pair

The system SHALL validate both rendered import documents without fetching,
hydrating, repairing or rewriting them. It SHALL reject missing/unreadable files,
invalid JSON including non-finite numbers, non-object roots, non-list `apps`,
non-object `settings`, malformed app records, duplicate ids within a variant,
and unsupported source types. Each app SHALL have nonempty string `id`, `name`
and absolute HTTP(S) `url`, string `author`, string-list `categories`, and
`overrideSource` equal to GitHub or HTML. Track-only ids SHALL NOT be required
to follow Android package-name syntax.

`additionalSettings` SHALL be a string decoding to an object with every key
defined by the committed defaults for its source type, with correctly typed
known settings. Nested HTML steps and header records SHALL be checked. Optional
`preferredApkIndex`, when present, SHALL be an integer, not a boolean. Unknown
fields SHALL NOT be removed or rejected solely for being unknown offline.
`settings.categories` SHALL decode from a string to a mapping of the exact
observed category names to unsigned 32-bit integer ARGB colours, consistent with
the configured colours and existing deterministic fallback rule. Other configured
pack settings SHALL agree with the rendered settings block.

#### Scenario: A rendered settings object is not string encoded

- **WHEN** an entry carries an object directly as `additionalSettings`
- **THEN** verification fails with its variant, id and field identified
- **AND** no repair or network request occurs

#### Scenario: Invalid entries in both variants

- **WHEN** one variant contains duplicate ids and the other contains a setting
  of the wrong type
- **THEN** both independently discoverable errors are reported

#### Scenario: Unknown fields are structurally valid

- **WHEN** a structurally valid entry includes an unknown extra setting
- **THEN** offline verification preserves the input and does not claim that the
  setting is supported by live resolution

### Requirement: Offline verification checks local composition constraints

The system SHALL validate denylist and overlay configuration using the existing
composition rules, including overlay object shape and forbidden id/source edits.
It SHALL reject an overlay target absent from its applicable rendered variants,
a denied id remaining in an applicable variant, or a single-screen id absent
from dual-screen without a dual-screen-scoped denylist exemption. A common
overlay target present in either variant SHALL be valid. Stale denylist entries
SHALL remain non-fatal. Checks SHALL NOT require fresh upstream catalogs or
claim that target existence proves that an overlay's values were applied.

#### Scenario: Dual-only overlay has no target

- **WHEN** the named id exists only in the single-screen file
- **THEN** verification reports the stale dual overlay as an error

#### Scenario: An explicit exclusion permits different coverage

- **WHEN** a single-screen id is absent from dual-screen and is denied for dual
- **THEN** that absence passes the coverage check even if no dual entry was removed

### Requirement: Live checks honor a declared compatibility boundary

The system SHALL provide live GitHub and HTML resolution against the repository's
Obtainium v1.6.14 compatibility baseline. It SHALL document supported settings
and explicit device-independent limitations. It SHALL support the release and
HTML behavior specified below and SHALL reject active unsupported resolution
features with the setting and entry identified, rather than ignoring them.

Unsupported features SHALL include archive downloads, non-date/non-none GitHub
sorting, `verifyLatestTag`, request proxies, embedded credentials, disabled TLS
verification, device-dependent HTML intermediate filtering, and HTML
pseudo-versioning without explicit version extraction. Inactive defaults SHALL
not activate unsupported features. Unknown additional settings SHALL produce a
live compatibility error unless explicitly classified as harmless presentation
or device controls. Final device architecture filtering and preferred APK
selection SHALL be outside the guarantee and SHALL be identified as such.

#### Scenario: Unsupported feature is enabled

- **WHEN** an entry enables ZIP downloads
- **THEN** live verification reports unsupported resolution behavior
- **AND** it does not pass the entry by checking only a direct APK

#### Scenario: Inactive HTML pseudo-version default

- **WHEN** an HTML entry successfully extracts an explicit version and retains
  its default pseudo-versioning setting
- **THEN** that unused default does not cause a compatibility error

### Requirement: GitHub resolution respects configured release selection

The system SHALL inspect up to the first 100 releases and report the inspected
window. It SHALL support `date` and `none` ordering, draft/prerelease eligibility,
title and notes filters, older-release fallback, direct APK assets, APK filename
regex filtering and inversion, title versions and release/asset dates according
to the pinned provider. With older-release fallback disabled, only the first
non-draft release permitted by the prerelease setting SHALL be considered; a
title, notes or APK mismatch SHALL fail rather than advance to another release.

An installable entry SHALL select a release with eligible APK candidates and a
nonempty version. A track-only entry SHALL apply the same configured filtering
without requiring an APK, and SHALL use the pinned provider's tags fallback when
no release qualifies. A network failure SHALL NOT trigger tags fallback. Once
metadata selects a release, failed reachability SHALL NOT select an older one.

#### Scenario: Latest eligible release has no matching APK

- **WHEN** fallback is enabled and an older release has a matching APK
- **THEN** resolution selects the older release and records its identity

#### Scenario: Title filter fails with fallback disabled

- **WHEN** the first non-draft, permitted-prerelease release fails the title filter
- **THEN** resolution fails even if a later inspected release matches

#### Scenario: Track-only resource has no APK

- **WHEN** an eligible release supplies a valid effective version but no APK
- **THEN** a track-only entry passes resolution without a download probe

#### Scenario: Selected release has dead downloads

- **WHEN** asset probing is explicitly enabled and every eligible APK candidate
  in the selected release is unreachable
- **THEN** the entry fails even if an older release has a reachable APK

### Requirement: HTML resolution follows the configured path

The system SHALL support anchor and link-text filtering, relative URLs resolved
against final response URLs, links outside anchor tags including JSON strings,
configured non-secret request headers, intermediate steps, alphanumeric and
last-segment sorting, skip/reverse sorting, custom link filters, APK filters and
inversion, and URL/whole-page version extraction. Intermediate entries with empty
custom-link filters SHALL be ignored, matching the pinned provider. Each remaining
step SHALL select the last link after its configured filtering and sorting. More than ten
nonempty intermediate steps SHALL fail explicitly. When final link selection is
required, the final selected link SHALL be the last remaining candidate and SHALL
be the sole HTML download candidate. An empty selection at an active intermediate
step SHALL fail with the page and stage identified. Installable entries SHALL
require a final download candidate and SHALL fail on an empty final selection.
Track-only entries using whole-page version extraction MAY succeed with a
nonempty effective version and no eligible final download links, but SHALL still
follow all configured active intermediate steps. URL-based version extraction
SHALL require a usable final selected URL, including for track-only entries.

#### Scenario: Two intermediate pages lead to the download

- **WHEN** configured steps select a release directory and then its Android page
- **THEN** the final APK and extracted version come from that traversal
- **AND** links elsewhere on the starting page do not bypass it

#### Scenario: Selected HTML download is unavailable

- **WHEN** asset probing is explicitly enabled and the final selected link fails
  the reachability check
- **THEN** the entry fails without probing an older link as a substitute

#### Scenario: Track-only HTML page has a version but no download links

- **WHEN** configured intermediate traversal reaches a final page with a valid
  whole-page version extraction but no eligible download links
- **THEN** a track-only entry succeeds without a download probe
- **AND** the same configuration on an installable entry fails final selection

#### Scenario: Track-only HTML still requires its extraction input

- **WHEN** a track-only entry has an empty active intermediate selection, or uses
  URL-based extraction without a usable final selected URL
- **THEN** resolution fails rather than bypassing traversal or inventing a URL

#### Scenario: Links are embedded in JSON

- **WHEN** outside-anchor extraction is enabled for a JSON response
- **THEN** string URLs are extracted, resolved and filtered using the entry settings

### Requirement: Effective versions are real extraction results

The system SHALL compute the effective version using the configured tag/title
or HTML URL/page input, regex and group substitution, and applicable date
override, rather than emitting a placeholder or an unprocessed fallback on
extraction failure. Regex behavior SHALL use the last match and the pinned
provider's default group, numeric or `$N` references, concatenation and unmatched
optional-group behavior. Malformed or unsupported regex constructs, invalid
groups, no match and empty results SHALL be errors. A requested date override
SHALL require a usable date and emit microseconds since the Unix epoch. The
report SHALL identify the raw value, effective value and version origin.
HTML `releaseDateAsVersion: true` SHALL be an unsupported active setting rejected
before HTTP because this source supplies no usable release date; false SHALL be
accepted. The supported regex subset SHALL translate ECMAScript whitespace, dot
line terminators and strict end anchors, including class-contained whitespace.
Pattern backreferences, numeric/octal escapes, class-contained `\S`, character-
class escapes beside hyphens and repeated groups containing captures SHALL be
explicitly unsupported rather than interpreted with Python semantics.

#### Scenario: Configured regex does not match

- **WHEN** a release has tag `continuous` and the configured numeric extraction
  finds no match
- **THEN** verification fails rather than reporting `continuous` as extracted

#### Scenario: Multiple matches and optional groups

- **WHEN** a version regex matches multiple times with a concatenated group template
- **THEN** extraction uses the last match and substitutes unmatched optional groups
  as empty strings, failing if the final output is empty

#### Scenario: Asset date controls the effective version

- **WHEN** release-date versioning and latest-asset-date selection are enabled
- **THEN** the effective version uses the date selected under the pinned provider
  rules and the report identifies date versioning

### Requirement: Reachability checks are bounded and do not prove binary identity

Ordinary live verification SHALL require successful metadata resolution, a
nonempty effective version and eligible candidates for installable entries,
without requesting those downloads or claiming reachability. Only when asset
probing is explicitly enabled SHALL an installable entry additionally require
at least one selected eligible APK candidate to respond to a bounded GET with
status 200 or 206 and a nonempty response prefix. The system SHALL read at most
1024 response-body bytes per probe and close the response, including when the
server ignores Range. It SHALL NOT require HEAD support or download a whole APK.
The system SHALL report attempted candidate failures as warnings when another
candidate succeeds, and as an entry failure when none succeeds. Track-only
entries SHALL not require download probes.

The diagnostic guarantee SHALL be described as source resolution and HTTP reachability,
without asserting APK identity, signatures, installability, architecture coverage
or correctness of a server's content. A probe SHALL use at most three attempts
with bounded backoff and a 30-second per-request timeout, and follow at most ten
redirects. Metadata responses SHALL be limited to 10 MiB. Exhausted failures
SHALL be errors and SHALL NOT be replaced by a prior run's success.

#### Scenario: Server ignores Range

- **WHEN** an APK endpoint responds with 200 and a body larger than the probe limit
- **THEN** the probe reads only its prefix, closes the response and can pass

#### Scenario: One candidate succeeds

- **WHEN** the first APK candidate fails and a second candidate in the same
  selected release responds successfully with data
- **THEN** the entry passes with the first failure recorded as a warning

### Requirement: Live requests minimize work and respect host limits

The system SHALL reuse identical metadata responses and failures within a run,
including release responses shared by variants with different selection settings.
Probe diagnostics SHALL also reuse identical requests and failures within a run.
Selected candidate URLs SHALL be passed directly to probes without re-resolving
the latest release. Separate per-variant evidence SHALL remain available.

Live requests SHALL have a minimum two-second per-host interval, including
retries and redirects. GitHub API requests SHALL require a nonempty credential
from the configured exact-host environment mapping before any API request.
Server-directed retry delays SHALL be honored within a bounded wait. A host
that reports rate limiting or a server delay beyond that bound SHALL receive no
more requests in that invocation; unrelated hosts SHALL continue. Suppressed
entries SHALL record network errors, not successful skips.

GitHub metadata MAY persist in a bounded conditional-response cache under
`.build/`. Every use in a later invocation SHALL require a fresh authenticated
304 response for the exact metadata request. Cache identities and values SHALL
exclude credentials and credential-derived hashes. Invalid cache data SHALL
fall back to a normal request. Failed acquisition SHALL NOT use stale metadata
or an earlier verification success. Probe results SHALL NOT persist across runs.

#### Scenario: Both variants select from one repository

- **WHEN** variants reference the same GitHub metadata request with different
  release or APK settings
- **THEN** one response is fetched and each variant applies its own selection
- **AND** later asset diagnostics do not fetch releases again

#### Scenario: GitHub authentication is missing

- **WHEN** a live GitHub API request has no configured credential value
- **THEN** it fails clearly before contacting the API

#### Scenario: A host reports rate limiting

- **WHEN** a response reports a rate limit or an excessive retry delay
- **THEN** subsequent entries for that host produce errors without another request
- **AND** entries using other hosts can still run

#### Scenario: Metadata is unchanged on a later night

- **WHEN** GitHub returns an authenticated 304 for cached metadata validators
- **THEN** that response revalidates the cached body for current resolution
- **AND** a timeout or error instead would fail without using the cached body

### Requirement: Live requests preserve credential boundaries

The system SHALL route live requests through the shared HTTP policy, using
credentials from exact-host environment mappings only. Redirects SHALL rebuild
authorization for the destination host. Configured non-secret HTML headers,
including User-Agent, SHALL be honored. Pack-provided Authorization or Cookie
headers and embedded credentials SHALL produce compatibility errors. Reports
SHALL exclude secret header values and redact URL credentials and query values.

#### Scenario: Authenticated API redirects to an asset host

- **WHEN** a request leaves an authenticated GitHub API host for an unregistered host
- **THEN** the destination receives no API credential
- **AND** the report contains no token value

### Requirement: Version lint evaluates effective GitHub versions

The system SHALL warn when a successfully resolved GitHub effective version does
not match the documented numeric-shape heuristic: optional `v` or `V`, at least
two dot-separated numeric components, and optional prerelease/build suffixes
introduced by `-` or `+` with ASCII letters, digits, dots or hyphens. The heuristic
SHALL match the entire value and SHALL NOT be described as a comparison with
the installed APK version. Track-only, disabled version detection and intentional
date versioning SHALL be recorded as distinct classifications without that warning.
Release-title or extraction-regex settings alone SHALL NOT suppress warnings.
Warnings SHALL NOT cause a nonzero verification result.

#### Scenario: A regex leaves a rolling tag unchanged

- **WHEN** extraction succeeds but the effective version is `continuous`
- **AND** numeric version detection is enabled without intentional date versioning
- **THEN** the report includes a version-format warning

#### Scenario: Effective version is numeric

- **WHEN** extraction turns a release title into `v1.2.3-beta1`
- **THEN** the effective version passes the numeric-shape lint
- **AND** the result does not claim agreement with Android versionName

### Requirement: Verification evidence belongs to an exact input snapshot

Standalone verification SHALL write `.build/verify.json` separately from the
build report. It SHALL include schema and verifier versions, the compatibility
baseline, mode (`offline`, `live`, or `live-probe`), observation times, completion
and status, input fingerprints,
errors, warnings, and per-variant entry results with resolution and probe evidence.
Fingerprints SHALL cover exact bytes of both output files, the denylist, both
overlays, pack settings and HTTP configuration, identifying missing/unreadable
inputs explicitly and excluding token values. Input changes during a run SHALL
prevent a successful result for the current files.

The system SHALL write an incomplete running record before live requests and
atomically replace it on completion, including failed completion. Offline errors
SHALL prevent live requests. After offline success, independent live failures
SHALL be collected across both variants instead of stopping at the first entry.
Equivalent resolution inputs SHALL share requests within a run, but each variant
and id SHALL retain its own result. HTML resolution identity SHALL preserve the
exact configured request URL, including scheme, authority, path, trailing slash
and query, unless request equivalence is established; project URL normalization
SHALL NOT establish this equivalence. Success SHALL require completion and no
errors, regardless of any cached package id or prior verification report.

#### Scenario: Same package id has different variant settings

- **WHEN** single-screen and dual-screen entries share an id but differ in URL or
  resolution settings
- **THEN** each is resolved with its own configuration and reported separately

#### Scenario: Trailing-slash HTML endpoints have different results

- **WHEN** two HTML entries have identical settings and configured URLs differing
  only by a trailing slash, but the endpoints serve different versions and
  relative download links
- **THEN** each entry resolves its own version and download URL using its own
  final response URL as the relative base
- **AND** project-normalized URL equality does not permit sharing their results

#### Scenario: A live attempt is interrupted

- **WHEN** verification stops after writing its running record but before completion
- **THEN** the stored report is incomplete and cannot be presented as a success

#### Scenario: A second entry fails independently

- **WHEN** two entries fail at different live stages after offline validation passes
- **THEN** the completed report contains both failures and the run fails
