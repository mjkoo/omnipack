from __future__ import annotations

import json
from email.message import Message
from typing import Any

import pytest

from omnipack.http import HttpError, HttpResponse
from omnipack.resolution.gitlab import resolve_gitlab
from omnipack.resolution.types import ResolutionError
from omnipack.settings_defaults import SETTINGS_DEFAULTS


class FakeHttp:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get_metadata(self, url: str, *, headers: Any = None) -> HttpResponse:
        self.calls.append((url, dict(headers or {})))
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        status, document = value if isinstance(value, tuple) else (200, value)
        body = (
            document if isinstance(document, bytes) else json.dumps(document).encode()
        )
        return HttpResponse(url, status, Message(), body)


def app(**updates: object) -> dict[str, object]:
    settings = {
        **SETTINGS_DEFAULTS["GitLab"],
        "apkFilterRegEx": r"^AuroraStore-[0-9]+(?:\.[0-9]+)+\.apk$",
    }
    setting_updates = updates.pop("settings", {})
    assert isinstance(setting_updates, dict)
    settings.update(setting_updates)
    return {
        "id": "com.aurora.store",
        "url": "https://gitlab.com/AuroraOSS/Parent/AuroraStore",
        "additionalSettings": settings,
        **updates,
    }


def urls() -> tuple[str, str]:
    encoded = "AuroraOSS%2FParent%2FAuroraStore"
    return (
        f"https://gitlab.com/api/v4/projects/{encoded}",
        f"https://gitlab.com/api/v4/projects/{encoded}/releases?per_page=100",
    )


def release(tag: str = "4.8.4", description: str = "") -> dict[str, object]:
    return {
        "tag_name": tag,
        "description": description,
        "assets": {"links": []},
        "released_at": "2026-09-01T12:00:00Z",
    }


def test_description_uploads_use_numeric_project_route_and_filter_flavors() -> None:
    project_url, releases_url = urls()
    description = "\n".join(
        f"[download](/uploads/hash/AuroraStore-{suffix}.apk)"
        for suffix in ("4.8.4", "4.8.4-hw", "4.8.4-preload")
    )
    http = FakeHttp(
        {project_url: {"id": 777}, releases_url: [release(description=description)]}
    )
    result = resolve_gitlab(app(), http)
    assert [(item.name, item.url) for item in result.candidates] == [
        (
            "AuroraStore-4.8.4.apk",
            "https://gitlab.com/-/project/777/uploads/hash/AuroraStore-4.8.4.apk",
        )
    ]
    assert result.raw_version == result.effective_version == "4.8.4"
    assert result.inspected_count == 1 and result.window_limit == 100
    assert [call[0] for call in http.calls] == [project_url, releases_url]


def test_asset_links_and_description_uploads_are_combined() -> None:
    project_url, releases_url = urls()
    item = release(description="[b](/uploads/h/description.apk)")
    item["assets"] = {
        "links": [
            {"name": "direct.apk", "direct_asset_url": "https://cdn.test/direct.apk"}
        ]
    }
    result = resolve_gitlab(
        app(settings={"apkFilterRegEx": r"\.apk$"}),
        FakeHttp({project_url: {"id": 4}, releases_url: [item]}),
    )
    assert [candidate.name for candidate in result.candidates] == [
        "direct.apk",
        "description.apk",
    ]


@pytest.mark.parametrize("fallback,expected", [(False, "gitlab-no-apk"), (True, None)])
def test_older_release_fallback(fallback: bool, expected: str | None) -> None:
    project_url, releases_url = urls()
    older = release("4.8.3", "[x](/uploads/h/AuroraStore-4.8.3.apk)")
    http = FakeHttp({project_url: {"id": 9}, releases_url: [release(), older]})
    if expected:
        with pytest.raises(ResolutionError) as caught:
            resolve_gitlab(app(settings={"fallbackToOlderReleases": fallback}), http)
        assert caught.value.code == expected
    else:
        assert resolve_gitlab(app(), http).raw_version == "4.8.3"


@pytest.mark.parametrize(
    "responses,code",
    [
        ({"project": {}}, "gitlab-invalid-response"),
        ({"project": {"id": 1}, "releases": {}}, "gitlab-invalid-response"),
        ({"project": (429, {})}, "gitlab-request-failed"),
        ({"project": HttpError("rate limited")}, "gitlab-request-failed"),
    ],
)
def test_malformed_and_failed_requests(responses: dict[str, object], code: str) -> None:
    project_url, releases_url = urls()
    mapped = {project_url: responses["project"]}
    if "releases" in responses:
        mapped[releases_url] = responses["releases"]
    with pytest.raises(ResolutionError) as caught:
        resolve_gitlab(app(), FakeHttp(mapped))
    assert caught.value.code == code


@pytest.mark.parametrize(
    "setting,value",
    [
        ("includeZips", True),
        ("trackOnly", True),
        ("versionDetection", False),
        ("releaseDateAsVersion", True),
        ("invertAPKFilter", True),
    ],
)
def test_unsupported_active_setting_fails_before_http(
    setting: str, value: bool
) -> None:
    http = FakeHttp({})
    with pytest.raises(ResolutionError) as caught:
        resolve_gitlab(app(settings={setting: value}), http)
    assert caught.value.code == "unsupported-setting"
    assert setting in str(caught.value)
    assert http.calls == []


def test_release_window_is_bounded_to_first_hundred_records() -> None:
    project_url, releases_url = urls()
    records = [release(str(index)) for index in range(100)]
    records.append(release("too-old", "[x](/uploads/h/AuroraStore-4.8.4.apk)"))
    with pytest.raises(ResolutionError) as caught:
        resolve_gitlab(app(), FakeHttp({project_url: {"id": 1}, releases_url: records}))
    assert caught.value.code == "gitlab-no-apk"


@pytest.mark.parametrize("segments", [21, 22])
def test_gitlab_project_depth_boundary(segments: int) -> None:
    path = "/".join(f"Group{i}" for i in range(segments))
    project = "https://gitlab.com/api/v4/projects/" + path.replace("/", "%2F")
    releases = project + "/releases?per_page=100"
    http = FakeHttp(
        {
            project: {"id": 1},
            releases: [release(description="[apk](/uploads/h/AuroraStore-4.8.4.apk)")],
        }
    )
    value = app(url="https://gitlab.com/" + path)
    if segments == 22:
        with pytest.raises(ResolutionError) as caught:
            resolve_gitlab(value, http)
        assert caught.value.code == "gitlab-url-invalid"
        assert http.calls == []
    else:
        assert resolve_gitlab(value, http).raw_version == "4.8.4"
        assert [url for url, _ in http.calls] == [project, releases]


@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize(
    "malformed",
    [
        None,
        {},
        {"assets": None},
        {"assets": {"links": None}},
        {"assets": {"links": [None]}},
        {"assets": {"links": [{"name": "bad.apk", "url": 42}]}},
        {"description": 42},
        {"tag_name": None},
        {"tag_name": ""},
        {"tag_name": 42},
    ],
)
def test_malformed_inspected_release_never_falls_back(malformed, fallback):
    project_url, releases_url = urls()
    first = None if malformed is None else {**release(), **malformed}
    if malformed == {}:
        first = {
            "name": "presentation",
            "description": "[x](/uploads/h/AuroraStore-4.8.4.apk)",
            "assets": {"links": []},
        }
    older = release("4.8.3", "[x](/uploads/h/AuroraStore-4.8.3.apk)")
    with pytest.raises(ResolutionError) as caught:
        resolve_gitlab(
            app(settings={"fallbackToOlderReleases": fallback}),
            FakeHttp({project_url: {"id": 9}, releases_url: [first, older]}),
        )
    assert caught.value.code == "gitlab-invalid-response"
