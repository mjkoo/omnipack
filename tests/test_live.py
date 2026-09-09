from __future__ import annotations

import json
import urllib.error
from collections import Counter
from dataclasses import asdict
from email.message import Message
from typing import Any
from urllib.request import Request

import pytest

from omnipack.http import (
    PROBE_BYTES,
    HttpClient,
    HttpConfig,
    HttpError,
    HttpResponse,
)
from omnipack.live import VersionClass, classify_version, verify_live
from omnipack.offline import ValidatedEntry
from omnipack.resolution.types import ResolutionResult
from omnipack.settings_defaults import SETTINGS_DEFAULTS


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

    result = verify_live({"single": (github_entry(),)}, http, probe_assets=True)

    assert result.ok
    entry = result.entries[0]
    assert entry.version_class is VersionClass.NUMERIC
    assert [probe.success for probe in entry.probes] == [False, True]
    assert [warning.code for warning in entry.warnings] == ["candidate-probe-failed"]
    assert "down" in entry.warnings[0].message
    assert "down" in (entry.probes[0].failure_reason or "")
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

    result = verify_live(
        {"single": (github_entry(), html_entry(page, "single"))},
        http,
        probe_assets=True,
    )

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
        probe_assets=True,
    )

    assert [entry.ok for entry in result.entries] == [False, False, True]
    assert {error.stage for error in result.errors} == {"resolution", "probe"}
    assert apk in [request.full_url for request in transport.requests]


def test_track_only_entry_skips_download_probe() -> None:
    releases_url = "https://api.github.com/repos/example/app/releases?per_page=100"
    http, transport = client(
        {
            releases_url: [
                response(
                    releases_url,
                    json.dumps(
                        [release("rolling", "https://downloads.example/app.apk")]
                    ).encode(),
                )
            ]
        }
    )

    result = verify_live(
        {"single": (github_entry(settings={"trackOnly": True}),)},
        http,
        probe_assets=True,
    )

    assert result.ok
    assert result.entries[0].version_class is VersionClass.TRACK_ONLY
    assert result.entries[0].resolution is not None
    assert result.entries[0].resolution.candidates
    assert result.entries[0].probes == ()
    assert len(transport.requests) == 1


def test_unsupported_setting_error_names_the_setting() -> None:
    http, transport = client({})

    result = verify_live(
        {"single": (github_entry(settings={"includeZips": True}),)}, http
    )

    assert not result.ok
    assert result.errors[0].code == "unsupported-setting"
    assert "includeZips" in result.errors[0].message
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

    result = verify_live({"single": (github_entry(),)}, http, probe_assets=True)

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
        ("1", {}, VersionClass.NUMERIC, False),
        ("4093", {}, VersionClass.NUMERIC, False),
        ("20250425", {}, VersionClass.NUMERIC, False),
        ("v20250425", {}, VersionClass.NUMERIC, False),
        ("V4093", {}, VersionClass.NUMERIC, False),
        ("2026-04-27", {}, VersionClass.NONNUMERIC, True),
        ("0b11201", {}, VersionClass.NONNUMERIC, True),
        ("Android-Build4", {}, VersionClass.NONNUMERIC, True),
        ("XenDroid-0b11201", {}, VersionClass.NONNUMERIC, True),
        ("", {}, VersionClass.NONNUMERIC, True),
        ("1junk", {}, VersionClass.NONNUMERIC, True),
        ("1-beta", {}, VersionClass.NONNUMERIC, True),
        ("1.2\n", {}, VersionClass.NONNUMERIC, True),
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

    result = verify_live(entries, http, probe_assets=True)

    counts = Counter(request.full_url for request in transport.requests)
    assert result.ok
    assert {(entry.variant, entry.entry_id) for entry in result.entries} == {
        ("single", "org.example.app"),
        ("dual", "org.example.app"),
    }
    assert counts[releases_url] == 1
    assert counts[apk] == 1
    assert all(entry.probes[0].success for entry in result.entries)


def test_metadata_only_resolves_candidates_without_asset_requests() -> None:
    releases_url = "https://api.github.com/repos/example/app/releases?per_page=100"
    apk = "https://downloads.example/app.apk"
    http, transport = client(
        {
            releases_url: [
                response(releases_url, json.dumps([release("v1.2", apk)]).encode())
            ]
        }
    )

    result = verify_live({"single": (github_entry(),)}, http)

    assert result.ok
    assert result.entries[0].probes == ()
    assert result.entries[0].resolution is not None
    assert [item.url for item in result.entries[0].resolution.candidates] == [apk]
    assert [request.full_url for request in transport.requests] == [releases_url]


def test_identical_metadata_failures_are_cached_with_per_entry_findings() -> None:
    releases_url = "https://api.github.com/repos/example/app/releases?per_page=100"
    http, transport = client(
        {
            releases_url: [
                urllib.error.URLError("offline"),
                urllib.error.URLError("offline"),
            ]
        }
    )
    entries = {
        "single": (github_entry("single"),),
        "dual": (github_entry("dual"),),
    }

    result = verify_live(entries, http)

    assert not result.ok
    assert len(result.entries) == 2
    assert all(
        entry.errors[0].code == "github-request-failed" for entry in result.entries
    )
    assert [entry.errors[0].variant for entry in result.entries] == ["single", "dual"]
    assert (
        Counter(request.full_url for request in transport.requests)[releases_url] == 1
    )
    assert not verify_live(entries, http).ok
    assert (
        Counter(request.full_url for request in transport.requests)[releases_url] == 2
    )


def test_wrapped_metadata_failure_keeps_actionable_reason() -> None:
    releases_url = "https://api.github.com/repos/example/app/releases?per_page=100"
    reason = "authenticated GitHub metadata requires a configured credential"
    http, _ = client({releases_url: [HttpError(reason)]})

    result = verify_live({"single": (github_entry(),)}, http)

    assert not result.ok
    assert reason in result.errors[0].message


def test_identical_probe_failures_are_cached_with_per_entry_evidence() -> None:
    releases_url = "https://api.github.com/repos/example/app/releases?per_page=100"
    apk = "https://downloads.example/dead.apk"
    http, transport = client(
        {
            releases_url: [
                response(releases_url, json.dumps([release("v1.2", apk)]).encode()),
                response(releases_url, json.dumps([release("v1.2", apk)]).encode()),
            ],
            apk: [
                urllib.error.URLError("offline"),
                urllib.error.URLError("offline"),
            ],
        }
    )
    entries = {
        "single": (github_entry("single"),),
        "dual": (github_entry("dual"),),
    }

    result = verify_live(
        entries,
        http,
        probe_assets=True,
    )

    assert not result.ok
    assert len(result.entries) == 2
    assert all(entry.probes[0].failure_reason for entry in result.entries)
    assert [entry.errors[0].variant for entry in result.entries] == ["single", "dual"]
    counts = Counter(request.full_url for request in transport.requests)
    assert counts[releases_url] == counts[apk] == 1
    assert not verify_live(entries, http, probe_assets=True).ok
    counts = Counter(request.full_url for request in transport.requests)
    assert counts[releases_url] == counts[apk] == 2


def test_different_settings_reuse_same_metadata_request_but_resolve_separately() -> (
    None
):
    releases_url = "https://api.github.com/repos/example/app/releases?per_page=100"
    first_apk = "https://downloads.example/stable.apk"
    second_apk = "https://downloads.example/beta.apk"
    metadata = json.dumps(
        [release("v1.2", first_apk), release("v2.0", second_apk)]
    ).encode()
    http, transport = client({releases_url: [response(releases_url, metadata)]})
    entries = {
        "single": (
            github_entry(
                "single",
                settings={
                    "filterReleaseTitlesByRegEx": "v1",
                    "fallbackToOlderReleases": True,
                },
            ),
        ),
        "dual": (
            github_entry(
                "dual",
                settings={
                    "filterReleaseTitlesByRegEx": "v2",
                    "fallbackToOlderReleases": True,
                },
            ),
        ),
    }
    result = verify_live(entries, http)
    assert result.ok
    assert [
        entry.resolution.effective_version
        for entry in result.entries
        if entry.resolution is not None
    ] == [
        "v1.2",
        "v2.0",
    ]
    assert [
        entry.resolution.candidates[0].url
        for entry in result.entries
        if entry.resolution is not None
    ] == [
        first_apk,
        second_apk,
    ]
    assert len(transport.requests) == 1


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
        probe_assets=True,
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


@pytest.mark.parametrize(
    "failure, reason",
    [
        (
            urllib.error.HTTPError(
                "https://downloads.example/dead.apk",
                429,
                "rate limited",
                Message(),
                None,
            ),
            "HTTP 429",
        ),
        (TimeoutError("timed out"), "timed out"),
        (urllib.error.URLError("DNS unavailable"), "DNS unavailable"),
        (response("https://downloads.example/dead.apk", b""), "empty response"),
        (
            urllib.error.URLError(
                "failed https://user:password@example.test/file?token=secret"
            ),
            "token=REDACTED",
        ),
    ],
)
def test_failed_probe_preserves_actionable_reason(
    failure: Exception | HttpResponse, reason: str
) -> None:
    api = "https://api.github.com/repos/example/app/releases?per_page=100"
    dead = "https://downloads.example/dead.apk"
    http, _ = client(
        {
            api: [response(api, json.dumps([release("v1.2", dead)]).encode())],
            dead: [failure],
        }
    )
    result = verify_live({"single": (github_entry(),)}, http, probe_assets=True)
    assert reason in (result.entries[0].probes[0].failure_reason or "")
    assert reason in result.errors[0].message
    assert "password" not in json.dumps(asdict(result))
    assert "token=secret" not in json.dumps(asdict(result))


def test_dead_selected_release_is_not_rescued_by_reachable_older_release() -> None:
    api = "https://api.github.com/repos/example/app/releases?per_page=100"
    dead, old = (
        "https://downloads.example/dead.apk",
        "https://downloads.example/old.apk",
    )
    http, transport = client(
        {
            api: [
                response(
                    api,
                    json.dumps(
                        [
                            release("v2.0", dead),
                            release("v1.0", old, published_at="2026-08-01T00:00:00Z"),
                        ]
                    ).encode(),
                )
            ],
            dead: [urllib.error.URLError("dead")],
            old: [response(old, b"apk")],
        }
    )
    result = verify_live(
        {"single": (github_entry(settings={"fallbackToOlderReleases": True}),)},
        http,
        probe_assets=True,
    )
    assert not result.ok
    assert result.entries[0].resolution is not None
    assert result.entries[0].resolution.effective_version == "v2.0"
    assert old not in [request.full_url for request in transport.requests]


def test_nonnumeric_version_warning_only_live_result_succeeds() -> None:
    api, apk = (
        "https://api.github.com/repos/example/app/releases?per_page=100",
        "https://downloads.example/app.apk",
    )
    http, _ = client(
        {
            api: [response(api, json.dumps([release("rolling", apk)]).encode())],
            apk: [response(apk, b"apk")],
        }
    )
    result = verify_live({"single": (github_entry(),)}, http)
    assert result.ok and not result.errors
    assert [warning.code for warning in result.warnings] == ["github-version-format"]
    assert "rolling" in result.warnings[0].message


def test_seeded_package_id_cache_does_not_hide_dead_source(
    tmp_path, monkeypatch
) -> None:
    from omnipack.package_id import CacheEntry, PackageIdCache
    from omnipack.verify import run_verification

    config = tmp_path / "config"
    config.mkdir()
    for name, value in [
        ("deny.json", []),
        ("overlay.json", []),
        ("overlay.dual.json", []),
        ("composition.json", {"schemaVersion": 1, "candidates": [], "pins": []}),
        ("settings.json", {}),
        ("http.json", {"credentials": {}}),
    ]:
        (config / name).write_text(json.dumps(value))
    entry = github_entry()
    cache = PackageIdCache(config / "package-ids.json")
    cache.put(entry.raw["url"], CacheEntry(entry.entry_id, 42))
    before = cache.path.read_bytes()
    (tmp_path / "dist").mkdir()
    for variant in ("single", "dual"):
        (tmp_path / "dist" / f"{variant}-screen.json").write_text(
            json.dumps({"settings": {"categories": "{}"}, "apps": [entry.raw]})
        )
    api, dead = (
        "https://api.github.com/repos/example/app/releases?per_page=100",
        "https://downloads.example/dead.apk",
    )
    http, transport = client(
        {
            api: [response(api, json.dumps([release("v1.2", dead)]).encode())],
            dead: [urllib.error.URLError("dead"), urllib.error.URLError("dead")],
        }
    )
    monkeypatch.setattr("omnipack.live_http.LiveHttpClient", lambda *_, **__: http)
    result = run_verification(tmp_path, live=True, probe_assets=True)
    assert result["status"] == "failed"
    assert len(result["entries"]) == 2
    assert all(
        entry["errors"][0]["code"] == "candidate-probes-failed"
        for entry in result["entries"]
    )
    assert Counter(request.full_url for request in transport.requests)[dead] == 1
    assert cache.path.read_bytes() == before


def test_html_probes_preserve_headers_and_cache_each_header_configuration() -> None:
    page = "https://example.test/releases/"
    asset = page + "app-1.2.apk"
    entries = []
    for variant, agent in (("single", "Agent-One"), ("dual", "Agent-Two")):
        entry = html_entry(page, variant)
        entry.settings["requestHeader"] = [{"requestHeader": f"User-Agent: {agent}"}]
        entry.raw["additionalSettings"] = json.dumps(entry.settings)
        entries.append(entry)
    requests = []

    def transport(
        request: Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse:
        agent = request.get_header("User-agent")
        requests.append((request.full_url, agent))
        if agent not in {"Agent-One", "Agent-Two"}:
            raise HttpError("configured User-Agent required")
        body = b"apk" if request.full_url == asset else b'<a href="app-1.2.apk">APK</a>'
        return response(request.full_url, body)

    result = verify_live(
        {"single": (entries[0], entries[0]), "dual": (entries[1],)},
        HttpClient(HttpConfig({}), transport=transport),
        probe_assets=True,
    )
    assert result.ok
    assert len(result.entries) == 3
    assert requests == [
        (page, "Agent-One"),
        (asset, "Agent-One"),
        (page, "Agent-Two"),
        (asset, "Agent-Two"),
    ]
