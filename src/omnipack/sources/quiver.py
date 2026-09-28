"""Load Quiver's reviewed, committed APK catalog for routine builds."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from omnipack.model import App
from omnipack.sources.common import SourceError


def fetch(
    root: Path,
    config: Mapping[str, object],
    report: Any | None = None,
) -> list[App]:
    catalog_path = config.get("catalog")
    if not isinstance(catalog_path, str) or not catalog_path.strip():
        raise SourceError("quiver", "configured location is empty")
    from omnipack.quiver_catalog import load_quiver_apps

    apps = load_quiver_apps(root / catalog_path)
    if report is not None:
        report.admitted.extend(
            {"source": "quiver", "url": app.url, "kind": "apk", "id": app.id}
            for app in apps
        )
    return apps
