"""Apply build-bound JSON Merge Patch overlays to composed imports."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from omnipack.model import Provenance, Variant
from omnipack.urls import normalize_project_url


class OverlayError(ValueError):
    """An overlay cannot be applied to the composed pack."""


@dataclass(frozen=True, slots=True)
class ComposedApp:
    variant: Variant
    provenance: Provenance
    data: dict[str, Any]
    family: str | None = None
    original_id: str | None = None
    origin: str | None = None

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def url(self) -> str:
        return self.data["url"]


@dataclass(frozen=True, slots=True)
class OverlayPatch:
    package_id: str
    url: str
    patch: dict[str, Any]

    @property
    def key(self) -> tuple[str, str]:
        return self.package_id, normalize_project_url(self.url)


def parse_overlay(document: object, label: str) -> tuple[OverlayPatch, ...]:
    if not isinstance(document, list):
        raise OverlayError(
            f"{label} must be an array of id-and-URL patch records; "
            "legacy package-id objects are unsupported"
        )
    result: list[OverlayPatch] = []
    keys: set[tuple[str, str]] = set()
    for index, value in enumerate(document):
        item_label = f"{label}[{index}]"
        if not isinstance(value, dict):
            raise OverlayError(f"{item_label} must be an object")
        unknown = set(value) - {"id", "url", "patch"}
        if unknown:
            raise OverlayError(f"{item_label} has unknown field {min(unknown)!r}")
        package_id, url, patch = value.get("id"), value.get("url"), value.get("patch")
        if not isinstance(package_id, str) or not package_id.strip():
            raise OverlayError(f"{item_label}.id must be a nonempty string")
        if not isinstance(url, str) or not url.strip():
            raise OverlayError(f"{item_label}.url must be a nonempty project URL")
        try:
            url = normalize_project_url(url)
        except ValueError as error:
            raise OverlayError(
                f"{item_label}.url is not a project URL: {url!r}"
            ) from error
        if not isinstance(patch, dict):
            raise OverlayError(f"{item_label}.patch must be an object")
        protected = {
            "id",
            "url",
            "overrideSource",
            "family",
            "originalId",
            "original_id",
            "origin",
            "eligibility",
            "eligible",
            "variant",
            "variants",
            "dualPreferred",
            "dual_preferred",
            "provenance",
            "selectionReason",
            "selection_reason",
        }.intersection(patch)
        if protected:
            raise OverlayError(
                f"{item_label}.patch contains protected field "
                + ", ".join(sorted(protected))
            )
        record = OverlayPatch(package_id, url, deepcopy(patch))
        if record.key in keys:
            raise OverlayError(f"{label} has duplicate selector {record.key!r}")
        keys.add(record.key)
        result.append(record)
    return tuple(result)


def merge_patch(target: object, patch: object) -> object:
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
    apps: list[ComposedApp], overlay: tuple[OverlayPatch, ...]
) -> list[ComposedApp]:
    patches = {item.key: item.patch for item in overlay}
    result: list[ComposedApp] = []
    for app in apps:
        data = deepcopy(app.data)
        patch = patches.get((app.id, normalize_project_url(app.url)))
        if patch is not None:
            patched = merge_patch(data, patch)
            assert isinstance(patched, dict)
            data = patched
        result.append(
            ComposedApp(
                app.variant,
                app.provenance,
                data,
                app.family,
                app.original_id,
                app.origin,
            )
        )
    return result
