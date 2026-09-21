"""Credential-scoped HTTP for source generation.

A request to a registered host carries a bearer token read from an
environment variable, a redirect selects the destination's own credential
and never forwards the source's, and a read can be bounded. The build's
catalog fetches use the plain client in `omnipack.http` instead.
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from http.client import HTTPMessage
from io import BytesIO
from pathlib import Path
from typing import IO, Any, Protocol, Unpack
from urllib.parse import urlsplit

from omnipack.http import (
    ClientSettings,
    HttpError,
    HttpResponse,
    RetryingClient,
    build_request,
    complete_response,
    redact_url,
)

MAX_REDIRECTS = 10


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
        return cls.from_document(document)

    @classmethod
    def from_document(cls, document: object) -> HttpConfig:
        """Validate an already captured HTTP configuration document."""
        credentials = (
            document.get("credentials") if isinstance(document, dict) else None
        )
        if not isinstance(credentials, dict) or not all(
            isinstance(host, str) and isinstance(variable, str)
            for host, variable in credentials.items()
        ):
            raise ValueError(
                "HTTP config credentials must map host strings to variable names"
            )
        return cls(credentials)


class GenerationHttp(Protocol):
    """HTTP operations needed to inspect releases and bounded APK content."""

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        max_bytes: int | None = None,
        method: str = "GET",
    ) -> HttpResponse: ...


class BoundedTransport(Protocol):
    def __call__(
        self, request: urllib.request.Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse: ...


class _CredentialRedirectHandler(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS

    def __init__(self, client: SourceHttpClient) -> None:
        self.client = client

    def http_error_302(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
    ) -> Any:
        # urllib drains redirect bodies without a bound. Give its redirect policy
        # an empty body after closing the real stream, preserving loop checks.
        fp.close()
        with BytesIO() as empty:
            return super().http_error_302(req, empty, code, msg, headers)

    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302
    http_error_308 = http_error_302

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


class SourceHttpClient(RetryingClient):
    """Fetch with exact-host credentials, bounded reads and transient retries."""

    def __init__(
        self,
        config: HttpConfig,
        *,
        transport: BoundedTransport | None = None,
        **settings: Unpack[ClientSettings],
    ) -> None:
        super().__init__(**settings)
        self.config = config
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
        return self._retry(
            url,
            lambda: self.transport(
                self.build_request(url, headers=headers, method=method),
                self.timeout,
                max_bytes,
            ),
        )

    def build_request(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        method: str = "GET",
    ) -> urllib.request.Request:
        """Build a request and attach credentials registered for its exact host."""
        request = build_request(
            url, user_agent=self.user_agent, headers=headers, method=method
        )
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
    ) -> HttpResponse:
        opener = urllib.request.build_opener(_CredentialRedirectHandler(self))
        with opener.open(request, timeout=timeout) as stream:
            body = stream.read() if max_bytes is None else stream.read(max_bytes + 1)
            if max_bytes is not None and len(body) > max_bytes:
                raise HttpError(
                    f"response from {redact_url(stream.url)} exceeds {max_bytes} bytes"
                )
            return complete_response(stream, body)
