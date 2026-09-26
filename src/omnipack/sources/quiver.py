"""Load Quiver's reviewed, committed APK catalog for routine builds."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from omnipack.model import App, Variant
from omnipack.sources.common import SourceError, normalize_record


def fetch(
    root: Path,
    config: Mapping[str, object],
    report: Any | None = None,
) -> list[App]:
    catalog_path = config.get("catalog")
    if not isinstance(catalog_path, str) or not catalog_path.strip():
        raise SourceError("quiver", "configured location is empty")
    from omnipack.quiver_catalog import load_quiver_catalog

    try:
        entries = load_quiver_catalog(root / catalog_path)
    except (OSError, ValueError, TypeError) as error:
        raise SourceError("quiver", str(error)) from error
    result: list[App] = []
    for record in entries:
        app = normalize_record(
            record,
            source="quiver",
            eligibility=frozenset(Variant),
            origin="quiver-generated",
        )
        result.append(app)
        if report is not None:
            report.admitted.append(
                {"source": "quiver", "url": app.url, "kind": "apk", "id": app.id}
            )
    return result
