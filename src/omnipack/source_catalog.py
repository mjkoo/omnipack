"""Catalog rendering and identity checks shared by generated sources."""

from __future__ import annotations

import json
from typing import Any, cast

from omnipack.overlay import ComposedApp
from omnipack.render import render
from omnipack.urls import normalize_project_url


def rendered_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Render one catalog entry through the same normalization the generator
    uses to write the catalog, so entries can be compared regardless of
    settings ordering or default-merging.
    """
    return cast(dict[str, Any], json.loads(render_catalog([entry]))["apps"][0])


def render_catalog(entries: list[dict[str, Any]]) -> bytes:
    apps: list[ComposedApp] = []
    for entry in entries:
        data = dict(entry)
        settings = data.get("additionalSettings", {})
        if isinstance(settings, str):
            settings = json.loads(settings)
        if not isinstance(settings, dict):
            raise TypeError(f"entry {data.get('id')!r} has invalid additionalSettings")
        data["additionalSettings"] = settings
        apps.append(ComposedApp(normalize_project_url(data["url"]), data))
    return render(apps).encode()


def validate_ids(entries: list[dict[str, Any]]) -> None:
    seen: dict[str, str] = {}
    for entry in entries:
        prior = seen.get(entry["id"])
        if prior is not None:
            raise ValueError(
                f"entry ID collision {entry['id']!r} between {prior} and {entry['url']}"
            )
        seen[entry["id"]] = entry["url"]
