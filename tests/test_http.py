from __future__ import annotations

import http.client
import urllib.error
import urllib.request
from email.message import Message
from io import BytesIO
from typing import TYPE_CHECKING
from urllib.response import addinfourl

import pytest

from omnipack.http import HttpClient, HttpError, HttpResponse, redact_url

if TYPE_CHECKING:
    from urllib.request import Request


class RecordingTransport:
    def __init__(self, outcomes: list[HttpResponse | Exception]) -> None:
        self.outcomes = iter(outcomes)
        self.requests: list[Request] = []

    def __call__(self, request: Request, timeout: float) -> HttpResponse:
        self.requests.append(request)
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def response(url: str = "https://example.com/data") -> HttpResponse:
    return HttpResponse(url=url, status=200, headers=Message(), body=b"ok")


def test_plain_client_sends_no_credentials_even_when_tokens_are_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    transport = RecordingTransport([response("https://api.github.com/data")])

    HttpClient(transport=transport).get("https://api.github.com/data")

    request = transport.requests[0]
    assert request.get_header("Authorization") is None
    assert request.get_header("User-agent") == "omnipack/0.1"


def test_truncated_body_is_retried_then_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[Request] = []
    sleeps: list[float] = []

    class Socket:
        def makefile(self, mode: str) -> BytesIO:
            return BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\nshort!")

    def open_fixture(handler: urllib.request.HTTPSHandler, request: Request):
        requests.append(request)
        stream = http.client.HTTPResponse(Socket())  # ty: ignore[invalid-argument-type]
        stream.begin()
        stream.url = request.full_url
        return stream

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)
    client = HttpClient(retries=1, sleep=sleeps.append)
    with pytest.raises(HttpError, match="failed after 2 attempts"):
        client.get("https://example.com/data")
    assert len(requests) == 2
    assert sleeps == [0.5]


def test_plain_client_follows_redirects_with_urllib_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[Request] = []

    class FixtureResponse(addinfourl):
        msg = "fixture response"

    def open_fixture(
        handler: urllib.request.HTTPSHandler, request: Request
    ) -> FixtureResponse:
        requests.append(request)
        headers = Message()
        if request.full_url == "https://source.example/data":
            headers["Location"] = "https://destination.example/file"
            return FixtureResponse(BytesIO(b""), headers, request.full_url, 302)
        return FixtureResponse(BytesIO(b"payload"), headers, request.full_url, 200)

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)

    result = HttpClient(retries=0).get("https://source.example/data")

    assert (result.url, result.body) == ("https://destination.example/file", b"payload")
    assert [request.full_url for request in requests] == [
        "https://source.example/data",
        "https://destination.example/file",
    ]
    assert all(request.get_header("Authorization") is None for request in requests)


def test_retries_transient_failures_with_bounded_backoff() -> None:
    sleeps: list[float] = []
    transport = RecordingTransport(
        [
            urllib.error.URLError("temporary"),
            urllib.error.URLError("temporary"),
            response(),
        ]
    )
    client = HttpClient(
        retries=2,
        backoff=0.25,
        sleep=sleeps.append,
        transport=transport,
    )

    assert client.get("https://example.com/data").body == b"ok"
    assert sleeps == [0.25, 0.5]
    assert len(transport.requests) == 3


def test_exhausted_retries_raise_http_error() -> None:
    transport = RecordingTransport([urllib.error.URLError("down")] * 3)
    client = HttpClient(retries=2, sleep=lambda _: None, transport=transport)

    with pytest.raises(HttpError, match="after 3 attempts"):
        client.get("https://example.com/data")


def test_rate_limit_retries_but_nontransient_http_error_does_not() -> None:
    rate_limited = urllib.error.HTTPError(
        "https://example.com", 429, "limited", Message(), None
    )
    missing = urllib.error.HTTPError(
        "https://example.com", 404, "missing", Message(), None
    )
    retry_transport = RecordingTransport([rate_limited, response()])
    fail_transport = RecordingTransport([missing])

    assert (
        HttpClient(sleep=lambda _: None, transport=retry_transport)
        .get("https://example.com")
        .body
        == b"ok"
    )
    with pytest.raises(HttpError, match="after 1 attempts"):
        HttpClient(transport=fail_transport).get("https://example.com")

    assert len(retry_transport.requests) == 2
    assert len(fail_transport.requests) == 1


def test_embedded_url_credentials_are_rejected() -> None:
    client = HttpClient(transport=RecordingTransport([]))

    with pytest.raises(ValueError, match="embedded URL credentials"):
        client.get("https://user:pass@example.com/app")


def test_diagnostic_urls_redact_credentials_and_query_values() -> None:
    assert redact_url("https://user:pass@example.com/app?q=secret&flag=#part") == (
        "https://example.com/app?q=REDACTED&flag=REDACTED#part"
    )
    transport = RecordingTransport([urllib.error.URLError("down")])

    with pytest.raises(HttpError) as raised:
        HttpClient(retries=0, transport=transport).get(
            "https://example.com/app?token=secret"
        )

    message = str(raised.value)
    assert "secret" not in message
    assert "token=REDACTED" in message
