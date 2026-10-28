"""Resolve a GitLab entry to the release Obtainium would show.

Obtainium reads gitlab.com's releases API and honours far fewer settings
than for GitHub: it takes the newest release, or with fallback the newest
that offers an APK, then applies the APK filter to that release alone.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from omnipack.archive import Asset, NoReleaseError, ResolvedRelease
from omnipack.archive.fetch import fetch
from omnipack.archive.selection import (
    APK_SUFFIXES,
    Candidate,
    ReleaseAsset,
    ReleaseSettings,
    SortMethod,
    is_installable,
    passes,
    release_version,
    select_release,
)
from omnipack.forge_health import decode_settings
from omnipack.http import HttpClient
from omnipack.urls import normalize_project_url

HOST = "gitlab.com"
API = f"https://{HOST}/api/v4/projects"
RELEASES_PER_PAGE = 100
# An APK a release links without a file extension is named or addressed by an
# "apk" token.
_APK_TOKEN = re.compile(r"(^|[^a-z])apk([^a-z]|$)", re.IGNORECASE)


def resolve_gitlab(
    entry: dict[str, Any],
    http: HttpClient,
    *,
    deadline: float | None = None,
) -> ResolvedRelease:
    """The release Obtainium selects for a GitLab pack entry.

    `deadline` is a reading of `http`'s clock that bounds every request.
    Raises `UnreachableError` for a missing project and `NoReleaseError`
    when no release offers a qualifying APK; anything else is a failure.
    """
    host, _, path = normalize_project_url(entry["url"]).partition("/")
    if host != HOST or not path:
        raise ValueError(f"not a {HOST} project URL: {entry['url']}")
    options = decode_settings(entry.get("additionalSettings"))
    settings = ReleaseSettings.from_options(options)

    headers = {"Referer": f"https://{HOST}"}
    project_api = f"{API}/{quote(path, safe='')}"
    project = fetch(http, project_api, headers=headers, deadline=deadline).json()
    project_id = project.get("id") if isinstance(project, dict) else None
    if not isinstance(project_id, int):
        raise NoReleaseError("the project has no id")
    response = fetch(
        http,
        f"{project_api}/releases?per_page={RELEASES_PER_PAGE}",
        headers=headers,
        deadline=deadline,
    )
    records = response.json()
    if not isinstance(records, list):
        raise NoReleaseError("the project has no releases")

    project_url = f"https://{HOST}/{path}"
    candidates = [
        candidate
        for record in records
        if (candidate := _candidate(record, project_id, project_url)) is not None
    ]
    # Only fallback shapes the choice, in the order GitLab lists the releases;
    # the APK filter comes after it.
    selected = select_release(
        candidates,
        ReleaseSettings(
            sort_method=SortMethod.NONE, fallback_to_older=settings.fallback_to_older
        ),
    )
    if selected is None:
        raise NoReleaseError("no release offers an APK")
    if settings.apk_filter is not None:
        kept = [
            a
            for a in selected.installable
            if passes(settings.apk_filter, a.name, settings.invert_apk_filter)
        ]
        if not kept:
            raise NoReleaseError("no APK passes the entry's filter")

    release = selected.candidate
    version_settings = replace(settings, release_title_as_version=False)
    return ResolvedRelease(
        version=release_version(selected, version_settings),
        tag=release.tag,
        date=selected.date,
        notes=release.notes or None,
        raw_record=release.record,
        assets=tuple(a for a, _ in _assets(release.record, project_id, project_url)),
    )


def _candidate(record: Any, project_id: int, project_url: str) -> Candidate | None:
    if not isinstance(record, dict):
        return None
    tag, title = record.get("tag_name"), record.get("name")
    if tag is None and title is None:
        return None
    notes = record.get("description")
    return Candidate(
        tag=tag if isinstance(tag, str) else None,
        title=title if isinstance(title, str) else None,
        notes=notes if isinstance(notes, str) else "",
        published=_date(record),
        prerelease=False,
        draft=False,
        assets=tuple(
            ReleaseAsset(asset.name, installable)
            for asset, installable in _assets(record, project_id, project_url)
        ),
        record=record,
    )


def _date(record: dict[str, Any]) -> datetime | None:
    commit = record.get("commit")
    value = (
        record.get("released_at")
        or record.get("created_at")
        or (commit.get("created_at") if isinstance(commit, dict) else None)
    )
    try:
        date = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return date if date.tzinfo else date.replace(tzinfo=UTC)


def _assets(
    record: dict[str, Any], project_id: int, project_url: str
) -> list[tuple[Asset, bool]]:
    """Every file the release offers, once per file name, with whether it is
    an APK: its asset links, then the APKs its description links from the
    project's uploads, which replace a link to a file of the same name."""
    found: dict[str, tuple[Asset, bool]] = {}
    job_artifact = re.compile(
        f"^{re.escape(project_url)}/-/jobs/[0-9]+/artifacts/file/[^/]+"
    )
    assets = record.get("assets")
    links = assets.get("links") if isinstance(assets, dict) else None
    for link in links if isinstance(links, list) else []:
        if not isinstance(link, dict):
            continue
        url = link.get("direct_asset_url") or link.get("url") or ""
        if not isinstance(url, str) or not url:
            continue
        name = link.get("name")
        name = name if isinstance(name, str) else ""
        installable = _is_apk(name, url, link.get("link_type"))
        if job_artifact.match(url):
            url = url.replace("/file/", "/raw/", 1)
        file_name = name or unquote(urlsplit(url).path.rsplit("/", 1)[-1]) or "unknown"
        found.setdefault(file_name, (Asset(file_name, url), installable))
    for line in _description_uploads(record.get("description")):
        url = f"https://{HOST}/-/project/{project_id}{line}"
        file_name = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
        found[file_name] = (Asset(file_name, url), True)
    return list(found.values())


def _is_apk(name: str, url: str, link_type: object) -> bool:
    if is_installable(name) or is_installable(url):
        return True
    return link_type == "package" and bool(
        _APK_TOKEN.search(name) or _APK_TOKEN.search(url)
    )


def _description_uploads(description: object) -> list[str]:
    """The APK upload paths a release description links, found as Obtainium
    finds them: split at each markdown link target and APK extension."""
    if not isinstance(description, str):
        return []
    text = description.replace("](", "\n")
    for extension in APK_SUFFIXES:
        text = text.replace(f"{extension})", f"{extension}\n")
    return [
        line
        for line in text.split("\n")
        if line.startswith("/uploads/") and is_installable(line)
    ]
