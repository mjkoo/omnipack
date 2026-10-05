"""Load a committed generated catalog as build candidates.

Routine builds read the committed catalog only: they fetch no upstream list,
repository host or APK, and keep each entry's committed id, URL, name and
settings, so composition rules and overlays that select it match it.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from omnipack.model import App, Variant
from omnipack.sources.common import SourceError, normalize_record


def fetch_generated(
    root: Path,
    config: Mapping[str, object],
    report: Any | None,
    *,
    source: str,
    provenance: str,
    origin: str,
    eligibility: frozenset[Variant],
) -> list[App]:
    """Normalize every entry of a source's committed catalog.

    A missing, unreadable or malformed catalog fails, and so does one that
    repeats an entry id.
    """
    catalog_path = config.get("catalog")
    if not isinstance(catalog_path, str) or not catalog_path.strip():
        raise SourceError(source, "configured location is empty")
    from omnipack.sources import load_json

    document = load_json(root / catalog_path, source)
    if not isinstance(document, dict) or not isinstance(document.get("apps"), list):
        raise SourceError(source, "catalog must be an object with an apps list")
    result: list[App] = []
    identities: dict[str, str] = {}
    for record in document["apps"]:
        app = normalize_record(
            record, source=provenance, eligibility=eligibility, origin=origin
        )
        previous = identities.get(app.id)
        if previous is not None:
            raise SourceError(
                source, f"duplicate id {app.id!r} for {previous!r} and {app.url!r}"
            )
        identities[app.id] = app.url
        result.append(app)
        if report is not None:
            report.admitted.append({"source": provenance, "url": app.url, "id": app.id})
    return result
