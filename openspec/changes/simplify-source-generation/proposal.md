## Why

The codm and Quiver generators look every listed repository up on GitHub,
select a release, download its APKs and read their manifests, then fail the
whole run when one project cannot be resolved; per-project policy, skips,
retention and credentials exist to manage that. None of it is something
Obtainium requires: given a repository URL, Obtainium finds releases and
learns the package id at install. Once families key on project URLs (the
`key-merge-by-url` change, which this change builds on), the generator only
has to turn an upstream list into Obtainium entries. Generated entries keep
the ids the committed catalogs already give them, so existing package ids, and
the composition rules, pins and installed apps that know them, are unchanged;
only a newly listed project gets an Obtainium placeholder id.

## What Changes

- **BREAKING** One generator serves every generated source. It reads the
  source's upstream inputs (the codm README's Project tables; the Quiver index,
  its lists and the release asset-name file the index names) and makes no other
  request: no repository API, release or APK.
- **BREAKING** Where a source's upstream publishes release asset names for its
  projects, discovery admits a listed project the committed catalog does not
  yet hold only when its entry names an asset ending in `.apk`; a new project
  without one, or without an entry, is reported and skipped. The asset names
  describe only the latest release while Obtainium falls back to older ones,
  so the screen never removes a committed entry the upstream still lists. A
  source whose upstream publishes no asset names, like the codm
  README, is not screened. Quiver rows form GitHub or GitLab URLs (an absent
  forge means GitHub); a row naming another forge or an invalid repository is
  reported and skipped.
- **BREAKING** Every project discovery keeps becomes one minimal entry,
  whatever its host: the committed entry's URL for a URL the committed
  catalog already holds, or else the listing's project URL with any deep link
  reduced to the repository root (the smallest when several collapse), `overrideSource` GitHub or GitLab where the URL makes that
  unambiguous and unset otherwise (Obtainium detects it), the listing's name
  with trailing emoji and symbols trimmed or the URL's last segment, default
  settings, no categories, and the committed entry's id for a URL the committed
  catalog already holds, or else an Obtainium placeholder id (the first twelve
  hex characters of the SHA-256 of the normalized URL), which Obtainium replaces
  with the APK's package id on first install. codm's links on other hosts
  (itch.io, Google Play, Modrinth, Nexus Mods) join the candidates; Quiver's
  GitLab ports join once their upstream lists an APK asset for them, which it
  does not today. The owner decides whether to deny a link Obtainium cannot
  use.
- **BREAKING** The pack stops limiting source types to GitHub, GitLab and HTML:
  ingestion keeps any declared type and leaves an undeclared non-GitHub,
  non-GitLab type unset, rendering fills default settings only for the types it
  holds defaults for, and verification type-checks settings only there. The
  GitLab URL boundary (gitlab.com only, a bare project path) is removed, so a
  self-hosted GitLab project is accepted as Obtainium's GitLab source accepts
  it.
- **BREAKING** Generation fails only when its discovery input or committed
  catalog cannot be read or is malformed (a committed catalog with two entries
  at one normalized URL included), or when the candidate it would write keeps
  no entry, however that happens. No single row's or project's outcome fails
  or blocks a run.
- **BREAKING** `config/codm-projects.json`, `config/quiver-projects.json` and
  `config/http.json` are deleted. Their per-app settings move to overlay
  records keyed by URL (Kanto Gear's track-only treatment included) only where
  the generated entry is the current published winner for that URL; a setting
  whose URL another source's entry wins by pin or precedence (codm's EmuLnk
  today) is dropped, so published settings stay unchanged. Quiver's categories
  move to the composition category map.
- `pack generate-source <source>` writes a candidate catalog and a report of
  the source, inputs, error, skipped listings with their reasons (screened-out
  projects included) and the catalog's added, removed and changed entries (a
  kept URL whose rendered entry differs, such as a new name). The proposal
  workflow's PR body and run summary carry the same.
- Retired: release selection, APK download and manifest reading, APK agreement
  checks, repository rename lookups, project policy and its track-only kind,
  policy-declared discovery skips, retention of committed entries after failures, no-Android
  and unavailable-repository outcomes, inactive-rule reports, HTTP credential
  configuration, the response-size bound on Quiver reads, rejection of a
  redirect that leaves the Quiver index's host and directory, and the `readme-source-generation` and
  `quiver-source-generation` capabilities.

Estimate: two capabilities removed (12 requirements) and one added with 5
requirements; roughly 2,000 implementation lines removed and 250 added; most
generation test modules deleted and replaced by about 400 lines.

## Capabilities

### New Capabilities

- `source-generation`: discovery of each generated source's upstream list,
  minimal entry rendering, and the proposal workflow that keeps each committed
  catalog current.

### Modified Capabilities

- `readme-source-generation`: every requirement removed, replaced by
  `source-generation`.
- `quiver-source-generation`: every requirement removed, replaced by
  `source-generation`.
- `pack-cli`: one `generate-source` requirement for every source; build reports
  identify admitted generated entries by id and URL.
- `source-ingestion`: committed codm and Quiver entries carry their committed
  ids or, when newly listed, placeholder ids, and no reviewed settings; GitLab entries may come from generated catalogs;
  any source type is accepted and an undeclared one may stay unset; no request
  carries credentials.
- `pack-rendering`: default settings are filled only for source types with
  defaults.
- `pack-verification`: no source-type allowlist; settings are type-checked only
  where defaults exist.
- `pack-curation`: generated catalogs are held only to validity, composition
  and canonical bytes.
- `nightly-publishing`: no project policy file remains to protect.

## Impact

- Code: a new discovery-and-render generator replaces `source_generation.py`,
  `quiver_generation.py`, `quiver_source.py`, `quiver_catalog.py`,
  `project_policy.py`, `package_id.py`, `source_release.py` and
  `source_http.py`; `scripts/source_proposal.py` loses the diagnostics those
  produced.
- Configuration: three files deleted, and the `project_policy` keys naming them
  removed from `config/sources.json`; overlay records added for settings whose
  generated entry wins its URL, settings for displaced entries dropped, and
  category keys added.
  Composition rules and pins that select a generated entry by id keep working,
  since existing entries keep their ids.
- Published packs: existing generated entries keep their ids, and their
  settings become defaults plus overlays, with every published winner's
  settings unchanged by the migration; newly listed projects carry
  placeholder ids; names may change to the upstream listing's, trimmed of
  trailing emoji; codm's other-host links are added, and newly listed Quiver
  projects whose upstream lists no APK asset are kept out and reported, while
  committed entries the upstream still lists stay. Repeated-package-id
  reports cannot see a newly listed generated entry, which carries a
  placeholder id.
- Workflow: the `pack generate-source` step in `source-maintenance.yml`, which
  `source-catalog.yml` calls, drops its `GITHUB_TOKEN`; generation needs no API
  token.
- Docs: `docs/source-generation.md`, `docs/quiver-ports.md`,
  `docs/curation.md`, `docs/development.md`.
