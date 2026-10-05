"""Render composed apps into the Obtainium import format."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from omnipack.overlay import ComposedApp
from omnipack.settings_defaults import SETTINGS_DEFAULTS
from omnipack.urls import normalize_project_url


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


def canonical_serialization(data: dict[str, Any]) -> str:
    """One canonical JSON text for an app record, used to order records totally."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hydrate_settings(source_type: str | None, values: dict[str, Any]) -> dict[str, Any]:
    """Fill source defaults, retaining entry values and future keys.

    An entry whose source type the pack holds no defaults for, or that has
    none, keeps exactly the settings it carries.
    """
    defaults = SETTINGS_DEFAULTS.get(source_type or "", {})
    result = deepcopy(defaults)
    for key in defaults:
        if key in values:
            result[key] = _canonical_value(values[key])
    for key in sorted(values.keys() - defaults.keys()):
        result[key] = _canonical_value(values[key])
    return result


def render_pack(apps: list[ComposedApp]) -> str:
    """Render a published pack, in which every app may adopt its APK's id.

    A source's package id can differ from the id its APK declares, and
    Obtainium refuses such an install unless the app allows an id change, so
    the flag is forced on whatever the source or an overlay says.
    """
    return render(
        [ComposedApp(app.family, {**app.data, "allowIdChange": True}) for app in apps]
    )


def render(apps: list[ComposedApp]) -> str:
    """Return a deterministic Obtainium import document as JSON text."""
    rendered_apps = [_render_app(app) for app in apps]
    rendered_apps.sort(key=_sort_key)
    document = {"settings": _render_settings(rendered_apps), "apps": rendered_apps}
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
    if not data["url"]:
        raise RenderError(
            f"app {package_id!r} has invalid url; expected nonempty string"
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
    if "overrideSource" in data and not isinstance(source_type, str):
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


def _sort_key(app: dict[str, Any]) -> tuple[str, str, str, str, str]:
    """Order apps totally: one package id may appear at several project URLs."""
    categories = app["categories"]
    return (
        categories[0] if categories else "",
        app["name"],
        app["id"],
        normalize_project_url(app["url"]),
        canonical_serialization(app),
    )


def _render_settings(apps: list[dict[str, Any]]) -> dict[str, str]:
    """Map each category the apps use to a colour derived from its name alone."""
    observed = sorted({category for app in apps for category in app["categories"]})
    categories = {
        category: int.from_bytes(
            b"\xff" + hashlib.sha256(category.encode()).digest()[:3]
        )
        for category in observed
    }
    return {"categories": json.dumps(categories, separators=(",", ":"))}
