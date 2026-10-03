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

- Generation is a pure function of the upstream lists.
- Every per-app choice lives in the configuration the pack build already
  reads: overlays, the category map, family rules and denials.

**Non-Goals:**

- Changing the proposal workflow's job split, permissions or publication
  checks beyond the diagnostics it reports.

## Decisions

### Entries carry an Obtainium placeholder id

Obtainium treats an id of exactly twelve lowercase hex characters (or all
digits) as a placeholder and replaces it with the APK's package id on first
install. The generator emits the first twelve hex characters of the SHA-256 of
the normalized URL, so the id is stable across runs and needs no lookup.
Obtainium's own placeholder hashes the URL plus settings; matching its exact
input is unnecessary because only the format matters. Emitting the repository
name or a guessed package id was rejected: a guessed id that looks real makes
Obtainium refuse the install unless `allowIdChange` is set, and a placeholder
states honestly that the id is unknown.

### No per-project policy file; overlays and the category map instead

The project policy files carried names, release settings, a track-only kind and
categories. Overlays already patch any selected entry by URL, and the category
map already assigns categories by family, so the policy files duplicated them
with a second format, a second validator and per-source rules. They are
deleted. A consequence: an overlay patches the selected entry at its URL
whichever source wins, where a policy rule applied only to the generated
entry. The migration checks, for each moved setting, which source's entry the
overlay now patches, and records any URL where that is not the generated one.

### Every listed link becomes an entry; Obtainium decides what it can track

The pack imposes nothing on an app that Obtainium does not. Obtainium has
dedicated sources for about thirty hosts (itch.io, Codeberg, F-Droid,
IzzyOnDroid, SourceForge and others) and detects the source from the URL when
an app declares none. So generation emits every listed link, declares
GitHub or GitLab only where the URL makes that unambiguous, and otherwise
leaves the source type unset. A link Obtainium cannot use (today: a Google Play
page, a Modrinth mod page and a Nexus Mods page in the codm README) ships as an
entry that fails in Obtainium until the owner denies its URL, if they choose. Keeping a
host list in generation was rejected because it would copy Obtainium's source
table and go stale.

The same principle removes the pack's own source-type allowlist: ingestion no
longer fails a declared or missing type it holds no defaults for, rendering
fills defaults only for GitHub, GitLab and HTML and passes other entries'
settings through, and verification type-checks settings only where defaults
exist; the GitLab URL boundary, which accepted only a bare gitlab.com project
path, goes too, since Obtainium's GitLab source reads self-hosted instances.
The cost is that an entry of another type shows only the setting
controls its settings carry, until Obtainium fills them; whether Obtainium
fills missing keys on import is checked on a device before the change lands.

### Names come from the listing

A codm Project table link's text and a Quiver row's `project` are the
upstream curator's name for the app; the URL's last path segment is the
fallback.
Several listings of one URL with different names take the first in
case-insensitive order, so the result does not depend on list order. An
overlay `name` patch overrides it.

### Failure is limited to unreadable discovery

With no per-project requests there are no per-project failures. A discovery
that cannot be read, is malformed, or lists nothing fails, because
a candidate built from it would propose removing every entry. A repository
that moved or vanished upstream is simply listed differently, and the
proposal's added and removed lists show it.

### No rename lookups

Collapsing a renamed repository's listings needed a GitHub API call per
listing. Without it, a repository listed under its old and new names yields
two entries until the upstream list is fixed; a family rule or denial covers
it meanwhile, as for any URL alias.

## Risks / Trade-offs

- [A listed link has no Android release, or is a page Obtainium cannot track]
  → its entry ships and fails in Obtainium; a denial for its URL removes it.
  Generation no longer screens this.
- [Obtainium does not fill missing settings keys for an entry of a source type
  the pack holds no defaults for] → its setting controls stay hidden until
  set; a device check on the AYN Thor, with the owner's approval, establishes
  the behavior before the change lands.
- [Names change to the upstream curator's wording] → the first rebuild shows
  every changed name in the proposal; an overlay `name` patch restores one.
- [Generated entries carry placeholder ids] → the repeated-package-id report
  cannot see forks among generated entries; a family rule is the fix, as
  before.
- [A policy setting is lost in migration] → the migration task lists each of
  the nine settings and its overlay record, and a curation test asserts them.
- [Archive leaves the two emptied capability specs as files with no
  requirements] → delete those spec directories when the change is archived.

## Migration Plan

1. Implement the generator and the reduced report and proposal script, and
   delete the replaced modules and their tests.
2. Move the nine policy settings to overlay records and Quiver's categories to
   category map keys; delete the three configuration files.
3. Regenerate both catalogs from live upstream inputs, update composition
   rules and pins that select a generated entry by its old id, rebuild, and
   compare: every family selects the same project as before apart from the
   added GitLab ports, the uncategorized list names only new families, and
   `pack verify` passes.
4. Rollback is reverting the branch; the previous catalogs are in history.
