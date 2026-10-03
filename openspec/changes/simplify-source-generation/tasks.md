## 1. The generator

- [ ] 1.1 Implement codm discovery (links inside Project tables, code blocks excluded) and Quiver discovery (index and lists within the index's host and directory, rows turned into forge URLs) behind one interface that returns listings and skipped rows, failing only on unreadable or malformed input or an empty discovery; verify with discovery tests for both sources, including a link outside the tables, an out-of-location list, an unavailable list, a row naming an unknown forge and an empty discovery
- [ ] 1.2 Render every listing as a minimal entry whatever its host (listed URL, `overrideSource` GitHub or GitLab where unambiguous and unset otherwise, listing name or last path segment, owner or empty author, placeholder id from the SHA-256 of the normalized URL, no categories), collapsing listings by normalized URL and ordering by it; verify with tests for a GitLab row, an itch.io link, two spellings of one repository, the placeholder id, name precedence and byte-identical output on unchanged input
- [ ] 1.3 Make `pack generate-source <source>` write the candidate and a report of source, inputs, error, skipped rows and changes, leaving no candidate on failure; verify with CLI tests for success, a failed rerun after success and a skipped row, asserting that no request other than the discovery inputs is made

## 2. The pack accepts any source type

- [ ] 2.1 Keep any declared source type in ingestion, derive only GitHub and GitLab from unambiguous URLs and leave other undeclared types unset, render default settings only for types with defaults and pass other entries' settings through, and type-check settings in verification only where defaults exist; verify with ingestion, rendering and offline tests for a declared Codeberg entry and an undeclared itch.io entry

## 3. Removal

- [ ] 3.1 Delete the replaced generation modules, `config/http.json` support, project policy parsing and their tests, and remove credential handling from HTTP fetching; verify that no source file imports the deleted modules and that `uv run pytest` passes
- [ ] 3.2 Reduce `scripts/source_proposal.py` and `.github/workflows/source-catalog.yml` to the new report: PR body and run summary list changes and skipped rows, and generation runs without an API token; verify with the source proposal and workflow tests

## 4. Configuration migration

- [ ] 4.1 Move the per-app policy settings (Emulnk, Showdown, Heimdall, DW2003, Kanto Gear, Melee PC, Silent Hill, LEGO Island) to overlay records, recording any URL where the overlay now patches another source's winning entry, move Quiver's category assignments to category map keys, and delete `config/codm-projects.json`, `config/quiver-projects.json` and `config/http.json`; verify with a curation test asserting each moved setting on its selected entry
- [ ] 4.2 Regenerate both catalogs from live upstream inputs, update composition rules and pins that select a generated entry by its old id, and rebuild; verify that `uv run pack build` and `uv run pack verify` pass, every family selects the same project URL as before apart from the newly listed GitLab and other-host entries, and the uncategorized list names only newly added families; list the newly added entries for the owner without denying any
- [ ] 4.3 With the owner's explicit approval obtained first, on the AYN Thor import a rebuilt pack and confirm that an entry without `overrideSource` (such as the itch.io link) and a GitLab entry are detected and show their setting controls; record the dated observation in `docs/curation.md`, and stop and report if Obtainium rejects either

## 5. Documentation

- [ ] 5.1 Rewrite `docs/source-generation.md` for the reduced generator and update `docs/quiver-ports.md`, `docs/curation.md`, `docs/development.md` and `docs/composition.md` (source types); verify with a search for project policy, skips, credentials, package-id resolution, supported source types and the deleted file names in `docs/`, and `just check-links`
- [ ] 5.2 Run `just check-all` and confirm it passes
