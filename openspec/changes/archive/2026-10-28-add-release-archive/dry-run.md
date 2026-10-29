# Dry run against the committed packs

`GITHUB_TOKEN=<token> uv run pack archive --dry-run` on 2026-10-28, against the committed
`dist/single-screen.json` and `dist/dual-screen.json`. The command exited 0 with no crash.

Every target reported a resolved version or a skipped outcome; none was unreachable, had no
release, or failed. Skipped targets were the track-only entries and one entry whose source
Obtainium would not resolve as GitHub, GitLab or HTML (an itch.io page with no source override).
The HTML entries (Dolphin, DuckStation and Eden) each resolved a version through their extraction
settings.
