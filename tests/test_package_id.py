from __future__ import annotations

import http.client
import json
import struct
import urllib.error
import urllib.request
import zipfile
from collections.abc import Mapping
from email.message import Message
from io import BytesIO
from pathlib import Path
from urllib.request import Request
from urllib.response import addinfourl

import pytest

from obtainium_pack.http import HttpClient, HttpConfig, HttpError, HttpResponse
from obtainium_pack.package_id import (
    MAX_APK_FULL_DOWNLOAD,
    CacheEntry,
    PackageIdCache,
    PackageIdResolver,
    ResolutionStatus,
    generated_project_entry,
)

PROJECT = "https://github.com/OWNER/REPO"
API = "https://api.github.com/repos/OWNER/REPO/releases/latest"
ASSET = "https://objects.example/app.apk"


def axml(package_id: str) -> bytes:
    strings = ["manifest", "package", package_id]
    encoded = b""
    offsets = []
    for value in strings:
        offsets.append(len(encoded))
        raw = value.encode("utf-16-le")
        encoded += struct.pack("<H", len(value)) + raw + b"\0\0"
    header_size = 28
    pool_size = header_size + 4 * len(strings) + len(encoded)
    pool_size = (pool_size + 3) & ~3
    pool = (
        struct.pack(
            "<HHI5I",
            1,
            header_size,
            pool_size,
            len(strings),
            0,
            0,
            header_size + 4 * len(strings),
            0,
        )
        + b"".join(struct.pack("<I", item) for item in offsets)
        + encoded
    )
    pool += b"\0" * (pool_size - len(pool))
    start = bytearray(56)
    struct.pack_into("<HHI", start, 0, 0x0102, 16, 56)
    struct.pack_into("<HHH", start, 24, 20, 20, 1)
    struct.pack_into("<III", start, 36, 0xFFFFFFFF, 1, 0xFFFFFFFF)
    struct.pack_into("<HBBI", start, 48, 8, 0, 3, 2)
    result = bytearray(8) + pool + start
    struct.pack_into("<HHI", result, 0, 3, 8, len(result))
    return bytes(result)


def apk(package_id: str) -> bytes:
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("AndroidManifest.xml", axml(package_id))
    return stream.getvalue()


def response(
    url: str, body: bytes = b"", status: int = 200, **headers: str
) -> HttpResponse:
    message = Message()
    for name, value in headers.items():
        message[name.replace("_", "-")] = value
    return HttpResponse(url, status, message, body)


class ReleaseTransport:
    def __init__(
        self, release: object, assets: Mapping[str, bytes | Exception]
    ) -> None:
        self.release = release
        self.assets = dict(assets)
        self.requests: list[tuple[Request, int | None]] = []

    def __call__(
        self, request: Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse:
        self.requests.append((request, max_bytes))
        if request.full_url == API:
            if isinstance(self.release, Exception):
                raise self.release
            return response(API, json.dumps(self.release).encode())
        value = self.assets[request.full_url]
        if isinstance(value, Exception):
            raise value
        if request.method == "HEAD":
            return response(
                request.full_url, Content_Length=str(len(value)), Accept_Ranges="bytes"
            )
        range_header = request.get_header("Range")
        body, status = value, 200
        if range_header:
            start, end = map(int, range_header.removeprefix("bytes=").split("-"))
            body, status = value[start : end + 1], 206
        if max_bytes is not None and len(body) > max_bytes:
            raise HttpError(f"response exceeds {max_bytes} bytes")
        return response(request.full_url, body, status)


def release(
    identifier: str | int | None, names: list[tuple[str, str]]
) -> dict[str, object]:
    return {
        "id": identifier,
        "tag_name": "rolling",
        "assets": [{"name": name, "browser_download_url": url} for name, url in names],
    }


def resolver(tmp_path: Path, transport: ReleaseTransport) -> PackageIdResolver:
    return PackageIdResolver(
        HttpClient(HttpConfig({}), retries=0, transport=transport),
        PackageIdCache(tmp_path / "ids.json"),
    )


def seed(path: Path, release_id: str | int = 1) -> None:
    PackageIdCache(path).put(PROJECT, CacheEntry("org.cached.app", release_id))


def test_fixture_apk_tail_resolves_package_id(tmp_path: Path) -> None:
    transport = ReleaseTransport(
        release(2, [("app.apk", ASSET)]), {ASSET: apk("org.example.app")}
    )
    result = resolver(tmp_path, transport).resolve(PROJECT)
    assert result.package_id == "org.example.app"
    assert result.status is ResolutionStatus.RESOLVED
    assert any(request.get_header("Range") for request, _ in transport.requests)


def test_matching_release_id_reuses_cache_without_asset_read(tmp_path: Path) -> None:
    path = tmp_path / "ids.json"
    seed(path, 7)
    transport = ReleaseTransport(
        release(7, [("app.apk", ASSET)]), {ASSET: apk("org.new.app")}
    )
    result = PackageIdResolver(
        HttpClient(HttpConfig({}), retries=0, transport=transport), PackageIdCache(path)
    ).resolve(PROJECT)
    assert result.package_id == "org.cached.app"
    assert [request.full_url for request, _ in transport.requests] == [API]


def test_new_host_id_under_same_tag_reresolves_and_persists_immediately(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ids.json"
    seed(path, 1)
    transport = ReleaseTransport(
        release(2, [("app.apk", ASSET)]), {ASSET: apk("org.new.app")}
    )
    result = PackageIdResolver(
        HttpClient(HttpConfig({}), retries=0, transport=transport), PackageIdCache(path)
    ).resolve(PROJECT)
    assert result.package_id == "org.new.app"
    assert json.loads(path.read_text())["github.com/owner/repo"] == {
        "packageId": "org.new.app",
        "releaseId": 2,
    }


@pytest.mark.parametrize(
    "spelling",
    ["http://github.com/owner/repo", "https://www.github.com/owner/repo.git/"],
)
def test_equivalent_project_spelling_hits_cache(tmp_path: Path, spelling: str) -> None:
    path = tmp_path / "ids.json"
    seed(path, "stable")
    transport = ReleaseTransport(
        release("stable", [("app.apk", ASSET)]), {ASSET: apk("org.new.app")}
    )
    result = PackageIdResolver(
        HttpClient(HttpConfig({}), retries=0, transport=transport), PackageIdCache(path)
    ).resolve(spelling)
    assert result.package_id == "org.cached.app"
    assert len(transport.requests) == 1


@pytest.mark.parametrize("identifier", [None, True, [], {}])
def test_missing_release_identifier_falls_back_or_is_unresolved(
    tmp_path: Path, identifier: object
) -> None:
    release_data = release(None, [])
    release_data["id"] = identifier
    with_cache = tmp_path / "cached.json"
    seed(with_cache, "old")
    cached_result = PackageIdResolver(
        HttpClient(
            HttpConfig({}), retries=0, transport=ReleaseTransport(release_data, {})
        ),
        PackageIdCache(with_cache),
    ).resolve(PROJECT)
    empty_result = resolver(
        tmp_path / "empty", ReleaseTransport(release_data, {})
    ).resolve(PROJECT)
    assert cached_result.package_id == "org.cached.app" and cached_result.failure
    assert empty_result.status is ResolutionStatus.UNRESOLVED and empty_result.failure


@pytest.mark.parametrize(
    ("names", "assets", "failure"),
    [
        ([("notes.zip", ASSET)], {}, "no eligible"),
        (
            [("one.apk", ASSET), ("two.APK", ASSET + "2")],
            {ASSET: apk("org.one.app"), ASSET + "2": apk("org.two.app")},
            "different",
        ),
        (
            [("one.apk", ASSET), ("two.apk", ASSET + "2")],
            {ASSET: apk("org.same.app"), ASSET + "2": b"bad"},
            "cannot read",
        ),
        (
            [("one.apk", ASSET), ("two.apk", ASSET + "2")],
            {ASSET: apk("org.same.app"), ASSET + "2": urllib.error.URLError("down")},
            "cannot read",
        ),
    ],
)
def test_asset_failures_reuse_cache_and_retry_unchanged_release(
    tmp_path: Path,
    names: list[tuple[str, str]],
    assets: dict[str, bytes | Exception],
    failure: str,
) -> None:
    path = tmp_path / "ids.json"
    seed(path, 1)
    transport = ReleaseTransport(release(2, names), assets)
    package_resolver = PackageIdResolver(
        HttpClient(HttpConfig({}), retries=0, transport=transport), PackageIdCache(path)
    )
    first = package_resolver.resolve(PROJECT)
    second = package_resolver.resolve(PROJECT)
    assert first.package_id == second.package_id == "org.cached.app"
    assert failure in (first.failure or "")
    assert json.loads(path.read_text())["github.com/owner/repo"]["releaseId"] == 1
    assert sum(request.full_url == API for request, _ in transport.requests) == 2


def test_all_eligible_apk_extensions_resolve_and_non_apk_is_ignored(
    tmp_path: Path,
) -> None:
    assets = {ASSET: apk("org.same.app"), ASSET + "2": apk("org.same.app")}
    data = release(
        "new",
        [("one.apk", ASSET), ("two.APK", ASSET + "2"), ("bundle.xapk", "ignored")],
    )
    result = resolver(tmp_path, ReleaseTransport(data, assets)).resolve(PROJECT)
    assert result.package_id == "org.same.app"


@pytest.mark.parametrize(
    "names,assets",
    [
        ([("notes.zip", ASSET)], {}),
        (
            [("one.apk", ASSET), ("two.apk", ASSET + "2")],
            {ASSET: apk("org.one.app"), ASSET + "2": apk("org.two.app")},
        ),
        ([("app.apk", ASSET)], {ASSET: b"not a zip"}),
    ],
)
def test_generated_project_never_uses_placeholder(
    tmp_path: Path, names: list[tuple[str, str]], assets: dict[str, bytes | Exception]
) -> None:
    result = generated_project_entry(
        PROJECT, resolver(tmp_path, ReleaseTransport(release(2, names), assets))
    )
    assert result.app is None
    assert result.resolution.status is ResolutionStatus.UNRESOLVED
    assert result.resolution.failure


@pytest.mark.parametrize(
    "names,assets",
    [
        ([], {}),
        (
            [("one.apk", ASSET), ("two.apk", ASSET + "2")],
            {ASSET: apk("org.one.app"), ASSET + "2": apk("org.two.app")},
        ),
        ([("app.apk", ASSET)], {ASSET: b"not a zip"}),
    ],
)
def test_generated_project_uses_cached_id_and_author_on_failed_refresh(
    tmp_path: Path,
    names: list[tuple[str, str]],
    assets: dict[str, bytes | Exception],
) -> None:
    path = tmp_path / "ids.json"
    seed(path)
    package_resolver = PackageIdResolver(
        HttpClient(
            HttpConfig({}),
            retries=0,
            transport=ReleaseTransport(release(2, names), assets),
        ),
        PackageIdCache(path),
    )
    result = generated_project_entry(PROJECT, package_resolver)
    assert result.app is not None
    assert result.app.id == "org.cached.app"
    assert result.app.name == "REPO"
    assert result.app.categories == ()
    assert result.app.raw["author"] == "OWNER"
    assert result.resolution.failure


def test_ignored_range_response_uses_bounded_full_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class IgnoreRange(ReleaseTransport):
        def __call__(
            self, request: Request, timeout: float, max_bytes: int | None
        ) -> HttpResponse:
            if request.get_header("Range"):
                self.requests.append((request, max_bytes))
                value = self.assets[request.full_url]
                assert isinstance(value, bytes)
                return response(request.full_url, value, 200)
            return super().__call__(request, timeout, max_bytes)

    monkeypatch.setenv("GITHUB_TOKEN", "fixture-token")
    transport = IgnoreRange(
        release(2, [("app.apk", ASSET)]), {ASSET: apk("org.example.app")}
    )
    package_resolver = PackageIdResolver(
        HttpClient(
            HttpConfig.from_path("config/http.json"), retries=0, transport=transport
        ),
        PackageIdCache(tmp_path / "ids.json"),
    )
    result = package_resolver.resolve(PROJECT)
    assert result.package_id == "org.example.app"
    assert any(
        max_bytes == MAX_APK_FULL_DOWNLOAD for _, max_bytes in transport.requests
    )
    assert all(
        request.get_header("Authorization") is None
        for request, _ in transport.requests
        if request.full_url == ASSET
    )


@pytest.mark.parametrize("token", [None, ""])
def test_cold_cache_default_http_config_resolves_without_optional_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, token: str | None
) -> None:
    if token is None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    else:
        monkeypatch.setenv("GITHUB_TOKEN", token)
    transport = ReleaseTransport(
        release(2, [("app.apk", ASSET)]), {ASSET: apk("org.example.app")}
    )
    http = HttpClient(
        HttpConfig.from_path("config/http.json"), retries=0, transport=transport
    )
    result = generated_project_entry(
        PROJECT, PackageIdResolver(http, PackageIdCache(tmp_path / "ids.json"))
    )
    assert result.app is not None
    assert all(
        request.get_header("Authorization") is None for request, _ in transport.requests
    )


def test_cold_cache_credential_reaches_only_api_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fixture-token")
    transport = ReleaseTransport(
        release(2, [("app.apk", ASSET)]), {ASSET: apk("org.example.app")}
    )
    http = HttpClient(
        HttpConfig.from_path("config/http.json"), retries=0, transport=transport
    )
    result = generated_project_entry(
        PROJECT, PackageIdResolver(http, PackageIdCache(tmp_path / "ids.json"))
    )
    assert result.app is not None
    api_request = next(
        request for request, _ in transport.requests if request.full_url == API
    )
    assert api_request.get_header("Authorization") == "Bearer fixture-token"
    assert all(
        request.get_header("Authorization") is None
        for request, _ in transport.requests
        if request.full_url != API
    )


def test_cold_cache_integration_covers_redirect_ranges_and_full_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise resolver and urllib helper together, replacing only HTTPS I/O."""
    monkeypatch.setenv("GITHUB_TOKEN", "fixture-token")
    ranged_url = "https://assets.example/ranged.apk"
    full_url = "https://downloads.example/full.apk"
    release_url = "https://fixtures.example/release.json"
    archives = {ranged_url: apk("org.example.app"), full_url: apk("org.example.app")}
    requests: list[Request] = []

    class FixtureResponse(addinfourl):
        msg = "fixture response"

    def fixture_response(
        request: Request, body: bytes, status: int, headers: Message
    ) -> FixtureResponse:
        return FixtureResponse(BytesIO(body), headers, request.full_url, status)

    def open_fixture(
        handler: urllib.request.HTTPSHandler, request: Request
    ) -> FixtureResponse:
        requests.append(request)
        headers = Message()
        if request.full_url == API:
            headers["Location"] = release_url
            return fixture_response(request, b"", 302, headers)
        if request.full_url == release_url:
            body = json.dumps(
                release(9, [("ranged.APK", ranged_url), ("full.apk", full_url)])
            ).encode()
            return fixture_response(request, body, 200, headers)
        if request.full_url in {
            "https://github.com/OWNER/REPO",
            "https://raw.githubusercontent.com/OWNER/REPO/main/catalog.json",
            "https://codeberg.org/owner/repo/releases",
        }:
            return fixture_response(request, b"fixture", 200, headers)
        archive = archives[request.full_url]
        if request.method == "HEAD":
            headers["Content-Length"] = str(len(archive))
            headers["Accept-Ranges"] = "bytes"
            return fixture_response(request, b"", 200, headers)
        byte_range = request.get_header("Range")
        if byte_range and request.full_url == ranged_url:
            start, end = map(int, byte_range.removeprefix("bytes=").split("-"))
            return fixture_response(request, archive[start : end + 1], 206, headers)
        return fixture_response(request, archive, 200, headers)

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)
    http = HttpClient(HttpConfig.from_path("config/http.json"), retries=0)
    result = generated_project_entry(
        PROJECT, PackageIdResolver(http, PackageIdCache(tmp_path / "ids.json"))
    )
    for url in (
        "https://github.com/OWNER/REPO",
        "https://raw.githubusercontent.com/OWNER/REPO/main/catalog.json",
        "https://codeberg.org/owner/repo/releases",
    ):
        http.get(url)

    assert result.app is not None and result.app.id == "org.example.app"
    assert requests[0].full_url == API
    assert requests[0].get_header("Authorization") == "Bearer fixture-token"
    release_request = next(
        request for request in requests if request.full_url == release_url
    )
    assert release_request.get_header("Authorization") is None
    assert any(
        request.full_url == ranged_url and request.get_header("Range")
        for request in requests
    )
    assert any(
        request.full_url == full_url and request.get_header("Range")
        for request in requests
    )
    assert any(
        request.full_url == full_url
        and request.method == "GET"
        and request.get_header("Range") is None
        for request in requests
    )
    assert all(
        request.get_header("Authorization") is None
        for request in requests
        if request.full_url != API
    )


def test_release_fetch_failure_preserves_cache_and_retries(tmp_path: Path) -> None:
    path = tmp_path / "ids.json"
    seed(path, 1)
    transport = ReleaseTransport(urllib.error.URLError("down"), {})
    package_resolver = PackageIdResolver(
        HttpClient(HttpConfig({}), retries=0, transport=transport), PackageIdCache(path)
    )
    first = package_resolver.resolve(PROJECT)
    second = package_resolver.resolve(PROJECT)
    assert first.package_id == second.package_id == "org.cached.app"
    assert first.failure and second.failure
    assert json.loads(path.read_text())["github.com/owner/repo"]["releaseId"] == 1


def test_cache_write_failure_aborts_successful_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "ids.json"
    transport = ReleaseTransport(
        release(2, [("app.apk", ASSET)]), {ASSET: apk("org.example.app")}
    )
    package_resolver = PackageIdResolver(
        HttpClient(HttpConfig({}), retries=0, transport=transport),
        PackageIdCache(cache_path),
    )

    def fail_replace(source: Path, target: Path) -> Path:
        raise OSError(f"cannot replace {target} from {source}")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError):
        package_resolver.resolve(PROJECT)


def malformed_manifest(encoding: str) -> bytes:
    # A two-unit length prefix ends before its continuation unit.
    raw = b"\x80" if encoding == "utf8" else b"\x00\x80"
    pool = (
        struct.pack(
            "<HHI5II",
            1,
            28,
            32 + len(raw),
            1,
            0,
            256 if encoding == "utf8" else 0,
            32,
            0,
            0,
        )
        + raw
    )
    manifest = struct.pack("<HHI", 3, 8, 8 + len(pool)) + pool
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("AndroidManifest.xml", manifest)
    return stream.getvalue()


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize(
    "body",
    [malformed_manifest("utf8"), malformed_manifest("utf16"), b"PK\x05\x06"],
    ids=["utf8-length", "utf16-length", "truncated-zip"],
)
def test_malformed_apk_is_reported_without_losing_cached_entry(
    tmp_path: Path, cached: bool, body: bytes
) -> None:
    path = tmp_path / "ids.json"
    if cached:
        seed(path)
    transport = ReleaseTransport(release(2, [("app.apk", ASSET)]), {ASSET: body})
    package_resolver = resolver(tmp_path, transport)
    result = generated_project_entry(PROJECT, package_resolver)
    assert result.resolution.failure
    if cached:
        assert result.app is not None and result.app.id == "org.cached.app"
        assert PackageIdCache(path).get(PROJECT) == CacheEntry("org.cached.app", 1)
        transport.assets[ASSET] = apk("org.recovered.app")
        retried = generated_project_entry(PROJECT, package_resolver)
        assert retried.app is not None and retried.app.id == "org.recovered.app"
        assert PackageIdCache(path).get(PROJECT) == CacheEntry("org.recovered.app", 2)
    else:
        assert result.app is None
        assert result.resolution.status is ResolutionStatus.UNRESOLVED
        assert not path.exists()


def test_uncached_asset_fetch_failure_omits_generated_entry(tmp_path: Path) -> None:
    transport = ReleaseTransport(
        release(2, [("app.apk", ASSET)]), {ASSET: urllib.error.URLError("offline")}
    )
    result = generated_project_entry(PROJECT, resolver(tmp_path, transport))
    assert result.app is None
    assert result.resolution.status is ResolutionStatus.UNRESOLVED
    assert "cannot read eligible APK" in (result.resolution.failure or "")
    assert not (tmp_path / "ids.json").exists()


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("failure", ["truncated", "oserror"])
def test_http_body_failure_is_reported_and_retried_without_losing_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cached: bool, failure: str
) -> None:
    path = tmp_path / "ids.json"
    if cached:
        seed(path)
    requests: list[Request] = []
    sleeps: list[float] = []

    class BrokenBody(BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            raise OSError("body read failed")

    class FixtureResponse(addinfourl):
        msg = "fixture response"

    class Socket:
        def makefile(self, mode: str) -> BytesIO:
            return BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\nshort!")

    def open_fixture(handler: urllib.request.HTTPSHandler, request: Request):
        requests.append(request)
        if failure == "oserror":
            headers = Message()
            return FixtureResponse(BrokenBody(), headers, request.full_url, 200)
        stream = http.client.HTTPResponse(Socket())  # ty: ignore[invalid-argument-type]
        stream.begin()
        stream.url = request.full_url
        return stream

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)
    package_resolver = PackageIdResolver(
        HttpClient(HttpConfig({}), retries=1, sleep=sleeps.append), PackageIdCache(path)
    )
    for _ in range(2):
        result = generated_project_entry(PROJECT, package_resolver)
        assert "failed after 2 attempts" in (result.resolution.failure or "")
        if cached:
            assert result.app is not None and result.app.id == "org.cached.app"
            assert PackageIdCache(path).get(PROJECT) == CacheEntry("org.cached.app", 1)
        else:
            assert result.app is None
            assert result.resolution.status is ResolutionStatus.UNRESOLVED
            assert not path.exists()
    assert len(requests) == 4
    assert sleeps == [0.5, 0.5]


@pytest.mark.parametrize("cached", [False, True])
def test_real_http_full_download_bound_retains_cache_or_omits_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cached: bool
) -> None:
    monkeypatch.setattr("obtainium_pack.package_id.MAX_APK_FULL_DOWNLOAD", 1024)
    path = tmp_path / "ids.json"
    if cached:
        seed(path)
    assets = {ASSET: apk("org.recovered.app"), ASSET + "2": b"x" * 1025}
    reads: list[int | None] = []
    requests: list[Request] = []

    class ObservedBody(BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            reads.append(size)
            return super().read(size)

    class FixtureResponse(addinfourl):
        msg = "fixture response"

    def open_fixture(handler: urllib.request.HTTPSHandler, request: Request):
        requests.append(request)
        if request.full_url == API:
            body = json.dumps(
                release(2, [("one.apk", ASSET), ("two.apk", ASSET + "2")])
            ).encode()
            stream = BytesIO(body)
        else:
            stream = ObservedBody(
                b"" if request.method == "HEAD" else assets[request.full_url]
            )
        return FixtureResponse(stream, Message(), request.full_url, 200)

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)
    package_resolver = PackageIdResolver(
        HttpClient(HttpConfig({}), retries=0), PackageIdCache(path)
    )
    for _ in range(2):
        result = generated_project_entry(PROJECT, package_resolver)
        assert "exceeds 1024 bytes" in (result.resolution.failure or "")
        if cached:
            assert result.app is not None and result.app.id == "org.cached.app"
            assert PackageIdCache(path).get(PROJECT) == CacheEntry("org.cached.app", 1)
        else:
            assert result.app is None
            assert result.resolution.status is ResolutionStatus.UNRESOLVED
            assert not path.exists()
    assert reads == [1, 1025, 1, 1025] * 2
    assert (
        sum(
            request.full_url == ASSET + "2" and request.method == "GET"
            for request in requests
        )
        == 2
    )
    assets[ASSET + "2"] = apk("org.recovered.app")
    retried = generated_project_entry(PROJECT, package_resolver)
    assert retried.app is not None and retried.app.id == "org.recovered.app"
    assert PackageIdCache(path).get(PROJECT) == CacheEntry("org.recovered.app", 2)
