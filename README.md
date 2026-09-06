# obtainium-pack

Nightly-rebuilt Obtainium import files, `single-screen.json` and
`dual-screen.json`, built as the union of several upstream app packs plus a
handful of hand-added apps, with a committed overlay of per-app fixes that
survives every upstream refresh.

Consumers fetch the rendered files directly from `dist/` on `main`.

## Development

Run `direnv allow` (or `nix develop`) to get every tool the `justfile`
targets need, then `just --list` for the available commands. `just
check-all` runs everything CI runs.

## Build the packs

Run `uv run pack build` from the repository root. It fetches the configured
upstreams, updates resolved package ids in `config/package-ids.json`, and
writes both import files to `dist/`. An optional `GITHUB_TOKEN` authenticates
requests to `api.github.com` through `config/http.json`.

The JSON diagnostics are in `.build/report.json`, including generated and
unresolved projects, precedence decisions, exclusions, and changes from the
previous output. A failed build returns a nonzero status and preserves the
previous output pair; successfully resolved ids remain cached for later runs.
The `verify` and `report` subcommands are still unimplemented.

See [live validation](docs/validation.md) for the observed import results.
