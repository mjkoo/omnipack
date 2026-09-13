"""Shared normalization and diagnostics for source catalogs."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any, Protocol
from urllib.parse import urlsplit

from omnipack.http import HttpResponse
from omnipack.model import App, Provenance, SourceType, Variant
from omnipack.urls import gitlab_project_path


class HttpGetter(Protocol):
    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        max_bytes: int | None = None,
        method: str = "GET",
    ) -> HttpResponse: ...


class SourceError(RuntimeError):
    """A configured source could not be fetched or normalized."""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        super().__init__(f"{source}: {message}")


def source_type(value: object, *, source: str, entry: str) -> SourceType:
    try:
        return SourceType(value)
    except (TypeError, ValueError) as error:
        raise SourceError(
            source, f"entry {entry!r} has unsupported source type {value!r}"
        ) from error


def derived_source_type(url: str) -> SourceType:
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
    return SourceType.HTML


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
    derive_type: bool = False,
    origin: str | None = None,
) -> App:
    if not isinstance(record, dict):
        raise SourceError(source, "catalog entry must be an object")
    label = record.get("name") or record.get("id") or "unnamed entry"
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
    declared_type = record.get("overrideSource")
    kind = (
        derived_source_type(url)
        if derive_type and "overrideSource" not in record
        else source_type(declared_type, source=source, entry=str(label))
    )
    if kind is SourceType.GITLAB:
        _validate_gitlab_url(url, source=source, entry=str(label))
    modeled = {
        "id",
        "url",
        "name",
        "overrideSource",
        "categories",
        "additionalSettings",
        "meta",
        "variants",
        "dualPreferred",
        "dual_preferred",
        "dualScreen",
        "eligible",
        "eligibility",
        "family",
        "origin",
        "originalId",
        "original_id",
        "provenance",
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


def _validate_gitlab_url(url: str, *, source: str, entry: str) -> None:
    try:
        gitlab_project_path(url)
    except ValueError as error:
        raise SourceError(
            source, f"entry {entry!r} has invalid GitLab URL {url!r}"
        ) from error
