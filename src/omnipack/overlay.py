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
    """A patch for every selected entry at one normalized project URL."""

    url: str
    patch: dict[str, Any]


# Fields only the source, composition and the category map decide.
PROTECTED_FIELDS = frozenset(
    {"url", "overrideSource", "family", "variant", "categories"}
)


def _record_context(record: dict[str, Any]) -> str:
    """Name the record's URL when it normalizes, so an error names what to look for.

    The index alone sends a maintainer counting records. A URL that does not
    normalize is left out and reported by the validation that follows.
    """
    url = record.get("url")
    if isinstance(url, str) and url.strip():
        try:
            return f" (url {normalize_project_url(url)!r})"
        except ValueError:
            pass
    return ""


def parse_overlay(document: object, label: str) -> tuple[OverlayPatch, ...]:
    if not isinstance(document, list):
        raise OverlayError(f"{label} must be an array of URL patch records")
    result: list[OverlayPatch] = []
    indexes: dict[str, int] = {}
    for index, value in enumerate(document):
        item_label = f"{label}[{index}]"
        if not isinstance(value, dict):
            raise OverlayError(f"{item_label} must be an object")
        context = _record_context(value)
        unknown = set(value) - {"url", "patch"}
        if unknown:
            raise OverlayError(
                f"{item_label} has unknown field {min(unknown)!r}{context}"
            )
        url, patch = value.get("url"), value.get("patch")
        if not isinstance(url, str) or not url.strip():
            raise OverlayError(f"{item_label}.url must be a nonempty project URL")
        try:
            url = normalize_project_url(url)
        except ValueError as error:
            raise OverlayError(
                f"{item_label}.url is not a project URL: {url!r}"
            ) from error
        if not isinstance(patch, dict):
            raise OverlayError(f"{item_label}.patch must be an object{context}")
        protected = PROTECTED_FIELDS.intersection(patch)
        if protected:
            raise OverlayError(
                f"{item_label}.patch for {url!r} contains protected field "
                f"{min(protected)}"
            )
        if "id" in patch and (
            not isinstance(patch["id"], str) or not patch["id"].strip()
        ):
            raise OverlayError(
                f"{item_label}.patch for {url!r} must set id to a nonempty string"
            )
        if url in indexes:
            raise OverlayError(
                f"{item_label} names the same project URL {url!r} as "
                f"{label}[{indexes[url]}]"
            )
        indexes[url] = index
        result.append(OverlayPatch(url, deepcopy(patch)))
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
    patches = {item.url: item.patch for item in overlay}
    result: list[ComposedApp] = []
    for app in apps:
        data = deepcopy(app.data)
        patch = patches.get(normalize_project_url(app.url))
        if patch is not None:
            patched = merge_patch(data, patch)
            assert isinstance(patched, dict)
            data = patched
        result.append(ComposedApp(app.family, data))
    return result
