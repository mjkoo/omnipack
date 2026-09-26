"""Bounded GitHub release selection shared by generated sources."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from omnipack.project_policy import ProjectRule
from omnipack.source_http import GenerationHttp

MAX_RELEASES = 100


class NoPermittedRelease(ValueError):
    """A successful bounded release list had no permitted release."""


def _release_api(project: str, listed: bool) -> str:
    _, owner, repo = project.split("/")
    suffix = "releases?per_page=100&page=1" if listed else "releases/latest"
    return f"https://api.github.com/repos/{owner}/{repo}/{suffix}"


def _release_id(release: dict[str, Any]) -> int:
    value = release.get("id")
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("release has no host-assigned identifier")
    if value <= 0:
        raise ValueError("release has an invalid host-assigned identifier")
    return value


def select_release(
    http: GenerationHttp, project: str, rule: ProjectRule
) -> dict[str, Any]:
    settings = rule.additional_settings
    listed = bool(
        settings.get("includePrereleases") or settings.get("filterReleaseTitlesByRegEx")
    )
    document = http.get(
        _release_api(project, listed), headers={"Accept": "application/vnd.github+json"}
    ).json()
    if not listed:
        if not isinstance(document, dict):
            raise ValueError("unexpected latest release response")
        _publication_time(document)
        _release_id(document)
        if document.get("draft") is True or document.get("prerelease") is True:
            raise ValueError("latest release must be published and stable")
        return document
    if not isinstance(document, list):
        raise TypeError("unexpected releases-list response")
    if len(document) > MAX_RELEASES:
        raise ValueError("release scan exceeded the 100-release bound")
    title_pattern = settings.get("filterReleaseTitlesByRegEx", "")
    pattern = re.compile(title_pattern) if title_pattern else None
    candidates: list[tuple[datetime, int, dict[str, Any]]] = []
    for release in document:
        if not isinstance(release, dict) or release.get("draft") is True:
            continue
        if release.get("prerelease") is True and not settings.get(
            "includePrereleases", False
        ):
            continue
        release_id = _release_id(release)
        timestamp = _publication_time(release)
        title = release.get("name")
        if title is None or (isinstance(title, str) and not title.strip()):
            title = release.get("tag_name")
        if not isinstance(title, str):
            raise TypeError("release has no title or tag")
        if pattern and pattern.search(title.strip()) is None:
            continue
        candidates.append((timestamp, release_id, release))
    if not candidates:
        raise NoPermittedRelease("no permitted release in the bounded 100-release scan")
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def _publication_time(release: dict[str, Any]) -> datetime:
    for flag in ("draft", "prerelease"):
        if flag in release and not isinstance(release[flag], bool):
            raise TypeError(f"release {flag} must be boolean")
    published = release.get("published_at")
    if not isinstance(published, str):
        raise TypeError("release has no publication date")
    try:
        timestamp = datetime.fromisoformat(published)
    except ValueError as error:
        raise ValueError(f"invalid release publication date {published!r}") from error
    if timestamp.tzinfo is None:
        raise ValueError("release publication date requires a timezone")
    return timestamp
