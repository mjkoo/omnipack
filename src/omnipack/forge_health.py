"""Read a GitHub project's update health the way Obtainium judges it.

A project is archived when GitHub reports its repository archived or
disabled, and stale when its newest qualifying release is 180 or more whole
days old, or when none of its newest 100 releases qualifies. A release
qualifies by the pack entry's own settings: drafts never do, prereleases only
for an entry that includes them, and otherwise any release of a track-only
entry or one carrying an APK-like asset. Per-entry release selection beyond
that, such as APK filters or version extraction, is deliberately left out.
The selection itself is the one the release archive uses.

Only GitHub repository URLs get a lookup. A lookup that cannot finish, for
any reason, is inconclusive rather than a guess.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from omnipack.archive.selection import (
    Candidate,
    ReleaseAsset,
    ReleaseSettings,
    SettingsError,
    SortMethod,
    is_installable,
    select_release,
)
from omnipack.http import HttpClient, HttpError, failure_reason
from omnipack.urls import normalize_project_url

API = "https://api.github.com"
STALE_DAYS = 180
RELEASES_PER_PAGE = 100


class ResponseError(ValueError):
    """A GitHub response has a shape or value the lookup cannot judge."""


@dataclass(frozen=True, slots=True)
class Release:
    """A qualifying release: its tag and the UTC date it is judged by."""

    tag: str
    date: datetime


@dataclass(frozen=True, slots=True)
class Health:
    """A finished lookup; `newest` is the newest qualifying release, if any."""

    archived: bool
    stale: bool
    newest: Release | None


@dataclass(frozen=True, slots=True)
class HealthUnknown:
    """A lookup that could not finish, with the reason naming its cause."""

    reason: str


def github_repository(url: str) -> str | None:
    """The `owner/repo` a pack URL names on github.com, otherwise None.

    The URL is normalized first, so a releases or tag page counts as its
    repository.
    """
    try:
        normalized = normalize_project_url(url)
    except ValueError:
        return None
    host, _, path = normalized.partition("/")
    segments = path.split("/")
    if host != "github.com" or len(segments) != 2 or not all(segments):
        return None
    return path


def decode_settings(settings: object) -> dict[str, Any]:
    """Decode an entry's `additionalSettings`, a JSON-encoded object in the
    committed packs, raising `SettingsError` naming the problem."""
    if not isinstance(settings, str):
        raise SettingsError("additionalSettings is not a JSON string")
    try:
        decoded = json.loads(settings)
    except ValueError as error:
        raise SettingsError(f"additionalSettings is not valid JSON: {error}") from error
    if not isinstance(decoded, dict):
        raise SettingsError("additionalSettings is not a JSON object")
    return decoded


def check_health(
    repository: str,
    settings: object,
    http: HttpClient,
    *,
    token: str | None,
    now: datetime,
    before_request: Callable[[], None] = lambda: None,
) -> Health | HealthUnknown:
    """Look up one repository's archive state and newest qualifying release.

    `settings` is the entry's `additionalSettings`. `token`, when given, is
    sent only to the GitHub API and never forwarded on a redirect.
    `before_request` runs before each request; an exception it raises is not
    caught, so a caller can stop the lookup.
    """
    credential = f"Bearer {token}" if token else None
    try:
        options = decode_settings(settings)
        before_request()
        state = _get_json(http, f"{API}/repos/{repository}", credential)
        before_request()
        releases = _get_json(
            http,
            f"{API}/repos/{repository}/releases?per_page={RELEASES_PER_PAGE}",
            credential,
        )
        archived = _repository_archived(state)
        newest = _newest_qualifying(releases, options)
    except (HttpError, ValueError) as error:
        return HealthUnknown(failure_reason(error))
    stale = newest is None or (now - newest.date).days >= STALE_DAYS
    return Health(archived=archived, stale=stale, newest=newest)


def _get_json(http: HttpClient, url: str, credential: str | None) -> object:
    headers = {"Accept": "application/vnd.github+json"}
    return http.get(url, headers=headers, credential=credential).json()


def _repository_archived(state: object) -> bool:
    if not isinstance(state, dict):
        raise ResponseError("repository response is not an object")
    archived, disabled = state.get("archived"), state.get("disabled")
    if not isinstance(archived, bool) or not isinstance(disabled, bool):
        raise ResponseError("repository response lacks archived and disabled flags")
    return archived or disabled


def _newest_qualifying(releases: object, options: dict[str, Any]) -> Release | None:
    settings = ReleaseSettings(
        include_prereleases=options.get("includePrereleases") is True,
        include_zips=options.get("includeZips") is True,
        track_only=options.get("trackOnly") is True,
        use_latest_asset_date=options.get("useLatestAssetDateAsReleaseDate") is True,
        sort_method=SortMethod.DATE,
        fallback_to_older=True,
    )
    # The health lookup dates a release by every asset, installable or not.
    selected = select_release(
        github_candidates(releases, settings), settings, date_by_all_assets=True
    )
    if selected is None:
        return None
    tag = selected.candidate.tag
    if tag is None:
        raise ResponseError("qualifying release has no tag")
    if selected.date is None:
        raise ResponseError("qualifying release has no date")
    return Release(tag, selected.date)


def github_candidates(releases: object, settings: ReleaseSettings) -> list[Candidate]:
    """Normalize a GitHub releases response for selection, raising
    `ResponseError` for a shape the lookup cannot judge.

    A release that selection will skip is not inspected further: a draft
    carries no publication date, and a prerelease the entry excludes is
    never dated.
    """
    if not isinstance(releases, list):
        raise ResponseError("releases response is not a list")
    candidates: list[Candidate] = []
    for release in releases:
        if not isinstance(release, dict):
            raise ResponseError("release is not an object")
        draft, prerelease = release.get("draft"), release.get("prerelease")
        if not isinstance(draft, bool) or not isinstance(prerelease, bool):
            raise ResponseError("release lacks draft and prerelease flags")
        published, assets = None, ()
        if not draft and (settings.include_prereleases or not prerelease):
            published = _parse_date(release.get("published_at"))
            assets = tuple(_release_asset(a, settings) for a in _assets(release))
        tag, title, notes = (
            release.get("tag_name"),
            release.get("name"),
            release.get("body"),
        )
        candidates.append(
            Candidate(
                tag=tag if isinstance(tag, str) else None,
                title=title if isinstance(title, str) else None,
                notes=notes if isinstance(notes, str) else "",
                published=published,
                prerelease=prerelease,
                draft=draft,
                assets=assets,
                record=release,
            )
        )
    return candidates


def _release_asset(asset: dict[str, Any], settings: ReleaseSettings) -> ReleaseAsset:
    name = asset.get("name")
    if not isinstance(name, str):
        raise ResponseError("release asset has no name")
    updated = None
    if settings.use_latest_asset_date:
        updated = _parse_date(asset.get("updated_at") or asset.get("created_at"))
    return ReleaseAsset(
        name, is_installable(name, include_zips=settings.include_zips), updated
    )


def _assets(release: dict[str, Any]) -> list[dict[str, Any]]:
    assets = release.get("assets", [])
    if not isinstance(assets, list) or not all(
        isinstance(asset, dict) for asset in assets
    ):
        raise ResponseError("release assets are not a list of objects")
    return assets


def _parse_date(value: object) -> datetime:
    if not isinstance(value, str):
        raise ResponseError(f"release date is missing: {value!r}")
    date = datetime.fromisoformat(value)
    if date.tzinfo is None:
        raise ResponseError(f"release date has no time zone: {value!r}")
    try:
        return date.astimezone(UTC)
    except OverflowError as error:
        raise ResponseError(f"release date is out of range: {value!r}") from error
