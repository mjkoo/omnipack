"""Fetch BBoi34's latest Codeberg release assets.

The single-screen asset (`Decomp-Recomp.V<x>.json`) maps to both variants;
the dual-screen asset (`Dual-Screen-Decomp-Recomp.V<x>.json`) maps to dual
only. `additionalSettings` is already a JSON string on this source.
"""

from __future__ import annotations

from obtainium_pack.model import App


def fetch() -> list[App]:
    """Return BBoi34's applications from its latest Codeberg release."""
    raise NotImplementedError
