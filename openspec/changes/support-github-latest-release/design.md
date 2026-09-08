## Context

See `proposal.md` for motivation. The existing GitHub resolver already separates
metadata acquisition, ordering/filtering, and effective-version processing. The
live HTTP client provides request reuse and bounded authenticated requests.
`verifyLatestTag` is currently classified as active unsupported, and compatibility
tests explicitly expect that finding for the committed packs.

The behavior reference is the repository's
[Obtainium v1.6.14 GitHub provider](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/app_sources/github.dart),
specifically `_fetchReleaseDetails`, `_positionLatestRelease`, and
`fetchReleaseDetailsWithTagFallback`. Latest lookup changes candidate priority;
it does not bypass selection filters. The provider requests latest metadata
before list metadata, supplements an absent identity, and promotes the matching
record after sorting. The shared fallback path also constructs `/tags/latest`.

## Goals / Non-Goals

**Goals:** Extend the existing resolver with a small, testable metadata and
ordering operation. Keep all transport policy in the existing HTTP client and
all effective-version logic in its current processing stage.

**Non-Goals:** No new resolver framework, new report format, pagination, source
refresh, or attempt to repair Obtainium's endpoint choices. No device or asset
traffic is needed to establish selection semantics.

## Decisions

### Integrate latest lookup into the existing acquisition path

In `resolution/github.py`, fetch and validate latest metadata only when the
setting is true, before the corresponding list request. Keep a helper for exact
tag-name-or-name identity and a pure ordering operation that accepts optional
latest metadata. Slice list responses before supplementation. Match against the
bounded list and use its record when present; otherwise prepend the supplemental
record before sorting. Promote after sorting so other candidates retain their
existing relative order. Do not mutate cached response documents.

Passing optional latest metadata through selection avoids duplicating filters
and version logic. Selecting `/releases/latest` directly would bypass configured
fallback; just enabling the support classifier would silently ignore behavior.
The classifier moves this setting into implemented support only alongside the
resolver implementation and tests.

### Preserve failure and track-only semantics explicitly

Reuse the existing request and invalid-response error categories, with messages
identifying whether releases/latest, releases, tags/latest, or tags failed.
Require a latest response object and a nonempty string identity, rejecting invalid
metadata before the list call. This adds deliberate validation at the existing
fail-closed boundary instead of reproducing dynamic-type failures.

For track-only fallback, reuse the same acquisition and prioritization operation
with the tags endpoint. A latest HTTP error, including 404, never initiates
fallback. Only exhausted release selection can enter it; version/date extraction
errors still fail directly. A tags/latest failure remains a failure, even if a
plain tags request could have succeeded. Bypassing that request would widen our
claimed compatibility beyond the pinned behavior.

### Retain the evidence format and request infrastructure

Keep `window_limit` as the list limit of 100, with `inspected_count` including a
supplemental latest release only when absent from that list. Thus 101 is valid
without pagination. Tags fallback retains the existing release inspection count;
document that this field is not a total HTTP-request or tag count. Selected
identity, candidates, raw/effective versions, and version origin continue through
the current result type and report schema.

Use the same metadata client for latest requests, inheriting response and failure
reuse within a run, authentication, pacing, retries, and host suppression. Latest
responses are reused only within a run; they do not receive persistent caching or
conditional revalidation. Preserve the existing persistent-cache scope: only
eligible release and tag list requests with `per_page=100` receive conditional
revalidation. No new cache or wider cache eligibility is warranted. Mixed-setting
variants can share the list response while computing different selections.

### Verify behavior with controlled metadata

Extend resolver tests for both supported sort modes, latest already first,
latest promotion, absent latest including a full 100-record window, list-record
precedence over a differing latest body, exact identities and name fallback,
draft/prerelease eligibility, filter/fallback combinations, and title/regex/date
processing after promotion. Include absent/false settings and unchanged requests.

Add failure fixtures for status errors including 404, transport errors, invalid
JSON, non-object latest bodies, and invalid identities. Exercise successful
track-only fallback with controlled tags/latest data, failure before its tag list,
and no fallback after version/date failure. Integration tests must establish
latest response/failure reuse across variants, independent mixed-setting
selection, truthful inspection counts through report reading, and zero routine
asset requests. Update the committed-pack compatibility assertion to expect no
currently active unsupported settings, without claiming live upstream health.

## Risks / Trade-offs

- Extra metadata costs: latest-enabled repositories add one distinct lookup to
  the ordinary release path per run. Existing in-run reuse limits repeated latest
  lookups across variants; persistent conditional revalidation remains available
  only for eligible list responses. Unit tests assert request budgets.
- Latest endpoint errors block otherwise usable catalogs: this is intentional
  compatibility behavior. Diagnostics identify the endpoint; no stale success
  or ordinary-order substitution is allowed.
- Separate latest and list responses can disagree: retain the list record when
  identities match, and cover differing assets in fixtures.
- Recorded observations become stale: increment verifier identity from `0.2.2`
  to `0.3.0`, retaining report schema `1`. Existing freshness checks invalidate
  old evidence without removing historical validation records.

## Migration Plan

Land resolver support, its spec delta, tests, documentation and verifier identity
together during the apply workflow. Update current compatibility guidance and add
a dated explanation to validation documentation while preserving historical live
observations. Run focused tests followed by `just check-all`. A full live refresh
is not an acceptance requirement and no generated pack or overlay edits are
expected. Reverting the change restores the previous explicit unsupported error;
no persisted input migration is needed.
