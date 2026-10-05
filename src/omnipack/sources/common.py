"""Shared normalization and diagnostics for source catalogs."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol
from urllib.parse import urlsplit

from omnipack.http import HttpResponse
from omnipack.model import App, Provenance, SourceType, Variant


class HttpGetter(Protocol):
    def get(self, url: str) -> HttpResponse: ...


class SourceError(RuntimeError):
    """A configured source could not be fetched or normalized."""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        super().__init__(f"{source}: {message}")


def declared_source_type(value: object, *, source: str, entry: str) -> str:
    """Keep any source type a record declares; Obtainium supports many more
    than the pack holds default settings for."""
    if not isinstance(value, str):
        raise SourceError(
            source, f"entry {entry!r} has malformed source type {value!r}"
        )
    return value


def derived_source_type(url: str) -> SourceType | None:
    """Derive the source type of a URL whose type is unambiguous.

    A github.com repository is GitHub and a gitlab.com project is GitLab. Any
    other URL gets no source type, leaving detection to Obtainium.
    """
    parsed = urlsplit(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower().removeprefix("www.")
    parts = parsed.path.strip("/").split("/")
    # GitHub site routes share the host but do not identify repositories.
    site_routes = {
        "about",
        "account",
        "apps",
        "codespaces",
        "collections",
        "contact",
        "customer-stories",
        "enterprise",
        "events",
        "explore",
        "features",
        "issues",
        "join",
        "login",
        "marketplace",
        "new",
        "notifications",
        "organizations",
        "orgs",
        "pricing",
        "pulls",
        "search",
        "security",
        "sessions",
        "settings",
        "signup",
        "site",
        "sponsors",
        "stars",
        "topics",
        "trending",
        "users",
    }
    if (
        host == "github.com"
        and len(parts) >= 2
        and parts[0].lower() not in site_routes
        and re.fullmatch(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", parts[0])
        and re.fullmatch(r"[A-Za-z0-9_.-]+", parts[1])
        and parts[1] not in {".", ".."}
    ):
        return SourceType.GITHUB
    # A gitlab.com project is a namespace path and a project; GitLab reserves
    # the `-` segment for its own routes inside a project.
    segments = [part for part in parts if part]
    if host == "gitlab.com" and len(segments) >= 2 and "-" not in segments:
        return SourceType.GITLAB
    return None


def settings(value: object, *, source: str, entry: str) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise SourceError(
                source, f"entry {entry!r} has malformed additionalSettings"
            ) from error
    if not isinstance(value, dict):
        raise SourceError(
            source, f"entry {entry!r} additionalSettings must decode to an object"
        )
    return dict(value)


def normalize_record(
    record: object,
    *,
    source: str,
    eligibility: frozenset[Variant],
    origin: str = "",
    default_label: str = "unnamed entry",
) -> App:
    if not isinstance(record, dict):
        raise SourceError(source, "catalog entry must be an object")
    label = record.get("name") or record.get("id") or default_label
    guarded = record.keys() & {"family", "variant"}
    if guarded:
        field = min(guarded)
        raise SourceError(
            source,
            f"entry {label!r} field {field!r} cannot come from a source record; "
            "composition policy in config/composition.json owns app families "
            "and per-pack selection",
        )
    for field in ("id", "url", "name"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise SourceError(source, f"entry {label!r} is missing {field}")
    categories = record.get("categories", [])
    if not isinstance(categories, list) or not all(
        isinstance(item, str) for item in categories
    ):
        raise SourceError(
            source, f"entry {label!r} categories must be a list of strings"
        )
    url = record["url"]
    kind = (
        declared_source_type(record["overrideSource"], source=source, entry=str(label))
        if "overrideSource" in record
        else derived_source_type(url)
    )
    modeled = {
        "id",
        "url",
        "name",
        "overrideSource",
        "categories",
        "additionalSettings",
        "meta",
    }
    return App(
        id=record["id"],
        url=url,
        name=record["name"],
        source_type=kind,
        categories=tuple(categories),
        provenance=Provenance(source, url),
        eligibility=eligibility,
        additional_settings=settings(
            record.get("additionalSettings"), source=source, entry=str(label)
        ),
        raw={key: value for key, value in record.items() if key not in modeled},
        origin=origin,
    )
