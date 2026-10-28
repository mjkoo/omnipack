from __future__ import annotations

import json
from typing import Any

import pytest

from omnipack.archive import Asset, NoReleaseError, UnreachableError
from omnipack.archive.github import resolve_github
from omnipack.archive.selection import SettingsError, VersionError
from omnipack.forge_health import ResponseError
from omnipack.http import DeadlineExceeded, HttpClient
from tests.http_support import RoutedTransport

REPO = "https://api.github.com/repos/owner/app"
RELEASES = f"{REPO}/releases?per_page=100"
LATEST = f"{REPO}/releases/latest"


def gh_release(
    tag: str,
    published: str,
    *assets: str,
    prerelease: bool = False,
    name: str | None = None,
    body: str = "",
) -> dict[str, Any]:
    return {
        "tag_name": tag,
        "name": name,
        "body": body,
        "draft": False,
        "prerelease": prerelease,
        "published_at": published,
        "assets": [
            {
                "name": asset,
                "updated_at": published,
                "browser_download_url": f"https://github.com/owner/app/releases/download/{tag}/{asset}",
            }
            for asset in assets
        ],
    }


def entry(**settings: object) -> dict[str, Any]:
    return {
        "url": "https://github.com/owner/app",
        "overrideSource": "GitHub",
        "additionalSettings": json.dumps(settings),
    }


def resolve(
    answers: dict[str, Any], entry_: dict[str, Any], **kwargs: Any
) -> tuple[Any, RoutedTransport]:
    transport = RoutedTransport(answers)
    http = HttpClient(transport=transport, sleep=lambda _seconds: None)
    return resolve_github(entry_, http, **kwargs), transport


def test_the_newest_release_resolves_with_every_asset_notes_and_record() -> None:
    newest = gh_release(
        "v2", "2026-03-01T00:00:00Z", "app.apk", "app.exe", "SHA256SUMS", body="Fixes"
    )
    older = gh_release("v1", "2026-01-01T00:00:00Z", "app.apk")

    release, _ = resolve({RELEASES: [older, newest]}, entry(sortMethodChoice="date"))

    assert release.version == "v2"
    assert release.tag == "v2"
    assert release.notes == "Fixes"
    assert release.date is not None and release.date.isoformat().startswith(
        "2026-03-01"
    )
    assert release.raw_record == newest
    assert release.assets == tuple(
        Asset(name, f"https://github.com/owner/app/releases/download/v2/{name}")
        for name in ("app.apk", "app.exe", "SHA256SUMS")
    )


def test_a_release_without_notes_has_none() -> None:
    release, _ = resolve(
        {RELEASES: [gh_release("v1", "2026-01-01T00:00:00Z", "app.apk")]}, entry()
    )

    assert release.notes is None


def test_prereleases_are_excluded_unless_the_entry_includes_them() -> None:
    releases = [
        gh_release("v2-rc", "2026-03-01T00:00:00Z", "app.apk", prerelease=True),
        gh_release("v1", "2026-01-01T00:00:00Z", "app.apk"),
    ]

    stable, _ = resolve(
        {RELEASES: releases},
        entry(fallbackToOlderReleases=True, sortMethodChoice="date"),
    )
    including, _ = resolve(
        {RELEASES: releases}, entry(includePrereleases=True, sortMethodChoice="date")
    )

    assert (stable.version, including.version) == ("v1", "v2-rc")


def test_a_zip_only_release_qualifies_where_the_entry_includes_zips() -> None:
    releases = [gh_release("v1", "2026-01-01T00:00:00Z", "app.zip")]

    release, _ = resolve({RELEASES: releases}, entry(includeZips=True))

    assert release.version == "v1"
    assert [a.name for a in release.assets] == ["app.zip"]
    with pytest.raises(NoReleaseError):
        resolve({RELEASES: releases}, entry())


def test_fallback_selects_an_older_release_with_a_matching_asset() -> None:
    releases = [
        gh_release("v2", "2026-03-01T00:00:00Z", "app-x86.apk"),
        gh_release("v1", "2026-01-01T00:00:00Z", "app-arm64.apk"),
    ]
    settings = {"apkFilterRegEx": "arm64", "sortMethodChoice": "date"}

    release, _ = resolve(
        {RELEASES: releases}, entry(fallbackToOlderReleases=True, **settings)
    )
    assert release.version == "v1"
    with pytest.raises(NoReleaseError):
        resolve({RELEASES: releases}, entry(**settings))


def test_version_extraction_replaces_the_raw_tag() -> None:
    releases = [gh_release("release-1.4", "2026-01-01T00:00:00Z", "app.apk")]

    release, _ = resolve(
        {RELEASES: releases},
        entry(versionExtractionRegEx=r"release-(.+)", matchGroupToUse="$1"),
    )

    assert (release.version, release.tag) == ("1.4", "release-1.4")


def test_an_extraction_pattern_that_matches_nothing_fails_the_target() -> None:
    releases = [gh_release("v1", "2026-01-01T00:00:00Z", "app.apk")]

    with pytest.raises(VersionError):
        resolve({RELEASES: releases}, entry(versionExtractionRegEx=r"nightly-(.+)"))


@pytest.mark.parametrize(
    "releases",
    [
        [],
        [gh_release("v1", "2026-01-01T00:00:00Z", "app.exe")],
        [gh_release("v1", "2026-01-01T00:00:00Z", "app.apk", prerelease=True)],
    ],
)
def test_no_qualifying_release_is_a_no_release_outcome(releases: list[Any]) -> None:
    with pytest.raises(NoReleaseError):
        resolve({RELEASES: releases}, entry())


@pytest.mark.parametrize("status", [404, 410])
def test_a_missing_repository_is_unreachable(status: int) -> None:
    with pytest.raises(UnreachableError):
        resolve({RELEASES: status}, entry())


def test_other_failures_are_not_mapped_to_an_outcome() -> None:
    with pytest.raises(ResponseError):
        resolve({RELEASES: {"message": "nope"}}, entry())


def test_verify_latest_tag_ranks_the_forges_latest_release_newest() -> None:
    releases = [
        gh_release("v2", "2026-03-01T00:00:00Z", "app.apk"),
        gh_release("v1", "2026-01-01T00:00:00Z", "app.apk"),
    ]
    latest = releases[1]

    release, transport = resolve(
        {RELEASES: releases, LATEST: latest},
        entry(verifyLatestTag=True, sortMethodChoice="date"),
    )

    assert release.version == "v1"
    assert [r.full_url for r in transport.requests] == [RELEASES, LATEST]


def test_a_missing_latest_release_is_a_no_release_outcome() -> None:
    releases = [gh_release("v1", "2026-01-01T00:00:00Z", "app.apk")]

    with pytest.raises(NoReleaseError):
        resolve({RELEASES: releases, LATEST: 404}, entry(verifyLatestTag=True))


def test_the_token_goes_only_to_the_api_and_the_accept_header_is_json() -> None:
    releases = [gh_release("v1", "2026-01-01T00:00:00Z", "app.apk")]

    _, transport = resolve({RELEASES: releases}, entry(), token="secret")
    _, anonymous = resolve({RELEASES: releases}, entry())

    request = transport.requests[0]
    assert request.get_header("Authorization") == "Bearer secret"
    assert request.get_header("Accept") == "application/vnd.github+json"
    assert anonymous.requests[0].get_header("Authorization") is None


def test_the_deadline_bounds_the_requests() -> None:
    transport = RoutedTransport({})
    http = HttpClient(transport=transport, clock=lambda: 10.0)

    with pytest.raises(DeadlineExceeded):
        resolve_github(entry(), http, deadline=10.0)

    assert transport.requests == []


@pytest.mark.parametrize(
    "bad",
    [
        {"url": "https://example.com/owner/app", "additionalSettings": "{}"},
        {"url": "https://github.com/owner/app", "additionalSettings": "["},
        {
            "url": "https://github.com/owner/app",
            "additionalSettings": '{"apkFilterRegEx": "("}',
        },
    ],
)
def test_an_unusable_entry_fails_without_a_request(bad: dict[str, Any]) -> None:
    transport = RoutedTransport({})
    http = HttpClient(transport=transport)

    with pytest.raises((ValueError, SettingsError)):
        resolve_github(bad, http)

    assert transport.requests == []
