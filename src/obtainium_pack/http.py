"""Small authenticated HTTP client for every pipeline network request."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.message import Message
from http.client import HTTPException, HTTPMessage
from pathlib import Path
from typing import IO, Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

METADATA_MAX_BYTES = 10 * 1024 * 1024
PROBE_BYTES = 1024
MAX_REDIRECTS = 10
_FORBIDDEN_CALLER_HEADERS = frozenset({"authorization", "cookie"})


class HttpError(RuntimeError):
    """A request failed or exceeded a configured response bound."""


@dataclass(frozen=True, slots=True)
class HttpConfig:
    """Exact-host mappings to environment variables containing credentials."""

    credentials: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "credentials",
            {host.lower(): variable for host, variable in self.credentials.items()},
        )

    @classmethod
    def from_path(cls, path: str | Path) -> HttpConfig:
        """Load and validate an HTTP configuration document."""
        with Path(path).open(encoding="utf-8") as stream:
            document = json.load(stream)
        credentials = document.get("credentials")
        if not isinstance(credentials, dict) or not all(
            isinstance(host, str) and isinstance(variable, str)
            for host, variable in credentials.items()
        ):
            raise ValueError(
                "HTTP config credentials must map host strings to variable names"
            )
        return cls(credentials)


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
        self, request: urllib.request.Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse: ...


class _CredentialRedirectHandler(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS

    def __init__(self, client: HttpClient) -> None:
        self.client = client

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None
        return self.client.redirect_request(redirected, newurl)


class HttpClient:
    """Fetch bytes with exact-host credentials and bounded transient retries."""

    def __init__(
        self,
        config: HttpConfig,
        *,
        timeout: float = 30.0,
        user_agent: str = "obtainium-emulation-pack/0.1",
        retries: int = 2,
        backoff: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
        transport: Transport | None = None,
    ) -> None:
        if retries < 0 or backoff < 0:
            raise ValueError("retries and backoff must be nonnegative")
        self.config = config
        self.timeout = timeout
        self.user_agent = user_agent
        self.retries = retries
        self.backoff = backoff
        self.sleep = sleep
        self.transport = transport or self._urllib_transport

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        max_bytes: int | None = None,
        method: str = "GET",
    ) -> HttpResponse:
        """Fetch one URL, retrying transient failures up to the configured bound."""
        if max_bytes is not None and max_bytes < 0:
            raise ValueError("max_bytes must be nonnegative")
        return self._request(url, headers=headers, max_bytes=max_bytes, method=method)

    def get_metadata(
        self, url: str, *, headers: Mapping[str, str] | None = None
    ) -> HttpResponse:
        """Fetch metadata and reject responses larger than the live policy limit."""
        return self.get(url, headers=headers, max_bytes=METADATA_MAX_BYTES)

    def probe(
        self, url: str, *, headers: Mapping[str, str] | None = None
    ) -> HttpResponse:
        """Read a nonempty response prefix without downloading the whole resource."""
        probe_headers = dict(headers or {})
        probe_headers["Range"] = f"bytes=0-{PROBE_BYTES - 1}"
        if self.transport == self._urllib_transport:
            response = self._request(
                url, headers=probe_headers, max_bytes=PROBE_BYTES, prefix=True
            )
        else:
            response = self._request(url, headers=probe_headers, max_bytes=PROBE_BYTES)
            if len(response.body) > PROBE_BYTES:
                response = HttpResponse(
                    response.url,
                    response.status,
                    response.headers,
                    response.body[:PROBE_BYTES],
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

    def _request(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        max_bytes: int | None = None,
        method: str = "GET",
        prefix: bool = False,
    ) -> HttpResponse:
        attempts = self.retries + 1
        for attempt in range(attempts):
            request = self.build_request(url, headers=headers, method=method)
            try:
                if prefix:
                    return self._urllib_transport(
                        request, self.timeout, max_bytes, prefix=True
                    )
                return self.transport(request, self.timeout, max_bytes)
            except (OSError, HTTPException) as error:
                if isinstance(error, urllib.error.HTTPError):
                    error.close()
                if not _is_transient(error) or attempt + 1 == attempts:
                    raise HttpError(
                        f"request to {redact_url(url)} failed after "
                        f"{attempt + 1} attempts"
                    ) from error
                self.sleep(self.backoff * (2**attempt))
        raise AssertionError("request loop did not return or raise")

    def build_request(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        method: str = "GET",
    ) -> urllib.request.Request:
        """Build a request and attach credentials registered for its exact host."""
        parsed = urlsplit(url)
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("embedded URL credentials are not allowed")
        forbidden = [
            name
            for name in (headers or {})
            if name.lower() in _FORBIDDEN_CALLER_HEADERS
        ]
        if forbidden:
            raise ValueError(f"caller credential header is not allowed: {forbidden[0]}")
        request = urllib.request.Request(
            url, headers=dict(headers or {}), method=method
        )
        if not request.has_header("User-agent"):
            request.add_header("User-Agent", self.user_agent)
        self._set_authorization(request)
        return request

    def redirect_request(
        self, request: urllib.request.Request, new_url: str
    ) -> urllib.request.Request:
        """Rebuild authorization for a redirect destination."""
        headers = {
            name: value
            for name, value in (
                *request.header_items(),
                *request.unredirected_hdrs.items(),
            )
            if name.lower() != "authorization"
        }
        redirected = urllib.request.Request(
            new_url, headers=headers, method=request.method
        )
        self._set_authorization(redirected)
        return redirected

    def _set_authorization(self, request: urllib.request.Request) -> None:
        host = (urlsplit(request.full_url).hostname or "").lower()
        variable = self.config.credentials.get(host)
        token = os.environ.get(variable, "") if variable else ""
        if token:
            request.add_unredirected_header("Authorization", f"Bearer {token}")

    def _urllib_transport(
        self,
        request: urllib.request.Request,
        timeout: float,
        max_bytes: int | None,
        *,
        prefix: bool = False,
    ) -> HttpResponse:
        opener = urllib.request.build_opener(_CredentialRedirectHandler(self))
        with opener.open(request, timeout=timeout) as stream:
            if prefix:
                body = stream.read(max_bytes)
            else:
                body = stream.read(None if max_bytes is None else max_bytes + 1)
            if not prefix and max_bytes is not None and len(body) > max_bytes:
                raise HttpError(
                    f"response from {redact_url(stream.url)} exceeds {max_bytes} bytes"
                )
            return HttpResponse(
                url=stream.url,
                status=stream.status,
                headers=stream.headers,
                body=body,
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
