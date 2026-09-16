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
from urllib.request import Request
from urllib.response import addinfourl

import pytest

from omnipack.http import HttpError, HttpResponse
from omnipack.package_id import resolve_release_assets
from omnipack.source_http import HttpConfig, SourceHttpClient

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
        manifest = zipfile.ZipInfo(
            "AndroidManifest.xml", date_time=(2026, 1, 1, 0, 0, 0)
        )
        manifest.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(manifest, axml(package_id))
    return stream.getvalue()


def response(
    url: str, body: bytes = b"", status: int = 200, **headers: str
) -> HttpResponse:
    message = Message()
    for name, value in headers.items():
        message[name.replace("_", "-")] = value
    return HttpResponse(url, status, message, body)


class AssetTransport:
    def __init__(self, assets: Mapping[str, bytes | Exception]) -> None:
        self.assets = dict(assets)
        self.requests: list[tuple[Request, int | None]] = []

    def __call__(
        self, request: Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse:
        self.requests.append((request, max_bytes))
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


def release(names: list[tuple[str, str]]) -> dict[str, object]:
    return {
        "assets": [{"name": name, "browser_download_url": url} for name, url in names]
    }


def client(
    transport: AssetTransport, config: HttpConfig | None = None
) -> SourceHttpClient:
    return SourceHttpClient(config or HttpConfig({}), retries=0, transport=transport)


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
def test_asset_failures_are_reported(
    names: list[tuple[str, str]],
    assets: dict[str, bytes | Exception],
    failure: str,
) -> None:
    with pytest.raises(ValueError, match=failure):
        resolve_release_assets(client(AssetTransport(assets)), release(names))


def test_all_eligible_apk_extensions_resolve_and_non_apk_is_ignored() -> None:
    assets = {ASSET: apk("org.same.app"), ASSET + "2": apk("org.same.app")}
    data = release(
        [("one.apk", ASSET), ("two.APK", ASSET + "2"), ("bundle.xapk", "ignored")]
    )
    assert resolve_release_assets(client(AssetTransport(assets)), data) == (
        "org.same.app"
    )


def test_integration_covers_redirect_ranges_and_full_fallback(
    monkeypatch: pytest.MonkeyPatch,
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
                release([("ranged.APK", ranged_url), ("full.apk", full_url)])
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
    http = SourceHttpClient(HttpConfig.from_path("config/http.json"), retries=0)
    listed = http.get(API, headers={"Accept": "application/vnd.github+json"}).json()
    package_id = resolve_release_assets(http, listed)
    for url in (
        "https://github.com/OWNER/REPO",
        "https://raw.githubusercontent.com/OWNER/REPO/main/catalog.json",
        "https://codeberg.org/owner/repo/releases",
    ):
        http.get(url)

    assert package_id == "org.example.app"
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


@pytest.mark.parametrize(
    "body",
    [malformed_manifest("utf8"), malformed_manifest("utf16"), b"PK\x05\x06"],
    ids=["utf8-length", "utf16-length", "truncated-zip"],
)
def test_malformed_apk_is_reported(body: bytes) -> None:
    transport = AssetTransport({ASSET: body})
    with pytest.raises(ValueError, match="cannot read eligible APK"):
        resolve_release_assets(client(transport), release([("app.apk", ASSET)]))


@pytest.mark.parametrize("failure", ["truncated", "oserror"])
def test_http_body_failure_is_retried_then_reported(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    requests: list[Request] = []
    observed_sleeps: list[float] = []

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
            return FixtureResponse(BrokenBody(), Message(), request.full_url, 200)
        stream = http.client.HTTPResponse(
            Socket(),  # ty: ignore[invalid-argument-type]
            method=request.method,
        )
        stream.begin()
        stream.url = request.full_url
        return stream

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)
    http_client = SourceHttpClient(
        HttpConfig({}), retries=1, sleep=observed_sleeps.append
    )
    with pytest.raises(ValueError, match="failed after 2 attempts"):
        resolve_release_assets(http_client, release([("app.apk", ASSET)]))
    assert sum(request.method == "GET" for request in requests) >= 2
    assert observed_sleeps and all(delay > 0 for delay in observed_sleeps)


def test_real_http_full_download_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("omnipack.package_id.MAX_APK_FULL_DOWNLOAD", 1024)
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
        stream = ObservedBody(
            b"" if request.method == "HEAD" else assets[request.full_url]
        )
        return FixtureResponse(stream, Message(), request.full_url, 200)

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)
    http_client = SourceHttpClient(HttpConfig({}), retries=0)
    data = release([("one.apk", ASSET), ("two.apk", ASSET + "2")])
    with pytest.raises(ValueError, match="exceeds 1024 bytes"):
        resolve_release_assets(http_client, data)
    assert reads and all(size is not None and 0 < size <= 1025 for size in reads)
    assets[ASSET + "2"] = apk("org.recovered.app")
    assert resolve_release_assets(http_client, data) == "org.recovered.app"
