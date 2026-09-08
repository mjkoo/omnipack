from __future__ import annotations

import json
from collections.abc import Mapping
from email.message import Message
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from obtainium_pack.http import HttpClient, HttpConfig, HttpResponse
from obtainium_pack.resolution.html import resolve_html
from obtainium_pack.resolution.types import ResolutionError

if TYPE_CHECKING:
    from urllib.request import Request

FIXTURES = Path(__file__).parent / "fixtures" / "verification"


class PageTransport:
    def __init__(self, pages: dict[str, tuple[str, str]]) -> None:
        self.pages = pages
        self.requests: list[Request] = []

    def __call__(
        self, request: Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse:
        self.requests.append(request)
        final_url, body = self.pages[request.full_url]
        return HttpResponse(final_url, 200, Message(), body.encode())


def resolve(
    body: str,
    settings: Mapping[str, object],
    *,
    url: str = "https://example.com/releases/",
    final_url: str | None = None,
):
    transport = PageTransport({url: (final_url or url, body)})
    result = resolve_html(
        {"url": url, "additionalSettings": json.dumps(settings)},
        HttpClient(HttpConfig({}), retries=0, transport=transport),
    )
    return result, transport


def test_anchor_text_filter_and_redirected_relative_base() -> None:
    result, _ = resolve(
        '<a href="old.apk">Linux</a><a href="new.apk">Android arm64</a>',
        {
            "customLinkFilterRegex": "Android",
            "filterByLinkText": True,
            "versionExtractionRegEx": r"(new)\.apk",
            "matchGroupToUse": "$1",
        },
        url="https://example.com/go",
        final_url="https://cdn.example/builds/",
    )
    assert result.candidates[0].url == "https://cdn.example/builds/new.apk"
    assert result.effective_version == "new"


def test_json_escaped_urls_are_extracted_and_decoded_for_filtering() -> None:
    result, _ = resolve(
        '{"assets":["https:\\/\\/cdn.example\\/app%2D2.apk"]}',
        {
            "matchLinksOutsideATags": True,
            "customLinkFilterRegex": "app-2",
            "versionExtractionRegEx": r"app-(\d+)",
            "matchGroupToUse": "$1",
        },
    )
    assert result.candidates[0].url == "https://cdn.example/app%2D2.apk"
    assert result.effective_version == "2"


def test_raw_text_url_is_extracted_when_document_is_not_json_or_html() -> None:
    result, _ = resolve(
        "download https://cdn.example/releases/app-7.apk now",
        {
            "customLinkFilterRegex": r"app-7\.apk$",
            "versionExtractionRegEx": r"app-(\d+)",
            "matchGroupToUse": "$1",
        },
    )
    assert result.candidates[0].url == "https://cdn.example/releases/app-7.apk"
    assert result.effective_version == "7"


@pytest.mark.parametrize(
    "body", ["release-9.apk", '<a href="release-9.apk">download</a>']
)
def test_outside_anchor_matching_does_not_resolve_arbitrary_page_as_url(
    body: str,
) -> None:
    with pytest.raises(ResolutionError) as raised:
        resolve(
            body,
            {
                "matchLinksOutsideATags": True,
                "customLinkFilterRegex": "release-9",
                "versionExtractionRegEx": r"release-(\d+)",
                "matchGroupToUse": "$1",
            },
        )
    assert raised.value.code == "html-final-empty"


def test_json_absolute_links_prevent_relative_fallback_across_all_strings() -> None:
    result, _ = resolve(
        json.dumps({"url": "https://cdn.example/app-2.apk", "notes": "app-99.apk"}),
        {"versionExtractionRegEx": r"app-(\d+)", "matchGroupToUse": "$1"},
    )
    assert result.candidates[0].url == "https://cdn.example/app-2.apk"
    assert result.effective_version == "2"


def test_json_relative_strings_are_used_when_no_absolute_link_exists() -> None:
    result, _ = resolve(
        json.dumps({"nested": ["app-2.apk", {"file": "app-10.apk"}]}),
        {"versionExtractionRegEx": r"app-(\d+)", "matchGroupToUse": "$1"},
    )
    assert result.candidates[0].url == "https://example.com/releases/app-10.apk"
    assert result.effective_version == "10"


def test_raw_url_match_preserves_non_whitespace_suffix() -> None:
    with pytest.raises(ResolutionError) as raised:
        resolve(
            'download https://cdn.example/app-7.apk" now',
            {"versionExtractionRegEx": r"app-(\d+)", "matchGroupToUse": "$1"},
        )
    assert raised.value.code == "html-final-empty"


def test_natural_and_last_segment_sort_choose_different_links() -> None:
    body = (
        '<a href="https://z.example/app-2.apk">two</a>'
        '<a href="https://a.example/app-10.apk">ten</a>'
    )
    natural, _ = resolve(
        body, {"versionExtractionRegEx": r"app-(\d+)", "matchGroupToUse": "$1"}
    )
    segment, _ = resolve(
        body,
        {
            "sortByLastLinkSegment": True,
            "versionExtractionRegEx": r"app-(\d+)",
            "matchGroupToUse": "$1",
        },
    )
    assert natural.effective_version == "2"
    assert segment.effective_version == "10"


@pytest.mark.parametrize(
    ("skip", "reverse", "expected"),
    [(True, False, "10"), (True, True, "2"), (False, True, "2")],
)
def test_skip_and_reverse_are_independent(
    skip: bool, reverse: bool, expected: str
) -> None:
    body = '<a href="app-2.apk">two</a><a href="app-10.apk">ten</a>'
    result, _ = resolve(
        body,
        {
            "skipSort": skip,
            "reverseSort": reverse,
            "versionExtractionRegEx": r"app-(\d+)",
            "matchGroupToUse": "$1",
        },
    )
    assert result.effective_version == expected


def test_custom_headers_are_used_on_every_metadata_request() -> None:
    result, transport = resolve(
        '<a href="app.apk">app</a>',
        {
            "requestHeader": [
                {"requestHeader": "User-Agent: Fixture/1"},
                {"requestHeader": "X-Channel: stable:arm64"},
            ],
            "versionExtractionRegEx": "(app)",
        },
    )
    assert result.effective_version == "app"
    assert transport.requests[0].get_header("User-agent") == "Fixture/1"
    assert transport.requests[0].get_header("X-channel") == "stable:arm64"


def test_apk_filter_and_inversion_apply_after_link_selection() -> None:
    result, _ = resolve(
        '<a href="debug.apk">debug</a><a href="release.apk">release</a>',
        {
            "apkFilterRegEx": "debug",
            "invertAPKFilter": True,
            "versionExtractionRegEx": "(release)",
            "matchGroupToUse": "$1",
        },
    )
    assert result.candidates[0].url == "https://example.com/releases/release.apk"


def test_intermediate_last_selection_and_empty_steps_are_ignored() -> None:
    pages = {
        "https://example.com/start": (
            "https://example.com/start",
            '<a href="v2/">v2</a><a href="v10/">v10</a>',
        ),
        "https://example.com/v10/": (
            "https://example.com/v10/",
            '<a href="app-2.apk">old</a><a href="app-10.apk">new</a>',
        ),
    }
    transport = PageTransport(pages)
    result = resolve_html(
        {
            "url": "https://example.com/start",
            "additionalSettings": json.dumps(
                {
                    "intermediateLink": [
                        {"customLinkFilterRegex": ""},
                        {"customLinkFilterRegex": r"/v\d+/"},
                    ],
                    "versionExtractionRegEx": r"app-(\d+)",
                    "matchGroupToUse": "$1",
                }
            ),
        },
        HttpClient(HttpConfig({}), retries=0, transport=transport),
    )
    assert result.candidates[0].url == "https://example.com/v10/app-10.apk"
    assert result.effective_version == "10"
    assert [request.full_url for request in transport.requests] == [
        "https://example.com/start",
        "https://example.com/v10/",
    ]


@pytest.mark.parametrize(
    ("settings", "code"),
    [
        (
            {"intermediateLink": [{"customLinkFilterRegex": "missing"}]},
            "html-intermediate-empty",
        ),
        ({"versionExtractionRegEx": "v(\\d+)"}, "html-final-empty"),
        (
            {"intermediateLink": [{"customLinkFilterRegex": "."}] * 11},
            "html-depth-exceeded",
        ),
    ],
)
def test_traversal_failures_are_explicit(
    settings: dict[str, object], code: str
) -> None:
    with pytest.raises(ResolutionError) as raised:
        resolve("<p>none</p>", settings)
    assert raised.value.code == code


def test_track_only_whole_page_version_can_omit_download_but_installable_cannot() -> (
    None
):
    settings = {
        "trackOnly": True,
        "versionExtractWholePage": True,
        "versionExtractionRegEx": r"Version: (\d+\.\d+)",
        "matchGroupToUse": "$1",
    }
    result, _ = resolve("Version: 3.4", settings)
    assert result.effective_version == "3.4"
    assert result.candidates == ()
    with pytest.raises(ResolutionError) as raised:
        resolve("Version: 3.4", {**settings, "trackOnly": False})
    assert raised.value.code == "html-final-empty"


def test_track_only_still_requires_intermediate_and_url_extraction_input() -> None:
    with pytest.raises(ResolutionError) as intermediate:
        resolve(
            "Version: 1.0",
            {
                "trackOnly": True,
                "intermediateLink": [{"customLinkFilterRegex": "missing"}],
                "versionExtractWholePage": True,
                "versionExtractionRegEx": r"(1\.0)",
            },
        )
    assert intermediate.value.code == "html-intermediate-empty"
    with pytest.raises(ResolutionError) as final:
        resolve(
            "Version: 1.0",
            {"trackOnly": True, "versionExtractionRegEx": r"(1\.0)"},
        )
    assert final.value.code == "html-final-empty"


def test_track_only_whole_page_still_completes_intermediate_traversal() -> None:
    pages = {
        "https://example.com/start": (
            "https://example.com/start",
            '<a href="versions/current/">current</a>',
        ),
        "https://example.com/versions/current/": (
            "https://example.com/versions/current/",
            "Release: 4.5\r\nNo downloads",
        ),
    }
    transport = PageTransport(pages)
    result = resolve_html(
        {
            "url": "https://example.com/start",
            "additionalSettings": json.dumps(
                {
                    "trackOnly": True,
                    "intermediateLink": [
                        {"customLinkFilterRegex": "/versions/current/"}
                    ],
                    "versionExtractWholePage": True,
                    "versionExtractionRegEx": r"Release: (\d+\.\d+)\\n",
                    "matchGroupToUse": "$1",
                }
            ),
        },
        HttpClient(HttpConfig({}), retries=0, transport=transport),
    )
    assert result.effective_version == "4.5"
    assert result.candidates == ()
    assert len(transport.requests) == 2


@pytest.mark.parametrize("track_only", [False, True])
def test_active_pseudo_versioning_without_extraction_fails(track_only: bool) -> None:
    with pytest.raises(ResolutionError) as raised:
        resolve(
            '<a href="app.apk">app</a>',
            {
                "trackOnly": track_only,
                "defaultPseudoVersioningMethod": "APKLinkHash",
                "versionExtractionRegEx": "",
            },
        )
    assert raised.value.code == "unsupported-setting"


def test_explicit_extraction_ignores_nonempty_pseudo_versioning_default() -> None:
    result, transport = resolve(
        '<a href="app-12.apk">app</a>',
        {
            "defaultPseudoVersioningMethod": "partialAPKHash",
            "versionExtractionRegEx": r"app-(\d+)",
            "matchGroupToUse": "$1",
        },
    )
    assert result.effective_version == "12"
    assert result.candidates[0].url == "https://example.com/releases/app-12.apk"
    assert len(transport.requests) == 1


@pytest.mark.parametrize(
    ("pattern", "group", "code"),
    [
        (r"missing-(\d+)", "$1", "regex-no-match"),
        (r"(x)?app", "$1", "version-empty"),
    ],
)
def test_version_extraction_never_uses_a_placeholder_or_raw_fallback(
    pattern: str, group: str, code: str
) -> None:
    with pytest.raises(ResolutionError) as raised:
        resolve(
            '<a href="app.apk">app</a>',
            {"versionExtractionRegEx": pattern, "matchGroupToUse": group},
        )
    assert raised.value.code == code


def test_resolver_returns_only_the_selected_html_candidate_without_probing() -> None:
    result, transport = resolve(
        '<a href="app-2.apk">older</a><a href="app-10.apk">selected</a>',
        {
            "versionExtractionRegEx": r"app-(\d+)",
            "matchGroupToUse": "$1",
        },
    )
    assert [candidate.url for candidate in result.candidates] == [
        "https://example.com/releases/app-10.apk"
    ]
    assert len(transport.requests) == 1


def test_all_seven_captured_html_fixtures_resolve_through_http() -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    for item in manifest["cases"]:
        if item["source"] != "HTML":
            continue
        fixture = json.loads((FIXTURES / item["fixture"]).read_text())
        pages = {
            response["url"]: (response["url"], response["body"])
            for response in fixture["responses"]
        }
        transport = PageTransport(pages)
        result = resolve_html(
            {
                "url": fixture["provenance"]["source_url"],
                "additionalSettings": json.dumps(fixture["settings"]),
            },
            HttpClient(HttpConfig({}), retries=0, transport=transport),
        )
        assert result.candidates[0].url == fixture["expected"]["selected_url"]
        assert result.effective_version == fixture["expected"]["version"]
        assert transport.requests


@pytest.mark.parametrize("active", [False, True])
def test_html_date_override_is_rejected_before_http_when_active(active: bool) -> None:
    transport = PageTransport(
        {
            "https://example.com": (
                "https://example.com",
                '<a href="app-2.apk">Android</a>',
            )
        }
    )
    entry = {
        "url": "https://example.com",
        "additionalSettings": json.dumps(
            {
                "versionExtractionRegEx": r"app-(\d+)",
                "matchGroupToUse": "1",
                "releaseDateAsVersion": active,
            }
        ),
    }
    http = HttpClient(HttpConfig({}), transport=transport)
    if active:
        with pytest.raises(ResolutionError, match="release date") as raised:
            resolve_html(entry, http)
        assert raised.value.code == "unsupported-setting"
        assert transport.requests == []
    else:
        assert resolve_html(entry, http).effective_version == "2"
        assert len(transport.requests) == 1


@pytest.mark.parametrize("active", [False, True])
def test_intermediate_arch_filter_only_rejects_active_steps(active: bool) -> None:
    transport = PageTransport(
        {"https://example.com": ("https://example.com", '<a href="v1.apk">one</a>')}
    )
    entry = {
        "url": "https://example.com",
        "additionalSettings": json.dumps(
            {
                "versionExtractionRegEx": r"v(\d+)",
                "matchGroupToUse": "1",
                "intermediateLink": [
                    {
                        "customLinkFilterRegex": "next" if active else "",
                        "autoLinkFilterByArch": True,
                    }
                ],
            }
        ),
    }
    http = HttpClient(HttpConfig({}), transport=transport)
    if active:
        with pytest.raises(ResolutionError, match="intermediateLink"):
            resolve_html(entry, http)
        assert transport.requests == []
    else:
        assert resolve_html(entry, http).effective_version == "1"
        assert len(transport.requests) == 1
