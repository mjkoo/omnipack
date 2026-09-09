# omnipack

Curated Obtainium import files, `single-screen.json` and
`dual-screen.json`, built as the union of several upstream app packs plus a
handful of hand-added apps, with a committed overlay of per-app fixes that
survives every upstream refresh.

Consumers fetch the rendered files directly from `dist/` on `main`.

The **Nightly publishing** workflow refreshes main daily at 06:23 UTC and also
supports manual dispatch on main. It runs offline checks, rebuilds, and requires
fresh metadata-only verification before publishing changed packs and the
package-id cache. See [publishing](docs/publishing.md) for permissions, failure
recovery, diagnostics, and the post-landing acceptance procedure.

## Development

Run `direnv allow` (or `nix develop`) to get every tool the `justfile`
targets need, then `just --list` for the available commands. `just
check-all` runs everything CI runs.

## Build the packs

Run `uv run pack build` from the repository root. It fetches the configured
upstreams, updates resolved package ids in `config/package-ids.json`, and
writes both import files to `dist/` after validating their serialized bytes
offline. An optional `GITHUB_TOKEN` authenticates
requests to `api.github.com` through `config/http.json`.

The JSON diagnostics are in `.build/report.json`, including generated and
unresolved projects, precedence decisions, exclusions, and changes from the
previous output. A failed build returns a nonzero status and preserves the
previous output pair; successfully resolved ids remain cached for later runs.

## Verify and inspect

Run `uv run pack verify` (or `just verify`) to validate the committed output
and local configuration without network access. `uv run pack verify --live`
also resolves configured GitHub and HTML metadata and versions without probing
downloads. Use `uv run pack verify --live --probe-assets` for explicit asset
reachability diagnostics. GitHub live requests require the `GITHUB_TOKEN`
environment variable mapped in `config/http.json`.
Verification leaves distribution files, configuration, package-id caches, and
the build report unchanged. Standalone evidence is written to `.build/verify.json`.

Run `uv run pack report` to display build and verification results, warnings,
observation times, and whether verification matches the current local inputs.
A matching fingerprint does not establish current upstream health.

See [verification](docs/verification.md) for supported settings, failure policy,
and the limits of a successful check. Ordinary CI runs offline verification;
nightly publication runs metadata-only live verification. Asset probes remain
an explicit manual troubleshooting operation.

See [live validation](docs/validation.md) for the observed import results.

See [maintained app curation](docs/curation.md) for version policies and known
identity findings, and [curation validation](docs/curation-validation.md) for
fixture, metadata and device acceptance results.
