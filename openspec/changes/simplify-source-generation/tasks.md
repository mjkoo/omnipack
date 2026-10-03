## 1. The generator

- [ ] 1.1 Implement codm discovery (links inside Project tables, code blocks excluded) and Quiver discovery (index and lists within the index's host and directory) behind one interface that returns listings and unsupported values, failing only on unreadable or malformed input or nothing renderable; verify with discovery tests for both sources, including a link outside the tables, an out-of-location list, an unavailable list and an all-unsupported discovery
- [ ] 1.2 Render each GitHub or GitLab listing as a minimal entry (listed URL, `overrideSource`, listing or repository name, owner as author, placeholder id from the SHA-256 of the normalized URL, default settings, no categories), collapsing listings by normalized URL and ordering by it; verify with tests for a GitLab row, two spellings of one repository, the placeholder id, name precedence and byte-identical output on unchanged input
- [ ] 1.3 Make `pack generate-source <source>` write the candidate and a report of source, inputs, error, unsupported listings and changes, leaving no candidate on failure; verify with CLI tests for success, a failed rerun after success and an unsupported listing, asserting that no request other than the discovery inputs is made

## 2. Removal

- [ ] 2.1 Delete the replaced generation modules, `config/http.json` support, project policy parsing and their tests, and remove credential handling from HTTP fetching; verify that no source file imports the deleted modules and that `uv run pytest` passes
- [ ] 2.2 Reduce `scripts/source_proposal.py` and `.github/workflows/source-catalog.yml` to the new report: PR body and run summary list changes and unsupported listings, and generation runs without an API token; verify with the source proposal and workflow tests

## 3. Configuration migration

- [ ] 3.1 Move the nine per-app policy settings (Emulnk, Showdown, Heimdall, DW2003, Kanto Gear, Melee PC, Silent Hill, LEGO Island, and any name overrides) to overlay records, Quiver's category assignments to category map keys, and delete `config/codm-projects.json`, `config/quiver-projects.json` and `config/http.json`; verify with a curation test asserting each moved setting on its selected entry
- [ ] 3.2 Regenerate both catalogs from live upstream inputs, update composition rules and pins that select a generated entry by its old id, and rebuild; verify that `uv run pack build` and `uv run pack verify` pass, every family selects the same project URL as before apart from the added GitLab ports, and the uncategorized list names only newly added families

## 4. Documentation

- [ ] 4.1 Rewrite `docs/source-generation.md` for the reduced generator and update `docs/quiver-ports.md`, `docs/curation.md` and `docs/development.md`; verify with a search for project policy, skips, credentials, package-id resolution and the deleted file names in `docs/`, and `just check-links`
- [ ] 4.2 Run `just check-all` and confirm it passes
