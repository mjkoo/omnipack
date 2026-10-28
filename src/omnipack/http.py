"""Plain retrying HTTP GET for every upstream read.

The build and source generation fetch public catalogs and lists, so
`HttpClient` sends no credentials unless a caller passes one, and follows
redirects with urllib's defaults. A credential a caller passes is never
forwarded to a redirect target. `download` streams a body to a file for the
release archive, bounded by a caller's deadline, and waits out a short rate
limit once.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping
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
    """A request ran out of the time its caller allowed."""

    def __init__(self, url: str) -> None:
        super().__init__(f"request to {redact_url(url)} passed its deadline")


class RateLimitError(HttpStatusError):
    """A rate-limited response whose limit lifts too far ahead to wait for."""

    def __init__(self, url: str, status: int, wait: float) -> None:
        super().__init__(url, status)
        self.wait = wait


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

    def read1(self, size: int = -1, /) -> bytes: ...


class StreamTransport(Protocol):
    def __call__(
        self, request: urllib.request.Request, timeout: float
    ) -> AbstractContextManager[ResponseStream]: ...


DOWNLOAD_CHUNK = 1024 * 1024
# The longest server-chosen rate-limit wait a download sits out; a limit that
# lifts later fails the request at once instead of stalling the caller.
MAX_RATE_LIMIT_WAIT = 120.0


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
        self.transport = transport
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
        retry waits and each body read; passing it raises `DeadlineExceeded`.
        """
        request = self._request(url, headers, credential)

        def attempt(timeout: float) -> HttpResponse:
            if self.transport is not None:
                return self.transport(request, timeout)
            if deadline is None:
                return self._urllib_transport(request, timeout)
            with self.stream_transport(request, timeout) as stream:
                body = b"".join(self._chunks(stream, deadline))
                return _complete_response(stream, body)

        return self._with_retries(url, deadline, attempt)

    def download(
        self,
        url: str,
        destination: Path,
        headers: Mapping[str, str] | None = None,
        *,
        deadline: float | None = None,
    ) -> None:
        """Stream one URL to `destination`.

        Retries follow `get`'s policy, each attempt rewriting the file from
        the start. A 403 or 429 that names when its rate limit resets
        (`Retry-After`, or `X-RateLimit-Reset` with none remaining) is waited
        out once, without spending a retry, when it lifts within
        `MAX_RATE_LIMIT_WAIT` seconds; a later reset raises `RateLimitError`.
        `deadline` is a reading of this client's `clock` that bounds the whole
        call, including every wait and each read; passing it raises
        `DeadlineExceeded`. A failed download leaves no file behind.
        """
        request = self._request(url, headers)

        def attempt(timeout: float) -> None:
            with (
                self.stream_transport(request, timeout) as stream,
                destination.open("wb") as file,
            ):
                for chunk in self._chunks(stream, deadline):
                    file.write(chunk)
                # A read ends early without raising when the connection
                # closes before Content-Length is satisfied.
                remaining = getattr(stream, "length", None)
                if remaining:
                    raise IncompleteRead(b"", remaining)

        try:
            self._with_retries(url, deadline, attempt, wait_rate_limits=True)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise

    def _request(
        self,
        url: str,
        headers: Mapping[str, str] | None,
        credential: str | None = None,
    ) -> urllib.request.Request:
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
        return request

    def _with_retries[T](
        self,
        url: str,
        deadline: float | None,
        attempt: Callable[[float], T],
        *,
        wait_rate_limits: bool = False,
    ) -> T:
        """Run `attempt` with each try's timeout, retrying transient failures
        and mapping the last failure to a typed `HttpError`."""
        attempts = self.retries + 1
        rate_limit_waited = not wait_rate_limits
        number = 0
        while True:
            timeout = self._remaining(url, deadline, self.timeout)
            try:
                return attempt(timeout)
            except (OSError, HTTPException) as error:
                if isinstance(error, urllib.error.HTTPError):
                    error.close()
                    wait = None if rate_limit_waited else self._reset_wait(error)
                    if wait is not None:
                        if wait > MAX_RATE_LIMIT_WAIT:
                            raise RateLimitError(url, error.code, wait) from error
                        self._wait(url, wait, deadline)
                        rate_limit_waited = True
                        continue
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
                number += 1

    def _chunks(
        self, stream: ResponseStream, deadline: float | None
    ) -> Iterator[bytes]:
        """A response body piece by piece, one receive per read, checking
        `deadline` before each so a trickling server cannot outlast it."""
        while True:
            self._remaining(stream.url, deadline, 0.0)
            chunk = stream.read1(DOWNLOAD_CHUNK)
            if not chunk:
                return
            yield chunk

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
    if isinstance(error, RateLimitError):
        return f"HTTP {error.status}: rate limit lifts in {error.wait:.0f} s"
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
