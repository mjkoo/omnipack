## Why

The codm and Quiver generators look every listed repository up on GitHub,
select a release, download its APKs and read their manifests, then fail the
whole run when one project cannot be resolved; per-project policy, skips,
retention and credentials exist to manage that. None of it is something
Obtainium requires: given a repository URL, Obtainium finds releases and
learns the package id at install. Once families key on project URLs (the
`key-merge-by-url` change, which this change builds on), the generator only
has to turn an upstream list into Obtainium entries.

## What Changes

- **BREAKING** One generator serves every generated source. It reads the
  source's upstream list (the codm README's Project tables, the Quiver index and
  lists) and makes no other request: no repository API, release or APK.
- **BREAKING** Every link a source lists becomes one minimal entry, whatever
  its host: listed URL, `overrideSource` GitHub or GitLab where the URL makes
  that unambiguous and unset otherwise (Obtainium detects it), the listing's
  name or the URL's last segment, default settings, no categories, and an
  Obtainium placeholder id (the first twelve hex characters of the SHA-256 of
  the normalized URL), which Obtainium replaces with the APK's package id on
  first install. Quiver's six GitLab ports and codm's four other-host links
  (itch.io, Google Play, Modrinth, Nexus Mods) join the candidates; the owner
  decides whether to deny a link Obtainium cannot use.
- **BREAKING** The pack stops limiting source types to GitHub, GitLab and HTML:
  ingestion keeps any declared type and leaves an undeclared non-GitHub,
  non-GitLab type unset, rendering fills default settings only for the types it
  holds defaults for, and verification type-checks settings only there.
- **BREAKING** Generation fails only when its discovery input cannot be read,
  is malformed, or lists nothing. No per-project outcome
  fails or blocks a run.
- **BREAKING** `config/codm-projects.json`, `config/quiver-projects.json` and
  `config/http.json` are deleted. Their nine per-app settings move to overlay
  records keyed by URL (Kanto Gear's track-only treatment included), and
  Quiver's categories move to the composition category map.
- `pack generate-source <source>` writes a candidate catalog and a report of
  the source, inputs, error, skipped Quiver rows and catalog changes. The
  proposal workflow's PR body and run summary carry the same.
- Retired: release selection, APK download and manifest reading, APK agreement
  checks, repository rename lookups, project policy and its track-only kind,
  discovery skips, retention of committed entries after failures, no-Android
  and unavailable-repository outcomes, inactive-rule reports, HTTP credential
  configuration, and the `readme-source-generation` and
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
- `source-ingestion`: committed codm and Quiver entries carry placeholder ids
  and no reviewed settings; GitLab entries may come from generated catalogs;
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
- Configuration: three files deleted; overlay records and category keys added;
  composition rules and pins that select a generated entry by id are updated to
  its placeholder id.
- Published packs: every generated entry's id changes to a placeholder and its
  settings to defaults plus overlays; names may change to the upstream
  listing's; Quiver's six GitLab ports and codm's four other-host links are
  added. Repeated-package-id reports
  no longer see generated entries.
- Workflow: `source-catalog.yml` needs no API token for generation.
- Docs: `docs/source-generation.md`, `docs/quiver-ports.md`,
  `docs/curation.md`, `docs/development.md`.
