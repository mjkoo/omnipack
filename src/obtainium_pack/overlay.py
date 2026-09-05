"""Apply JSON Merge Patch (RFC 7386) overlays keyed by package id.

An overlay key that names a package id present in no source fails the
build, since it indicates a stale patch.
"""

from __future__ import annotations

from typing import Any

from obtainium_pack.model import App


def apply_overlay(apps: list[App], overlay: dict[str, dict[str, Any]]) -> list[App]:
    """Return `apps` with each named entry merge-patched by `overlay`."""
    raise NotImplementedError
