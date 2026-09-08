"""Polite, conditional HTTP policy for an explicitly requested live run."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import time
from collections.abc import Callable, Mapping
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from obtainium_pack.http import (
    METADATA_MAX_BYTES,
    PROBE_BYTES,
    HttpClient,
    HttpConfig,
    HttpError,
    HttpResponse,
    TransientHttpError,
    Transport,
    redact_url,
)

_CACHE_LIMIT = 256
_GITHUB_METADATA_PATH = re.compile(r"/repos/[^/]+/[^/]+/(?:releases|tags)\Z")
_RATE_LIMIT_STATUSES = frozenset({429})
_TRANSIENT_STATUSES = frozenset({408, 425, 500, 502, 503, 504})
_RETURNED_STATUSES = _RATE_LIMIT_STATUSES | _TRANSIENT_STATUSES | {304, 403}
_SAFE_CACHE_HEADERS = frozenset(
    {"accept", "x-github-api-version", "if-none-match", "if-modified-since"}
)


class LiveHttpClient(HttpClient):
    """HTTP client with per-host pacing, rate suppression, and validators."""

    def __init__(
        self,
        config: HttpConfig,
        *,
        cache_dir: str | Path,
        timeout: float = 30.0,
        minimum_interval: float = 2.0,
        max_server_wait: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        transport: Transport | None = None,
    ) -> None:
        if minimum_interval < 0 or max_server_wait < 0:
            raise ValueError("live HTTP wait bounds must be nonnegative")
        self.cache_dir = Path(cache_dir)
        self.minimum_interval = minimum_interval
        self.max_server_wait = max_server_wait
        self.clock = clock
        self.wall_clock = wall_clock
        self._last_request: dict[str, float] = {}
        self._retry_after: dict[str, float] = {}
        self._suppressed_hosts: set[str] = set()
        super().__init__(
            config,
            timeout=timeout,
            retries=0,
            sleep=sleep,
            transport=transport,
            request_gate=self._gate,
            returned_http_statuses=_RETURNED_STATUSES,
            response_hook=self._observe_response,
        )

    def get_metadata(
        self, url: str, *, headers: Mapping[str, str] | None = None
    ) -> HttpResponse:
        """Fetch metadata and conditionally revalidate bounded GitHub responses."""
        self._require_github_auth(url)
        cache = self._read_cache(url, headers)
        request_headers = dict(headers or {})
        if cache is not None:
            if cache.get("etag"):
                request_headers["If-None-Match"] = cache["etag"]
            if cache.get("last_modified"):
                request_headers["If-Modified-Since"] = cache["last_modified"]
        response = self._request_with_retries(
            lambda: super(LiveHttpClient, self).get_metadata(
                url, headers=request_headers
            )
        )
        if response.status == 304:
            if cache is None:
                raise HttpError(
                    f"request to {redact_url(url)} returned 304 without a valid cached response"
                )
            response = HttpResponse(response.url, 200, response.headers, cache["body"])
        elif response.status == 200:
            self._write_cache(url, headers, response)
        elif response.status in _RATE_LIMIT_STATUSES or _is_rate_limited(response):
            raise HttpError(
                f"host {self._host(response.url)} is rate limited for this run"
            )
        else:
            raise HttpError(
                f"request to {redact_url(url)} returned status {response.status}"
            )
        return response

    def probe(
        self, url: str, *, headers: Mapping[str, str] | None = None
    ) -> HttpResponse:
        """Probe an asset when the caller explicitly opts in."""
        probe_headers = dict(headers or {})
        probe_headers["Range"] = f"bytes=0-{PROBE_BYTES - 1}"
        response = self._request_with_retries(
            lambda: self._request(
                url,
                headers=probe_headers,
                max_bytes=PROBE_BYTES,
                prefix=self.transport == self._urllib_transport,
            )
        )
        if response.status not in {200, 206}:
            raise HttpError(
                f"probe of {redact_url(response.url)} returned status {response.status}"
            )
        if not response.body:
            raise HttpError(
                f"probe of {redact_url(response.url)} returned an empty response"
            )
        return response

    def _request_with_retries(
        self, request: Callable[[], HttpResponse]
    ) -> HttpResponse:
        for attempt in range(3):
            try:
                response = request()
            except TransientHttpError as error:
                if attempt == 2:
                    raise TransientHttpError(error.url, attempt + 1) from error
                continue
            if response.status not in _TRANSIENT_STATUSES:
                return response
            wait = _server_wait(response, self.wall_clock())
            if wait is not None and wait > self.max_server_wait:
                host = self._host(response.url)
                self._suppressed_hosts.add(host)
                raise HttpError(f"host {host} is rate limited for this run")
            if wait is not None:
                self._retry_after[self._host(response.url)] = self.clock() + wait
            if attempt == 2:
                raise HttpError(
                    f"request to {redact_url(response.url)} returned status "
                    f"{response.status} after {attempt + 1} attempts"
                )
        raise AssertionError("live request loop did not return or raise")

    def _require_github_auth(self, url: str) -> None:
        if self._host(url) != "api.github.com":
            return
        variable = self.config.credentials.get("api.github.com")
        if not variable or not os.environ.get(variable):
            raise HttpError(
                "authenticated GitHub metadata requires a configured, nonempty "
                "credential for api.github.com"
            )

    def _gate(self, url: str) -> None:
        self._require_github_auth(url)
        host = self._host(url)
        if host in self._suppressed_hosts:
            raise HttpError(f"requests to rate-limited host {host} are suppressed")
        now = self.clock()
        last = self._last_request.get(host)
        next_request = self._retry_after.get(host, now)
        if last is not None:
            next_request = max(next_request, last + self.minimum_interval)
        delay = next_request - now
        if delay > 0:
            self.sleep(delay)
        self._last_request[host] = self.clock()

    def _observe_response(self, response: HttpResponse) -> None:
        if response.status in _RATE_LIMIT_STATUSES or _is_rate_limited(response):
            self._suppressed_hosts.add(self._host(response.url))

    def _read_cache(
        self, url: str, headers: Mapping[str, str] | None
    ) -> dict[str, Any] | None:
        if not _is_cacheable_github_metadata(url):
            return None
        path = self._cache_path(url, headers)
        try:
            if path.stat().st_size > (METADATA_MAX_BYTES * 4 // 3) + 4096:
                return None
            value = json.loads(path.read_text(encoding="utf-8"))
            expected_headers = [list(item) for item in _safe_headers(headers)]
            if (
                not isinstance(value, dict)
                or value.get("version") != 1
                or value.get("url") != url
                or value.get("headers") != expected_headers
                or not isinstance(value.get("body"), str)
                or not isinstance(value.get("etag"), (str, type(None)))
                or not isinstance(value.get("last_modified"), (str, type(None)))
                or not (value.get("etag") or value.get("last_modified"))
            ):
                return None
            body = base64.b64decode(value["body"], validate=True)
            if len(body) > METADATA_MAX_BYTES:
                return None
        except OSError, ValueError, TypeError, json.JSONDecodeError:
            return None
        value["body"] = body
        return value

    def _write_cache(
        self,
        url: str,
        headers: Mapping[str, str] | None,
        response: HttpResponse,
    ) -> None:
        if not _is_cacheable_github_metadata(url):
            return
        etag = response.headers.get("ETag")
        last_modified = response.headers.get("Last-Modified")
        if not etag and not last_modified:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            path = self._cache_path(url, headers)
            document = {
                "version": 1,
                "url": url,
                "headers": list(_safe_headers(headers)),
                "etag": etag,
                "last_modified": last_modified,
                "body": base64.b64encode(response.body).decode("ascii"),
            }
            temporary = path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(document, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            temporary.replace(path)
            cached = sorted(
                self.cache_dir.glob("*.json"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
            for stale in cached[_CACHE_LIMIT:]:
                stale.unlink(missing_ok=True)
        except OSError:
            return

    def _cache_path(self, url: str, headers: Mapping[str, str] | None) -> Path:
        encoded = json.dumps(
            [url, list(_safe_headers(headers))], separators=(",", ":")
        ).encode()
        return self.cache_dir / f"{hashlib.sha256(encoded).hexdigest()}.json"

    @staticmethod
    def _host(url: str) -> str:
        return (urlsplit(url).hostname or "").lower()


def _safe_headers(headers: Mapping[str, str] | None) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (name.lower(), value)
            for name, value in (headers or {}).items()
            if name.lower() in _SAFE_CACHE_HEADERS
            and not name.lower().startswith("if-")
        )
    )


def _is_cacheable_github_metadata(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "api.github.com"
        and parsed.username is None
        and parsed.password is None
        and _GITHUB_METADATA_PATH.fullmatch(parsed.path) is not None
        and parse_qsl(parsed.query, keep_blank_values=True) == [("per_page", "100")]
    )


def _is_rate_limited(response: HttpResponse) -> bool:
    return response.headers.get("X-RateLimit-Remaining") == "0" or (
        response.status == 403 and response.headers.get("Retry-After") is not None
    )


def _server_wait(response: HttpResponse, now: float) -> float | None:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return _finite_delay(float(retry_after))
        except ValueError:
            try:
                return _finite_delay(
                    parsedate_to_datetime(retry_after).timestamp() - now
                )
            except TypeError, ValueError, OverflowError:
                return None
    reset = response.headers.get("X-RateLimit-Reset")
    if reset:
        try:
            return _finite_delay(float(reset) - now)
        except ValueError:
            return None
    return None


def _finite_delay(value: float) -> float | None:
    if not math.isfinite(value):
        return None
    return max(0.0, value)
