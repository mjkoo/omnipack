## Context

See proposal.md for motivation. The design-relevant facts below were
established by reading the live upstreams rather than their documentation.

- RJNY publishes both a source catalog (`src/applications.json` on `main`, 76
  entries under 72 unique ids) and two rendered exports committed alongside
  it. The source catalog stores per-app settings as an object and carries a
  `meta` block on 33 entries.
- Applying RJNY's `meta` flags as "drop `excludeFromExport`, then drop the
  per-variant opt-outs" reproduces its committed exports exactly: 62 and 66
  entries, with identical id sets and identical URLs per id. Its
  `nameOverride` and `urlOverride` flags are not applied by its own renderer.
- A package id is not unique per catalog. RJNY carries four ids twice, using
  the flags to pick a different project per variant; `info.cemu.cemu` resolves
  to `SSimco/Cemu` for single-screen and `sapphirerhodonite/cemu` for
  dual-screen. Four BBoi34 ids appear in both of its assets with a different
  category, name or APK filter.
- An app's source type is an explicit per-app field in Obtainium's import
  format, `overrideSource`. Across the two rendered upstream exports its only
  values are GitHub and HTML: 66 RJNY and all 25 BBoi34 entries are GitHub, 10
  RJNY entries are HTML. That field predicts the per-app settings key set
  exactly - every GitHub app carries one identical 29-key set and every HTML
  app one identical 29-key set, split 19 shared, 10 GitHub-only and 10
  HTML-only - and the rendered exports fill every key.
- Every release the projects behind the codm2000 links publish carries a
  host-assigned identifier distinct from its tag name, so keying the resolved-id
  cache on that identifier rather than on the tag costs nothing and does not
  depend on a project's tagging convention. A project that republishes under one
  rolling tag still gets a new identifier per release.
- A latest release does not always publish an APK. One project the README
  contributes today publishes a latest release whose only asset is a `.zip`, so
  a release with no eligible APK asset is a case the pipeline meets on its first
  run rather than a hypothetical one.
- RJNY's package-id resolver is 733 lines of standard library only, released
  into the public domain, and reads an APK's manifest through ranged requests
  against the archive tail rather than downloading the whole file.
- The project currently declares no runtime dependencies.

## Goals / Non-Goals

**Goals:**

- Rebuild both variants from scratch on every run, so the output is a pure
  function of the upstreams, the committed configuration and the cache.
- Detect upstream shape and semantics drift at build time rather than after a
  bad pack has been published.
- Keep the network cost of a nightly rebuild proportional to what actually
  changed upstream.

**Non-Goals:**

- Incremental or partial rebuilds. A build either produces both variants or
  fails.
- Preserving upstream byte formatting. Only our own output needs to be stable.
- Modelling Obtainium source types beyond the two the upstreams use.

## Decisions

### Read RJNY's source catalog, not its rendered exports

The rendered exports are committed artifacts refreshed by a release process,
so they can lag `main`, and they have already discarded the metadata that says
which variant an entry belongs to. Reading the source catalog keeps the pack
current and gives composition the structured settings it needs to patch.

The cost is that we reimplement RJNY's export rules and inherit the risk of
their changing. That risk is mitigated directly: a test fetches RJNY's own
committed exports and asserts our normalization reproduces their id sets and
per-id URLs. If upstream changes what a flag means, that test fails before a
wrong pack is published.

Alternative considered: consume the two rendered exports. Simpler, and it
would remove the reimplementation risk, but it pins us to whenever upstream
last released and loses the per-variant metadata we need.

### Compose each variant independently

The original sketch modelled one entry per package id carrying a set of
variant memberships. That cannot represent the Cemu case, where one id must
carry a different URL per variant, nor the BBoi34 ids that differ per variant.
Ingestion therefore produces candidates tagged with the variant they apply to,
and union, denylist, overlay and render all run once per variant. The variants
are related only by the check that dual-screen covers every single-screen id.

The stages run in a fixed order, because each guard's verdict depends on what
it observes: union by precedence, denylist removal, overlay target validation,
overlay application, then the dual-screen coverage check. The denylist
therefore sees entries exactly as their sources contributed them and is not
re-applied afterwards, which is safe because an overlay's patch may contain
neither the package-id field nor the source-type field: the id is the key an
overlay is matched under and every id-keyed guard has already run by the time
overlays apply, and the source type decides which settings key set the entry is
hydrated against. Both guards are on the field being present rather than on a
value being assigned, because an overlay is a JSON Merge Patch, where mapping a
field to null deletes it; a deletion of either field would otherwise slip past
a guard written on assignment. For the same reason an overlay's patch must
itself be an object: a package id mapped directly to null would delete the
whole entry under a uniform merge-patch implementation, removing an app with no
denylist entry to report it and no coverage check to notice. Overlay targets,
in turn, are validated against the set that survived the denylist. The denylist
names a package id, optionally scoped to one variant, because a package id is
the only identifier that means the same thing in both variants - one id can
legitimately carry a different URL in each. A denial scoped to the dual-screen
variant is a deliberate exclusion, so it exempts that id from the coverage
check. The denylist entry is the authority there, not the removal it performed:
the exemption holds whether or not an entry carrying the id was present in the
dual-screen variant to remove, so the two verdicts stay consistent when
upstream stops contributing the app to that variant while the single-screen one
still carries it. A denial that matches nothing is not an error, unlike an
overlay that patches nothing: the overlay has stopped being applied, while the
denial has already got what it asked for, so failing would break the scheduled
rebuild exactly when upstream removed the app the denial wanted gone. The
mismatch is reported as a stale exclusion instead, and a variant-scoped denial
is judged against the variant it names alone. A denial naming a variant the
pack does not have is still an error, since nothing about it was understood.

### No runtime dependencies

Every fetch is a plain GET against a public URL, and the vendored package-id
resolver already uses the standard library. Adding an HTTP client would buy
retry and connection reuse that a handful of requests per build does not need,
while complicating the nix packaging that the repository is set up for. A
small internal helper adds a timeout, a descriptive user agent, bounded
retries with backoff, and a host-scoped bearer token.

All pipeline HTTP goes through this shared helper, including catalog fetches
and the vendored resolver's release metadata requests, ranged APK reads and
full asset downloads. GitHub latest-release metadata is requested from
`https://api.github.com/repos/OWNER/REPO/releases/latest`; a repository link on
`github.com` does not make that host the release API host.

The dedicated `config/http.json` stores a `credentials` object mapping exact
hostnames to environment-variable names, with committed default content
`{"credentials": {"api.github.com": "GITHUB_TOKEN"}}`. It stores no token values.
Host matching uses the request's hostname case-insensitively, without the
project-URL normalization rules: no wildcard, subdomain inference or `www.`
removal is allowed. Registering `github.com` therefore does not register
`api.github.com` or any other host.

The helper attaches `Authorization: Bearer <token>` only when the contacted
host has a registered variable whose value is nonempty. An unset or empty
variable leaves requests unauthenticated, which public release metadata
supports. Unregistered hosts receive no Authorization header even when other
hosts' tokens are set. On a cross-host redirect the outgoing host's credential
is stripped; any credential for the destination must be selected independently
from that destination's exact registration. With the default map,
`github.com`, `raw.githubusercontent.com`, `codeberg.org` and release asset
hosts receive no token.

A fixture-backed cold-cache generated-project test must exercise the actual
resolver and shared helper together, intercepting only network transport. With
a fake `GITHUB_TOKEN`, it asserts the latest-release request reaches
`api.github.com` with that token, while unregistered catalog and asset hosts
receive none, including ranged reads, full-download fallback and a cross-host
redirect from an authenticated request. Separate cases cover an unset and an
empty token. Helper-only tests cannot prove the resolver uses authentication.

Alternative considered: `httpx`. Better ergonomics, but it does not earn a
dependency for this request volume.

### Compare URLs in one normalized form

Two places compare URLs written by different hands: a codm2000 README link
against what a higher-precedence source already contributes as a dual-screen
candidate, since a generated entry supplies that variant only, and the resolved
package id cache against a project. Left to spelling, each of them silently
fails open - a duplicate generated entry, a cache miss that costs a request.
One normalization is defined once and used at both sites: discard the scheme,
lowercase the host, drop a `www.` prefix, drop a trailing slash and a `.git`
suffix, and reduce a GitHub link to its owner and repository compared without
regard to case.

Two details are deliberate. The scheme is discarded rather than lowercased, so
that `http` and `https` spellings of one project compare equal; nothing in the
pipeline treats them as different projects, and upstreams do write both. Case
is folded in the host and in a GitHub link's owner and repository, which GitHub
itself treats case-insensitively, but not in an arbitrary path, where case can
be significant. Normalization is used for comparison only; the URL the pack
renders is the one its source wrote.

The denylist is not one of these sites. It names a package id rather than a
URL, so it needs no URL comparison at all.

### Vendor the package-id resolver

The upstream resolver is public domain and self-contained, and it already
solves the expensive part: reading an APK manifest through ranged requests
instead of downloading the archive. Vendoring it as a module, with its origin
recorded in the file, is cheaper and more predictable than reimplementing
binary XML parsing. Its command-line entry point and dotenv handling are
dropped; only the resolution path is kept, and its HTTP calls are routed
through the shared helper so release metadata and asset reads obey the same
credential rules as catalog fetches.

### Hydrate settings from a committed defaults table

Obtainium renders a control only for a settings key that is present, so a
partially populated entry hides switches in its app settings UI. Hydration
needs the full key set and default value for each source type, which Obtainium
does not publish in machine-readable form. An entry's source type is the
`overrideSource` field of the upstream record it came from; a generated entry
and an extras entry have no upstream record, so their type is derived from
their URL, GitHub for a github.com repository and HTML otherwise. The type is
fixed at ingestion and an overlay may not patch it, so the key set an entry is
hydrated against is always the one its own record or URL established. Anything
outside those two types fails the build rather than rendering an entry whose
settings key set we cannot fill. We commit a defaults table for the
GitHub and HTML source types, seeded from the values the upstream exports
already carry. The table records the Obtainium version its key set was seeded
from, which is the Obtainium release current when the table is committed, so a
later reader can tell how old the key set is. That record is a provenance
note, not a detector: the test asserting that hydrating a shared entry
reproduces upstream's rendered settings remains what catches a key Obtainium
has added since. Keys an entry sets that the table does not know,
which is how a future Obtainium setting first appears through an overlay, are
preserved and emitted after the known keys.

### Order output by content, not by input

Determinism is what lets the scheduled rebuild commit only on a real change.
Entries are ordered by primary category, then name, then package id, which is
a total order because ids are unique within a rendered variant. An entry's
categories are a list, so the primary category is defined as its first element,
and an entry with no category sorts as though that were the empty string, which
places uncategorized entries ahead of every named category. Serialization
pins separators and disables key reordering so that formatting does not drift
between runs or Python versions.

### Treat the package-id cache as committed state

The cache is read as a build input and written back as a build output, and it
is committed. That makes a nightly run cheap, keeps a project in the pack when
its release feed is briefly unavailable, and makes any change to a resolved id
visible in review rather than silent.

Visible only holds if an id is ever resolved a second time, so each cache entry
records the release its id was resolved from beside the id itself, and a build
resolves a project again exactly when that project's latest release identifier
differs from the recorded one, compared verbatim. What is recorded is the
release's host-assigned identifier, the stable id the release host assigns to a
release, rather than its tag name: a project publishing every build under one
rolling tag would otherwise never look as though it had released again, and the
trigger would never fire. Reading a release identifier is one request;
reading every eligible APK asset of that release is the expensive part a
matching identifier skips. The same trigger is what makes falling back to the
cached id on a failed resolution reachable at all, and it is why an app that
changed its package id upstream turns into a diff in the committed cache
instead of keeping a stale id forever. That read is also a request that can
fail on its own, on every warm project, so a failure to read the identifier
falls back to the cached id when there is one and leaves the project unresolved
when there is not. The same fallback applies when the latest release has no
eligible APK assets, its APKs disagree on the package id, or any eligible APK
cannot be read, including a size bound, fetch failure or unreadable manifest.
Each failure keeps the generated entry under its cached id and is reported;
only a project with no cached id is omitted and reported as unresolved. Failed
resolution never updates either cached field, including the recorded release
identifier, so the next build retries that release. Both fields are replaced
only after every eligible APK is read and all declare the same id. A newly
resolved id is written as soon
as it resolves rather than at the end of a successful build, so the cache is
deliberately exempt from the atomicity rule below: a build that fails later
keeps the resolution work it already paid for.

### Write output atomically

Automation commits whatever the distribution directory holds. Rendering both
variants fully in memory and replacing the files only once both succeed means
a build that fails partway leaves the previous pack in place. Rendering in
memory is not enough on its own, because publishing two files is two
replacements: the pair is therefore published so that a failure between them
restores both files to their previous contents, or removes both when the
directory held no output before. The guarantee covers the two import files; the
package id cache and the build report sit outside it.

## Risks / Trade-offs

- Upstream changes its catalog shape or its flag semantics, and we publish a
  wrong pack. → Parse failures abort the build, and the differential test
  against RJNY's own exports catches semantic drift.
- BBoi34 renames its release assets, so the configured patterns match nothing.
  → No match aborts the build rather than composing a pack without that
  source.
- A codm2000 README restructure breaks link extraction, silently shrinking the
  generated set. → The build report, written as JSON to `.build/report.json`,
  lists skipped and unresolved rows, and the scheduled run surfaces the
  report. It sits outside the distribution directory and is not committed, so
  its per-run contents cannot make an unchanged pack look like a change, and it
  is written on a failed build too, naming the stage and the error, so the
  scheduled run can explain an abort without being rerun. Its added and removed
  lists are computed against the import files as they stood before the build,
  read before either file is replaced.
- GitHub rate limits throttle package-id resolution on a cold cache. → The
  cache means a warm build resolves almost nothing, and the token registered
  for `api.github.com` is sent on release metadata requests when `GITHUB_TOKEN`
  is nonempty, including on a cold cache.
- A release host does not honour ranged requests, so an APK read falls back to
  a full download. → The vendored resolver already bounds that fallback by
  size and skips archives above it. The failure is reported and uses the cached
  id when available; without a cached id the project is omitted as unresolved.
- Vendored code drifts from its upstream and stops matching its behavior. →
  It is public domain and small, so it is maintained as our own code from the
  point it is vendored, with its origin recorded.

## Migration Plan

There are no consumers yet and no existing output to preserve. The first build
seeds `config/package-ids.json` and writes both variants into `dist/`. Both are
reviewed as a normal change before they become the files consumers fetch.
Rollback is reverting the commit, since the output is committed state.

## Open Questions

- Whether a cached package id should ever expire on age alone. Today an id is
  revisited only when the project publishes a new release, which is the only
  signal that the id could have changed.
- Whether the package-id cache needs an eviction policy for projects that
  leave the README. It grows by at most a few entries a year and costs nothing
  to carry, so it can stay append-only until it is a nuisance.
- Whether the two source types the pack supports will ever need a third. They
  are the only values the upstreams use, an extras entry derives its type from
  its URL, and any other value fails the build; adding a type later means
  extending the defaults table and that rule together.
