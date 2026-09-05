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
