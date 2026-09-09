from __future__ import annotations

import json
import urllib.error
import urllib.request
from email.message import Message
from io import BytesIO
from typing import TYPE_CHECKING
from urllib.response import addinfourl

import pytest

from omnipack.http import (
    METADATA_MAX_BYTES,
    PROBE_BYTES,
    HttpClient,
    HttpConfig,
    HttpError,
    HttpResponse,
    redact_url,
)

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


def test_metadata_uses_the_live_response_limit() -> None:
    transport = RecordingTransport([response()])
    client = HttpClient(HttpConfig({}), transport=transport)

    client.get_metadata("https://example.com/releases")

    assert transport.requests[0].method == "GET"
    assert transport.max_bytes == [METADATA_MAX_BYTES]


def test_request_gate_covers_each_retry_attempt() -> None:
    transport = RecordingTransport([OSError("temporary"), response()])
    gated: list[str] = []
    client = HttpClient(
        HttpConfig({}),
        retries=1,
        transport=transport,
        request_gate=gated.append,
    )

    client.get_metadata("https://example.com/releases")

    assert gated == [
        "https://example.com/releases",
        "https://example.com/releases",
    ]


def test_metadata_rejects_an_oversized_real_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixtureResponse(addinfourl):
        msg = "fixture response"

    def open_fixture(
        handler: urllib.request.HTTPSHandler, request: Request
    ) -> FixtureResponse:
        return FixtureResponse(
            BytesIO(b"x" * (METADATA_MAX_BYTES + 1)),
            Message(),
            request.full_url,
            200,
        )

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)

    with pytest.raises(HttpError, match="exceeds 10485760 bytes"):
        HttpClient(HttpConfig({}), retries=0).get_metadata("https://example.com/data")


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
        HttpClient(HttpConfig({}), sleep=lambda _: None, transport=retry_transport)
        .get_metadata("https://example.com")
        .body
        == b"ok"
    )
    with pytest.raises(HttpError, match="after 1 attempts"):
        HttpClient(HttpConfig({}), transport=fail_transport).get_metadata(
            "https://example.com"
        )

    assert len(retry_transport.requests) == 2
    assert len(fail_transport.requests) == 1


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


def test_caller_user_agent_is_preserved() -> None:
    transport = RecordingTransport([response()])
    client = HttpClient(HttpConfig({}), user_agent="default/1", transport=transport)

    client.get("https://example.com", headers={"User-Agent": "configured/2"})

    assert transport.requests[0].get_header("User-agent") == "configured/2"


@pytest.mark.parametrize("name", ["Authorization", "authorization", "Cookie"])
def test_pack_credentials_are_rejected(name: str) -> None:
    client = HttpClient(HttpConfig({}), transport=RecordingTransport([]))

    with pytest.raises(ValueError, match="credential header"):
        client.get("https://example.com", headers={name: "secret"})


def test_embedded_url_credentials_are_rejected() -> None:
    client = HttpClient(HttpConfig({}), transport=RecordingTransport([]))

    with pytest.raises(ValueError, match="embedded URL credentials"):
        client.get("https://user:pass@example.com/app")


def test_probe_reads_only_prefix_and_closes_ignored_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[Request] = []
    streams: list[TrackingBody] = []

    class TrackingBody(BytesIO):
        def __init__(self, body: bytes) -> None:
            super().__init__(body)
            self.read_sizes: list[int | None] = []

        def read(self, size: int | None = -1) -> bytes:
            self.read_sizes.append(size)
            return super().read(size)

    class FixtureResponse(addinfourl):
        msg = "fixture response"

    def open_fixture(
        handler: urllib.request.HTTPSHandler, request: Request
    ) -> FixtureResponse:
        requests.append(request)
        body = TrackingBody(b"x" * (PROBE_BYTES * 4))
        streams.append(body)
        return FixtureResponse(body, Message(), request.full_url, 200)

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)

    result = HttpClient(HttpConfig({}), retries=0).probe("https://example.com/app.apk")

    assert result.status == 200
    assert len(result.body) == PROBE_BYTES
    assert requests[0].method == "GET"
    assert requests[0].get_header("Range") == f"bytes=0-{PROBE_BYTES - 1}"
    assert streams[0].read_sizes == [PROBE_BYTES]
    assert streams[0].closed


@pytest.mark.parametrize("status", [200, 206])
def test_probe_accepts_nonempty_success_from_injected_transport(status: int) -> None:
    transport = RecordingTransport(
        [HttpResponse("https://cdn.example/app.apk", status, Message(), b"prefix")]
    )

    result = HttpClient(HttpConfig({}), transport=transport).probe(
        "https://example.com/app.apk"
    )

    assert result.body == b"prefix"
    assert transport.requests[0].get_header("Range") == "bytes=0-1023"
    assert transport.max_bytes == [PROBE_BYTES]


def test_probe_rejects_empty_or_unexpected_responses() -> None:
    client = HttpClient(
        HttpConfig({}),
        transport=RecordingTransport(
            [
                HttpResponse("https://example.com", 200, Message(), b""),
                HttpResponse("https://example.com", 204, Message(), b"prefix"),
            ]
        ),
    )

    with pytest.raises(HttpError, match="empty response"):
        client.probe("https://example.com/empty")
    with pytest.raises(HttpError, match="status 204"):
        client.probe("https://example.com/no-content")


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
        HttpClient(HttpConfig({}), retries=0).probe("https://example.com/0")

    assert len(requests) == 11


def test_diagnostic_urls_redact_credentials_and_query_values() -> None:
    assert redact_url("https://user:pass@example.com/app?q=secret&flag=#part") == (
        "https://example.com/app?q=REDACTED&flag=REDACTED#part"
    )
    transport = RecordingTransport([urllib.error.URLError("down")])

    with pytest.raises(HttpError) as raised:
        HttpClient(HttpConfig({}), retries=0, transport=transport).get_metadata(
            "https://example.com/app?token=secret"
        )

    message = str(raised.value)
    assert "secret" not in message
    assert "token=REDACTED" in message
