from __future__ import annotations

import json
import socket
import urllib.error
from datetime import UTC, datetime, timedelta
from email.message import Message
from urllib.request import Request

import pytest

from omnipack.forge_health import (
    Health,
    HealthUnknown,
    Release,
    check_health,
    github_repository,
)
from omnipack.http import HttpClient, HttpResponse

NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)
REPO_API = "https://api.github.com/repos/owner/app"
RELEASES_API = f"{REPO_API}/releases?per_page=100"


def ago(days: float) -> str:
    return (NOW - timedelta(days=days)).isoformat().replace("+00:00", "Z")


def release(
    tag: str,
    days: float,
    *assets: str,
    prerelease: bool = False,
    draft: bool = False,
    asset_days: float | None = None,
) -> dict[str, object]:
    return {
        "tag_name": tag,
        "draft": draft,
        "prerelease": prerelease,
        "published_at": None if draft else ago(days),
        "assets": [
            {
                "name": name,
                "updated_at": ago(days if asset_days is None else asset_days),
            }
            for name in assets
        ],
    }


class Api:
    """Answer each URL with a JSON body, an HTTP error status or an exception,
    and record every request."""

    def __init__(self, answers: dict[str, object]) -> None:
        self.answers = answers
        self.requests: list[Request] = []

    def __call__(self, request: Request, timeout: float) -> HttpResponse:
        self.requests.append(request)
        answer = self.answers[request.full_url]
        if isinstance(answer, BaseException):
            raise answer
        if isinstance(answer, int):
            raise urllib.error.HTTPError(
                request.full_url, answer, "fixture", Message(), None
            )
        body = answer if isinstance(answer, bytes) else json.dumps(answer).encode()
        return HttpResponse(request.full_url, 200, Message(), body)


def lookup(
    releases: object,
    settings: object = "{}",
    *,
    repository: object = None,
) -> tuple[Health | HealthUnknown, Api]:
    api = Api(
        {
            REPO_API: {"archived": False, "disabled": False}
            if repository is None
            else repository,
            RELEASES_API: releases,
        }
    )
    client = HttpClient(transport=api, sleep=lambda _seconds: None)
    result = check_health("owner/app", settings, client, token=None, now=NOW)
    return result, api


def settings(**values: object) -> str:
    return json.dumps(values)


@pytest.mark.parametrize(
    ("url", "repository"),
    [
        ("https://github.com/owner/app", "owner/app"),
        ("https://www.github.com/Owner/App.git/", "owner/app"),
        ("https://github.com/owner/app/releases", "owner/app"),
        ("https://github.com/owner/app/releases/tag/v1", "owner/app"),
        ("https://github.com/owner", None),
        ("https://github.com", None),
        ("https://gitlab.com/owner/app", None),
        ("https://codeberg.org/owner/app", None),
        ("https://example.com/download.html", None),
    ],
)
def test_only_github_repository_urls_are_forge_targets(
    url: str, repository: str | None
) -> None:
    assert github_repository(url) == repository


def test_an_old_apk_release_is_stale_despite_a_newer_desktop_release() -> None:
    result, _ = lookup(
        [release("v2", 10, "app-linux.tar.gz"), release("v1", 200, "app.apk")]
    )

    assert result == Health(
        archived=False,
        stale=True,
        newest=Release("v1", NOW - timedelta(days=200)),
    )


@pytest.mark.parametrize(("days", "stale"), [(179.99, False), (180, True)])
def test_a_release_is_stale_after_180_whole_days(days: float, stale: bool) -> None:
    result, _ = lookup([release("v1", days, "app.apk")])

    assert isinstance(result, Health)
    assert result.stale is stale


def test_prereleases_count_only_where_the_entry_opts_in() -> None:
    releases = [
        release("nightly", 3, "app.apk", prerelease=True),
        release("v1", 200, "app.apk"),
    ]

    excluded, _ = lookup(releases)
    included, _ = lookup(releases, settings(includePrereleases=True))

    assert isinstance(excluded, Health) and excluded.stale
    assert excluded.newest is not None and excluded.newest.tag == "v1"
    assert isinstance(included, Health) and not included.stale


def test_a_track_only_entry_needs_no_apk() -> None:
    result, _ = lookup([release("v1", 10)], settings(trackOnly=True))

    assert isinstance(result, Health) and not result.stale


@pytest.mark.parametrize("name", ["app.APK", "app.xapk", "app.apkm", "app.apks"])
def test_apk_container_extensions_qualify(name: str) -> None:
    result, _ = lookup([release("v1", 10, name)])

    assert isinstance(result, Health) and not result.stale


def test_a_zip_qualifies_only_where_the_entry_includes_zips() -> None:
    releases = [release("v1", 10, "app.zip")]

    excluded, _ = lookup(releases)
    included, _ = lookup(releases, settings(includeZips=True))

    assert isinstance(excluded, Health) and excluded.stale
    assert excluded.newest is None
    assert isinstance(included, Health) and not included.stale


def test_a_rolling_release_is_dated_by_its_assets() -> None:
    releases = [release("latest", 400, "app.apk", asset_days=5)]

    rolling, _ = lookup(releases, settings(useLatestAssetDateAsReleaseDate=True))
    published, _ = lookup(releases)

    assert isinstance(rolling, Health) and not rolling.stale
    assert isinstance(published, Health) and published.stale


def test_a_rolling_release_is_dated_by_the_newest_of_all_its_assets() -> None:
    rolling = {
        **release("latest", 400),
        "assets": [
            {"name": "app.apk", "updated_at": ago(300)},
            {"name": "win.zip", "updated_at": ago(5)},
        ],
    }

    result, _ = lookup([rolling], settings(useLatestAssetDateAsReleaseDate=True))

    assert isinstance(result, Health) and not result.stale
    assert result.newest == Release("latest", NOW - timedelta(days=5))


def test_the_newest_qualifying_release_is_chosen_by_date() -> None:
    result, _ = lookup([release("v1", 300, "app.apk"), release("v2", 200, "app.apk")])

    assert isinstance(result, Health)
    assert result.newest is not None and result.newest.tag == "v2"


def test_no_qualifying_release_is_stale_without_a_release() -> None:
    result, _ = lookup([release("v1", 10, "app.exe"), release("v0", 20)])

    assert result == Health(archived=False, stale=True, newest=None)


def test_an_empty_release_list_is_stale() -> None:
    result, _ = lookup([])

    assert result == Health(archived=False, stale=True, newest=None)


@pytest.mark.parametrize(
    "repository",
    [{"archived": True, "disabled": False}, {"archived": False, "disabled": True}],
)
def test_an_archived_repository_is_reported_independently_of_staleness(
    repository: dict[str, bool],
) -> None:
    result, _ = lookup([release("v1", 10, "app.apk")], repository=repository)

    assert result == Health(
        archived=True, stale=False, newest=Release("v1", NOW - timedelta(days=10))
    )


def test_a_draft_without_a_publication_date_is_ignored() -> None:
    result, _ = lookup(
        [release("draft", 0, "app.apk", draft=True), release("v1", 10, "app.apk")]
    )

    assert isinstance(result, Health) and not result.stale


def test_a_draft_never_qualifies_even_when_dated() -> None:
    draft = release("draft", 1, "app.apk", draft=True) | {"published_at": ago(1)}

    result, _ = lookup([draft, release("v1", 200, "app.apk")])

    assert isinstance(result, Health) and result.stale


@pytest.mark.parametrize(
    ("answers", "reason"),
    [
        ({REPO_API: 404}, "HTTP 404"),
        ({RELEASES_API: 403}, "HTTP 403"),
        ({RELEASES_API: 429}, "HTTP 429"),
        ({REPO_API: TimeoutError("timed out")}, "timed out"),
        ({REPO_API: socket.gaierror("no such host")}, "no such host"),
        ({RELEASES_API: b"not json"}, "Expecting value"),
        ({RELEASES_API: {"message": "list expected"}}, "releases"),
        ({REPO_API: ["object expected"]}, "repository"),
        ({REPO_API: {"archived": "yes", "disabled": False}}, "repository"),
        ({RELEASES_API: ["release object expected"]}, "release is not an object"),
        ({RELEASES_API: [{"draft": False, "prerelease": False}]}, "date"),
        ({RELEASES_API: [{"published_at": "2026-01-01T00:00:00Z"}]}, "draft"),
        (
            {RELEASES_API: [release("v1", 10, "app.apk") | {"published_at": "soon"}]},
            "soon",
        ),
        (
            {
                RELEASES_API: [
                    release("v1", 10, "app.apk")
                    | {"published_at": "2026-01-01T00:00:00"}
                ]
            },
            "release date has no time zone",
        ),
        (
            {
                RELEASES_API: [
                    release("v1", 10, "app.apk")
                    | {"published_at": "0001-01-01T00:00:00+05:00"}
                ]
            },
            "release date is out of range",
        ),
        (
            {RELEASES_API: [release("v1", 10, "app.apk") | {"tag_name": None}]},
            "tag",
        ),
        (
            {RELEASES_API: [release("v1", 10) | {"assets": [{"name": 1}]}]},
            "asset",
        ),
    ],
)
def test_a_failed_lookup_is_inconclusive_with_its_reason(
    answers: dict[str, object], reason: str
) -> None:
    api = Api(
        {
            REPO_API: {"archived": True, "disabled": False},
            RELEASES_API: [release("v1", 400, "app.apk")],
        }
        | answers
    )
    client = HttpClient(transport=api, sleep=lambda _seconds: None)

    result = check_health("owner/app", "{}", client, token=None, now=NOW)

    assert isinstance(result, HealthUnknown)
    assert reason in result.reason


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        (None, "additionalSettings is not a JSON string"),
        ("{not json", "additionalSettings is not valid JSON"),
        ("[]", "additionalSettings is not a JSON object"),
    ],
)
def test_undecodable_settings_are_inconclusive_without_a_request(
    value: object, reason: str
) -> None:
    result, api = lookup([release("v1", 400, "app.apk")], value)

    assert isinstance(result, HealthUnknown)
    assert result.reason.startswith(reason)
    assert api.requests == []


def test_a_release_date_is_normalized_to_utc() -> None:
    late = release("v1", 10, "app.apk") | {"published_at": "2025-01-31T22:00:00-05:00"}

    result, _ = lookup([late])

    assert isinstance(result, Health)
    assert result.newest == Release("v1", datetime(2025, 2, 1, 3, tzinfo=UTC))
    assert result.newest.date.tzinfo is UTC
