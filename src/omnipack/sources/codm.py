"""Load the accepted codm2000 catalog with its source-specific semantics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from omnipack.model import App, Variant
from omnipack.sources.common import SourceError, normalize_record
from omnipack.urls import normalize_project_url


def fetch(
    root: Path,
    config: Mapping[str, object],
    higher_precedence: Sequence[App],
    report: Any | None = None,
) -> list[App]:
    """Normalize the committed catalog and suppress dual-covered projects."""
    catalog_path = config.get("catalog")
    if not isinstance(catalog_path, str) or not catalog_path.strip():
        raise SourceError("codm", "configured location is empty")
    from omnipack.sources import load_json

    document = load_json(root / catalog_path, "codm")
    if not isinstance(document, dict) or not isinstance(document.get("apps"), list):
        raise SourceError("codm", "catalog must be an object with an apps list")
    covered = {
        normalize_project_url(app.url)
        for app in higher_precedence
        if Variant.DUAL in app.eligibility
    }
    result: list[App] = []
    identities: dict[str, str] = {}
    for record in document["apps"]:
        app = normalize_record(
            record,
            source="codm2000",
            variant=Variant.DUAL,
            derive_type=True,
            eligibility=frozenset({Variant.DUAL}),
            dual_preferred=True,
            origin="codm-generated",
        )
        previous = identities.get(app.id)
        if previous is not None:
            raise SourceError(
                "codm", f"duplicate id {app.id!r} for {previous!r} and {app.url!r}"
            )
        identities[app.id] = app.url
        if normalize_project_url(app.url) not in covered:
            result.append(app)
            if report is not None:
                report.admitted.append(
                    {
                        "source": "codm2000",
                        "url": app.url,
                        "kind": "track-only"
                        if app.additional_settings.get("trackOnly") is True
                        else "apk",
                        "id": app.id,
                    }
                )
    return result
