"""Render a variant's apps into the Obtainium import format.

Filters by variant membership, hydrates `additionalSettings` with the
source's full default keys, serializes it to a string, sorts by category
then name, and wraps the result in the `{apps, settings}` export shape.
"""

from __future__ import annotations

from typing import Any

from obtainium_pack.model import App, Variant


def render(
    apps: list[App], variant: Variant, settings: dict[str, Any]
) -> dict[str, Any]:
    """Return the Obtainium import document for `variant`."""
    raise NotImplementedError
