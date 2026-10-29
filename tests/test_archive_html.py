from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from omnipack.archive import Asset, NoReleaseError, UnreachableError
from omnipack.archive.html import resolve_html
from omnipack.archive.selection import SettingsError, VersionError
from omnipack.http import DeadlineExceeded, HttpClient
from tests.http_support import RoutedTransport

PAGE = "https://example.com/downloads/"


def anchors(*hrefs: str) -> str:
    links = "".join(f'<li><a href="{href}">{href}</a></li>' for href in hrefs)
    return f"<html><body><ul>{links}</ul></body></html>"


def entry(url: str = PAGE, **settings: object) -> dict[str, Any]:
    return {
        "url": url,
        "overrideSource": "HTML",
        "additionalSettings": json.dumps(settings),
    }


def resolve(
    answers: dict[str, Any], entry_: dict[str, Any], **kwargs: Any
) -> tuple[Any, RoutedTransport]:
    transport = RoutedTransport(answers)
    http = HttpClient(transport=transport, sleep=lambda _seconds: None)
    return resolve_html(entry_, http, **kwargs), transport


def test_a_direct_link_resolves_to_the_last_sorted_apk_and_its_version() -> None:
    page = anchors("app-1.2.apk", "app-1.10.apk", "app-1.9.apk", "readme.txt")

    release, transport = resolve(
        {PAGE: page},
        entry(versionExtractionRegEx=r"app-(.+)\.apk", matchGroupToUse="$1"),
    )

    url = "https://example.com/downloads/app-1.10.apk"
    assert release.version == "1.10"
    assert release.assets == (Asset("app-1.10.apk", url),)
    assert release.fetched_urls == (PAGE,)
    assert release.raw_record == {}
    assert (release.tag, release.date, release.notes) == (None, None, None)
    assert len(transport.requests) == 1


def test_a_two_step_chain_follows_each_stage_and_records_the_pages() -> None:
    root = "https://example.com/stable/"
    series = "https://example.com/stable/2.3/"
    patch = "https://example.com/stable/2.3/2.3.1/"
    answers = {
        root: anchors("/stable/1.9/", "/stable/2.3/", "/other/"),
        series: anchors("/stable/2.3/2.3.0/", "/stable/2.3/2.3.1/"),
        patch: anchors("app-aarch64.apk", "app-x86.apk"),
    }
    steps = [
        {"customLinkFilterRegex": r"/stable/\d+\.\d+/$"},
        {"customLinkFilterRegex": r"/stable/\d+\.\d+/\d+\.\d+\.\d+/$"},
    ]

    release, transport = resolve(
        answers,
        entry(
            root,
            intermediateLink=steps,
            customLinkFilterRegex="aarch64",
            versionExtractionRegEx=r"/([0-9.]+)/[^/]*\.apk$",
            matchGroupToUse="$1",
        ),
    )

    assert release.version == "2.3.1"
    assert release.assets == (Asset("app-aarch64.apk", f"{patch}app-aarch64.apk"),)
    assert release.fetched_urls == (root, series, patch)
    assert [r.full_url for r in transport.requests] == [root, series, patch]


def test_a_json_body_yields_links_and_a_whole_page_version() -> None:
    url = "https://example.com/latest/release.json"
    body = json.dumps(
        {
            "tag_name": "v0.2",
            "assets": [
                {"url": "https://cdn.example.com/Eden-Android-0.2-standard.apk"},
                {"url": "https://cdn.example.com/Eden-Android-0.2-legacy.apk"},
            ],
        }
    )

    release, _ = resolve(
        {url: body},
        entry(
            url,
            customLinkFilterRegex=r"Eden-Android-.*-standard\.apk$",
            matchLinksOutsideATags=True,
            versionExtractWholePage=True,
            versionExtractionRegEx=r'"tag_name"\s*:\s*"v?([^"]+)"',
            matchGroupToUse="$1",
        ),
    )

    assert release.version == "0.2"
    assert release.assets == (
        Asset(
            "Eden-Android-0.2-standard.apk",
            "https://cdn.example.com/Eden-Android-0.2-standard.apk",
        ),
    )


def test_links_outside_anchors_count_only_where_the_entry_asks() -> None:
    text = "<p>Get https://cdn.example.com/app-1.apk, now</p>"
    version = {"versionExtractionRegEx": r"app-(.+)\.apk", "matchGroupToUse": "$1"}

    with pytest.raises(NoReleaseError):
        resolve({PAGE: anchors("a.txt") + text}, entry(**version))
    release, _ = resolve(
        {PAGE: anchors("a.txt") + text}, entry(matchLinksOutsideATags=True, **version)
    )

    assert release.version == "1"
    assert release.assets[0].url == "https://cdn.example.com/app-1.apk"


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        ({}, "app-2.apk"),
        ({"reverseSort": True}, "app-9.apk"),
        ({"skipSort": True}, "app-9.apk"),
        ({"skipSort": True, "reverseSort": True}, "app-2.apk"),
        ({"sortByLastLinkSegment": True}, "app-10.apk"),
        ({"filterByLinkText": True, "customLinkFilterRegex": "^Get 1"}, "app-10.apk"),
        ({"apkFilterRegEx": "app-2", "invertAPKFilter": True}, "app-10.apk"),
    ],
)
def test_link_options_decide_which_link_is_last(
    settings: dict[str, Any], expected: str
) -> None:
    page = (
        '<a href="/e/app-2.apk">Get 2</a><a href="/d/app-10.apk">Get 10</a>'
        '<a href="/d/app-9.apk">Get 9</a>'
    )
    release, _ = resolve(
        {PAGE: page}, entry(defaultPseudoVersioningMethod="APKLinkHash", **settings)
    )

    assert release.assets[0].name == expected


def test_the_request_headers_are_sent_to_every_page() -> None:
    root, final = "https://example.com/a/", "https://example.com/a/b/"
    answers = {root: anchors("/a/b/"), final: anchors("app.apk")}

    _, transport = resolve(
        answers,
        entry(
            root,
            intermediateLink=[{"customLinkFilterRegex": "/b/$"}],
            requestHeader=[
                {"requestHeader": "User-Agent: Obtainium/1.0"},
                {"requestHeader": "X-Mirror: https://m.example/x"},
            ],
            defaultPseudoVersioningMethod="APKLinkHash",
        ),
    )

    for request in transport.requests:
        assert request.get_header("User-agent") == "Obtainium/1.0"
        assert request.get_header("X-mirror") == "https://m.example/x"


def test_without_a_version_pattern_a_link_hash_versions_the_link() -> None:
    page = anchors("app.apk")

    release, _ = resolve(
        {PAGE: page}, entry(defaultPseudoVersioningMethod="APKLinkHash")
    )

    link = "https://example.com/downloads/app.apk"
    assert release.version == hashlib.sha256(link.encode()).hexdigest()[:16]


@pytest.mark.parametrize("method", ["partialAPKHash", "ETag", None])
def test_pseudo_versions_that_need_a_download_are_not_supported(
    method: str | None,
) -> None:
    settings = {} if method is None else {"defaultPseudoVersioningMethod": method}

    with pytest.raises(SettingsError):
        resolve({PAGE: anchors("app.apk")}, entry(**settings))


def test_versioning_by_release_date_is_not_supported_and_fetches_nothing() -> None:
    transport = RoutedTransport({})
    http = HttpClient(transport=transport)

    with pytest.raises(SettingsError):
        resolve_html(entry(releaseDateAsVersion=True), http)

    assert transport.requests == []


def test_a_version_pattern_that_matches_nothing_fails_the_target() -> None:
    with pytest.raises(VersionError):
        resolve({PAGE: anchors("app.apk")}, entry(versionExtractionRegEx="zzz"))


def test_a_scheme_less_entry_url_is_fetched_over_https() -> None:
    _, transport = resolve(
        {"https://example.com/dl": anchors("a.apk")},
        entry("example.com/dl", defaultPseudoVersioningMethod="APKLinkHash"),
    )

    assert transport.requests[0].full_url == "https://example.com/dl"


@pytest.mark.parametrize(
    "answers",
    [
        {PAGE: anchors("readme.txt")},
        {PAGE: ""},
        {PAGE: anchors("/step/"), "https://example.com/step/": anchors("none.txt")},
    ],
)
def test_a_page_without_a_matching_link_is_a_no_release_outcome(
    answers: dict[str, Any],
) -> None:
    steps = [{"customLinkFilterRegex": "/step/"}] if len(answers) > 1 else []

    with pytest.raises(NoReleaseError):
        resolve(answers, entry(intermediateLink=steps))


def test_a_missing_page_is_unreachable_at_any_stage() -> None:
    step = "https://example.com/step/"
    with pytest.raises(UnreachableError):
        resolve({PAGE: 404}, entry())
    with pytest.raises(UnreachableError):
        resolve(
            {PAGE: anchors("/step/"), step: 410},
            entry(intermediateLink=[{"customLinkFilterRegex": "/step/"}]),
        )


def test_the_deadline_bounds_the_requests() -> None:
    transport = RoutedTransport({})
    http = HttpClient(transport=transport, clock=lambda: 10.0)

    with pytest.raises(DeadlineExceeded):
        resolve_html(entry(), http, deadline=10.0)

    assert transport.requests == []
