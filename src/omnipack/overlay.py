"""Apply build-bound JSON Merge Patch overlays to composed imports."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from omnipack.urls import normalize_project_url


class OverlayError(ValueError):
    """An overlay cannot be applied to the composed pack."""


@dataclass(frozen=True, slots=True)
class ComposedApp:
    """A selected entry: its app family and the import data rendered for it."""

    family: str
    data: dict[str, Any]

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


def _record_context(record: dict[str, Any]) -> str:
    """Name the record's usable selector parts, so an error names what to look for.

    The index alone sends a maintainer counting records. A nonblank id and a
    URL that normalizes are quoted as a suffix; anything else is left out and
    reported by the validation that follows, in its usual order.
    """
    parts: list[str] = []
    package_id, url = record.get("id"), record.get("url")
    if isinstance(package_id, str) and package_id.strip():
        parts.append(f"id {package_id!r}")
    if isinstance(url, str) and url.strip():
        try:
            parts.append(f"url {normalize_project_url(url)!r}")
        except ValueError:
            pass
    return f" ({', '.join(parts)})" if parts else ""


def parse_overlay(document: object, label: str) -> tuple[OverlayPatch, ...]:
    if not isinstance(document, list):
        raise OverlayError(f"{label} must be an array of id-and-URL patch records")
    result: list[OverlayPatch] = []
    keys: set[tuple[str, str]] = set()
    for index, value in enumerate(document):
        item_label = f"{label}[{index}]"
        if not isinstance(value, dict):
            raise OverlayError(f"{item_label} must be an object")
        context = _record_context(value)
        unknown = set(value) - {"id", "url", "patch"}
        if unknown:
            raise OverlayError(
                f"{item_label} has unknown field {min(unknown)!r}{context}"
            )
        package_id, url, patch = value.get("id"), value.get("url"), value.get("patch")
        if not isinstance(package_id, str) or not package_id.strip():
            raise OverlayError(f"{item_label}.id must be a nonempty string{context}")
        if not isinstance(url, str) or not url.strip():
            raise OverlayError(
                f"{item_label}.url must be a nonempty project URL{context}"
            )
        try:
            url = normalize_project_url(url)
        except ValueError as error:
            raise OverlayError(
                f"{item_label}.url is not a project URL: {url!r}{context}"
            ) from error
        if not isinstance(patch, dict):
            raise OverlayError(f"{item_label}.patch must be an object{context}")
        protected = {
            "id",
            "url",
            "overrideSource",
            "family",
            "packageId",
            "variant",
        }.intersection(patch)
        if protected:
            raise OverlayError(
                f"{item_label}.patch for selector {(package_id, url)!r} "
                f"contains protected field {min(protected)}"
            )
        record = OverlayPatch(package_id, url, deepcopy(patch))
        if record.key in keys:
            raise OverlayError(f"{item_label} has duplicate selector {record.key!r}")
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
        result.append(ComposedApp(app.family, data))
    return result
