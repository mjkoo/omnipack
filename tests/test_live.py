from __future__ import annotations

import json
import urllib.error
from collections import Counter
from dataclasses import asdict
from email.message import Message
from typing import Any
from urllib.request import Request

import pytest

from obtainium_pack.http import PROBE_BYTES, HttpClient, HttpConfig, HttpResponse
from obtainium_pack.live import VersionClass, classify_version, verify_live
from obtainium_pack.offline import ValidatedEntry
from obtainium_pack.resolution.types import ResolutionResult
from obtainium_pack.settings_defaults import SETTINGS_DEFAULTS


class RoutingTransport:
    def __init__(self, routes: dict[str, list[HttpResponse | Exception]]) -> None:
        self.routes = {url: iter(outcomes) for url, outcomes in routes.items()}
        self.requests: list[Request] = []
        self.max_bytes: list[int | None] = []

    def __call__(
        self, request: Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse:
        self.requests.append(request)
        self.max_bytes.append(max_bytes)
        outcome = next(self.routes[request.full_url])
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def response(url: str, body: bytes, status: int = 200) -> HttpResponse:
    return HttpResponse(url, status, Message(), body)


def github_entry(
    variant: str = "single",
    *,
    entry_id: str = "org.example.app",
    settings: dict[str, Any] | None = None,
) -> ValidatedEntry:
    complete = {**SETTINGS_DEFAULTS["GitHub"], **(settings or {})}
    raw = {
        "id": entry_id,
        "url": "https://github.com/example/app",
        "name": "Example",
        "author": "Example",
        "categories": [],
        "overrideSource": "GitHub",
        "additionalSettings": json.dumps(complete),
    }
    return ValidatedEntry(variant, 0, entry_id, "GitHub", raw, complete)


def html_entry(
    url: str,
    variant: str,
    *,
    entry_id: str = "org.example.html",
) -> ValidatedEntry:
    complete = {
        **SETTINGS_DEFAULTS["HTML"],
        "customLinkFilterRegex": r"app-[0-9.]+\.apk$",
        "versionExtractionRegEx": r"app-([0-9.]+)\.apk$",
        "matchGroupToUse": "$1",
    }
    raw = {
        "id": entry_id,
        "url": url,
        "name": "HTML app",
        "author": "Example",
        "categories": [],
        "overrideSource": "HTML",
        "additionalSettings": json.dumps(complete),
    }
    return ValidatedEntry(variant, 0, entry_id, "HTML", raw, complete)


def release(
    tag: str,
    *urls: str,
    published_at: str = "2026-09-01T00:00:00Z",
) -> dict[str, object]:
    return {
        "tag_name": tag,
        "name": tag,
        "body": "",
        "draft": False,
        "prerelease": False,
        "published_at": published_at,
        "assets": [
            {"name": f"app-{index}.apk", "browser_download_url": url}
            for index, url in enumerate(urls)
        ],
    }


def client(
    routes: dict[str, list[HttpResponse | Exception]],
) -> tuple[HttpClient, RoutingTransport]:
    transport = RoutingTransport(routes)
    return HttpClient(HttpConfig({}), retries=0, transport=transport), transport


def test_github_probes_candidates_until_success_and_warns_for_prior_failure() -> None:
    releases_url = "https://api.github.com/repos/example/app/releases?per_page=100"
    first = "https://downloads.example/first.apk"
    second = "https://downloads.example/second.apk"
    http, transport = client(
        {
            releases_url: [
                response(
                    releases_url,
                    json.dumps([release("v1.2.3", first, second)]).encode(),
                )
            ],
            first: [urllib.error.URLError("down")],
            second: [response(second, b"apk")],
        }
    )

    result = verify_live({"single": (github_entry(),)}, http)

    assert result.ok
    entry = result.entries[0]
    assert entry.version_class is VersionClass.NUMERIC
    assert [probe.success for probe in entry.probes] == [False, True]
    assert [warning.code for warning in entry.warnings] == ["candidate-probe-failed"]
    assert transport.max_bytes[-2:] == [PROBE_BYTES, PROBE_BYTES]
    assert all(request.method == "GET" for request in transport.requests)
    assert (
        json.loads(json.dumps(asdict(result)))["entries"][0]["version_class"]
        == "numeric"
    )


def test_all_candidates_failing_is_one_entry_error_and_later_entries_continue() -> None:
    releases_url = "https://api.github.com/repos/example/app/releases?per_page=100"
    dead = "https://downloads.example/dead.apk"
    page = "https://html.example/downloads/"
    apk = "https://html.example/downloads/app-2.4.apk"
    http, transport = client(
        {
            releases_url: [
                response(releases_url, json.dumps([release("v1.2", dead)]).encode())
            ],
            dead: [urllib.error.URLError("dead")],
            page: [response(page, b'<a href="app-2.4.apk">download</a>')],
            apk: [response(apk, b"apk")],
        }
    )

    result = verify_live({"single": (github_entry(), html_entry(page, "single"))}, http)

    assert not result.ok
    assert [error.code for error in result.entries[0].errors] == [
        "candidate-probes-failed"
    ]
    assert result.entries[1].ok
    assert apk in [request.full_url for request in transport.requests]


def test_resolution_and_probe_failures_are_both_collected_before_later_success() -> (
    None
):
    releases_url = "https://api.github.com/repos/example/app/releases?per_page=100"
    dead = "https://downloads.example/dead.apk"
    page = "https://html.example/downloads/"
    apk = "https://html.example/downloads/app-2.4.apk"
    invalid = github_entry(entry_id="invalid")
    invalid.raw["url"] = "https://example.com/not-github"
    http, transport = client(
        {
            releases_url: [
                response(
                    releases_url,
                    json.dumps([release("v1.2", dead)]).encode(),
                )
            ],
            dead: [urllib.error.URLError("dead")],
            page: [response(page, b'<a href="app-2.4.apk">download</a>')],
            apk: [response(apk, b"apk")],
        }
    )

    result = verify_live(
        {
            "single": (
                invalid,
                github_entry(entry_id="probe-failure"),
                html_entry(page, "single", entry_id="success"),
            )
        },
        http,
    )

    assert [entry.ok for entry in result.entries] == [False, False, True]
    assert {error.stage for error in result.errors} == {"resolution", "probe"}
    assert apk in [request.full_url for request in transport.requests]


def test_track_only_entry_skips_download_probe() -> None:
    releases_url = "https://api.github.com/repos/example/app/releases?per_page=100"
    http, transport = client(
        {
            releases_url: [
                response(releases_url, json.dumps([release("rolling")]).encode())
            ]
        }
    )

    result = verify_live(
        {"single": (github_entry(settings={"trackOnly": True}),)}, http
    )

    assert result.ok
    assert result.entries[0].version_class is VersionClass.TRACK_ONLY
    assert result.entries[0].probes == ()
    assert len(transport.requests) == 1


def test_unsupported_setting_error_names_the_setting() -> None:
    http, transport = client({})

    result = verify_live(
        {"single": (github_entry(settings={"verifyLatestTag": True}),)}, http
    )

    assert not result.ok
    assert result.errors[0].code == "unsupported-setting"
    assert "verifyLatestTag" in result.errors[0].message
    assert transport.requests == []


def test_malformed_candidate_url_is_recorded_without_stopping_later_probe() -> None:
    releases_url = "https://api.github.com/repos/example/app/releases?per_page=100"
    malformed = "https://[invalid/app.apk"
    valid = "https://downloads.example/app.apk"
    http, transport = client(
        {
            releases_url: [
                response(
                    releases_url,
                    json.dumps([release("v1.2", malformed, valid)]).encode(),
                )
            ],
            valid: [response(valid, b"apk")],
        }
    )

    result = verify_live({"single": (github_entry(),)}, http)

    assert result.ok
    assert [probe.success for probe in result.entries[0].probes] == [False, True]
    assert result.entries[0].probes[0].url == "<invalid-url>"
    assert result.warnings[0].code == "candidate-probe-failed"
    assert [request.full_url for request in transport.requests][-1] == valid


def test_resolution_error_preserves_context_but_redacts_query_values() -> None:
    url = "https://html.example/releases/?token=secret-value"
    http, _ = client({url: [response(url, b"no downloads here")]})

    result = verify_live({"single": (html_entry(url, "single"),)}, http)

    message = result.errors[0].message
    assert "final page selected no download" in message
    assert "token=REDACTED" in message
    assert "secret-value" not in message


@pytest.mark.parametrize(
    ("version", "settings", "expected", "warning"),
    [
        ("1.2", {}, VersionClass.NUMERIC, False),
        ("V1.2.3-beta.1+build-7", {}, VersionClass.NUMERIC, False),
        ("1", {}, VersionClass.NONNUMERIC, True),
        (
            "continuous",
            {"versionExtractionRegEx": "(.*)"},
            VersionClass.NONNUMERIC,
            True,
        ),
        ("rolling", {"releaseTitleAsVersion": True}, VersionClass.NONNUMERIC, True),
        ("anything", {"trackOnly": True}, VersionClass.TRACK_ONLY, False),
        (
            "anything",
            {"versionDetection": False},
            VersionClass.DETECTION_DISABLED,
            False,
        ),
        ("1", {"releaseDateAsVersion": True}, VersionClass.DATE, False),
    ],
)
def test_version_classification_is_anchored_and_exclusions_are_distinct(
    version: str,
    settings: dict[str, Any],
    expected: VersionClass,
    warning: bool,
) -> None:
    resolution = ResolutionResult(version, version, "tag", ())
    classification, finding = classify_version("GitHub", settings, resolution)
    assert classification is expected
    assert (finding is not None) is warning


def test_identical_resolution_inputs_reuse_metadata_but_keep_entry_results() -> None:
    releases_url = "https://api.github.com/repos/example/app/releases?per_page=100"
    apk = "https://downloads.example/app.apk"
    http, transport = client(
        {
            releases_url: [
                response(releases_url, json.dumps([release("v1.2", apk)]).encode())
            ],
            apk: [response(apk, b"one"), response(apk, b"two")],
        }
    )
    entries = {
        "single": (github_entry("single"),),
        "dual": (github_entry("dual"),),
    }

    result = verify_live(entries, http)

    counts = Counter(request.full_url for request in transport.requests)
    assert result.ok
    assert {(entry.variant, entry.entry_id) for entry in result.entries} == {
        ("single", "org.example.app"),
        ("dual", "org.example.app"),
    }
    assert counts[releases_url] == 1
    assert counts[apk] == 2


def test_different_settings_reuse_same_metadata_request_but_resolve_separately() -> (
    None
):
    releases_url = "https://api.github.com/repos/example/app/releases?per_page=100"
    apk = "https://downloads.example/app.apk"
    metadata = json.dumps([release("v1.2", apk)]).encode()
    http, transport = client(
        {
            releases_url: [response(releases_url, metadata)],
            apk: [response(apk, b"one"), response(apk, b"two")],
        }
    )
    entries = {
        "single": (github_entry("single"),),
        "dual": (github_entry("dual", settings={"versionDetection": False}),),
    }

    result = verify_live(entries, http)

    assert result.entries[0].version_class is VersionClass.NUMERIC
    assert result.entries[1].version_class is VersionClass.DETECTION_DISABLED
    assert (
        Counter(request.full_url for request in transport.requests)[releases_url] == 1
    )


def test_slash_distinct_html_urls_resolve_separate_versions_and_relative_bases() -> (
    None
):
    plain = "https://html.example/releases"
    slash = "https://html.example/releases/"
    plain_apk = "https://html.example/app-1.2.apk"
    slash_apk = "https://html.example/releases/app-2.3.apk"
    http, transport = client(
        {
            plain: [response(plain, b'<a href="app-1.2.apk">one</a>')],
            slash: [response(slash, b'<a href="app-2.3.apk">two</a>')],
            plain_apk: [response(plain_apk, b"one")],
            slash_apk: [response(slash_apk, b"two")],
        }
    )

    result = verify_live(
        {
            "single": (html_entry(plain, "single"),),
            "dual": (html_entry(slash, "dual"),),
        },
        http,
    )

    assert result.ok
    resolutions = [entry.resolution for entry in result.entries]
    assert all(resolution is not None for resolution in resolutions)
    assert [
        resolution.effective_version
        for resolution in resolutions
        if resolution is not None
    ] == [
        "1.2",
        "2.3",
    ]
    assert [entry.probes[0].url for entry in result.entries] == [plain_apk, slash_apk]
    requested = [request.full_url for request in transport.requests]
    assert plain in requested and slash in requested


def test_each_invocation_makes_fresh_requests() -> None:
    releases_url = "https://api.github.com/repos/example/app/releases?per_page=100"
    metadata = json.dumps([release("v1.2")]).encode()
    http, transport = client(
        {
            releases_url: [
                response(releases_url, metadata),
                response(releases_url, metadata),
            ]
        }
    )
    entries = {"single": (github_entry(settings={"trackOnly": True}),)}

    assert verify_live(entries, http).ok
    assert verify_live(entries, http).ok
    assert len(transport.requests) == 2
