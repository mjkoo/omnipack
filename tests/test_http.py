from __future__ import annotations

import json
import urllib.error
import urllib.request
from email.message import Message
from io import BytesIO
from typing import TYPE_CHECKING
from urllib.response import addinfourl

import pytest

from obtainium_pack.http import HttpClient, HttpConfig, HttpError, HttpResponse

if TYPE_CHECKING:
    from pathlib import Path
    from urllib.request import Request


class RecordingTransport:
    def __init__(self, outcomes: list[HttpResponse | Exception]) -> None:
        self.outcomes = iter(outcomes)
        self.requests: list[Request] = []

    def __call__(
        self, request: Request, timeout: float, max_bytes: int | None
    ) -> HttpResponse:
        self.requests.append(request)
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


def test_head_method_and_response_metadata_are_available() -> None:
    headers = Message()
    headers["Content-Length"] = "42"
    transport = RecordingTransport(
        [HttpResponse("https://example.com/file", 200, headers, b"")]
    )
    client = HttpClient(HttpConfig({}), transport=transport)

    result = client.get("https://example.com/file", method="HEAD")

    assert transport.requests[0].method == "HEAD"
    assert result.status == 200
    assert result.headers["Content-Length"] == "42"


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
        HttpConfig({}),
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
    client = HttpClient(
        HttpConfig({}), retries=2, sleep=lambda _: None, transport=transport
    )

    with pytest.raises(HttpError, match="after 3 attempts"):
        client.get("https://example.com/data")


@pytest.mark.parametrize("token", [None, ""])
def test_unset_or_empty_credentials_leave_request_unauthenticated(
    monkeypatch: pytest.MonkeyPatch, token: str | None
) -> None:
    if token is None:
        monkeypatch.delenv("REGISTERED_TOKEN", raising=False)
    else:
        monkeypatch.setenv("REGISTERED_TOKEN", token)
    transport = RecordingTransport([response()])
    client = HttpClient(
        HttpConfig({"api.example.com": "REGISTERED_TOKEN"}), transport=transport
    )

    client.get("https://API.EXAMPLE.COM/data")

    assert transport.requests[0].get_header("Authorization") is None


def test_credentials_match_exact_host_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REGISTERED_TOKEN", "secret")
    transport = RecordingTransport([response()])
    client = HttpClient(
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
    client = HttpClient(
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
    client = HttpClient(
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
    client = HttpClient(HttpConfig({"source.example": "SOURCE_TOKEN"}))

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
    client = HttpClient(
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
