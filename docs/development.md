# Development

Run `direnv allow` (or `nix develop`) to get every tool the `justfile`
targets need, then `just --list` for the available commands. `just
check-all` runs everything CI runs.

## Build the packs

Run `uv run pack build` from the repository root. It fetches the configured
upstreams, updates resolved package ids in `config/package-ids.json`, and
writes both import files to `dist/` and regenerates the README catalog after
validating their serialized bytes offline. Keep exactly one standalone pair of
catalog markers in README; the build preserves all bytes outside them. An
optional `GITHUB_TOKEN` authenticates requests to `api.github.com` through
`config/http.json`.

The JSON diagnostics are in `.build/report.json`, including generated and
unresolved projects, family selections and alternatives, selection reasons,
identity transitions, exclusions, and changes from the previous output. A
failed build returns a nonzero status and preserves the previous packs and README;
successfully resolved ids remain cached for later runs.

## Verify and inspect

Run `uv run pack verify` (or `just verify`) to validate the committed packs,
README catalog and local configuration without network access.
Verification does not consult HTTP configuration or credentials. The retired
`--live` and `--probe-assets` flags are rejected; use Obtainium to investigate
source selection and version behavior.
Verification leaves distribution files, README, configuration, package-id caches, and
the build report unchanged. Standalone evidence is written to `.build/verify.json`.

Run `uv run pack report` to display build and verification results, warnings,
observation times, and whether verification matches the current local inputs.
A matching fingerprint does not establish current upstream health.

See [verification](verification.md) for structural checks, failure policy,
and the limits of a successful check. CI verifies committed files offline;
nightly publication runs fresh structural verification after building its candidate.
Old verification report schemas require regeneration with `uv run pack verify`.

See [pack composition](composition.md) for family selection, policy,
exclusion, overlay, migration, and rollback behavior.

See [live validation](validation.md) for the observed import results.

See [maintained app curation](curation.md) for version policies and known
identity findings, and [curation validation](curation-validation.md) for
fixture, metadata and device acceptance results.

See [nightly publishing](publishing.md) for scheduled refreshes, permissions,
failure recovery, diagnostics, and post-landing acceptance.

See [onboarding validation](onboarding-validation.md) for the latest README,
schedule, tracker-exclusion, and pack verification evidence.
