from __future__ import annotations

import json
from copy import deepcopy
from email.message import Message
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from omnipack.http import HttpClient, HttpConfig, HttpResponse
from omnipack.resolution.github import resolve_github
from omnipack.resolution.types import ResolutionError

if TYPE_CHECKING:
    from urllib.request import Request


class GitHubTransport:
    def __init__(self, documents: dict[str, object | Exception]) -> None:
        self.documents = documents
        self.requests: list[Request] = []

    def __call__(
        self, request: Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse:
        self.requests.append(request)
        outcome = self.documents[request.full_url]
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, HttpResponse):
            return outcome
        return HttpResponse(
            request.full_url, 200, Message(), json.dumps(outcome).encode()
        )


def app(settings: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "url": "https://github.com/example/emulator",
        "overrideSource": "GitHub",
        "additionalSettings": settings or {},
    }


def asset(
    name: str = "app.apk", *, date: str = "2026-01-01T00:00:00Z"
) -> dict[str, str]:
    return {
        "name": name,
        "browser_download_url": f"https://downloads.example/{name}",
        "updated_at": date,
    }


def release(
    tag: str,
    *,
    date: str = "2026-01-01T00:00:00Z",
    assets: list[dict[str, str]] | None = None,
    name: str | None = None,
    body: str = "",
    draft: bool = False,
    prerelease: bool = False,
) -> dict[str, object]:
    return {
        "tag_name": tag,
        "name": name,
        "body": body,
        "draft": draft,
        "prerelease": prerelease,
        "published_at": date,
        "assets": [asset()] if assets is None else assets,
    }


def resolver(
    releases: object,
    settings: dict[str, object] | None = None,
    *,
    tags: object = (),
    latest: object = None,
    tags_latest: object = None,
):
    transport = GitHubTransport(
        {
            "https://api.github.com/repos/example/emulator/releases/latest": latest,
            "https://api.github.com/repos/example/emulator/releases?per_page=100": releases,
            "https://api.github.com/repos/example/emulator/tags?per_page=100": tags,
            "https://api.github.com/repos/example/emulator/tags/latest": tags_latest,
        }
    )
    result = resolve_github(
        app(settings), HttpClient(HttpConfig({}), retries=0, transport=transport)
    )
    return result, transport


def test_resolves_release_version_and_ordered_apk_candidates() -> None:
    result, _ = resolver(
        [
            release(
                "v2.0.0",
                assets=[asset("notes.txt"), asset("second.apk"), asset("first.apkm")],
            )
        ]
    )
    assert result.raw_version == "v2.0.0"
    assert result.effective_version == "v2.0.0"
    assert result.version_origin == "tag"
    assert [(item.name, item.url) for item in result.candidates] == [
        ("second.apk", "https://downloads.example/second.apk"),
        ("first.apkm", "https://downloads.example/first.apkm"),
    ]
    assert result.inspected_count == 1
    assert result.window_limit == 100


def test_first_100_release_window_is_applied_before_sorting() -> None:
    releases = [
        release(f"v{i}", date=f"2025-01-{(i % 28) + 1:02d}T00:00:00Z", assets=[])
        for i in range(101)
    ]
    releases[100] = release("v-outside", date="2030-01-01T00:00:00Z")
    with pytest.raises(ResolutionError) as raised:
        resolver(releases, {"fallbackToOlderReleases": True})
    assert raised.value.code == "github-no-release"


def test_date_sort_descends_and_reverses_api_order_for_ties() -> None:
    result, _ = resolver(
        [release("first", name="first"), release("second", name="second")],
        {"sortMethodChoice": "date"},
    )
    assert result.raw_version == "second"


def test_none_sort_preserves_api_order() -> None:
    result, _ = resolver(
        [release("first"), release("second", date="2030-01-01T00:00:00Z")],
        {"sortMethodChoice": "none"},
    )
    assert result.raw_version == "first"


def test_drafts_and_excluded_prereleases_do_not_consume_no_fallback_boundary() -> None:
    result, _ = resolver(
        [
            release("draft", draft=True),
            release("pre", prerelease=True),
            release("stable"),
        ],
        {"sortMethodChoice": "none", "fallbackToOlderReleases": False},
    )
    assert result.raw_version == "stable"


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("filterReleaseTitlesByRegEx", "wanted"),
        ("filterReleaseNotesByRegEx", "wanted"),
        ("apkFilterRegEx", "wanted"),
    ],
)
def test_eligible_mismatch_does_not_fall_back_when_disabled(
    setting: str, value: str
) -> None:
    with pytest.raises(ResolutionError) as raised:
        resolver(
            [
                release("latest", name="wrong", body="wrong"),
                release(
                    "older", name="wanted", body="wanted", assets=[asset("wanted.apk")]
                ),
            ],
            {
                "sortMethodChoice": "none",
                "fallbackToOlderReleases": False,
                setting: value,
            },
        )
    assert raised.value.code == "github-no-release"


def test_fallback_selects_older_release_with_matching_apk() -> None:
    result, _ = resolver(
        [release("latest", assets=[]), release("older", assets=[asset("wanted.apk")])],
        {
            "sortMethodChoice": "none",
            "fallbackToOlderReleases": True,
            "apkFilterRegEx": "wanted",
        },
    )
    assert result.raw_version == "older"


def test_apk_filter_and_inversion_apply_to_direct_assets() -> None:
    result, _ = resolver(
        [
            release(
                "v1",
                assets=[asset("debug.apk"), asset("release.apk"), asset("file.zip")],
            )
        ],
        {"apkFilterRegEx": "debug", "invertAPKFilter": True},
    )
    assert [candidate.name for candidate in result.candidates] == ["release.apk"]


def test_track_only_release_succeeds_without_apk() -> None:
    result, transport = resolver([release("2026.09", assets=[])], {"trackOnly": True})
    assert result.effective_version == "2026.09"
    assert result.candidates == ()
    assert len(transport.requests) == 1


def test_track_only_uses_tags_only_when_no_release_qualifies() -> None:
    result, transport = resolver([], {"trackOnly": True}, tags=[{"name": "2026.10"}])
    assert result.raw_version == "2026.10"
    assert result.version_origin == "tag"
    assert len(transport.requests) == 2


def test_tags_fallback_still_applies_version_extraction() -> None:
    result, _ = resolver(
        [],
        {
            "trackOnly": True,
            "versionExtractionRegEx": r"v(\d+\.\d+)",
            "matchGroupToUse": "1",
        },
        tags=[{"name": "v2.4"}],
    )
    assert result.raw_version == "v2.4"
    assert result.effective_version == "2.4"
    assert result.version_origin == "extracted"


def test_tags_fallback_cannot_supply_a_requested_release_date() -> None:
    with pytest.raises(ResolutionError) as raised:
        resolver(
            [],
            {"trackOnly": True, "releaseDateAsVersion": True},
            tags=[{"name": "v2.4"}],
        )
    assert raised.value.code == "github-date-missing"


def test_transport_failure_does_not_trigger_tags_fallback() -> None:
    transport = GitHubTransport(
        {
            "https://api.github.com/repos/example/emulator/releases?per_page=100": OSError(
                "down"
            ),
            "https://api.github.com/repos/example/emulator/tags?per_page=100": [
                {"name": "v2"}
            ],
        }
    )
    with pytest.raises(ResolutionError) as raised:
        resolve_github(
            app({"trackOnly": True}),
            HttpClient(HttpConfig({}), retries=0, transport=transport),
        )
    assert raised.value.code == "github-request-failed"
    assert len(transport.requests) == 1


@pytest.mark.parametrize(
    "settings",
    [
        {"allowInsecure": True},
        {"sortMethodChoice": "smartname"},
        {"unknownFlag": False},
    ],
)
def test_active_unsupported_settings_fail_by_name(settings: dict[str, object]) -> None:
    with pytest.raises(ResolutionError) as raised:
        resolver([release("v1")], settings)
    assert raised.value.code == "unsupported-setting"
    assert next(iter(settings)) in str(raised.value)


def test_title_extraction_then_release_date_override() -> None:
    result, _ = resolver(
        [release("continuous", name="Release 2.4", date="2026-01-02T03:04:05.123456Z")],
        {
            "releaseTitleAsVersion": True,
            "versionExtractionRegEx": r"(\d+\.\d+)",
            "matchGroupToUse": "1",
            "releaseDateAsVersion": True,
        },
    )
    assert result.raw_version == "Release 2.4"
    assert result.effective_version == "1767323045123456"
    assert result.version_origin == "release-date"


def test_latest_filtered_asset_date_controls_date_version() -> None:
    result, _ = resolver(
        [
            release(
                "v1",
                assets=[
                    asset("ignored.txt", date="2030-01-01T00:00:00Z"),
                    asset("old.apk", date="2026-01-01T00:00:00Z"),
                    asset("new.apk", date="2026-02-01T00:00:00Z"),
                ],
            )
        ],
        {
            "releaseDateAsVersion": True,
            "useLatestAssetDateAsReleaseDate": True,
        },
    )
    assert result.version_origin == "asset-date"
    assert result.effective_version == "1769904000000000"


def test_missing_requested_date_fails_instead_of_using_tag() -> None:
    value = release("v1")
    value.pop("published_at")
    with pytest.raises(ResolutionError) as raised:
        resolver([value], {"releaseDateAsVersion": True})
    assert raised.value.code == "github-date-missing"


def test_regex_no_match_never_becomes_raw_version_success() -> None:
    with pytest.raises(ResolutionError) as raised:
        resolver(
            [release("continuous")],
            {"versionExtractionRegEx": r"(\d+\.\d+)", "matchGroupToUse": "1"},
        )
    assert raised.value.code == "regex-no-match"


_FIXTURE_ROOT = Path("tests/fixtures/verification")
_GITHUB_CASES = [
    item
    for item in json.loads((_FIXTURE_ROOT / "manifest.json").read_text())["cases"]
    if item["source"] == "GitHub"
]


@pytest.mark.parametrize("item", _GITHUB_CASES, ids=lambda item: item["pattern"])
def test_every_manifest_github_fixture_derives_its_expected_evidence(
    item: dict[str, str],
) -> None:
    fixture = json.loads((_FIXTURE_ROOT / item["fixture"]).read_text())
    if "case" in item:
        selected_case = fixture["cases"][item["case"]]
        settings = selected_case["settings"]
        expected = selected_case["expected"]
        releases = fixture["releases"]
        tags: object = ()
    else:
        settings = fixture["settings"]
        expected = fixture["expected"]
        releases = fixture["responses"]["releases"]
        tags = fixture["responses"]["tags"]

    result, transport = resolver(releases, settings, tags=tags)

    assert result.effective_version == expected["version"]
    if expected["selected_url"]:
        assert result.candidates[0].url == expected["selected_url"]
    else:
        assert result.candidates == ()
    if item["pattern"] == "track-only-tags-fallback":
        assert result.selected == {"kind": "tag", "tag": expected["version"]}
        assert result.raw_version == expected["version"]
        assert result.inspected_count == 0
        assert [request.full_url for request in transport.requests] == [
            "https://api.github.com/repos/example/emulator/releases?per_page=100",
            "https://api.github.com/repos/example/emulator/tags?per_page=100",
        ]


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@github.com/example/emulator",
        "https://user@github.com/example/emulator",
        "https://@github.com/example/emulator",
        "https://[github.com/example/emulator",
    ],
)
def test_invalid_repository_url_is_rejected_before_request(url: str) -> None:
    entry = app()
    entry["url"] = url
    transport = GitHubTransport({})
    with pytest.raises(ResolutionError) as raised:
        resolve_github(
            entry, HttpClient(HttpConfig({}), retries=0, transport=transport)
        )
    assert raised.value.code == "github-url-invalid"
    assert "secret" not in str(raised.value)
    assert transport.requests == []


@pytest.mark.parametrize(
    "setting", ["filterReleaseTitlesByRegEx", "filterReleaseNotesByRegEx"]
)
def test_title_and_notes_mismatches_fall_back_when_enabled(setting: str) -> None:
    result, _ = resolver(
        [
            release("latest", name="wrong", body="wrong"),
            release("older", name="wanted", body="wanted"),
        ],
        {
            "sortMethodChoice": "none",
            "fallbackToOlderReleases": True,
            setting: "wanted",
        },
    )
    assert result.raw_version == "older"


@pytest.mark.parametrize("name", [None, "", "   "])
def test_title_version_falls_back_to_tag_when_name_is_empty(name: str | None) -> None:
    value = release("v2.4", name=name)
    if name is None:
        value.pop("name")
    result, _ = resolver([value], {"releaseTitleAsVersion": True})
    assert result.raw_version == "v2.4"
    assert result.effective_version == "v2.4"
    assert result.version_origin == "title"
    assert result.selected is not None
    assert result.selected["title"] == "v2.4"


@pytest.mark.parametrize("fallback", [True, False])
def test_tags_fallback_applies_title_filter_and_older_release_boundary(
    fallback: bool,
) -> None:
    settings: dict[str, object] = {
        "trackOnly": True,
        "sortMethodChoice": "none",
        "filterReleaseTitlesByRegEx": "wanted",
        "fallbackToOlderReleases": fallback,
    }
    tags = [{"name": "wrong"}, {"name": "wanted"}]
    if fallback:
        result, _ = resolver([], settings, tags=tags)
        assert result.raw_version == "wanted"
    else:
        with pytest.raises(ResolutionError) as raised:
            resolver([], settings, tags=tags)
        assert raised.value.code == "github-no-release"


def test_tags_fallback_applies_notes_filter_to_empty_body() -> None:
    with pytest.raises(ResolutionError) as raised:
        resolver(
            [],
            {"trackOnly": True, "filterReleaseNotesByRegEx": "wanted"},
            tags=[{"name": "v2"}],
        )
    assert raised.value.code == "github-no-release"


@pytest.mark.parametrize(("sort", "expected"), [("date", "v1"), ("none", "v2")])
def test_tags_fallback_applies_date_tie_or_api_order(sort: str, expected: str) -> None:
    result, _ = resolver(
        [],
        {"trackOnly": True, "sortMethodChoice": sort},
        tags=[{"name": "v2"}, {"name": "v1"}],
    )
    assert result.raw_version == expected
    assert result.selected == {"kind": "tag", "tag": expected}


@pytest.mark.parametrize("sort", ["date", "none"])
@pytest.mark.parametrize("position", [0, 1])
def test_latest_promotes_list_record_without_replacing_its_metadata(
    sort: str, position: int
) -> None:
    listed = release("stable", assets=[asset("listed.apk")])
    other = release("newer", date="2030-01-01T00:00:00Z")
    releases = [other]
    releases.insert(position, listed)
    result, transport = resolver(
        releases,
        {"verifyLatestTag": True, "sortMethodChoice": sort},
        latest=release("stable", assets=[asset("separate.apk")]),
    )
    assert result.raw_version == "stable"
    assert [candidate.name for candidate in result.candidates] == ["listed.apk"]
    assert result.inspected_count == 2
    assert [request.full_url.rsplit("/", 2)[-2:] for request in transport.requests] == [
        ["releases", "latest"],
        ["emulator", "releases?per_page=100"],
    ]


def test_latest_resolution_preserves_shared_decoded_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = "https://api.github.com/repos/example/emulator"
    releases = [
        release("newer", date="2030-01-01T00:00:00Z"),
        release("stable", assets=[asset("listed.apk")]),
    ]
    documents: dict[str, object] = {f"{base}/releases?per_page=100": releases}
    monkeypatch.setattr(HttpResponse, "json", lambda response: documents[response.url])
    for tag in ("stable", "outside"):
        latest = release(tag, assets=[asset("separate.apk")])
        documents[f"{base}/releases/latest"] = latest
        original = deepcopy(documents)
        result, _ = resolver(
            releases,
            {"verifyLatestTag": True, "sortMethodChoice": "none"},
            latest=latest,
        )
        assert result.raw_version == tag
        assert result.candidates[0].name == (
            "listed.apk" if tag == "stable" else "separate.apk"
        )
        assert documents == original
        ordinary, _ = resolver(releases, {"sortMethodChoice": "none"})
        assert ordinary.raw_version == "newer"
        assert documents == original


@pytest.mark.parametrize("sort", ["date", "none"])
def test_absent_latest_supplements_only_the_bounded_list(sort: str) -> None:
    releases = [release(f"v{i}") for i in range(100)]
    releases.append(release("outside", assets=[asset("ignored.apk")]))
    result, transport = resolver(
        releases,
        {"verifyLatestTag": True, "sortMethodChoice": sort},
        latest=release("outside", assets=[asset("supplement.apk")]),
    )
    assert result.raw_version == "outside"
    assert result.candidates[0].name == "supplement.apk"
    assert result.inspected_count == 101
    assert result.window_limit == 100
    assert len(transport.requests) == 2


@pytest.mark.parametrize(
    ("latest_identity", "listed_identity", "count"),
    [
        ({"name": "v1"}, {"tag_name": "v1"}, 1),
        ({"tag_name": None, "name": "v1"}, {"name": "v1"}, 1),
        ({"tag_name": "v1", "name": "other"}, {"tag_name": "v1"}, 1),
        ({"tag_name": "v1"}, {"tag_name": "V1"}, 2),
        ({"tag_name": "v1"}, {"tag_name": " v1 "}, 2),
        ({"tag_name": "v1"}, {"tag_name": "1"}, 2),
    ],
)
def test_latest_identity_uses_exact_tag_or_fallback_name(
    latest_identity: dict[str, object], listed_identity: dict[str, object], count: int
) -> None:
    result, _ = resolver(
        [{**listed_identity, "assets": [asset("listed.apk")]}],
        {"verifyLatestTag": True},
        latest={**latest_identity, "assets": [asset("separate.apk")]},
    )
    assert result.raw_version == "v1"
    assert result.inspected_count == count
    assert result.candidates[0].name == ("listed.apk" if count == 1 else "separate.apk")


@pytest.mark.parametrize("settings", [{}, {"verifyLatestTag": False}])
def test_disabled_latest_keeps_existing_order_and_request_budget(
    settings: dict[str, object],
) -> None:
    result, transport = resolver(
        [release("stable"), release("newer", date="2030-01-01T00:00:00Z")], settings
    )
    assert result.raw_version == "newer"
    assert len(transport.requests) == 1
    assert transport.requests[0].full_url.endswith("releases?per_page=100")


@pytest.mark.parametrize(
    ("flags", "include", "expected"),
    [
        ({"draft": True}, True, "other"),
        ({"prerelease": True}, False, "other"),
        ({"prerelease": True}, True, "latest"),
    ],
)
def test_promoted_latest_still_obeys_release_eligibility(
    flags: dict[str, bool], include: bool, expected: str
) -> None:
    latest = {**release("latest"), **flags}
    result, _ = resolver(
        [release("other"), latest],
        {
            "verifyLatestTag": True,
            "sortMethodChoice": "none",
            "includePrereleases": include,
        },
        latest=latest,
    )
    assert result.raw_version == expected


@pytest.mark.parametrize(
    ("sort", "fallback", "expected"),
    [("date", True, "first"), ("none", True, "second"), ("none", False, None)],
)
@pytest.mark.parametrize(
    "filter_setting",
    ["filterReleaseTitlesByRegEx", "filterReleaseNotesByRegEx", "apkFilterRegEx"],
)
def test_promoted_latest_mismatch_obeys_fallback_and_remaining_order(
    sort: str, fallback: bool, expected: str | None, filter_setting: str
) -> None:
    latest = release("latest", name="wrong", body="wrong")
    releases = [
        release(
            "second",
            date="2029-01-01T00:00:00Z",
            name="wanted",
            body="wanted",
            assets=[asset("wanted.apk")],
        ),
        release(
            "first",
            date="2030-01-01T00:00:00Z",
            name="wanted",
            body="wanted",
            assets=[asset("wanted.apk")],
        ),
        latest,
    ]
    settings: dict[str, object] = {
        "verifyLatestTag": True,
        "sortMethodChoice": sort,
        "fallbackToOlderReleases": fallback,
        filter_setting: "wanted",
    }
    if fallback:
        result, _ = resolver(releases, settings, latest=latest)
        assert result.raw_version == expected
    else:
        with pytest.raises(ResolutionError) as raised:
            resolver(releases, settings, latest=latest)
        assert raised.value.code == "github-no-release"


@pytest.mark.parametrize(
    ("extra", "effective", "origin"),
    [
        ({}, "Release 2.4", "title"),
        (
            {"versionExtractionRegEx": r"(\d+\.\d+)", "matchGroupToUse": "1"},
            "2.4",
            "extracted",
        ),
        ({"releaseDateAsVersion": True}, "1767323045123456", "release-date"),
        (
            {"releaseDateAsVersion": True, "useLatestAssetDateAsReleaseDate": True},
            "1767225600000000",
            "asset-date",
        ),
    ],
)
def test_promoted_latest_flows_through_version_processing(
    extra: dict[str, object], effective: str, origin: str
) -> None:
    latest = release(
        "continuous", name="Release 2.4", date="2026-01-02T03:04:05.123456Z"
    )
    result, _ = resolver(
        [release("newer", date="2030-01-01T00:00:00Z"), latest],
        {"verifyLatestTag": True, "releaseTitleAsVersion": True, **extra},
        latest=latest,
    )
    assert result.raw_version == "Release 2.4"
    assert result.effective_version == effective
    assert result.version_origin == origin


@pytest.mark.parametrize("endpoint", ["releases", "tags"])
@pytest.mark.parametrize(
    ("outcome", "code"),
    [
        (HttpResponse("", 404, Message(), b"{}"), "github-request-failed"),
        (HttpResponse("", 500, Message(), b"{}"), "github-request-failed"),
        (OSError("offline"), "github-request-failed"),
        (HttpResponse("", 200, Message(), b"{"), "github-request-failed"),
        ([], "github-invalid-response"),
        (None, "github-invalid-response"),
        ({}, "github-invalid-response"),
        ({"tag_name": "", "name": "valid"}, "github-invalid-response"),
        ({"tag_name": 1, "name": "valid"}, "github-invalid-response"),
        ({"name": False}, "github-invalid-response"),
    ],
)
def test_latest_failure_names_endpoint_and_stops_before_list_or_fallback(
    endpoint: str, outcome: object, code: str
) -> None:
    base = "https://api.github.com/repos/example/emulator"
    transport = GitHubTransport(
        {
            f"{base}/releases/latest": release("draft", draft=True),
            f"{base}/releases?per_page=100": [],
            f"{base}/{endpoint}/latest": outcome,
        }
    )
    with pytest.raises(ResolutionError) as raised:
        resolve_github(
            app({"verifyLatestTag": True, "trackOnly": True}),
            HttpClient(HttpConfig({}), retries=0, transport=transport),
        )
    assert raised.value.code == code
    assert f"{endpoint}/latest" in str(raised.value)
    expected = [f"{base}/releases/latest"]
    if endpoint == "tags":
        expected += [f"{base}/releases?per_page=100", f"{base}/tags/latest"]
    assert [request.full_url for request in transport.requests] == expected


@pytest.mark.parametrize("sort", ["date", "none"])
@pytest.mark.parametrize("present", [True, False])
def test_track_only_tags_latest_promotes_or_supplements_and_retains_release_count(
    sort: str, present: bool
) -> None:
    tags = [{"name": "v3", "commit": {"created": "2030-01-01T00:00:00Z"}}]
    if present:
        tags.append({"name": "v2", "body": "listed"})
    result, transport = resolver(
        [release("draft", draft=True)],
        {"verifyLatestTag": True, "trackOnly": True, "sortMethodChoice": sort},
        latest=release("draft", draft=True),
        tags=tags,
        tags_latest={"name": "v2"},
    )
    assert result.raw_version == "v2"
    assert result.selected == {"kind": "tag", "tag": "v2"}
    assert result.candidates == ()
    assert result.inspected_count == 1
    assert [
        request.full_url.split("/emulator/")[1] for request in transport.requests
    ] == [
        "releases/latest",
        "releases?per_page=100",
        "tags/latest",
        "tags?per_page=100",
    ]


@pytest.mark.parametrize("fallback", [True, False])
def test_tags_latest_mismatch_uses_configured_fallback_boundary(fallback: bool) -> None:
    settings: dict[str, object] = {
        "verifyLatestTag": True,
        "trackOnly": True,
        "sortMethodChoice": "none",
        "filterReleaseTitlesByRegEx": "wanted",
        "fallbackToOlderReleases": fallback,
    }
    kwargs = {
        "latest": release("draft", draft=True),
        "tags": [{"name": "wanted"}, {"name": "wrong"}],
        "tags_latest": {"name": "wrong"},
    }
    if fallback:
        result, _ = resolver([], settings, **kwargs)
        assert result.raw_version == "wanted"
        assert result.inspected_count == 1
    else:
        with pytest.raises(ResolutionError) as raised:
            resolver([], settings, **kwargs)
        assert raised.value.code == "github-no-release"


@pytest.mark.parametrize(
    ("settings", "code"),
    [
        (
            {"versionExtractionRegEx": r"(\d+)", "matchGroupToUse": "1"},
            "regex-no-match",
        ),
        ({"releaseDateAsVersion": True}, "github-date-missing"),
    ],
)
def test_latest_selected_version_failure_never_attempts_tags_fallback(
    settings: dict[str, object], code: str
) -> None:
    base = "https://api.github.com/repos/example/emulator"
    latest = {"tag_name": "rolling"}
    transport = GitHubTransport(
        {f"{base}/releases/latest": latest, f"{base}/releases?per_page=100": [latest]}
    )
    with pytest.raises(ResolutionError) as raised:
        resolve_github(
            app({"verifyLatestTag": True, "trackOnly": True, **settings}),
            HttpClient(HttpConfig({}), retries=0, transport=transport),
        )
    assert raised.value.code == code
    assert len(transport.requests) == 2


@pytest.mark.parametrize(
    "invert,expected",
    [(False, ["Game-Android.zip"]), (True, ["Game-Linux.zip", "direct.apk"])],
)
def test_enabled_zip_assets_use_outer_filename_filter(
    invert: bool, expected: list[str]
) -> None:
    result, transport = resolver(
        [
            release(
                "v3.0.0",
                assets=[
                    asset("Game-Android.zip"),
                    asset("Game-Linux.zip"),
                    asset("direct.apk"),
                    asset("source.tar.gz"),
                ],
            )
        ],
        {
            "includeZips": True,
            "apkFilterRegEx": r"-Android\.zip$",
            "invertAPKFilter": invert,
            "zippedApkFilterRegEx": r"^MissingMember\.apk$",
        },
    )
    assert [candidate.name for candidate in result.candidates] == expected
    assert result.effective_version == "v3.0.0"
    assert len(transport.requests) == 1


@pytest.mark.parametrize("enabled", [False, True])
def test_zip_eligibility_controls_older_release_fallback(enabled: bool) -> None:
    result, _ = resolver(
        [
            release("v2", assets=[asset("Game-Android.zip")]),
            release("v1", assets=[asset("old.apk")]),
        ],
        {
            "includeZips": enabled,
            "fallbackToOlderReleases": True,
            "sortMethodChoice": "none",
        },
    )
    assert result.raw_version == ("v2" if enabled else "v1")


def test_disabled_zip_only_release_is_not_installable() -> None:
    with pytest.raises(ResolutionError, match="no release qualifies"):
        resolver([release("v3", assets=[asset("Android.zip")])])


@pytest.mark.parametrize("enabled", [False, True])
def test_invalid_zip_member_regex_fails_before_http(enabled: bool) -> None:
    transport = GitHubTransport({})
    with pytest.raises(ResolutionError) as raised:
        resolve_github(
            app({"includeZips": enabled, "zippedApkFilterRegEx": "["}),
            HttpClient(HttpConfig({}), retries=0, transport=transport),
        )
    assert raised.value.code == "regex-invalid"
    assert transport.requests == []


def test_nonstring_zip_member_regex_fails_by_name_before_http() -> None:
    transport = GitHubTransport({})
    with pytest.raises(ResolutionError) as raised:
        resolve_github(
            app({"zippedApkFilterRegEx": 7}),
            HttpClient(HttpConfig({}), retries=0, transport=transport),
        )
    assert raised.value.code == "settings-invalid"
    assert "zippedApkFilterRegEx" in str(raised.value)
    assert transport.requests == []


def test_package_containers_use_asset_names_without_enabling_generic_zips() -> None:
    names = ["one.apk", "two.XAPK", "three.apkm", "four.apks"]
    misleading = asset("download")
    misleading["browser_download_url"] = "https://downloads.example/hidden.apk"
    result, _ = resolver(
        [
            release(
                "v1.0",
                assets=[
                    *(asset(name) for name in names),
                    asset("other.zip"),
                    misleading,
                ],
            )
        ],
        {"includeZips": False},
    )
    assert [item.name for item in result.candidates] == names


@pytest.mark.parametrize(
    "invert,expected", [(False, ["keep.xapk"]), (True, ["drop.apks"])]
)
def test_package_container_filter_and_inversion_use_asset_name(
    invert: bool, expected: list[str]
) -> None:
    keep = asset("keep.xapk")
    keep["browser_download_url"] = "https://downloads.example/drop.apks"
    result, _ = resolver(
        [release("v1.0", assets=[keep, asset("drop.apks")])],
        {"apkFilterRegEx": "^keep", "invertAPKFilter": invert, "includeZips": False},
    )
    assert [item.name for item in result.candidates] == expected
