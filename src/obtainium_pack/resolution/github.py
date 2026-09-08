"""Resolve GitHub release metadata within the supported Obtainium boundary."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from obtainium_pack.http import HttpClient, HttpError

from .support import SupportClass, classify_settings
from .types import Candidate, ResolutionError, ResolutionResult
from .version import (
    compile_compatible_regex,
    epoch_microseconds,
    extract_version,
    parse_timestamp,
)

RELEASE_WINDOW = 100
_APK_EXTENSIONS = (".apk", ".xapk", ".apkm", ".apks")
_EPOCH = datetime(1, 1, 1, tzinfo=UTC)


def resolve_github(app: Mapping[str, object], http: HttpClient) -> ResolutionResult:
    """Resolve one validated GitHub entry without probing its candidates."""
    url = _required_string(app, "url")
    settings = _settings(app.get("additionalSettings"))
    _validate_support(settings)
    owner, repository = _repository(url)
    base = f"https://api.github.com/repos/{owner}/{repository}"
    releases, latest_identity = _fetch_records(
        http, base, "releases", latest=settings.get("verifyLatestTag") is True
    )
    inspected_count = len(releases)

    selected = _select_release(releases, settings, latest_identity)
    if selected is None and settings.get("trackOnly") is True:
        tags_url = f"{base}/tags?per_page={RELEASE_WINDOW}"
        try:
            tags = _get_json(http, tags_url)
        except (HttpError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise ResolutionError(
                "github-request-failed", "GitHub tag metadata request failed"
            ) from error
        if not isinstance(tags, list):
            raise ResolutionError(
                "github-invalid-response", "GitHub tags must be a list"
            )
        return _resolve_tag(tags[:RELEASE_WINDOW], settings, inspected_count)
    if selected is None:
        raise ResolutionError(
            "github-no-release", "no release qualifies within the inspected window"
        )
    return _result(selected, settings, inspected_count)


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
    for name, support in classify_settings("GitHub", settings).items():
        if support.classification is SupportClass.LIVE_ERROR:
            raise ResolutionError(
                "unsupported-setting", f"unsupported setting {name}: {support.reason}"
            )


def _repository(url: str) -> tuple[str, str]:
    try:
        parsed = urlsplit(url)
    except ValueError as error:
        raise ResolutionError(
            "github-url-invalid", "GitHub repository URL is malformed"
        ) from error
    if parsed.username is not None or parsed.password is not None:
        raise ResolutionError(
            "github-url-invalid", "embedded credentials are unsupported"
        )
    if parsed.hostname not in {"github.com", "www.github.com"}:
        raise ResolutionError(
            "github-url-invalid", "entry URL is not a GitHub repository"
        )
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise ResolutionError(
            "github-url-invalid", "GitHub URL must identify one repository"
        )
    return parts[0], parts[1]


def _get_json(http: HttpClient, url: str) -> object:
    response = http.get_metadata(url)
    if response.status != 200:
        raise ValueError(f"unexpected status {response.status}")
    return response.json()


def _identity(record: Mapping[str, Any]) -> object:
    tag = record.get("tag_name")
    return record.get("name") if tag is None else tag


def _fetch_records(
    http: HttpClient, base: str, endpoint: str, *, latest: bool
) -> tuple[list[object], str | None]:
    latest_record = None
    latest_identity = None
    if latest:
        latest_endpoint = f"{endpoint}/latest"
        latest_record = _request_metadata(
            http, f"{base}/{latest_endpoint}", latest_endpoint
        )
        if not isinstance(latest_record, dict):
            raise ResolutionError(
                "github-invalid-response", f"GitHub {latest_endpoint} must be an object"
            )
        identity = _identity(latest_record)
        if not isinstance(identity, str) or not identity:
            raise ResolutionError(
                "github-invalid-response",
                f"GitHub {latest_endpoint} must have a nonempty string identity",
            )
        latest_identity = identity
    document = _request_metadata(
        http, f"{base}/{endpoint}?per_page={RELEASE_WINDOW}", endpoint
    )
    if not isinstance(document, list):
        raise ResolutionError(
            "github-invalid-response", f"GitHub {endpoint} must be a list"
        )
    records = document[:RELEASE_WINDOW]
    if latest_record is not None and not any(
        isinstance(record, dict) and _identity(record) == latest_identity
        for record in records
    ):
        records.insert(0, latest_record)
    return records, latest_identity


def _request_metadata(http: HttpClient, url: str, endpoint: str) -> object:
    try:
        return _get_json(http, url)
    except (HttpError, ValueError, TypeError) as error:
        raise ResolutionError(
            "github-request-failed", f"GitHub {endpoint} metadata request failed"
        ) from error


def _ordered_releases(
    releases: list[object], settings: dict[str, Any], latest_identity: str | None = None
) -> list[dict[str, Any]]:
    typed = [release for release in releases if isinstance(release, dict)]
    if settings.get("sortMethodChoice", "date") != "none":
        use_asset_date = settings.get("useLatestAssetDateAsReleaseDate") is True
        typed.sort(
            key=lambda item: (
                _release_date(item, use_asset_date, filtered=False) or _EPOCH
            )
        )
        typed.reverse()
    if latest_identity is not None:
        for index, record in enumerate(typed):
            if _identity(record) == latest_identity:
                typed.insert(0, typed.pop(index))
                break
    return typed


def _select_release(
    releases: list[object], settings: dict[str, Any], latest_identity: str | None = None
) -> dict[str, Any] | None:
    fallback = settings.get("fallbackToOlderReleases") is True
    prereleases = settings.get("includePrereleases") is True
    title_pattern = _optional_regex(settings.get("filterReleaseTitlesByRegEx"))
    notes_pattern = _optional_regex(settings.get("filterReleaseNotesByRegEx"))
    apk_pattern = _optional_regex(settings.get("apkFilterRegEx"))
    invert = settings.get("invertAPKFilter") is True
    track_only = settings.get("trackOnly") is True

    for release in _ordered_releases(releases, settings, latest_identity):
        if release.get("draft") is True:
            continue
        if release.get("prerelease") is True and not prereleases:
            continue
        title = _release_title(release)
        candidates = _candidates(release, apk_pattern, invert)
        matches = (
            (title_pattern is None or title_pattern.search(title.strip()) is not None)
            and (
                notes_pattern is None
                or notes_pattern.search(str(release.get("body") or "").strip())
                is not None
            )
            and (track_only or bool(candidates))
        )
        if matches:
            selected = dict(release)
            selected["_candidates"] = candidates
            selected["_title"] = title
            return selected
        if not fallback:
            break
    return None


def _optional_regex(value: object):
    return compile_compatible_regex(value) if isinstance(value, str) and value else None


def _release_title(release: Mapping[str, Any]) -> str:
    name = release.get("name")
    if isinstance(name, str) and name.strip():
        return name
    tag = release.get("tag_name")
    return str(tag) if tag is not None else ""


def _candidates(
    release: Mapping[str, Any], pattern: Any, invert: bool
) -> tuple[Candidate, ...]:
    assets = release.get("assets")
    if not isinstance(assets, list):
        return ()
    result: list[Candidate] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name")
        url = asset.get("browser_download_url") or asset.get("url")
        if not isinstance(name, str) or not isinstance(url, str):
            continue
        if not name.lower().endswith(_APK_EXTENSIONS):
            continue
        matched = pattern is None or pattern.search(name) is not None
        if invert:
            matched = pattern is None or not matched
        if matched:
            result.append(Candidate(name, url))
    return tuple(result)


def _result(
    release: dict[str, Any], settings: dict[str, Any], inspected_count: int
) -> ResolutionResult:
    title_version = settings.get("releaseTitleAsVersion") is True
    raw = (
        release.get("_title")
        if title_version
        else release.get("tag_name") or release.get("name")
    )
    if not isinstance(raw, str) or not raw:
        raise ResolutionError(
            "github-version-missing", "selected release has no version"
        )
    effective = raw
    origin = "title" if title_version else "tag"
    pattern = settings.get("versionExtractionRegEx")
    if isinstance(pattern, str) and pattern:
        effective = extract_version(raw, pattern, settings.get("matchGroupToUse"))
        origin = "extracted"

    use_asset_date = settings.get("useLatestAssetDateAsReleaseDate") is True
    date = _release_date(release, use_asset_date, filtered=True)
    if settings.get("releaseDateAsVersion") is True:
        if date is None:
            raise ResolutionError(
                "github-date-missing", "selected release has no usable date"
            )
        effective = epoch_microseconds(date)
        origin = "asset-date" if use_asset_date else "release-date"

    selected = {
        "kind": "release",
        "tag": release.get("tag_name"),
        "title": release.get("_title"),
        "published_at": release.get("published_at"),
    }
    return ResolutionResult(
        raw,
        effective,
        origin,
        release["_candidates"],
        selected,
        inspected_count,
        RELEASE_WINDOW,
    )


def _resolve_tag(
    tags: list[object], settings: dict[str, Any], inspected_count: int
) -> ResolutionResult:
    selected = _select_release(tags, settings)
    if selected is None:
        raise ResolutionError(
            "github-no-release", "no release or tag supplies a version"
        )
    result = _result(selected, settings, inspected_count)
    return ResolutionResult(
        result.raw_version,
        result.effective_version,
        result.version_origin,
        result.candidates,
        {"kind": "tag", "tag": result.raw_version},
        result.inspected_count,
        result.window_limit,
    )


def _release_date(
    release: Mapping[str, Any], use_asset_date: bool, *, filtered: bool
) -> datetime | None:
    if not use_asset_date:
        return parse_timestamp(release.get("published_at")) or parse_timestamp(
            release.get("commit", {}).get("created")
            if isinstance(release.get("commit"), dict)
            else None
        )
    assets: object = release.get("assets")
    if filtered:
        candidates = release.get("_candidates")
        names = (
            {candidate.name for candidate in candidates}
            if isinstance(candidates, tuple)
            else set()
        )
        if isinstance(assets, list):
            assets = [
                asset
                for asset in assets
                if isinstance(asset, dict) and asset.get("name") in names
            ]
    if not isinstance(assets, list):
        return None
    dates = [
        parse_timestamp(asset.get("updated_at"))
        for asset in assets
        if isinstance(asset, dict)
    ]
    usable = [date for date in dates if date is not None]
    return max(usable) if usable else None


def _required_string(values: Mapping[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ResolutionError("entry-invalid", f"entry {key} must be a nonempty string")
    return value
