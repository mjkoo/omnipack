"""Scrape codm2000's README table for GitHub links and generate entries.

Each GitHub link not already present by URL in a higher-precedence source
has its package id resolved from its latest release APK (see
`obtainium_pack.package_id`) and cached in `config/package-ids.json` so
nightly runs stay cheap. Non-GitHub rows have no APK feed and are skipped.
Generated entries map to the dual variant only.
"""

from __future__ import annotations

from obtainium_pack.model import App


def fetch() -> list[App]:
    """Return generated entries for codm2000's GitHub-hosted catalog rows."""
    raise NotImplementedError
