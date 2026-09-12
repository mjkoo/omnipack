# Development

Run `direnv allow` (or `nix develop`) to get every tool the `justfile`
targets need, then `just --list` for the available commands. `just
check-all` runs everything CI runs.

## Build the packs

Run `uv run pack build` from the repository root. It fetches the configured
pack sources, including the committed codm catalog, and writes both import files
to `dist/` and regenerates the README catalog after validating their serialized
bytes offline. It does not fetch the codm README or release APKs. Keep exactly
one standalone pair of catalog markers in README; the build preserves all bytes
outside them. An optional `GITHUB_TOKEN` authenticates requests to
`api.github.com` through `config/http.json`.

The JSON diagnostics are in `.build/report.json`, including family selections
and alternatives, selection reasons, identity transitions, exclusions, and
changes from the previous output. A failed build returns a nonzero status and
preserves the previous packs and README.

## Verify and inspect

Run `uv run pack verify` (or `just verify`) to validate the committed packs,
README catalog and local configuration without network access.
Verification does not consult HTTP configuration or credentials. The retired
`--live` and `--probe-assets` flags are rejected; use Obtainium to investigate
source selection and version behavior.
Verification leaves distribution files, README, configuration, and the build
report unchanged. Standalone evidence is written to `.build/verify.json`.

Run `uv run pack report` to display build and verification results, warnings,
observation times, and whether verification matches the current local inputs.
A matching fingerprint does not establish current upstream health.

See [verification](verification.md) for structural checks, failure policy,
and the limits of a successful check. CI verifies committed files offline;
nightly publication builds and verifies once, in a read-only job, then hands
the exact verified commit to a separate write job that pushes it. Formatting,
lint, types and the full suite remain development CI responsibilities. Main
advancing past a run's base fails that run without another attempt; release
synchronization is checked separately, after the main outcome. Old
verification report schemas require regeneration with `uv run pack verify`.

See [pack composition](composition.md) for family selection, policy,
exclusion, overlay, migration, and rollback behavior.

See [source generation](source-generation.md) for editing reviewed project
rules, generating isolated candidates, accepting source data, and operating the
separate source proposal workflow. See [source generation validation](../openspec/changes/archive/2026-09-11-generate-reviewed-readme-catalog/source-generation-validation.md)
for the dated controlled, live-build, and device evidence.

See [maintained app curation](curation.md) for version policies and known
identity findings, and [curation validation](../openspec/changes/archive/2026-09-09-curate-app-version-policies/curation-validation.md) for
fixture, metadata and device acceptance results.

See [nightly publishing](publishing.md) for scheduled refreshes, permissions,
failure recovery, diagnostics, and post-landing acceptance.

See [onboarding validation](../openspec/changes/archive/2026-09-10-simplify-pack-onboarding/onboarding-validation.md) for the latest README,
schedule, tracker-exclusion, and pack verification evidence.
