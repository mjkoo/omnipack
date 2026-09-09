"""Apply JSON Merge Patch overlays to composed import documents."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from omnipack.model import Provenance, Variant


class OverlayError(ValueError):
    """An overlay cannot be applied to the composed pack."""


@dataclass(frozen=True, slots=True)
class ComposedApp:
    """An import document plus composition metadata overlays cannot rewrite."""

    variant: Variant
    provenance: Provenance
    data: dict[str, Any]

    @property
    def id(self) -> str:
        """Return the protected package id used to key the document."""
        return self.data["id"]


def merge_patch(target: object, patch: object) -> object:
    """Return RFC 7386 JSON Merge Patch of `target` by `patch`."""
    if not isinstance(patch, dict):
        return deepcopy(patch)
    result: dict[str, Any] = deepcopy(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = merge_patch(result.get(key), value)
    return result


def apply_overlay(
    apps: list[ComposedApp], overlay: dict[str, object]
) -> list[ComposedApp]:
    """Return deep-copied apps with matching import documents patched."""
    _validate_patches(overlay)
    result: list[ComposedApp] = []
    for app in apps:
        data = deepcopy(app.data)
        if app.id in overlay:
            patched = merge_patch(data, overlay[app.id])
            assert isinstance(patched, dict)
            data = patched
        result.append(ComposedApp(app.variant, app.provenance, data))
    return result


def _validate_patches(overlay: dict[str, object]) -> None:
    for package_id, patch in overlay.items():
        if not isinstance(patch, dict):
            raise OverlayError(f"overlay for {package_id!r} must be an object")
        protected = {"id", "overrideSource"}.intersection(patch)
        if protected:
            fields = ", ".join(sorted(protected))
            raise OverlayError(
                f"overlay for {package_id!r} contains protected field {fields}"
            )
