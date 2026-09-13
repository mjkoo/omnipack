from __future__ import annotations

import http.client
import json
import urllib.request
from email.message import Message
from io import BytesIO
from typing import TYPE_CHECKING
from urllib.response import addinfourl

import pytest

from omnipack.http import HttpError, HttpResponse
from omnipack.source_http import HttpConfig, SourceHttpClient

if TYPE_CHECKING:
    from pathlib import Path
    from urllib.request import Request


class RecordingTransport:
    def __init__(self, outcomes: list[HttpResponse | Exception]) -> None:
        self.outcomes = iter(outcomes)
        self.requests: list[Request] = []
        self.max_bytes: list[int | None] = []

    def __call__(
        self, request: Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse:
        self.requests.append(request)
        self.max_bytes.append(max_bytes)
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def response(url: str = "https://example.com/data") -> HttpResponse:
    return HttpResponse(url=url, status=200, headers=Message(), body=b"ok")


def test_http_config_loads_default_shape(tmp_path: Path) -> None:
    path = tmp_path / "http.json"
    path.write_text(json.dumps({"credentials": {"api.github.com": "TOKEN"}}))

    assert HttpConfig.from_path(path).credentials == {"api.github.com": "TOKEN"}


@pytest.mark.parametrize("max_bytes", [None, 1024])
def test_truncated_body_is_retried_then_reported(
    monkeypatch: pytest.MonkeyPatch, max_bytes: int | None
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
    client = SourceHttpClient(HttpConfig({}), retries=1, sleep=sleeps.append)
    with pytest.raises(HttpError, match="failed after 2 attempts"):
        client.get("https://example.com/data", max_bytes=max_bytes)
    assert len(requests) == 2
    assert sleeps == [0.5]


def test_head_method_and_response_metadata_are_available() -> None:
    headers = Message()
    headers["Content-Length"] = "42"
    transport = RecordingTransport(
        [HttpResponse("https://example.com/file", 200, headers, b"")]
    )
    client = SourceHttpClient(HttpConfig({}), transport=transport)

    result = client.get("https://example.com/file", method="HEAD")

    assert transport.requests[0].method == "HEAD"
    assert result.status == 200
    assert result.headers["Content-Length"] == "42"


def test_get_passes_response_limit_to_transport() -> None:
    transport = RecordingTransport([response()])
    client = SourceHttpClient(HttpConfig({}), transport=transport)

    client.get("https://example.com/releases", max_bytes=4096)

    assert transport.requests[0].method == "GET"
    assert transport.max_bytes == [4096]


def test_get_rejects_an_oversized_real_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixtureResponse(addinfourl):
        msg = "fixture response"

    def open_fixture(
        handler: urllib.request.HTTPSHandler, request: Request
    ) -> FixtureResponse:
        return FixtureResponse(
            BytesIO(b"x" * 11),
            Message(),
            request.full_url,
            200,
        )

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)

    with pytest.raises(HttpError, match="exceeds 10 bytes"):
        SourceHttpClient(HttpConfig({}), retries=0).get(
            "https://example.com/data", max_bytes=10
        )


@pytest.mark.parametrize("token", [None, ""])
def test_unset_or_empty_credentials_leave_request_unauthenticated(
    monkeypatch: pytest.MonkeyPatch, token: str | None
) -> None:
    if token is None:
        monkeypatch.delenv("REGISTERED_TOKEN", raising=False)
    else:
        monkeypatch.setenv("REGISTERED_TOKEN", token)
    transport = RecordingTransport([response()])
    client = SourceHttpClient(
        HttpConfig({"api.example.com": "REGISTERED_TOKEN"}), transport=transport
    )

    client.get("https://API.EXAMPLE.COM/data")

    assert transport.requests[0].get_header("Authorization") is None


def test_credentials_match_exact_host_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REGISTERED_TOKEN", "secret")
    transport = RecordingTransport([response()])
    client = SourceHttpClient(
        HttpConfig({"API.Example.COM": "REGISTERED_TOKEN"}), transport=transport
    )

    client.get("https://api.example.com/data")

    assert transport.requests[0].get_header("Authorization") == "Bearer secret"


@pytest.mark.parametrize(
    "host", ["sub.api.example.com", "www.api.example.com", "other.test"]
)
def test_credentials_are_not_inferred_for_other_hosts(
    monkeypatch: pytest.MonkeyPatch, host: str
) -> None:
    monkeypatch.setenv("REGISTERED_TOKEN", "secret")
    monkeypatch.setenv("UNRELATED_TOKEN", "also-secret")
    transport = RecordingTransport([response()])
    client = SourceHttpClient(
        HttpConfig(
            {"api.example.com": "REGISTERED_TOKEN", "unrelated.test": "UNRELATED_TOKEN"}
        ),
        transport=transport,
    )

    client.get(f"https://{host}/data")

    assert transport.requests[0].get_header("Authorization") is None


def test_redirect_reselects_credentials_without_forwarding_source_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCE_TOKEN", "source-secret")
    monkeypatch.setenv("DEST_TOKEN", "destination-secret")
    client = SourceHttpClient(
        HttpConfig(
            {"source.example": "SOURCE_TOKEN", "destination.example": "DEST_TOKEN"}
        )
    )
    original = client.build_request("https://source.example/data")

    redirected = client.redirect_request(original, "https://destination.example/file")

    assert original.get_header("Authorization") == "Bearer source-secret"
    assert redirected.get_header("Authorization") == "Bearer destination-secret"


def test_redirect_to_unregistered_host_strips_source_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCE_TOKEN", "source-secret")
    client = SourceHttpClient(HttpConfig({"source.example": "SOURCE_TOKEN"}))

    redirected = client.redirect_request(
        client.build_request("https://source.example/data"),
        "https://assets.example/file",
    )

    assert redirected.get_header("Authorization") is None


@pytest.mark.parametrize("destination_registered", [False, True])
def test_urllib_redirect_selects_destination_credentials(
    monkeypatch: pytest.MonkeyPatch, destination_registered: bool
) -> None:
    monkeypatch.setenv("SOURCE_TOKEN", "source-secret")
    monkeypatch.setenv("DEST_TOKEN", "destination-secret")
    credentials = {"source.example": "SOURCE_TOKEN"}
    if destination_registered:
        credentials["destination.example"] = "DEST_TOKEN"
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
        assert request.full_url == "https://destination.example/file"
        return FixtureResponse(BytesIO(b"payload"), headers, request.full_url, 200)

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)
    client = SourceHttpClient(
        HttpConfig(credentials), timeout=7.5, user_agent="fixture-client/2", retries=0
    )

    result = client.get("https://source.example/data")

    assert result.body == b"payload"
    assert result.url == "https://destination.example/file"
    assert len(requests) == 2
    assert requests[0].get_header("Authorization") == "Bearer source-secret"
    assert requests[1].get_header("Authorization") == (
        "Bearer destination-secret" if destination_registered else None
    )
    for request in requests:
        assert request.timeout == 7.5
        assert request.get_header("User-agent") == "fixture-client/2"


def test_caller_user_agent_is_preserved() -> None:
    transport = RecordingTransport([response()])
    client = SourceHttpClient(
        HttpConfig({}), user_agent="default/1", transport=transport
    )

    client.get("https://example.com", headers={"User-Agent": "configured/2"})

    assert transport.requests[0].get_header("User-agent") == "configured/2"


@pytest.mark.parametrize("name", ["Authorization", "authorization", "Cookie"])
def test_pack_credentials_are_rejected(name: str) -> None:
    client = SourceHttpClient(HttpConfig({}), transport=RecordingTransport([]))

    with pytest.raises(ValueError, match="credential header"):
        client.get("https://example.com", headers={name: "secret"})


def test_embedded_url_credentials_are_rejected() -> None:
    client = SourceHttpClient(HttpConfig({}), transport=RecordingTransport([]))

    with pytest.raises(ValueError, match="embedded URL credentials"):
        client.get("https://user:pass@example.com/app")


def test_redirect_limit_is_ten(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[Request] = []

    class FixtureResponse(addinfourl):
        msg = "fixture response"

    def open_fixture(
        handler: urllib.request.HTTPSHandler, request: Request
    ) -> FixtureResponse:
        requests.append(request)
        headers = Message()
        redirect_number = int(request.full_url.rsplit("/", 1)[-1])
        headers["Location"] = f"https://example.com/{redirect_number + 1}"
        return FixtureResponse(BytesIO(), headers, request.full_url, 302)

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)

    with pytest.raises(HttpError, match="after 1 attempts"):
        SourceHttpClient(HttpConfig({}), retries=0).get("https://example.com/0")

    assert len(requests) == 11
