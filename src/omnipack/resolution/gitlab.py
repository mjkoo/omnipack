"""Resolve public GitLab releases within the supported Obtainium boundary."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

from omnipack.http import HttpError, HttpResponse
from omnipack.urls import gitlab_project_path

from .support import SupportClass, classify_settings
from .types import Candidate, ResolutionError, ResolutionResult
from .version import compile_compatible_regex, extract_version

RELEASE_WINDOW = 100
_APK_EXTENSIONS = (".apk", ".xapk", ".apkm", ".apks")
_UPLOAD = re.compile(r"\]\((/uploads/[^)\s]+\.(?:apk|xapk|apkm|apks))\)", re.IGNORECASE)


class MetadataGetter(Protocol):
    """The shared bounded metadata operation used by source resolvers."""

    def get_metadata(
        self, url: str, *, headers: Mapping[str, str] | None = None
    ) -> HttpResponse: ...


def resolve_gitlab(app: Mapping[str, object], http: MetadataGetter) -> ResolutionResult:
    """Resolve one validated public gitlab.com entry without probing assets."""
    url = _required_string(app, "url")
    settings = _settings(app.get("additionalSettings"))
    _validate_support(settings)
    path = _project_path(url)
    encoded = quote(path, safe="")
    base = f"https://gitlab.com/api/v4/projects/{encoded}"
    project = _request(http, base, "project")
    if not isinstance(project, dict) or type(project.get("id")) is not int:
        raise ResolutionError(
            "gitlab-invalid-response", "GitLab project must contain a numeric id"
        )
    document = _request(http, f"{base}/releases?per_page={RELEASE_WINDOW}", "releases")
    if not isinstance(document, list):
        raise ResolutionError(
            "gitlab-invalid-response", "GitLab releases must be a list"
        )
    releases = document[:RELEASE_WINDOW]
    fallback = settings.get("fallbackToOlderReleases") is True
    pattern = _optional_regex(settings.get("apkFilterRegEx"))
    selected: dict[str, Any] | None = None
    candidates: tuple[Candidate, ...] = ()
    for raw in releases:
        if not isinstance(raw, dict):
            if not fallback:
                break
            continue
        version = raw.get("tag_name") or raw.get("name")
        if isinstance(version, str) and version:
            possible = _candidates(raw, project["id"], pattern)
            if possible:
                selected, candidates = raw, possible
                break
        if not fallback:
            break
    if selected is None:
        raise ResolutionError("gitlab-no-apk", "no release supplies a qualifying APK")
    raw_version = selected.get("tag_name") or selected.get("name")
    assert isinstance(raw_version, str)
    effective = raw_version
    origin = "tag"
    extraction = settings.get("versionExtractionRegEx")
    if isinstance(extraction, str) and extraction:
        effective = extract_version(
            raw_version, extraction, settings.get("matchGroupToUse")
        )
        origin = "extracted"
    return ResolutionResult(
        raw_version,
        effective,
        origin,
        candidates,
        {
            "kind": "release",
            "tag": selected.get("tag_name"),
            "released_at": selected.get("released_at") or selected.get("created_at"),
        },
        len(releases),
        RELEASE_WINDOW,
        (("Referer", "https://gitlab.com"),),
    )


def _settings(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ResolutionError(
                "settings-invalid", "additionalSettings is invalid JSON"
            ) from error
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ResolutionError(
            "settings-invalid", "additionalSettings must be an object"
        )
    return value


def _validate_support(settings: dict[str, Any]) -> None:
    for name, support in classify_settings("GitLab", settings).items():
        if support.classification is SupportClass.LIVE_ERROR:
            raise ResolutionError(
                "unsupported-setting", f"unsupported setting {name}: {support.reason}"
            )


def _project_path(url: str) -> str:
    try:
        return gitlab_project_path(url)
    except ValueError as error:
        raise ResolutionError(
            "gitlab-url-invalid", "URL must identify one public gitlab.com project"
        ) from error


def _request(http: MetadataGetter, url: str, endpoint: str) -> object:
    try:
        response = http.get_metadata(url)
        if response.status != 200:
            raise ValueError(f"unexpected status {response.status}")
        return response.json()
    except (HttpError, ValueError, TypeError) as error:
        raise ResolutionError(
            "gitlab-request-failed", f"GitLab {endpoint} metadata request failed"
        ) from error


def _optional_regex(value: object):
    return compile_compatible_regex(value) if isinstance(value, str) and value else None


def _candidates(
    release: Mapping[str, Any], project_id: int, pattern: Any
) -> tuple[Candidate, ...]:
    result: dict[str, str] = {}
    assets = release.get("assets")
    links = assets.get("links") if isinstance(assets, dict) else None
    if isinstance(links, list):
        for link in links:
            if not isinstance(link, dict):
                continue
            url = link.get("direct_asset_url") or link.get("url")
            name = link.get("name")
            if not isinstance(url, str):
                continue
            if not isinstance(name, str) or not name:
                name = urlsplit(url).path.rsplit("/", 1)[-1]
            if _apk(name, url):
                result[name] = url
    description = release.get("description")
    if isinstance(description, str):
        for match in _UPLOAD.finditer(description):
            path = match.group(1)
            name = path.rsplit("/", 1)[-1]
            result[name] = f"https://gitlab.com/-/project/{project_id}{path}"
    return tuple(
        Candidate(name, url)
        for name, url in result.items()
        if pattern is None or pattern.search(name) is not None
    )


def _apk(name: str, url: str) -> bool:
    return name.lower().endswith(_APK_EXTENSIONS) or urlsplit(
        url
    ).path.lower().endswith(_APK_EXTENSIONS)


def _required_string(values: Mapping[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ResolutionError("entry-invalid", f"entry {key} must be a nonempty string")
    return value
