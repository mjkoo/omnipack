"""Load a committed generated catalog as build candidates.

Routine builds read the committed catalog only: they fetch no upstream list,
repository host or APK, and keep each entry's committed id, URL, name and
settings, so composition rules and overlays that select it match it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from omnipack.model import App
from omnipack.source_registry import GENERATED, GeneratedSource
from omnipack.sources import IngestionReport, load_json
from omnipack.sources.common import SourceError, normalize_record
from omnipack.urls import normalize_project_url


def fetch_generated(
    source: GeneratedSource,
    root: Path,
    config: Mapping[str, object],
    report: IngestionReport | None = None,
) -> list[App]:
    """Normalize every entry of a source's committed catalog, with the origin
    and pack eligibility the registry gives that source.

    A missing, unreadable or malformed catalog fails, and so does one that
    repeats an entry id or holds two entries at one normalized URL.
    """
    catalog_path = config.get("catalog")
    if not isinstance(catalog_path, str) or not catalog_path.strip():
        raise SourceError(source, "configured location is empty")
    document = load_json(root / catalog_path, source)
    if not isinstance(document, dict) or not isinstance(document.get("apps"), list):
        raise SourceError(source, "catalog must be an object with an apps list")
    catalog = GENERATED[source]
    result = [
        normalize_record(
            record,
            source=source,
            eligibility=catalog.eligibility,
            origin=catalog.origin,
        )
        for record in document["apps"]
    ]
    try:
        catalog_urls([(app.id, app.url) for app in result])
    except ValueError as error:
        raise SourceError(source, str(error)) from error
    if report is not None:
        report.admitted.extend(
            {"source": source, "url": app.url, "id": app.id} for app in result
        )
    return result


def catalog_urls(entries: Sequence[tuple[str, str]]) -> list[str]:
    """The normalized URL of each `(id, url)` entry of a committed catalog.

    A catalog that repeats an id, or holds two entries at one normalized URL,
    is malformed: either entry could be the one a rule, pin or regeneration
    means.
    """
    urls = [normalize_project_url(url) for _, url in entries]
    owners: dict[str, str] = {}
    ids_at: dict[str, list[str]] = {}
    for (identifier, url), normalized in zip(entries, urls, strict=True):
        previous = owners.get(identifier)
        if previous is not None:
            raise ValueError(
                f"duplicate id {identifier!r} for {previous!r} and {url!r}"
            )
        owners[identifier] = url
        ids_at.setdefault(normalized, []).append(identifier)
    for normalized, ids in ids_at.items():
        if len(ids) > 1:
            raise ValueError(
                f"several entries for {normalized}: {', '.join(sorted(ids))}"
            )
    return urls
