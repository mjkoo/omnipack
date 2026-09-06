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
from http.client import HTTPMessage
from pathlib import Path
from typing import IO, Any, Protocol
from urllib.parse import urlsplit


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
        attempts = self.retries + 1
        for attempt in range(attempts):
            request = self.build_request(url, headers=headers, method=method)
            try:
                return self.transport(request, self.timeout, max_bytes)
            except (urllib.error.URLError, TimeoutError) as error:
                if not _is_transient(error) or attempt + 1 == attempts:
                    raise HttpError(
                        f"request to {url} failed after {attempt + 1} attempts"
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
        request = urllib.request.Request(
            url, headers=dict(headers or {}), method=method
        )
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
        self, request: urllib.request.Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse:
        opener = urllib.request.build_opener(_CredentialRedirectHandler(self))
        with opener.open(request, timeout=timeout) as stream:
            body = stream.read(None if max_bytes is None else max_bytes + 1)
            if max_bytes is not None and len(body) > max_bytes:
                raise HttpError(f"response from {stream.url} exceeds {max_bytes} bytes")
            return HttpResponse(
                url=stream.url,
                status=stream.status,
                headers=stream.headers,
                body=body,
            )


def _is_transient(error: urllib.error.URLError | TimeoutError) -> bool:
    return not isinstance(error, urllib.error.HTTPError) or error.code in {
        408,
        425,
        429,
        500,
        502,
        503,
        504,
    }
