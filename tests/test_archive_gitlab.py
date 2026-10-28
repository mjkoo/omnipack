from __future__ import annotations

import json
from typing import Any

import pytest

from omnipack.archive import Asset, NoReleaseError, UnreachableError
from omnipack.archive.gitlab import resolve_gitlab
from omnipack.http import DeadlineExceeded, HttpClient
from tests.http_support import RoutedTransport

PROJECT = "https://gitlab.com/api/v4/projects/group%2Fapp"
RELEASES = f"{PROJECT}/releases?per_page=100"


def gl_release(
    tag: str,
    *links: tuple[str, str],
    description: str = "",
    released: str = "2026-01-01T00:00:00Z",
) -> dict[str, Any]:
    return {
        "tag_name": tag,
        "name": f"Release {tag}",
        "description": description,
        "released_at": released,
        "assets": {
            "links": [
                {"name": name, "url": url, "direct_asset_url": url}
                for name, url in links
            ]
        },
    }


def entry(**settings: object) -> dict[str, Any]:
    return {
        "url": "https://gitlab.com/group/app",
        "overrideSource": "GitLab",
        "additionalSettings": json.dumps(settings),
    }


def resolve(
    answers: dict[str, Any], entry_: dict[str, Any] | None = None, **kwargs: Any
) -> tuple[Any, RoutedTransport]:
    transport = RoutedTransport({PROJECT: {"id": 77}} | answers)
    http = HttpClient(transport=transport, sleep=lambda _seconds: None)
    return resolve_gitlab(entry_ or entry(), http, **kwargs), transport


def test_releases_are_taken_in_the_order_gitlab_lists_them() -> None:
    apk = ("a.apk", "https://x.test/a.apk")
    releases = [gl_release("v1", apk), gl_release("v2", apk)]

    release, _ = resolve({RELEASES: releases})

    assert release.version == "v1"


def test_the_newest_release_resolves_with_its_asset_links_and_record() -> None:
    newest = gl_release(
        "v2",
        ("app-2.apk", "https://gitlab.com/group/app/-/releases/v2/downloads/app.apk"),
        ("app.tar.gz", "https://example.com/app.tar.gz"),
        description="Fixes",
    )

    release, transport = resolve({RELEASES: [newest, gl_release("v1")]})

    assert (release.version, release.tag, release.notes) == ("v2", "v2", "Fixes")
    assert release.date is not None and release.date.year == 2026
    assert release.raw_record == newest
    assert release.assets == (
        Asset(
            "app-2.apk", "https://gitlab.com/group/app/-/releases/v2/downloads/app.apk"
        ),
        Asset("app.tar.gz", "https://example.com/app.tar.gz"),
    )
    assert transport.requests[0].get_header("Referer") == "https://gitlab.com"


def test_an_apk_linked_only_from_the_description_is_an_asset() -> None:
    description = "Download [the app](/uploads/abc123/Aurora.apk) and [notes](/uploads/x/notes.txt)"
    uploaded = "https://gitlab.com/-/project/77/uploads/abc123/Aurora.apk"

    release, _ = resolve({RELEASES: [gl_release("v1", description=description)]})

    assert release.assets == (Asset("Aurora.apk", uploaded),)


def test_a_file_reached_by_link_and_description_is_listed_once() -> None:
    uploaded = "https://gitlab.com/-/project/77/uploads/abc123/Aurora.apk"
    release_json = gl_release(
        "v1",
        ("Aurora.apk", uploaded),
        description="[apk](/uploads/abc123/Aurora.apk)",
    )

    release, _ = resolve({RELEASES: [release_json]})

    assert release.assets == (Asset("Aurora.apk", uploaded),)


def test_a_description_upload_replaces_a_link_to_a_file_of_the_same_name() -> None:
    linked = "https://gitlab.com/group/app/uploads/abc123/Aurora.apk"
    uploaded = "https://gitlab.com/-/project/77/uploads/abc123/Aurora.apk"
    release_json = gl_release(
        "v1",
        ("Aurora.apk", linked),
        ("notes.txt", "https://x.test/notes.txt"),
        description="[apk](/uploads/abc123/Aurora.apk)",
    )

    release, _ = resolve({RELEASES: [release_json]})

    assert release.assets == (
        Asset("Aurora.apk", uploaded),
        Asset("notes.txt", "https://x.test/notes.txt"),
    )


def test_a_package_link_without_an_extension_counts_as_an_apk() -> None:
    link = {
        "name": "Android APK Install File",
        "url": "https://gitlab.com/group/app/-/releases/v1/downloads/apk",
        "link_type": "package",
    }
    release_json = gl_release("v1") | {"assets": {"links": [link]}}

    release, _ = resolve({RELEASES: [release_json]})

    assert release.assets == (Asset(link["name"], link["url"]),)


def test_a_job_artifact_link_is_fetched_raw() -> None:
    url = "https://gitlab.com/group/app/-/jobs/12/artifacts/file/app.apk"

    release, _ = resolve({RELEASES: [gl_release("v1", ("app.apk", url))]})

    assert release.assets == (
        Asset(
            "app.apk", "https://gitlab.com/group/app/-/jobs/12/artifacts/raw/app.apk"
        ),
    )


def test_only_the_newest_release_is_tried_without_fallback() -> None:
    releases = [gl_release("v2"), gl_release("v1", ("a.apk", "https://x.test/a.apk"))]

    with pytest.raises(NoReleaseError):
        resolve({RELEASES: releases})
    release, _ = resolve({RELEASES: releases}, entry(fallbackToOlderReleases=True))

    assert release.version == "v1"


def test_the_apk_filter_applies_after_the_release_is_chosen() -> None:
    releases = [
        gl_release("v2", ("a-x86.apk", "https://x.test/a-x86.apk")),
        gl_release("v1", ("a-arm64.apk", "https://x.test/a-arm64.apk")),
    ]
    settings = entry(fallbackToOlderReleases=True, apkFilterRegEx="arm64")

    with pytest.raises(NoReleaseError):
        resolve({RELEASES: releases}, settings)


def test_version_extraction_applies() -> None:
    releases = [gl_release("release-3.1", ("a.apk", "https://x.test/a.apk"))]

    release, _ = resolve(
        {RELEASES: releases},
        entry(versionExtractionRegEx=r"release-(.+)", matchGroupToUse="$1"),
    )

    assert (release.version, release.tag) == ("3.1", "release-3.1")


def test_no_releases_is_a_no_release_outcome() -> None:
    with pytest.raises(NoReleaseError):
        resolve({RELEASES: []})


@pytest.mark.parametrize("missing", [PROJECT, RELEASES])
def test_a_missing_project_is_unreachable(missing: str) -> None:
    with pytest.raises(UnreachableError):
        resolve({RELEASES: [], missing: 404})


def test_the_deadline_bounds_the_requests() -> None:
    transport = RoutedTransport({})
    http = HttpClient(transport=transport, clock=lambda: 10.0)

    with pytest.raises(DeadlineExceeded):
        resolve_gitlab(entry(), http, deadline=10.0)

    assert transport.requests == []
