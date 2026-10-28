"""Plain retrying HTTP GET for every upstream read.

The build and source generation fetch public catalogs and lists, so
`HttpClient` sends no credentials unless a caller passes one, and follows
redirects with urllib's defaults. A credential a caller passes is never
forwarded to a redirect target.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from email.message import Message
from http.client import HTTPException, IncompleteRead
from pathlib import Path
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


class DeadlineExceeded(HttpError):
    """A download ran out of the time its caller allowed."""

    def __init__(self, url: str) -> None:
        super().__init__(f"download of {redact_url(url)} passed its deadline")


@dataclass(frozen=True, slots=True)
class Download:
    """A finished download: the final URL, bytes written and their SHA-256."""

    url: str
    size: int
    sha256: str


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


class ResponseStream(Protocol):
    """An open response whose body is read in pieces."""

    url: str
    status: int
    headers: Message

    def read(self, size: int = -1, /) -> bytes: ...


class StreamTransport(Protocol):
    def __call__(
        self, request: urllib.request.Request, timeout: float
    ) -> AbstractContextManager[ResponseStream]: ...


DOWNLOAD_CHUNK = 1024 * 1024


class HttpClient:
    """Fetch public URLs with bounded transient retries.

    A request carries no credentials unless the caller passes one to `get`.
    """

    def __init__(
        self,
        *,
        transport: Transport | None = None,
        timeout: float = 30.0,
        user_agent: str = "omnipack/0.1",
        retries: int = 2,
        backoff: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
        stream_transport: StreamTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        if retries < 0 or backoff < 0:
            raise ValueError("retries and backoff must be nonnegative")
        self.transport = transport or self._urllib_transport
        self.timeout = timeout
        self.user_agent = user_agent
        self.retries = retries
        self.backoff = backoff
        self.sleep = sleep
        self.stream_transport = stream_transport or self._urllib_stream_transport
        self.clock = clock
        self.wall_clock = wall_clock

    def get(
        self,
        url: str,
        headers: Mapping[str, str] | None = None,
        *,
        credential: str | None = None,
        deadline: float | None = None,
    ) -> HttpResponse:
        """Fetch one URL, retrying transient failures up to the configured bound.

        `headers` are sent with the request and may replace the client's
        default user agent. `credential` is an `Authorization` value sent
        only to `url` itself, never to a redirect target. `deadline` is a
        reading of this client's `clock` that bounds the call, including its
        retry waits; passing it raises `DeadlineExceeded`.
        """
        # http.client rejects a control or non-Latin-1 character with a message
        # quoting it, and failure reasons reach published reports.
        if credential is not None and not (
            credential.isascii() and credential.isprintable()
        ):
            raise ValueError("credential is not a valid header value")
        request = _build_request(url, user_agent=self.user_agent, headers=headers)
        if credential is not None:
            # urllib copies only `Request.headers` into a redirected request.
            request.add_unredirected_header("Authorization", credential)
        attempts = self.retries + 1
        for number in range(attempts):
            try:
                timeout = self._remaining(url, deadline, self.timeout)
                return self.transport(request, timeout)
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
                self._wait(url, self.backoff * (2**number), deadline)
        raise AssertionError("request loop did not return or raise")

    def download(
        self,
        url: str,
        destination: Path,
        headers: Mapping[str, str] | None = None,
        *,
        credential: str | None = None,
        deadline: float | None = None,
    ) -> Download:
        """Stream one URL to `destination`, hashing the bytes as they arrive.

        Retries follow `get`'s policy, each attempt rewriting the file from
        the start; `credential` is sent only to `url` itself. A 403 or 429
        that names when its rate limit resets (`Retry-After`, or
        `X-RateLimit-Reset` with none remaining) is waited out once, without
        spending a retry. `deadline` is a reading of this client's `clock`
        that bounds the whole call, including every wait and each chunk read;
        passing it raises `DeadlineExceeded` and leaves no file behind.
        """
        if credential is not None and not (
            credential.isascii() and credential.isprintable()
        ):
            raise ValueError("credential is not a valid header value")
        request = _build_request(url, user_agent=self.user_agent, headers=headers)
        if credential is not None:
            request.add_unredirected_header("Authorization", credential)
        attempts = self.retries + 1
        rate_limit_waited = False
        number = 0
        try:
            while True:
                timeout = self._remaining(url, deadline, self.timeout)
                try:
                    return self._stream_to(request, destination, timeout, deadline)
                except (OSError, HTTPException) as error:
                    if isinstance(error, urllib.error.HTTPError):
                        error.close()
                        wait = None if rate_limit_waited else self._reset_wait(error)
                        if wait is not None:
                            self._wait(url, wait, deadline)
                            rate_limit_waited = True
                            continue
                        if not _is_transient(error):
                            raise HttpStatusError(
                                url, error.code, number + 1
                            ) from error
                    if number + 1 == attempts:
                        raise TransientHttpError(
                            url,
                            number + 1,
                            status=error.code
                            if isinstance(error, urllib.error.HTTPError)
                            else None,
                            detail=str(error) or type(error).__name__,
                        ) from error
                    self._wait(url, self.backoff * (2**number), deadline)
                    number += 1
        except BaseException:
            destination.unlink(missing_ok=True)
            raise

    def _stream_to(
        self,
        request: urllib.request.Request,
        destination: Path,
        timeout: float,
        deadline: float | None,
    ) -> Download:
        digest = hashlib.sha256()
        size = 0
        url = request.full_url
        with self.stream_transport(request, timeout) as stream:
            url = stream.url
            with destination.open("wb") as file:
                while chunk := stream.read(DOWNLOAD_CHUNK):
                    self._remaining(url, deadline, 0.0)
                    digest.update(chunk)
                    file.write(chunk)
                    size += len(chunk)
            self._remaining(url, deadline, 0.0)
            # A sized read ends early without raising when the connection
            # closes before Content-Length is satisfied.
            remaining = getattr(stream, "length", None)
            if remaining:
                raise IncompleteRead(b"", remaining)
        return Download(url=url, size=size, sha256=digest.hexdigest())

    def _remaining(self, url: str, deadline: float | None, cap: float) -> float:
        """The time left before `deadline`, at most `cap` when `cap` is positive;
        raises `DeadlineExceeded` when none is left."""
        if deadline is None:
            return cap
        left = deadline - self.clock()
        if left <= 0:
            raise DeadlineExceeded(url)
        return min(cap, left) if cap > 0 else left

    def _wait(self, url: str, seconds: float, deadline: float | None) -> None:
        """Sleep, or give up when the deadline falls before the wait ends."""
        if deadline is not None and self.clock() + seconds >= deadline:
            raise DeadlineExceeded(url)
        self.sleep(seconds)

    def _reset_wait(self, error: urllib.error.HTTPError) -> float | None:
        """Seconds until a rate limit lifts, when the response says so."""
        if error.code not in {403, 429}:
            return None
        retry_after = error.headers.get("Retry-After")
        if retry_after is not None and retry_after.strip().isdigit():
            return float(retry_after)
        reset = error.headers.get("X-RateLimit-Reset")
        remaining = error.headers.get("X-RateLimit-Remaining")
        if reset is not None and reset.strip().isdigit() and remaining == "0":
            return max(0.0, float(reset) - self.wall_clock())
        return None

    def _urllib_stream_transport(
        self, request: urllib.request.Request, timeout: float
    ) -> AbstractContextManager[ResponseStream]:
        return urllib.request.urlopen(request, timeout=timeout)

    def _urllib_transport(
        self, request: urllib.request.Request, timeout: float
    ) -> HttpResponse:
        with urllib.request.urlopen(request, timeout=timeout) as stream:
            return _complete_response(stream, stream.read())


def _build_request(
    url: str, *, user_agent: str, headers: Mapping[str, str] | None = None
) -> urllib.request.Request:
    """Build a request that carries no credentials of its own."""
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


def failure_reason(error: Exception) -> str:
    """Name a failure's cause: the last attempt's HTTP status when it got one,
    otherwise the failure's own message."""
    if isinstance(error, HttpStatusError):
        return f"HTTP {error.status}"
    if isinstance(error, TransientHttpError):
        return f"HTTP {error.status}" if error.status is not None else error.detail
    return str(error) or type(error).__name__


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
