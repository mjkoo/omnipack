"""Validated installable Quiver catalogs and deterministic entry rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from omnipack.model import Variant
from omnipack.package_id import PACKAGE_NAME_RE
from omnipack.project_policy import ProjectRule, parse_project_policy, repository_url
from omnipack.quiver_source import QuiverRule
from omnipack.settings_defaults import SETTINGS_DEFAULTS
from omnipack.source_catalog import _rendered_entry, _validate_ids
from omnipack.source_generation import effective_settings
from omnipack.sources.common import SourceError, normalize_record

_POLICY_SETTINGS = {
    "includePrereleases",
    "filterReleaseTitlesByRegEx",
    "apkFilterRegEx",
    "versionExtractionRegEx",
    "matchGroupToUse",
    "fallbackToOlderReleases",
}


def load_quiver_catalog(path: Path) -> list[dict[str, Any]]:
    """Read accepted source records without fetching or changing their bytes."""
    try:
        document = json.loads(path.read_bytes())
        if not isinstance(document, dict) or not isinstance(document.get("apps"), list):
            raise TypeError("catalog must be an object with an apps list")
        entries = document["apps"]
        projects: set[str] = set()
        for entry in entries:
            app = normalize_record(
                entry,
                source="quiver",
                eligibility=frozenset(Variant),
                origin="quiver-generated",
            )
            project = repository_url(app.url)
            if project in projects:
                raise ValueError(f"duplicate normalized project URL {project}")
            projects.add(project)
            if not PACKAGE_NAME_RE.fullmatch(app.id):
                raise ValueError(f"invalid APK package id {app.id!r}")
            if entry.get("overrideSource") != "GitHub":
                raise ValueError(f"{project}: overrideSource must be GitHub")
            defaults = SETTINGS_DEFAULTS["GitHub"]
            for key, value in app.additional_settings.items():
                if key not in defaults or type(value) is not type(defaults[key]):
                    raise ValueError(f"{project}: unsupported setting {key!r}")
            if app.additional_settings.get("trackOnly", False):
                raise ValueError(f"{project}: track-only entries are prohibited")
            if app.additional_settings.get("includeZips", False):
                raise ValueError(
                    f"{project}: generated entries must select direct APKs"
                )
            parse_project_policy(
                {
                    "schemaVersion": 1,
                    "projects": {
                        project: {
                            "kind": "apk",
                            "additionalSettings": {
                                k: v
                                for k, v in app.additional_settings.items()
                                if k in _POLICY_SETTINGS
                            },
                        }
                    },
                }
            )
        _validate_ids(entries)
        return entries
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise SourceError("quiver", str(error)) from error


def render_quiver_entry(
    url: str, name: str, rule: QuiverRule, identifier: str
) -> dict[str, Any]:
    """Render an APK identity with current discovery text and reviewed settings."""
    owner = url.removeprefix("https://").split("/")[1]
    return _rendered_entry(
        {
            "id": identifier,
            "url": url,
            "author": owner,
            "name": rule.name or name,
            "additionalSettings": effective_settings(
                ProjectRule("apk", rule.name, rule.additional_settings)
            ),
            "categories": [rule.category or "Decomps/Recomps"],
            "overrideSource": "GitHub",
        }
    )
