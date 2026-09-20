from __future__ import annotations

import json
from email.message import Message
from http.client import IncompleteRead
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from omnipack.http import HttpResponse
from omnipack.source_generation import generate_codm
from omnipack.source_http import HttpConfig, SourceHttpClient
from tests.test_package_id import AssetTransport, apk
from tests.test_source_generation import MappingHttp, tracking_root
from tests.test_source_generation_boundaries import (
    API,
    ASSET,
    PROJECT,
    README,
    release,
    setup,
)

LIST_API = "https://api.github.com/repos/example/tracker/releases?per_page=100&page=1"


RELEASE_RULES = [
    pytest.param({}, API, False, id="stable"),
    pytest.param({"includePrereleases": True}, LIST_API, True, id="prerelease"),
    pytest.param({"filterReleaseTitlesByRegEx": "^v7$"}, LIST_API, False, id="title"),
]


def _release_body(endpoint: str, selected: dict[str, object]) -> bytes:
    return json.dumps(selected if endpoint == API else [selected]).encode()


@pytest.mark.parametrize(("settings", "endpoint", "prerelease"), RELEASE_RULES)
@pytest.mark.parametrize("retry", [False, True])
def test_generation_looks_up_only_the_rule_selected_release_endpoint(
    tmp_path: Path,
    settings: dict[str, object],
    endpoint: str,
    prerelease: bool,
    retry: bool,
) -> None:
    source = setup(tmp_path, {"kind": "apk", "additionalSettings": settings})
    selected = release(name="v7", prerelease=prerelease)
    transport = AssetTransport(
        {
            source: README,
            endpoint: _release_body(endpoint, selected),
            ASSET: apk("org.example.app"),
        }
    )
    release_requests: list[str] = []

    def fetch(request: Request, timeout: float, max_bytes: int | None) -> HttpResponse:
        if "/releases" in request.full_url:
            release_requests.append(request.full_url)
            if retry and len(release_requests) == 1:
                raise IncompleteRead(b"truncated", 20)
        return transport(request, timeout, max_bytes)

    http = SourceHttpClient(
        HttpConfig({}), transport=fetch, retries=1, sleep=lambda _: None
    )
    result = generate_codm(tmp_path, http=http)
    assert result["status"] == "success", result
    assert release_requests == [endpoint] * (2 if retry else 1)
    [entry] = json.loads(
        (tmp_path / ".build/source-generation/codm/catalog.json").read_bytes()
    )["apps"]
    assert entry["id"] == "org.example.app"
    rendered_settings = json.loads(entry["additionalSettings"])
    for key, value in settings.items():
        assert rendered_settings[key] == value


@pytest.mark.parametrize(("settings", "endpoint", "prerelease"), RELEASE_RULES)
def test_failed_release_lookup_never_asks_the_other_endpoint(
    tmp_path: Path, settings: dict[str, object], endpoint: str, prerelease: bool
) -> None:
    source = setup(tmp_path, {"kind": "apk", "additionalSettings": settings})
    other = LIST_API if endpoint == API else API
    transport = AssetTransport(
        {
            source: README,
            endpoint: HTTPError(endpoint, 404, "Not Found", Message(), None),
            other: _release_body(other, release(name="v7", prerelease=prerelease)),
            ASSET: apk("org.example.app"),
        }
    )
    http = SourceHttpClient(
        HttpConfig({}), transport=transport, retries=1, sleep=lambda _: None
    )
    result = generate_codm(tmp_path, http=http)
    assert result["status"] == "failed"
    assert [item["url"] for item in result["unresolved"]] == [PROJECT]
    assert [request.full_url for request, _ in transport.requests] == [
        source,
        endpoint,
    ]


@pytest.mark.parametrize(
    "setting", ["apkFilterRegEx", "versionExtractionRegEx", "matchGroupToUse"]
)
def test_track_only_apk_settings_fail_before_network_with_project_and_setting(
    tmp_path: Path, setting: str
) -> None:
    tracking_root(tmp_path)
    policy_path = tmp_path / "config/codm-projects.json"
    policy = json.loads(policy_path.read_text())
    policy["projects"][PROJECT]["additionalSettings"] = {setting: ""}
    policy_path.write_text(json.dumps(policy))
    http = MappingHttp({})
    result = generate_codm(tmp_path, http=http)
    assert result["status"] == "failed"
    assert PROJECT in result["error"]
    assert f"APK-only setting {setting!r}" in result["error"]
    assert http.urls == []


@pytest.mark.parametrize("setting", ["includePrereleases", "fallbackToOlderReleases"])
def test_track_only_release_settings_are_accepted_and_exported(
    tmp_path: Path, setting: str
) -> None:
    source, _ = tracking_root(tmp_path)
    policy_path = tmp_path / "config/codm-projects.json"
    policy = json.loads(policy_path.read_text())
    policy["projects"][PROJECT]["additionalSettings"] = {setting: True}
    policy_path.write_text(json.dumps(policy))
    selected = release(name="v7", prerelease=setting == "includePrereleases", assets=[])
    endpoint = LIST_API if setting == "includePrereleases" else API
    http = MappingHttp(
        {source: README, endpoint: [selected] if endpoint == LIST_API else selected}
    )
    result = generate_codm(tmp_path, http=http)
    assert result["status"] == "success", result
    assert http.urls == [source, endpoint]
    [entry] = json.loads(
        (tmp_path / ".build/source-generation/codm/catalog.json").read_bytes()
    )["apps"]
    settings = json.loads(entry["additionalSettings"])
    assert settings["trackOnly"] is True
    assert settings[setting] is True


def test_accepted_catalog_duplicate_normalized_project_fails_generation(
    tmp_path: Path,
) -> None:
    source, _ = tracking_root(tmp_path)
    entries = [
        {"id": str(index), "url": url}
        for index, url in enumerate(
            (
                "https://github.com/Example/Tracker",
                "http://www.github.com/example/tracker.git/",
            )
        )
    ]
    (tmp_path / "config/catalogs/codm.json").write_text(json.dumps({"apps": entries}))
    http = MappingHttp({source: README})
    result = generate_codm(tmp_path, http=http)
    assert result["status"] == "failed"
    assert result["error"] == f"accepted codm catalog has duplicate project {PROJECT}"
    assert http.urls == [source]
    assert not (tmp_path / ".build/source-generation/codm/catalog.json").exists()


@pytest.mark.parametrize(
    "document",
    [
        None,
        {"apps": {}},
        {"apps": [{"id": 123, "url": "https://github.com/a/b"}]},
        {"apps": [{"id": "123", "url": None}]},
    ],
)
def test_accepted_catalog_malformed_shape_fails_generation(
    tmp_path: Path, document: object
) -> None:
    source, _ = tracking_root(tmp_path)
    (tmp_path / "config/catalogs/codm.json").write_text(json.dumps(document))
    result = generate_codm(tmp_path, http=MappingHttp({source: README}))
    assert result["status"] == "failed"
    assert result["error"] == "accepted codm catalog is malformed"


def test_accepted_catalog_repeated_id_names_both_projects(tmp_path: Path) -> None:
    source, _ = tracking_root(tmp_path)
    urls = ["https://github.com/example/tracker", "https://github.com/example/other"]
    (tmp_path / "config/catalogs/codm.json").write_text(
        json.dumps({"apps": [{"id": "12345", "url": url} for url in urls]})
    )
    result = generate_codm(tmp_path, http=MappingHttp({source: README}))
    assert result["status"] == "failed"
    assert (
        result["error"]
        == f"accepted codm catalog ID collision '12345' between {urls[0]} and {urls[1]}"
    )
