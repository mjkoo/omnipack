"""Plain retrying HTTP GET, and the request pieces every client shares.

The build fetches whole public catalogs, so `HttpClient` sends no credentials
and follows redirects with urllib's defaults. Source generation, which
authenticates and bounds its reads, uses `omnipack.source_http`, built on the
shared request, response and retry helpers here.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.message import Message
from http.client import HTTPException, IncompleteRead
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_FORBIDDEN_CALLER_HEADERS = frozenset({"authorization", "cookie"})


class HttpError(RuntimeError):
    """A request failed or exceeded a configured response bound."""


class TransientHttpError(HttpError):
    """A transient acquisition failure eligible for a caller-owned retry policy."""

    def __init__(self, url: str, attempts: int) -> None:
        self.url = url
        super().__init__(
            f"request to {redact_url(url)} failed after {attempts} attempts"
        )


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """The response data needed by catalog and APK consumers."""

    url: str
    status: int
    headers: Message
    body: bytes

    def json(self) -> Any:
        """Decode a JSON response body."""
        return json.loads(self.body)


class Transport(Protocol):
    def __call__(
        self, request: urllib.request.Request, timeout: float
    ) -> HttpResponse: ...


class RetryingClient:
    """Retry configuration and dispatch shared by every retrying HTTP client.

    A subclass owns its own `transport` attribute, since each accepts a
    differently shaped transport callable, and calls `_retry` from its `get`.
    """

    timeout: float
    user_agent: str
    retries: int
    backoff: float
    sleep: Callable[[float], None]

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        user_agent: str = "omnipack/0.1",
        retries: int = 2,
        backoff: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if retries < 0 or backoff < 0:
            raise ValueError("retries and backoff must be nonnegative")
        self.timeout = timeout
        self.user_agent = user_agent
        self.retries = retries
        self.backoff = backoff
        self.sleep = sleep

    def _retry(self, url: str, attempt: Callable[[], HttpResponse]) -> HttpResponse:
        return retrying(
            url,
            attempt,
            retries=self.retries,
            backoff=self.backoff,
            sleep=self.sleep,
        )


class HttpClient(RetryingClient):
    """Fetch public URLs with bounded transient retries and no credentials."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        user_agent: str = "omnipack/0.1",
        retries: int = 2,
        backoff: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
        transport: Transport | None = None,
    ) -> None:
        super().__init__(
            timeout=timeout,
            user_agent=user_agent,
            retries=retries,
            backoff=backoff,
            sleep=sleep,
        )
        self.transport = transport or self._urllib_transport

    def get(self, url: str) -> HttpResponse:
        """Fetch one URL, retrying transient failures up to the configured bound."""
        return self._retry(
            url,
            lambda: self.transport(
                build_request(url, user_agent=self.user_agent), self.timeout
            ),
        )

    def _urllib_transport(
        self, request: urllib.request.Request, timeout: float
    ) -> HttpResponse:
        with urllib.request.urlopen(request, timeout=timeout) as stream:
            return complete_response(stream, stream.read())


def build_request(
    url: str,
    *,
    user_agent: str,
    headers: Mapping[str, str] | None = None,
    method: str = "GET",
) -> urllib.request.Request:
    """Build a request that carries neither URL nor caller-supplied credentials."""
    parsed = urlsplit(url)
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("embedded URL credentials are not allowed")
    forbidden = [
        name for name in (headers or {}) if name.lower() in _FORBIDDEN_CALLER_HEADERS
    ]
    if forbidden:
        raise ValueError(f"caller credential header is not allowed: {forbidden[0]}")
    request = urllib.request.Request(url, headers=dict(headers or {}), method=method)
    if not request.has_header("User-agent"):
        request.add_header("User-Agent", user_agent)
    return request


def complete_response(stream: Any, body: bytes) -> HttpResponse:
    """Wrap a body read from a urllib response, rejecting a truncated read."""
    # A sized read returns a short body instead of raising when the
    # connection closes before Content-Length is satisfied.
    remaining = getattr(stream, "length", None)
    if remaining:
        raise IncompleteRead(body, remaining)
    status = stream.status
    if not isinstance(status, int):
        raise HttpError(f"response from {redact_url(stream.url)} has no HTTP status")
    return HttpResponse(
        url=stream.url, status=status, headers=stream.headers, body=body
    )


def retrying(
    url: str,
    attempt: Callable[[], HttpResponse],
    *,
    retries: int,
    backoff: float,
    sleep: Callable[[float], None],
) -> HttpResponse:
    """Run one request attempt, retrying transient failures with backoff."""
    attempts = retries + 1
    for number in range(attempts):
        try:
            return attempt()
        except (OSError, HTTPException) as error:
            if isinstance(error, urllib.error.HTTPError):
                error.close()
            if not _is_transient(error) or number + 1 == attempts:
                if _is_transient(error):
                    raise TransientHttpError(url, number + 1) from error
                raise HttpError(
                    f"request to {redact_url(url)} failed after {number + 1} attempts"
                ) from error
            sleep(backoff * (2**number))
    raise AssertionError("request loop did not return or raise")


def _is_transient(error: OSError | HTTPException) -> bool:
    return not isinstance(error, urllib.error.HTTPError) or error.code in {
        408,
        425,
        429,
        500,
        502,
        503,
        504,
    }


def redact_url(url: str) -> str:
    """Remove user information and query values from a diagnostic URL."""
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    query = urlencode(
        [
            (name, "REDACTED")
            for name, _ in parse_qsl(parsed.query, keep_blank_values=True)
        ]
    )
    return urlunsplit((parsed.scheme, host, parsed.path, query, parsed.fragment))
