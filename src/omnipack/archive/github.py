"""Resolve a GitHub entry to the release Obtainium would show.

The releases come from the REST API, 100 at a time like Obtainium's request,
and the selection is the shared one. Assets are listed by their public
download URL, which needs no API request, rather than the API URL Obtainium
uses to install.
"""

from __future__ import annotations

from typing import Any

from omnipack.archive import Asset, NoReleaseError, ResolvedRelease, UnreachableError
from omnipack.archive.fetch import fetch
from omnipack.archive.selection import (
    ReleaseSettings,
    release_version,
    select_release,
)
from omnipack.forge_health import (
    GITHUB_API,
    RELEASES_PER_PAGE,
    ResponseError,
    decode_settings,
    github_candidates,
    github_repository,
)
from omnipack.http import HttpClient


def resolve_github(
    entry: dict[str, Any],
    http: HttpClient,
    *,
    token: str | None = None,
    deadline: float | None = None,
) -> ResolvedRelease:
    """The release Obtainium selects for a GitHub pack entry.

    `token`, when given, is sent only to the GitHub API. `deadline` is a
    reading of `http`'s clock that bounds every request. Raises
    `UnreachableError` for a missing repository and `NoReleaseError` when no
    release qualifies; anything else that goes wrong is a failure.
    """
    repository = github_repository(entry["url"])
    if repository is None:
        raise ValueError(f"not a github.com repository URL: {entry['url']}")
    settings = ReleaseSettings.from_options(
        decode_settings(entry.get("additionalSettings"))
    )
    credential = f"Bearer {token}" if token else None

    def get_json(url: str) -> Any:
        response = fetch(
            http,
            url,
            headers={"Accept": "application/vnd.github+json"},
            credential=credential,
            deadline=deadline,
        )
        return response.json()

    releases = get_json(
        f"{GITHUB_API}/repos/{repository}/releases?per_page={RELEASES_PER_PAGE}"
    )
    latest = None
    if settings.verify_latest_tag:
        try:
            latest_record = get_json(f"{GITHUB_API}/repos/{repository}/releases/latest")
        except UnreachableError as error:
            raise NoReleaseError("the repository has no latest release") from error
        [latest] = github_candidates([latest_record], settings)
    selected = select_release(
        github_candidates(releases, settings), settings, latest=latest
    )
    if selected is None:
        raise NoReleaseError("no release qualifies under the entry's settings")

    release = selected.candidate
    return ResolvedRelease(
        version=release_version(selected, settings),
        tag=release.tag,
        date=selected.date,
        notes=release.notes or None,
        raw_record=release.record,
        assets=tuple(_asset(a) for a in release.record.get("assets", [])),
    )


def _asset(record: dict[str, Any]) -> Asset:
    name = record.get("name")
    # The API `url` would answer with JSON metadata, not the file.
    url = record.get("browser_download_url")
    if not isinstance(name, str) or not isinstance(url, str):
        raise ResponseError("release asset lacks a name or download URL")
    return Asset(name, url)
