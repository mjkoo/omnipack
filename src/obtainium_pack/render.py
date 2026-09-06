"""Render composed apps into the Obtainium import format."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from obtainium_pack.overlay import ComposedApp
from obtainium_pack.settings_defaults import SETTINGS_DEFAULTS


class RenderError(ValueError):
    """Composed data cannot be represented as an Obtainium import."""


_APP_FIELD_ORDER = (
    "id",
    "url",
    "author",
    "name",
    "installedVersion",
    "latestVersion",
    "apkUrls",
    "preferredApkIndex",
    "additionalSettings",
    "lastUpdateCheck",
    "pinned",
    "categories",
    "releaseDate",
    "changeLog",
    "overrideSource",
    "allowIdChange",
    "otherAssetUrls",
    "pendingRepoRenameUrl",
)


def _canonical_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    return deepcopy(value)


def hydrate_settings(source_type: str, values: dict[str, Any]) -> dict[str, Any]:
    """Fill source defaults, retaining entry values and future keys."""
    try:
        defaults = SETTINGS_DEFAULTS[source_type]
    except KeyError as error:
        raise RenderError(f"unsupported source type {source_type!r}") from error
    result = deepcopy(defaults)
    for key in defaults:
        if key in values:
            result[key] = _canonical_value(values[key])
    for key in sorted(values.keys() - defaults.keys()):
        result[key] = _canonical_value(values[key])
    return result


def render(apps: list[ComposedApp], settings: dict[str, Any]) -> str:
    """Return a deterministic Obtainium import document as JSON text."""
    _validate_unique_ids(apps)
    rendered_apps = [_render_app(app) for app in apps]
    rendered_apps.sort(key=_sort_key)
    rendered_settings = _render_settings(settings, rendered_apps)
    document = {"settings": rendered_settings, "apps": rendered_apps}
    try:
        encoded = json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except ValueError as error:
        raise RenderError(
            "rendered document contains a value invalid in JSON"
        ) from error
    return encoded + "\n"


def _render_app(app: ComposedApp) -> dict[str, Any]:
    data = deepcopy(app.data)
    package_id = data.get("id")
    if not isinstance(package_id, str):
        raise RenderError(f"app {package_id!r} has invalid id; expected string")
    for field in ("url", "name"):
        if not isinstance(data.get(field), str):
            raise RenderError(
                f"app {package_id!r} has invalid {field}; expected string"
            )
    if "author" not in data:
        data["author"] = ""
    elif not isinstance(data["author"], str):
        raise RenderError(f"app {package_id!r} has invalid author; expected string")

    categories = data.get("categories", [])
    if not isinstance(categories, list) or not all(
        isinstance(category, str) for category in categories
    ):
        raise RenderError(
            f"app {package_id!r} has invalid categories; expected string list"
        )
    data["categories"] = categories

    source_type = data.get("overrideSource")
    if not isinstance(source_type, str):
        raise RenderError(
            f"app {package_id!r} has invalid overrideSource; expected string"
        )
    additional = data.get("additionalSettings", {})
    if not isinstance(additional, dict):
        raise RenderError(
            f"app {package_id!r} has invalid additionalSettings; expected object"
        )
    hydrated = hydrate_settings(source_type, additional)
    try:
        data["additionalSettings"] = json.dumps(
            hydrated,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except ValueError as error:
        raise RenderError(
            f"app {package_id!r} settings contain a value invalid in JSON"
        ) from error

    ordered: dict[str, Any] = {}
    for field in _APP_FIELD_ORDER:
        if field in data:
            ordered[field] = _canonical_value(data[field])
    for field in sorted(data.keys() - ordered.keys()):
        ordered[field] = _canonical_value(data[field])
    return ordered


def _sort_key(app: dict[str, Any]) -> tuple[str, str, str]:
    categories = app["categories"]
    return (categories[0] if categories else "", app["name"], app["id"])


def _render_settings(
    configured: dict[str, Any], apps: list[dict[str, Any]]
) -> dict[str, Any]:
    configured = deepcopy(configured)
    category_config = configured.pop("categories", {})
    if isinstance(category_config, str):
        try:
            category_config = json.loads(category_config)
        except json.JSONDecodeError as error:
            raise RenderError("settings categories must be a JSON object") from error
    if not isinstance(category_config, dict):
        raise RenderError("settings categories must be an object or encoded object")

    observed = sorted({category for app in apps for category in app["categories"]})
    categories: dict[str, int] = {}
    for category in observed:
        color = category_config.get(category)
        if color is None:
            color = int.from_bytes(
                b"\xff" + hashlib.sha256(category.encode()).digest()[:3]
            )
        if not isinstance(color, int) or isinstance(color, bool):
            raise RenderError(f"category {category!r} color must be an integer")
        categories[category] = color

    result = {key: _canonical_value(configured[key]) for key in sorted(configured)}
    result["categories"] = json.dumps(categories, separators=(",", ":"))
    return result


def _validate_unique_ids(apps: list[ComposedApp]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for app in apps:
        package_id = app.data.get("id")
        if not isinstance(package_id, str):
            raise RenderError(f"app {package_id!r} has invalid id; expected string")
        if package_id in seen:
            duplicates.add(package_id)
        seen.add(package_id)
    if duplicates:
        values = ", ".join(repr(value) for value in sorted(duplicates))
        raise RenderError(f"duplicate package id(s): {values}")
