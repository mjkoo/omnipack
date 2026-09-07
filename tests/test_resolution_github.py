from __future__ import annotations

import json
from email.message import Message
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from obtainium_pack.http import HttpClient, HttpConfig, HttpResponse
from obtainium_pack.resolution.github import resolve_github
from obtainium_pack.resolution.types import ResolutionError

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
    releases: object, settings: dict[str, object] | None = None, *, tags: object = ()
):
    transport = GitHubTransport(
        {
            "https://api.github.com/repos/example/emulator/releases?per_page=100": releases,
            "https://api.github.com/repos/example/emulator/tags?per_page=100": tags,
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
        {"verifyLatestTag": True},
        {"includeZips": True},
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


def test_compatibility_fixture_cases_resolve_expected_release_evidence() -> None:
    fixture = json.loads(
        Path("tests/fixtures/verification/github-release-patterns.json").read_text()
    )
    for case in fixture["cases"].values():
        result, _ = resolver(fixture["releases"], case["settings"])
        assert result.effective_version == case["expected"]["version"]
        assert result.candidates[0].url == case["expected"]["selected_url"]


def test_track_only_compatibility_fixture_resolves_without_candidates() -> None:
    fixture = json.loads(
        Path("tests/fixtures/verification/github-track-only.json").read_text()
    )
    result, _ = resolver(
        fixture["responses"]["releases"],
        fixture["settings"],
        tags=fixture["responses"]["tags"],
    )
    assert result.effective_version == fixture["expected"]["version"]
    assert result.candidates == ()
