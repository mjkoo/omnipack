from __future__ import annotations

import json
from email.message import Message
from typing import Any

import pytest

from omnipack.discovery import (
    DiscoveryError,
    EmptyDiscovery,
    GeneratedSource,
    Listing,
    SkipReason,
    discover,
)
from omnipack.http import HttpError, HttpResponse
from omnipack.urls import normalize_project_url

README_URL = "https://example.test/README.md"
INDEX_URL = "https://catalog.test/quiver/index.json"
LIST_URL = "https://catalog.test/quiver/lists/one.json"
ASSETS_URL = "https://catalog.test/quiver/platform-index.json"


class FakeHttp:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def get(self, url: str) -> HttpResponse:
        self.urls.append(url)
        value = self.responses.get(url, HttpError(f"no response for {url}"))
        if isinstance(value, Exception):
            raise value
        if not isinstance(value, (str, bytes)):
            value = json.dumps(value)
        body = value if isinstance(value, bytes) else value.encode()
        return HttpResponse(url, 200, Message(), body)


def codm(readme: str, committed: frozenset[str] = frozenset()) -> list[Listing]:
    http = FakeHttp({README_URL: readme})
    discovery = discover(
        GeneratedSource.CODM, {"readme_url": README_URL}, http, committed
    )
    assert http.urls == [README_URL]
    assert discovery.skipped == ()
    return list(discovery.listings)


TABLE = "| Project | Game |\n|---|---|\n"


def test_codm_takes_every_link_in_the_project_tables_whatever_its_host() -> None:
    readme = (
        "Intro [outside](https://github.com/outside/repo)\n\n"
        + TABLE
        + "| [Kanto Gear 🤖](https://github.com/AverageConsumer/kanto-gear) | x |\n"
        + "| [Pokétch](https://christt105.itch.io/poketch) | y |\n\n"
        + "```\n| [Fenced](https://github.com/fenced/repo) | z |\n```\n\n"
        + "| Project | Description |\n|---|---|\n"
        + "| [Hermit](https://play.google.com/store/apps/details?id=a) "
        + "| alt [Native Alpha](https://github.com/cylonid/NativeAlphaForAndroid) |\n"
    )
    assert codm(readme) == [
        Listing("https://github.com/AverageConsumer/kanto-gear", "Kanto Gear 🤖"),
        Listing("https://christt105.itch.io/poketch", "Pokétch"),
        Listing("https://play.google.com/store/apps/details?id=a", "Hermit"),
        Listing("https://github.com/cylonid/NativeAlphaForAndroid", "Native Alpha"),
    ]


def test_codm_link_inside_an_indented_code_block_is_not_a_project() -> None:
    readme = (
        TABLE
        + "| [A](https://github.com/a/a) | x |\n\n    | [B](https://github.com/b/b) |\n"
    )
    assert [listing.url for listing in codm(readme)] == ["https://github.com/a/a"]


@pytest.mark.parametrize(
    "broken",
    [
        "| Project | Game |\n| [B](https://github.com/b/b) | y |\n",
        "| Project | Game |\n|--|\n",
    ],
    ids=["missing-delimiter", "invalid-delimiter"],
)
def test_a_malformed_project_table_beside_a_valid_one_fails(broken: str) -> None:
    readme = TABLE + "| [A](https://github.com/a/a) | x |\n\n" + broken
    with pytest.raises(DiscoveryError, match="delimiter"):
        codm(readme)


def test_a_readme_without_a_project_table_fails() -> None:
    with pytest.raises(DiscoveryError, match="no Project table"):
        codm("# Nothing here\n")


def test_codm_is_not_screened_even_for_a_project_with_no_release() -> None:
    readme = TABLE + "| [A](https://github.com/new/project) | x |\n"
    assert codm(readme) == [Listing("https://github.com/new/project", "A")]


def test_codm_tables_without_links_discover_nothing() -> None:
    with pytest.raises(EmptyDiscovery):
        codm(TABLE + "| plain text | x |\n")


# --- Quiver ---------------------------------------------------------------


def asset(repository: str, *names: str, provider: str = "github") -> dict[str, Any]:
    return {
        "provider": provider,
        "repository": repository,
        "preferredRelease": None,
        "releaseTag": "v1",
        "assetNames": list(names),
    }


def quiver_http(
    rows: list[dict[str, Any]],
    assets: list[dict[str, Any]] | None = None,
    **overrides: Any,
) -> FakeHttp:
    responses: dict[str, Any] = {
        INDEX_URL: {
            "version": 2,
            "lists": [{"id": "one", "remoteLocation": LIST_URL}],
            "platformMetadataUrl": ASSETS_URL,
        },
        LIST_URL: {"name": "One", "apps": rows},
        ASSETS_URL: {"formatRevision": 1, "entries": assets or []},
    }
    responses.update(overrides)
    return FakeHttp(responses)


def quiver(http: FakeHttp, committed: frozenset[str] = frozenset()):
    return discover(GeneratedSource.QUIVER, {"index_url": INDEX_URL}, http, committed)


def row(repository: object, project: str = "Port", **fields: Any) -> dict[str, Any]:
    return {"project": project, "repository": repository, **fields}


def test_quiver_reads_only_the_index_its_lists_and_the_asset_name_file() -> None:
    http = quiver_http([row("owner/repo")], [asset("owner/repo", "app.apk")])
    discovery = quiver(http)
    assert discovery.listings == (Listing("https://github.com/owner/repo", "Port"),)
    assert http.urls == [INDEX_URL, ASSETS_URL, LIST_URL]


@pytest.mark.parametrize(
    ("fields", "url"),
    [
        ({}, "https://github.com/owner/repo"),
        ({"repositorySource": None}, "https://github.com/owner/repo"),
        ({"repositorySource": "GitHub"}, "https://github.com/owner/repo"),
        ({"repositorySource": "GITLAB"}, "https://gitlab.com/owner/repo"),
    ],
    ids=["absent", "null", "mixed-case-github", "mixed-case-gitlab"],
)
def test_quiver_forms_the_project_url_from_the_forge(
    fields: dict[str, Any], url: str
) -> None:
    provider = "gitlab" if "gitlab" in url else "github"
    http = quiver_http(
        [row("owner/repo", **fields)], [asset("owner/repo", "a.apk", provider=provider)]
    )
    assert [listing.url for listing in quiver(http).listings] == [url]


def test_gitlab_row_in_a_nested_group_keeps_its_whole_path() -> None:
    http = quiver_http(
        [row("group/subgroup/app", repositorySource="gitlab")],
        [asset("group/subgroup/app", "app.apk", provider="gitlab")],
    )
    assert [listing.url for listing in quiver(http).listings] == [
        "https://gitlab.com/group/subgroup/app"
    ]


@pytest.mark.parametrize(
    ("bad", "reason"),
    [
        (row("owner/repo", repositorySource="codeberg"), SkipReason.UNKNOWN_FORGE),
        (row("owner/repo", repositorySource=7), SkipReason.UNKNOWN_FORGE),
        (row(None), SkipReason.INVALID_REPOSITORY),
        (row(["owner", "repo"]), SkipReason.INVALID_REPOSITORY),
        (row("owner"), SkipReason.INVALID_REPOSITORY),
        (row("owner/repo/extra"), SkipReason.INVALID_REPOSITORY),
        (row("owner//repo", repositorySource="gitlab"), SkipReason.INVALID_REPOSITORY),
        (row("owner/my repo"), SkipReason.INVALID_REPOSITORY),
    ],
    ids=[
        "unknown-forge",
        "forge-not-a-string",
        "null-repository",
        "repository-not-a-string",
        "github-one-segment",
        "github-three-segments",
        "gitlab-empty-segment",
        "whitespace",
    ],
)
def test_an_unformable_row_is_skipped_with_its_reason(
    bad: dict[str, Any], reason: SkipReason
) -> None:
    http = quiver_http([bad, row("ok/repo")], [asset("ok/repo", "ok.apk")])
    discovery = quiver(http)
    assert [listing.url for listing in discovery.listings] == [
        "https://github.com/ok/repo"
    ]
    [skip] = discovery.skipped
    assert skip.reason is reason
    assert skip.listing == {
        "list": "one",
        "project": "Port",
        "repository": bad["repository"],
        "repositorySource": bad.get("repositorySource"),
    }


def test_an_apk_asset_is_recognized_without_regard_to_case() -> None:
    http = quiver_http([row("owner/repo")], [asset("Owner/Repo", "App-v2.APK")])
    assert len(quiver(http).listings) == 1


@pytest.mark.parametrize(
    ("assets", "reason"),
    [
        ([asset("owner/repo", "app.zip", "app.apk.sig")], SkipReason.NO_APK_ASSET),
        ([], SkipReason.NO_ASSET_ENTRY),
    ],
    ids=["no-apk-asset", "no-entry"],
)
def test_a_new_project_without_an_apk_asset_is_screened_out(
    assets: list[dict[str, Any]], reason: SkipReason
) -> None:
    http = quiver_http(
        [row("owner/repo"), row("ok/repo")], [*assets, asset("ok/repo", "a.apk")]
    )
    discovery = quiver(http)
    assert [listing.url for listing in discovery.listings] == [
        "https://github.com/ok/repo"
    ]
    assert [
        (skip.listing["repository"], skip.reason) for skip in discovery.skipped
    ] == [("owner/repo", reason)]


@pytest.mark.parametrize("assets", [[asset("owner/repo", "app.zip")], []])
def test_a_committed_project_is_kept_whatever_its_latest_release_lists(
    assets: list[dict[str, Any]],
) -> None:
    committed = frozenset({normalize_project_url("https://github.com/Owner/Repo")})
    discovery = quiver(quiver_http([row("owner/repo")], assets), committed)
    assert discovery.listings == (Listing("https://github.com/owner/repo", "Port"),)
    assert discovery.skipped == ()


def test_every_row_skipped_fails_and_reports_the_skipped_rows() -> None:
    http = quiver_http([row(None), row("a/b", repositorySource="codeberg")])
    with pytest.raises(EmptyDiscovery) as error:
        quiver(http)
    assert [skip.reason for skip in error.value.skipped] == [
        SkipReason.INVALID_REPOSITORY,
        SkipReason.UNKNOWN_FORGE,
    ]


def test_every_new_project_screened_out_fails_and_reports_them() -> None:
    http = quiver_http([row("a/b"), row("c/d")], [asset("a/b", "a.zip")])
    with pytest.raises(EmptyDiscovery) as error:
        quiver(http, frozenset({"github.com/unlisted/project"}))
    assert [skip.reason for skip in error.value.skipped] == [
        SkipReason.NO_APK_ASSET,
        SkipReason.NO_ASSET_ENTRY,
    ]


def test_an_empty_upstream_list_fails() -> None:
    with pytest.raises(EmptyDiscovery):
        quiver(quiver_http([]))


@pytest.mark.parametrize(
    "location",
    [
        "https://elsewhere.test/quiver/lists/one.json",
        "https://catalog.test/other/one.json",
        "https://catalog.test/quiver/../other/one.json",
        "http://catalog.test/quiver/lists/one.json",
    ],
)
@pytest.mark.parametrize("field", ["remoteLocation", "platformMetadataUrl"])
def test_a_location_outside_the_index_directory_is_a_malformed_index(
    location: str, field: str
) -> None:
    index = {
        "version": 2,
        "lists": [{"id": "one", "remoteLocation": LIST_URL}],
        "platformMetadataUrl": ASSETS_URL,
    }
    if field == "remoteLocation":
        index["lists"][0]["remoteLocation"] = location
    else:
        index["platformMetadataUrl"] = location
    http = quiver_http([row("a/b")], [asset("a/b", "a.apk")], **{INDEX_URL: index})
    with pytest.raises(DiscoveryError, match="outside its host and directory"):
        quiver(http)
    assert http.urls == [INDEX_URL]


@pytest.mark.parametrize(
    "failure",
    [
        {LIST_URL: HttpError("list unavailable")},
        {LIST_URL: "not json"},
        {LIST_URL: {"apps": "bad"}},
        {LIST_URL: {"apps": ["bad"]}},
        {ASSETS_URL: HttpError("asset names unavailable")},
        {ASSETS_URL: "not json"},
        {ASSETS_URL: {"entries": {}}},
        {ASSETS_URL: {"entries": [{"provider": "github", "repository": "a/b"}]}},
        {ASSETS_URL: {"entries": [{**asset("a/b"), "assetNames": [7]}]}},
        {
            INDEX_URL: {
                "version": 2,
                "lists": [{"id": "one", "remoteLocation": LIST_URL}],
            }
        },
        {INDEX_URL: {"version": 1, "lists": []}},
    ],
    ids=[
        "list-unavailable",
        "list-not-json",
        "list-apps-not-a-list",
        "list-row-not-an-object",
        "assets-unavailable",
        "assets-not-json",
        "assets-entries-not-a-list",
        "assets-entry-without-names",
        "assets-name-not-a-string",
        "index-without-asset-file",
        "index-wrong-version",
    ],
)
def test_an_unreadable_or_malformed_input_fails(failure: dict[str, Any]) -> None:
    http = quiver_http([row("a/b")], [asset("a/b", "a.apk")], **failure)
    with pytest.raises((DiscoveryError, HttpError)):
        quiver(http)
