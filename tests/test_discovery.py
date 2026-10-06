from __future__ import annotations

from typing import Any

import pytest

from omnipack.discovery import (
    Discovery,
    DiscoveryError,
    GeneratedSource,
    LinkSkip,
    Listing,
    Skip,
    SkipReason,
    discover,
)
from omnipack.http import HttpError
from omnipack.urls import normalize_project_url
from tests.http_support import FakeHttp

README_URL = "https://example.test/README.md"
INDEX_URL = "https://catalog.test/quiver/index.json"
LIST_URL = "https://catalog.test/quiver/lists/one.json"
ASSETS_URL = "https://catalog.test/quiver/platform-index.json"


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


def test_codm_link_no_project_url_can_be_formed_from_is_skipped() -> None:
    readme = TABLE + (
        "| [Port](https://example.org:99999/app) | x |\n"
        "| [Bracket](https://[bad/app) | y |\n"
        "| [No host](https:///app) | w |\n"
        "| [Port only](https://:80/app) | v |\n"
        "| [Valid](https://github.com/o/app) | z |\n"
    )
    discovery = discover(
        GeneratedSource.CODM,
        {"readme_url": README_URL},
        FakeHttp({README_URL: readme}),
        frozenset(),
    )
    assert discovery.listings == (Listing("https://github.com/o/app", "Valid"),)
    assert discovery.skipped == (
        LinkSkip(
            {"name": "Port", "url": "https://example.org:99999/app"},
            SkipReason.INVALID_URL,
        ),
        LinkSkip(
            {"name": "Bracket", "url": "https://[bad/app"}, SkipReason.INVALID_URL
        ),
        LinkSkip({"name": "No host", "url": "https:///app"}, SkipReason.INVALID_URL),
        LinkSkip(
            {"name": "Port only", "url": "https://:80/app"}, SkipReason.INVALID_URL
        ),
    )


def test_codm_badge_image_inside_a_link_is_not_a_project() -> None:
    readme = (
        TABLE + "| [![badge](https://img.test/b.svg) App](https://github.com/o/app) |\n"
    )
    assert codm(readme) == [Listing("https://github.com/o/app", " App")]


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
        "| Project | Game |\n|-x-|---|\n",
    ],
    ids=["missing-delimiter", "invalid-delimiter"],
)
def test_a_malformed_project_table_beside_a_valid_one_fails(broken: str) -> None:
    readme = TABLE + "| [A](https://github.com/a/a) | x |\n\n" + broken
    with pytest.raises(DiscoveryError, match="delimiter"):
        codm(readme)


def test_codm_reads_a_project_table_in_compact_markdown_syntax() -> None:
    readme = (
        "Project | Game\n-|:-:\n"
        "[A](https://github.com/a/a) | x\n"
        "| [B](https://github.com/b/b) | y |\n"
        "\n"
        "After the table [C](https://github.com/c/c)\n"
    )
    assert [listing.url for listing in codm(readme)] == [
        "https://github.com/a/a",
        "https://github.com/b/b",
    ]


@pytest.mark.parametrize(
    "other",
    [
        "| Name | S |\n|---|---|\n| Project | y |\n| [C](https://github.com/c/c) | z |\n",
        "project | is lowercase prose [C](https://github.com/c/c)\n",
        "Project | prose without a delimiter [C](https://github.com/c/c)\n",
    ],
    ids=["row-of-another-table", "lowercase-prose", "unpiped-prose"],
)
def test_text_that_is_not_a_project_header_starts_no_project_table(
    other: str,
) -> None:
    readme = TABLE + "| [A](https://github.com/a/a) | x |\n\n" + other
    assert [listing.url for listing in codm(readme)] == ["https://github.com/a/a"]


def test_codm_reads_a_single_column_project_table() -> None:
    readme = "| Project\n| ---\n| [A](https://github.com/a/a)\n"
    assert [listing.url for listing in codm(readme)] == ["https://github.com/a/a"]


def test_codm_reads_titled_angle_bracket_and_parenthesized_links() -> None:
    readme = TABLE + (
        '| [A](https://github.com/a/a "Title") | x |\n'
        "| [B](<https://github.com/b/b>) | y |\n"
        "| [C](https://example.org/c_(game)) | z |\n"
    )
    assert codm(readme) == [
        Listing("https://github.com/a/a", "A"),
        Listing("https://github.com/b/b", "B"),
        Listing("https://example.org/c_(game)", "C"),
    ]


def test_an_indented_row_continues_its_project_table() -> None:
    readme = TABLE + (
        "| [A](https://github.com/a/a) | x |\n"
        "    | [B](https://github.com/b/b) | y |\n"
        "| [C](https://github.com/c/c) | z |\n"
    )
    assert [listing.url for listing in codm(readme)] == [
        "https://github.com/a/a",
        "https://github.com/b/b",
        "https://github.com/c/c",
    ]


def test_codm_reads_link_text_with_brackets_and_an_uppercase_scheme() -> None:
    readme = TABLE + (
        "| [App [beta]](https://github.com/a/a) | x |\n"
        "| [App \\[rc\\]](https://github.com/b/b) | y |\n"
        "| [C](HTTPS://github.com/c/c) | z |\n"
    )
    assert codm(readme) == [
        Listing("https://github.com/a/a", "App [beta]"),
        Listing("https://github.com/b/b", "App [rc]"),
        Listing("HTTPS://github.com/c/c", "C"),
    ]


@pytest.mark.parametrize(
    "block",
    ["# Next", "> see", "- item", "* item", "1. item", "---", "***", "<!-- note -->"],
    ids=[
        "heading",
        "blockquote",
        "dash-list",
        "star-list",
        "ordered-list",
        "dash-break",
        "star-break",
        "comment",
    ],
)
def test_another_block_ends_a_project_table(block: str) -> None:
    readme = TABLE + (
        f"| [A](https://github.com/a/a) | x |\n{block}\n"
        "[C](https://github.com/c/c) | y\n"
    )
    assert [listing.url for listing in codm(readme)] == ["https://github.com/a/a"]


def test_codm_reads_only_the_links_markdown_renders() -> None:
    readme = TABLE + (
        "| `[A](https://github.com/a/a)` <!-- [B](https://github.com/b/b) --> "
        "\\[C](https://github.com/c/c) [D](https://github.com/d/d) | x |\n"
        "<!--\n| [E](https://github.com/e/e) | y |\n-->\n"
    )
    assert [listing.url for listing in codm(readme)] == ["https://github.com/d/d"]


def test_a_byte_order_mark_does_not_hide_the_first_table() -> None:
    readme = "\ufeff" + TABLE + "| [A](https://github.com/a/a) | x |\n"
    assert [listing.url for listing in codm(readme)] == ["https://github.com/a/a"]


def test_a_readme_without_a_project_table_fails() -> None:
    with pytest.raises(DiscoveryError, match="no Project table"):
        codm("# Nothing here\n")


def test_codm_tables_without_links_discover_nothing() -> None:
    assert codm(TABLE + "| plain text | x |\n") == []


def test_a_project_table_whose_header_and_delimiter_disagree_fails() -> None:
    with pytest.raises(DiscoveryError, match="header and delimiter disagree"):
        codm("| Project | Game | Notes |\n|---|---|\n| [A](https://github.com/a/a) |\n")


HIDDEN_TABLE = "| Project | Game |\n|---|---|\n| [B](https://github.com/b/b) | y |\n"


@pytest.mark.parametrize(
    "hidden",
    [
        "~~~\n" + HIDDEN_TABLE + "~~~\n",
        "~~~ info`with`backticks\n" + HIDDEN_TABLE + "~~~\n",
        "".join("\t" + line + "\n" for line in HIDDEN_TABLE.splitlines()),
        "````\n```\n" + HIDDEN_TABLE + "````\n",
    ],
    ids=["tilde-fence", "tilde-fence-backtick-info", "tab-indented", "short-close"],
)
def test_codm_project_table_inside_code_is_not_read(hidden: str) -> None:
    readme = TABLE + "| [A](https://github.com/a/a) | x |\n\n" + hidden
    assert [listing.url for listing in codm(readme)] == ["https://github.com/a/a"]


def test_a_backtick_line_whose_info_has_a_backtick_opens_no_fence() -> None:
    readme = "```not`a fence\n" + HIDDEN_TABLE
    assert [listing.url for listing in codm(readme)] == ["https://github.com/b/b"]


@pytest.mark.parametrize(
    "header",
    [
        "| Project | A \\| B |\n|---|---|\n",
        "| Project | Game\n|---|---|\n",
        "   | Project | Game |\n   |---|---|\n",
    ],
    ids=["escaped-pipe", "no-trailing-pipe", "indented-three-spaces"],
)
def test_a_project_table_header_may_vary_in_form(header: str) -> None:
    readme = header + "   | [A](https://github.com/a/a) | x |\n"
    assert [listing.url for listing in codm(readme)] == ["https://github.com/a/a"]


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


def quiver(
    http: FakeHttp,
    committed: frozenset[str] = frozenset(),
    index_url: str = INDEX_URL,
) -> Discovery:
    return discover(GeneratedSource.QUIVER, {"index_url": index_url}, http, committed)


def row(repository: object, project: str = "Port", **fields: Any) -> dict[str, Any]:
    return {"project": project, "repository": repository, **fields}


def test_quiver_reads_only_the_index_its_lists_and_the_asset_name_file() -> None:
    http = quiver_http([row("owner/repo")], [asset("owner/repo", "app.apk")])
    discovery = quiver(http)
    assert discovery.listings == (Listing("https://github.com/owner/repo", "Port"),)
    assert set(http.urls) == {INDEX_URL, ASSETS_URL, LIST_URL}


@pytest.mark.parametrize(
    ("fields", "url"),
    [
        ({}, "https://github.com/owner/repo"),
        ({"repositorySource": "GitHub"}, "https://github.com/owner/repo"),
        ({"repositorySource": "GITLAB"}, "https://gitlab.com/owner/repo"),
    ],
    ids=["absent", "mixed-case-github", "mixed-case-gitlab"],
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
        (row("?owner/repo"), SkipReason.INVALID_REPOSITORY),
        (row("owner/re#po"), SkipReason.INVALID_REPOSITORY),
        (
            row("owner/re%2Fpo", repositorySource="gitlab"),
            SkipReason.INVALID_REPOSITORY,
        ),
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
        "query-mark",
        "fragment-mark",
        "percent-escape",
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
    assert discovery.skipped == (
        Skip(
            {
                "list": "one",
                "project": "Port",
                "repository": bad["repository"],
                "repositorySource": bad.get("repositorySource"),
            },
            reason,
        ),
    )


def test_an_apk_asset_is_recognized_without_regard_to_case() -> None:
    http = quiver_http([row("owner/repo")], [asset("Owner/Repo", "App-v2.APK")])
    assert len(quiver(http).listings) == 1


@pytest.mark.parametrize("apk_first", [True, False])
def test_asset_entries_for_one_project_merge_and_any_apk_admits(
    apk_first: bool,
) -> None:
    entries = [asset("owner/repo", "app.apk"), asset("Owner/Repo", "app.zip")]
    if not apk_first:
        entries.reverse()
    discovery = quiver(quiver_http([row("owner/repo")], entries))
    assert discovery.listings == (Listing("https://github.com/owner/repo", "Port"),)
    assert discovery.skipped == ()


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
        (skip.listing["repository"], skip.reason)
        for skip in discovery.skipped
        if isinstance(skip, Skip)
    ] == [("owner/repo", reason)]
    assert len(discovery.skipped) == 1


@pytest.mark.parametrize("assets", [[asset("owner/repo", "app.zip")], []])
def test_a_committed_project_is_kept_whatever_its_latest_release_lists(
    assets: list[dict[str, Any]],
) -> None:
    committed = frozenset({normalize_project_url("https://github.com/Owner/Repo")})
    discovery = quiver(quiver_http([row("owner/repo")], assets), committed)
    assert discovery.listings == (Listing("https://github.com/owner/repo", "Port"),)
    assert discovery.skipped == ()


def test_every_row_skipped_keeps_nothing_and_reports_the_skipped_rows() -> None:
    http = quiver_http([row(None), row("a/b", repositorySource="codeberg")])
    discovery = quiver(http)
    assert discovery.listings == ()
    assert [skip.reason for skip in discovery.skipped] == [
        SkipReason.INVALID_REPOSITORY,
        SkipReason.UNKNOWN_FORGE,
    ]


def test_every_new_project_screened_out_keeps_nothing_and_reports_them() -> None:
    http = quiver_http([row("a/b"), row("c/d")], [asset("a/b", "a.zip")])
    discovery = quiver(http, frozenset({"github.com/unlisted/project"}))
    assert discovery.listings == ()
    assert [skip.reason for skip in discovery.skipped] == [
        SkipReason.NO_APK_ASSET,
        SkipReason.NO_ASSET_ENTRY,
    ]


def test_an_empty_upstream_list_keeps_nothing() -> None:
    assert quiver(quiver_http([])) == Discovery((), ())


@pytest.mark.parametrize(
    "index_url",
    [
        "http://catalog.test/quiver/index.json",
        "https://catalog.test/quiver/index.json?ref=main",
        "https://catalog.test/quiver/%2e%2e/index.json",
        "https://catalog.test/quiver/../index.json",
    ],
    ids=["not-https", "query", "percent-encoded", "dot-dot"],
)
def test_an_index_url_that_is_not_a_plain_https_json_path_fails(
    index_url: str,
) -> None:
    http = quiver_http([row("a/b")], [asset("a/b", "a.apk")])
    with pytest.raises(DiscoveryError, match="HTTPS catalog JSON URL"):
        quiver(http, index_url=index_url)
    assert http.urls == []


@pytest.mark.parametrize(
    ("lists", "message"),
    [
        (
            [
                {"id": "one", "remoteLocation": LIST_URL},
                {"id": "one", "remoteLocation": LIST_URL},
            ],
            "repeats list 'one'",
        ),
        ([{"id": "one"}], "malformed list reference"),
        ([{"id": "", "remoteLocation": LIST_URL}], "malformed list reference"),
    ],
    ids=["repeated-id", "no-location", "empty-id"],
)
def test_a_malformed_list_entry_in_the_index_fails(
    lists: list[dict[str, Any]], message: str
) -> None:
    index = {"version": 2, "lists": lists, "platformMetadataUrl": ASSETS_URL}
    http = quiver_http([row("a/b")], [asset("a/b", "a.apk")], **{INDEX_URL: index})
    with pytest.raises(DiscoveryError, match=message):
        quiver(http)


@pytest.mark.parametrize(
    "location",
    [
        "https://elsewhere.test/quiver/lists/one.json",
        "https://catalog.test/other/one.json",
        "https://catalog.test/quiver/../other/one.json",
        "http://catalog.test/quiver/lists/one.json",
        "https://catalog.test/quiver/%2e%2e/other/one.json",
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
    ("failure", "message"),
    [
        ({LIST_URL: HttpError("list unavailable")}, "list unavailable"),
        ({LIST_URL: "not json"}, "quiver list one is not JSON"),
        ({LIST_URL: {"apps": "bad"}}, "quiver list one is malformed"),
        ({LIST_URL: {"apps": ["bad"]}}, "quiver list one has a malformed row"),
        ({ASSETS_URL: HttpError("asset names unavailable")}, "asset names unavailable"),
        ({ASSETS_URL: "not json"}, "release asset-name file is not JSON"),
        ({ASSETS_URL: {"entries": {}}}, "release asset-name file is malformed"),
        (
            {ASSETS_URL: {"entries": [{"provider": "github", "repository": "a/b"}]}},
            "release asset-name file has a malformed entry",
        ),
        (
            {ASSETS_URL: {"entries": [{**asset("a/b"), "assetNames": [7]}]}},
            "release asset-name file has a malformed entry",
        ),
        (
            {ASSETS_URL: {"entries": [{"repository": "a/b", "assetNames": []}]}},
            "release asset-name file has a malformed entry",
        ),
        (
            {ASSETS_URL: {"entries": [{"provider": "github", "assetNames": []}]}},
            "release asset-name file has a malformed entry",
        ),
        (
            {
                INDEX_URL: {
                    "version": 2,
                    "lists": [{"id": "one", "remoteLocation": LIST_URL}],
                }
            },
            "quiver index names no release asset-name file",
        ),
        ({INDEX_URL: {"version": 1, "lists": []}}, "quiver index is malformed"),
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
        "assets-entry-without-provider",
        "assets-entry-without-repository",
        "index-without-asset-file",
        "index-wrong-version",
    ],
)
def test_an_unreadable_or_malformed_input_fails(
    failure: dict[str, Any], message: str
) -> None:
    # The row is committed, so a run that read every input would keep it.
    http = quiver_http([row("a/b")], [asset("a/b", "a.apk")], **failure)
    with pytest.raises((DiscoveryError, HttpError), match=message):
        quiver(http, frozenset({"github.com/a/b"}))


@pytest.mark.parametrize(
    "unmatched",
    [asset("a/b", "a.apk", provider="codeberg"), asset("a/b/c", "a.apk")],
    ids=["unknown-provider", "github-three-segments"],
)
def test_an_asset_entry_forming_no_project_url_is_ignored(
    unmatched: dict[str, Any],
) -> None:
    http = quiver_http([row("ok/repo")], [unmatched, asset("ok/repo", "ok.apk")])
    discovery = quiver(http)
    assert [listing.url for listing in discovery.listings] == [
        "https://github.com/ok/repo"
    ]
    assert discovery.skipped == ()
