"""Plain retrying HTTP GET for every upstream read.

The build and source generation fetch public catalogs and lists, so
`HttpClient` sends no credentials and follows redirects with urllib's
defaults.
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


class HttpError(RuntimeError):
    """A request failed or returned an unusable response."""


class HttpStatusError(HttpError):
    """A non-retryable HTTP response with its status available to callers."""

    def __init__(self, url: str, status: int, attempts: int = 1) -> None:
        self.status = status
        super().__init__(
            f"request to {redact_url(url)} returned HTTP {status} after {attempts} attempts"
        )


class TransientHttpError(HttpError):
    """A request that still failed transiently after the client's retries.

    `status` is the last attempt's HTTP status when it got an error
    response, otherwise None; `detail` is the last failure's own message.
    """

    def __init__(
        self, url: str, attempts: int, *, status: int | None = None, detail: str = ""
    ) -> None:
        self.url = url
        self.status = status
        self.detail = detail
        super().__init__(
            f"request to {redact_url(url)} failed after {attempts} attempts"
        )


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """The response data callers read: final URL, status, headers and body."""

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


class HttpClient:
    """Fetch public URLs with bounded transient retries and no credentials."""

    def __init__(
        self,
        *,
        transport: Transport | None = None,
        timeout: float = 30.0,
        user_agent: str = "omnipack/0.1",
        retries: int = 2,
        backoff: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if retries < 0 or backoff < 0:
            raise ValueError("retries and backoff must be nonnegative")
        self.transport = transport or self._urllib_transport
        self.timeout = timeout
        self.user_agent = user_agent
        self.retries = retries
        self.backoff = backoff
        self.sleep = sleep

    def get(self, url: str, headers: Mapping[str, str] | None = None) -> HttpResponse:
        """Fetch one URL, retrying transient failures up to the configured bound.

        `headers` are sent with the request and may replace the client's
        default user agent.
        """
        request = _build_request(url, user_agent=self.user_agent, headers=headers)
        attempts = self.retries + 1
        for number in range(attempts):
            try:
                return self.transport(request, self.timeout)
            except (OSError, HTTPException) as error:
                if isinstance(error, urllib.error.HTTPError):
                    error.close()
                    if not _is_transient(error):
                        raise HttpStatusError(url, error.code, number + 1) from error
                if number + 1 == attempts:
                    raise TransientHttpError(
                        url,
                        number + 1,
                        status=error.code
                        if isinstance(error, urllib.error.HTTPError)
                        else None,
                        detail=str(error) or type(error).__name__,
                    ) from error
                self.sleep(self.backoff * (2**number))
        raise AssertionError("request loop did not return or raise")

    def _urllib_transport(
        self, request: urllib.request.Request, timeout: float
    ) -> HttpResponse:
        with urllib.request.urlopen(request, timeout=timeout) as stream:
            return _complete_response(stream, stream.read())


def _build_request(
    url: str, *, user_agent: str, headers: Mapping[str, str] | None = None
) -> urllib.request.Request:
    """Build a request that carries no credentials."""
    parsed = urlsplit(url)
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("embedded URL credentials are not allowed")
    # urllib normalizes header name case, so a given User-Agent of any
    # spelling replaces the default.
    return urllib.request.Request(
        url, headers={"User-Agent": user_agent, **(headers or {})}
    )


def _complete_response(stream: Any, body: bytes) -> HttpResponse:
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
