"""Bounded GitHub transport for rolling-release metadata and binary assets."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from scripts.nightly_release import RELEASE_PATH, ReleaseAsset, ReleaseError

MAX_RELEASE_BYTES = 1_000_000
MAX_ASSET_BYTES = 10_000_000


class Readable(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...


class OpenedResponse(Readable, Protocol):
    def __enter__(self): ...
    def __exit__(self, *args: object) -> None: ...
    def getcode(self) -> int: ...
    def read(self, size: int = -1) -> bytes: ...
    @property
    def headers(self) -> Mapping[str, str]: ...


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


def _trusted_open(request: Request, *, timeout: float) -> OpenedResponse:
    return build_opener(_RejectRedirects()).open(request, timeout=timeout)


def _unsigned_open(request: Request, *, timeout: float) -> OpenedResponse:
    return build_opener().open(request, timeout=timeout)


class GitHubReleaseRemote:
    """Operate only on the fixed release through bounded, explicit requests."""

    def __init__(
        self,
        token: str,
        *,
        timeout: float = 30.0,
        retries: int = 2,
        trusted_opener: Callable[..., OpenedResponse] = _trusted_open,
        unsigned_opener: Callable[..., OpenedResponse] = _unsigned_open,
    ) -> None:
        if not token:
            raise ValueError("GitHub release synchronization requires a token")
        if retries < 0 or retries > 5:
            raise ValueError("release retries must be between zero and five")
        self.token = token
        self.timeout = timeout
        self.retries = retries
        self.trusted_opener = trusted_opener
        self.unsigned_opener = unsigned_opener

    def discover(self) -> object:
        status, _headers, body = self._request(
            "GET",
            f"https://api.github.com{RELEASE_PATH}",
            max_bytes=MAX_RELEASE_BYTES,
            retry=True,
        )
        if status != 200:
            raise ReleaseError(f"release discovery failed with status {status}")
        try:
            return json.loads(body)
        except (json.JSONDecodeError, UnicodeError) as error:
            raise ReleaseError("release discovery response is malformed") from error

    def update(self, release_id: int, *, title: str, body: str) -> None:
        payload = json.dumps({"name": title, "body": body}).encode()
        status, _, _ = self._request(
            "PATCH",
            f"https://api.github.com/repos/mjkoo/omnipack/releases/{release_id}",
            data=payload,
            content_type="application/json",
            max_bytes=MAX_RELEASE_BYTES,
        )
        if status != 200:
            raise ReleaseError(f"release update failed with status {status}")

    def delete_asset(self, asset: ReleaseAsset) -> None:
        status, _, _ = self._request(
            "DELETE",
            f"https://api.github.com/repos/mjkoo/omnipack/releases/assets/{asset.asset_id}",
            max_bytes=MAX_RELEASE_BYTES,
        )
        if status != 204:
            raise ReleaseError(f"asset deletion failed with status {status}")

    def upload_asset(self, release_id: int, name: str, content: bytes) -> None:
        if len(content) > MAX_ASSET_BYTES:
            raise ReleaseError("release asset exceeds byte limit")
        url = (
            f"https://uploads.github.com/repos/mjkoo/omnipack/releases/{release_id}/assets"
            f"?name={quote(name, safe='')}"
        )
        status, _, _ = self._request(
            "POST",
            url,
            data=content,
            content_type="application/octet-stream",
            max_bytes=MAX_RELEASE_BYTES,
        )
        if status != 201:
            raise ReleaseError(f"asset upload failed with status {status}")

    def download_asset(self, asset: ReleaseAsset) -> bytes:
        expected = f"https://api.github.com/repos/mjkoo/omnipack/releases/assets/{asset.asset_id}"
        status, headers, body = self._request(
            "GET",
            expected,
            accept="application/octet-stream",
            max_bytes=MAX_ASSET_BYTES,
            retry=True,
        )
        if status == 200:
            return body
        if status != 302:
            raise ReleaseError(f"asset download failed with status {status}")
        location = headers.get("Location") or headers.get("location")
        if not isinstance(location, str):
            raise ReleaseError("asset download redirect is missing")
        parsed = urlsplit(location)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ReleaseError("asset download redirect is unsafe")
        return self._unsigned_download(location)

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: bytes | None = None,
        content_type: str | None = None,
        accept: str = "application/vnd.github+json",
        max_bytes: int,
        retry: bool = False,
    ) -> tuple[int, Mapping[str, str], bytes]:
        host = urlsplit(url).hostname
        if host not in {"api.github.com", "uploads.github.com"}:
            raise ReleaseError("authenticated request target is not trusted")
        headers = {
            "Accept": accept,
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "omnipack-nightly-publisher",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if content_type:
            headers["Content-Type"] = content_type
        attempts = self.retries + 1 if retry else 1
        for attempt in range(attempts):
            request = Request(url, data=data, headers=headers, method=method)
            try:
                with self.trusted_opener(request, timeout=self.timeout) as response:
                    return (
                        response.getcode(),
                        dict(response.headers),
                        _bounded_read(response, max_bytes),
                    )
            except HTTPError as error:
                body = _bounded_read(error, max_bytes)
                if (
                    retry
                    and error.code in {500, 502, 503, 504}
                    and attempt + 1 < attempts
                ):
                    continue
                return error.code, dict(error.headers or {}), body
            except URLError as error:
                if retry and attempt + 1 < attempts:
                    continue
                raise OSError("GitHub release request failed") from error
        raise AssertionError("unreachable")

    def _unsigned_download(self, url: str) -> bytes:
        request = Request(url, headers={"User-Agent": "omnipack-nightly-publisher"})
        try:
            with self.unsigned_opener(request, timeout=self.timeout) as response:
                if response.getcode() != 200:
                    raise ReleaseError(
                        f"redirected asset download failed with status {response.getcode()}"
                    )
                return _bounded_read(response, MAX_ASSET_BYTES)
        except (HTTPError, URLError) as error:
            raise OSError("redirected asset download failed") from error


def _bounded_read(response: Readable, limit: int) -> bytes:
    body = response.read(limit + 1)
    if len(body) > limit:
        raise ReleaseError("release response exceeds byte limit")
    return body
