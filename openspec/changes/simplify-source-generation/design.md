## Context

This change assumes `key-merge-by-url` has landed: families form by normalized
URL, a family rule claims its whole URL, denials and overlays key on URLs, and
every rendered app carries `allowIdChange: true`. With that in place nothing
downstream needs a generated entry's real package id. See proposal.md for why.

Today's generation state that moves elsewhere:

- `config/codm-projects.json`: five rules. Emulnk, Showdown, Heimdall and
  DW2003 set names and release or APK settings; Kanto Gear is a track-only
  tracker with a rationale and installation text.
- `config/quiver-projects.json`: Melee PC prerelease inclusion, Silent Hill
  and LEGO Island APK filters, and five category assignments.
- `config/http.json`: the `api.github.com` token registration, used only by
  generation.

## Goals / Non-Goals

**Goals:**

- Generation is a pure function of the upstream inputs and the committed
  catalog's ids and URLs.
- Every per-app choice lives in the configuration the pack build already
  reads: overlays, the category map, family rules and denials.

**Non-Goals:**

- Changing the proposal workflow's job split, permissions or publication
  checks beyond the diagnostics it reports.

## Decisions

### Entries keep their committed id; new ones carry an Obtainium placeholder

When a regenerated entry's normalized URL matches an entry in the committed
catalog, it keeps that entry's id. Generation already reads the committed
catalog to report added, removed and changed entries, so this adds no input or request,
and it keeps the real package ids today's catalogs carry: composition rules and
pins that select a generated entry by id, installed apps and the
repeated-package-id report keep working through the migration. A missing
committed catalog means every entry is new; an unreadable or malformed one
fails generation, because guessing would change published ids. A committed
catalog with two entries whose URLs normalize to the same project counts as
malformed: either id could be kept, so generation fails and names the
normalized URL and the competing ids rather than pick one.

A URL with no committed entry gets a placeholder. Obtainium treats an id of
exactly twelve lowercase hex characters (or all digits) as a placeholder and
replaces it with the APK's package id on first install. The generator emits the
first twelve hex characters of the SHA-256 of the normalized URL, so the id is
stable across runs and needs no lookup. Obtainium's own placeholder hashes the
URL plus settings; matching its exact input is unnecessary because only the
format matters. Emitting the repository name or a guessed package id was
rejected: a guessed id that looks real makes Obtainium refuse the install
unless `allowIdChange` is set, and a placeholder states honestly that the id is
unknown. Replacing every id with a placeholder was rejected because it would
change every published id and every id-keyed selector at once for no gain.

### No per-project policy file; overlays and the category map instead

The project policy files carried names, release settings, a track-only kind and
categories. Overlays already patch any selected entry by URL, and the category
map already assigns categories by family, so the policy files duplicated them
with a second format, a second validator and per-source rules. They are
deleted. A consequence: an overlay patches the selected entry at its URL
whichever source wins, where a policy rule applied only to the generated
entry. So the migration moves only winners: a setting becomes an overlay record
only where the generated entry is the current published winner for that URL.
Where a pin or source precedence selects another source's entry (codm's EmuLnk
today), the setting is dropped rather than moved, because an overlay there
would patch the other source's entry and change what is published. Either way
every published winner's settings stay unchanged, and the migration asserts
that by comparing the packs built before and after it.

### Screen on upstream-published asset names; otherwise every listed link becomes an entry

The pack imposes nothing on an app that Obtainium does not, and generation
inspects no project. But some upstreams already publish what their projects
release: the Quiver index names `platformMetadataUrl`, a file with one entry
per listed repository giving its forge, repository, release tag and asset
names. Reading it is one more upstream read, with no repository API, release
or APK request. The asset names describe only each project's latest release,
while Obtainium by default falls back to older releases when the latest has no
matching APK, so a project whose latest release carries no `.apk` asset may
still install. The screen therefore gates admission and never evicts: where a
source's upstream publishes asset names, discovery keeps a listed project when
its entry names an asset ending in `.apk` (case-insensitive) or when the
committed catalog already holds an entry with its normalized URL. A project not
yet committed with no such asset, or no entry, is reported and skipped, never a
failure. A committed entry leaves only when the upstream stops listing it or
the owner denies it; a committed project whose latest release ships no APK,
such as one selected by a composition rule under its real package id, stays.
Screening reads only the committed catalog's URLs, which generation already
reads for ids, so it adds no input. The asset-name file is discovery input:
unreadable or malformed, it fails generation like the lists. Today this keeps
Quiver's GitLab ports out, since the file names no APK asset for them; they
join once it does. The rule is stated over what an upstream publishes, not
over one source, so a source that publishes no asset names (the codm README)
is not screened.

For every project discovery keeps, Obtainium decides what it can track.
Obtainium has dedicated sources for many hosts (itch.io, Codeberg, F-Droid,
IzzyOnDroid, SourceForge and others) and detects the source from the URL when
an app declares none. So generation emits every kept link, declares GitHub or
GitLab only where the URL makes that unambiguous, and otherwise leaves the
source type unset. A link Obtainium cannot use (today: a Google Play page, a
Modrinth mod page and a Nexus Mods page in the codm README) ships as an entry
that fails in Obtainium until the owner denies its URL, if they choose.
Keeping a host list in generation was rejected because it would copy
Obtainium's source table and go stale.

Quiver rows form their URL from `repositorySource` and `repository`: an absent
forge means GitHub, forge names match case-insensitively, `github` and
`gitlab` form github.com and gitlab.com URLs (a GitLab path may include
subgroups), and a row with another forge or a missing or invalid repository is
reported and skipped like a screened-out project.

The same principle removes the pack's own source-type allowlist: ingestion no
longer fails a declared or missing type it holds no defaults for, rendering
fills defaults only for GitHub, GitLab and HTML and passes other entries'
settings through, and verification type-checks settings only where defaults
exist; the GitLab URL boundary, which accepted only a bare gitlab.com project
path, goes too, since Obtainium's GitLab source reads self-hosted instances.
The cost is that an entry of another type shows only the setting
controls its settings carry, until Obtainium fills them; whether Obtainium
fills missing keys on import is an open question, recorded under Risks.

### Names and URLs come from the listing, independent of list order

A codm Project table link's text and a Quiver row's `project` are the
upstream curator's name for the app; the URL's last path segment is the
fallback. Curators decorate names (a codm link reads "Kanto Gear 🤖"), so
generation trims trailing emoji and other-symbol characters (keeping
punctuation, math and currency signs, as in `C++`) and surrounding whitespace
from every listing-derived name, the same way for every source.
Several listings of one URL with different names take the first in
case-insensitive order, with names equal ignoring case (`App` and `app`)
ordered by code point, so `App` wins whichever row upstream lists first and
reordering rows never changes the name. An overlay `name` patch overrides the name.

An entry's URL is its project URL, never a deep link. When the committed
catalog holds an entry with the same normalized URL, the regenerated entry
keeps that entry's URL verbatim, the same way it keeps the id, and so keeps the
author derived from it: re-casing or reordering upstream rows then changes no
catalog bytes, whereas choosing among listed spellings on every run would
rewrite the URL and author whenever upstream re-cased the smallest one. Only a
URL with no committed entry is chosen from the listings: each listing is first
reduced to the project URL URL normalization identifies (its scheme, its
lowercased host without `www.`, any port other than its scheme's default, and
the project path in the listing's case, which for a GitHub link is owner and
repository alone, so a releases, tags, blob or release-asset link becomes the
repository root, and for a gitlab.com project link stops before GitLab's
reserved `/-/` route segment, though a GitLab site page such as a group's is
kept whole), and an `https` reduced URL is preferred to an `http` one, then
the smallest in code point order wins, with the author taken from
it. Emitting a listed spelling unreduced was rejected because a codm link to a
release asset would become an entry URL Obtainium reads as something other
than the repository. On hosts other than GitHub and gitlab.com the reduction
keeps the path, query and fragment normalization retains, since the system cannot know which
parts of another host's link identify the project.

### Failure is limited to unreadable input and an empty candidate

With no per-project requests there are no per-project failures: an
unformable row or a project screened out for publishing no APK is reported and
skipped. A discovery input that cannot be read or is malformed fails; so does a
malformed codm Project table beside a valid one, since a partial read would
propose removing that table's projects. The empty-result protection is measured
on the candidate, not on the upstream list: whenever the candidate would keep
no entry, whether the list has no rows, every row is skipped, or every listed
project is screened out with no committed project still listed, generation
fails, because that candidate would propose removing every entry. A per-row
skip or screen never fails on its own. A repository
that moved or vanished upstream is simply listed differently, and the
proposal's added, removed and changed lists show it.

Generation reads its inputs with the plain credential-free HTTP client the
build already uses, with no response-size bound beyond the client's own and
no redirect containment: redirects are followed as the client follows them.
The bounded, redirect-checking fetch Quiver discovery uses today goes with
`source_http.py`. The upstream lists are trusted content, and every candidate
they produce lands only through a reviewed PR, so rejecting a redirect that
leaves the index's host and directory adds no correctness, and a size bound
would only guard CI memory against small JSON files. A location the index
names outside its host and directory still fails as a malformed index, since
that is a property of the index's content, not of transport.

### No rename lookups

Collapsing a renamed repository's listings needed a GitHub API call per
listing. Without it, a repository listed under its old and new names yields
two entries until the upstream list is fixed; a family rule or denial covers
it meanwhile, as for any URL alias.

## Risks / Trade-offs

- [A listed link has no Android release, or is a page Obtainium cannot track,
  on a source whose upstream publishes no asset names] → its entry ships and
  fails in Obtainium; a denial for its URL removes it.
- [An upstream asset-name file is stale] → a new project that newly publishes
  an APK stays out until the upstream refreshes the file; the report lists
  every screened-out project, and the next run follows the refreshed file.
- [A committed project stops shipping Android builds] → the screen never
  evicts, so its entry stays in the catalog until the upstream delists it or
  the owner denies its URL; the cost is accepted because evicting on the latest
  release's assets would drop projects Obtainium still installs from an older
  release.
- [Obtainium may not fill missing settings keys on import for an entry of a
  source type the pack holds no defaults for] → this is an open question; if
  it does not, that entry's setting controls stay hidden until set, and an
  overlay can supply the keys an app needs.
- [An upstream redirect serves a list from another host] → generation follows
  redirects as the HTTP client does, so a list could be read from a host
  other than the index's; every candidate lands only through PR review, which
  shows each added, removed and changed entry.
- [Names change to the upstream curator's wording] → the first rebuild lists
  every renamed entry as changed in the proposal; an overlay `name` patch restores one.
- [Newly listed generated entries carry placeholder ids] → the
  repeated-package-id report cannot see forks among them; a family rule is the
  fix, as before.
- [The full-suite check with a candidate catalog installed fails on category
  coverage] → curation assertions that a build has no uncategorized family and
  no stale category key would block a valid catalog-only proposal, contrary to
  pack-curation's rule that such a proposal needs no other edit; they are
  rescoped to report those lists, and catalog-only addition and removal
  regression cases guard it.
- [A policy setting is lost in migration] → the migration task lists each
  setting with its overlay record or, where another source's entry wins, as
  dropped; a curation test asserts the moved ones, and a before-and-after build
  comparison asserts every published winner's settings are unchanged.
- [A dropped setting matters if the winner later changes] → when a pin or
  precedence change makes the generated entry win, it ships with default
  settings until the owner adds an overlay record for its URL.
- [Archive leaves the two emptied capability specs as files with no
  requirements] → delete those spec directories when the change is archived.

## Migration Plan

1. Implement the generator and the reduced report and proposal script, and
   delete the replaced modules and their tests.
2. Move each policy setting to an overlay record where the generated entry is
   the current published winner for its URL, and drop it where a pin or
   precedence selects another source's entry (codm's EmuLnk today); move
   Quiver's categories to category map keys; delete the three configuration
   files. Compare both pack variants before and after: every published
   winner's settings are unchanged.
3. Regenerate both catalogs from live upstream inputs and rebuild; existing
   entries keep their ids, so composition rules and pins need no update.
   Compare: every family selects the same project as before apart from newly
   listed entries, committed entries the upstream still lists stay whether or
   not their latest release names an APK asset, newly listed Quiver projects
   screened out for publishing no APK are reported and absent, the
   uncategorized list names only new families, and `pack verify` passes.
4. Rollback is reverting the branch; the previous catalogs are in history.
