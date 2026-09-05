"""Fetch RJNY's `src/applications.json` from its main branch.

RJNY entries carry `meta` flags (`includeInStandard`, `includeInDualScreen`,
`excludeFromExport`, `nameOverride`, `urlOverride`) that map to variant
membership; `additionalSettings` is an object on this source (a JSON string
in the rendered Obtainium export).
"""

from __future__ import annotations

from obtainium_pack.model import App


def fetch() -> list[App]:
    """Return RJNY's applications, normalized, honoring `excludeFromExport`."""
    raise NotImplementedError
