from __future__ import annotations

import hashlib
import json
from email.message import Message
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from omnipack.http import HttpConfig, HttpError, HttpResponse
from omnipack.live_http import LiveHttpClient

if TYPE_CHECKING:
    from urllib.request import Request


class Clock:
    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def time(self) -> float:
        return 1_000.0 + self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class Transport:
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


def response(
    status: int = 200,
    *,
    url: str = "https://api.github.com/repos/o/r/releases",
    body: bytes = b"[]",
    headers: dict[str, str] | None = None,
) -> HttpResponse:
    message = Message()
    for name, value in (headers or {}).items():
        message[name] = value
    return HttpResponse(url, status, message, body)


def client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcomes: list[HttpResponse | Exception],
    *,
    clock: Clock | None = None,
    max_server_wait: float = 60.0,
) -> tuple[LiveHttpClient, Transport, Clock]:
    monkeypatch.setenv("GH_TOKEN", "secret")
    fake_clock = clock or Clock()
    transport = Transport(outcomes)
    live = LiveHttpClient(
        HttpConfig({"api.github.com": "GH_TOKEN"}),
        cache_dir=tmp_path,
        clock=fake_clock.monotonic,
        wall_clock=fake_clock.time,
        sleep=fake_clock.sleep,
        transport=transport,
        max_server_wait=max_server_wait,
    )
    return live, transport, fake_clock


def test_github_metadata_requires_configured_available_token_before_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = Transport([response()])
    live = LiveHttpClient(HttpConfig({}), cache_dir=tmp_path, transport=transport)

    with pytest.raises(HttpError, match="authenticated GitHub metadata"):
        live.get_metadata("https://api.github.com/repos/o/r/releases")

    assert transport.requests == []


def test_requests_to_each_host_are_spaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live, transport, clock = client(
        tmp_path,
        monkeypatch,
        [response(), response(url="https://api.github.com/repos/a/b/releases")],
    )

    live.get_metadata("https://api.github.com/repos/o/r/releases")
    live.get_metadata("https://api.github.com/repos/a/b/releases")

    assert len(transport.requests) == 2
    assert clock.sleeps == [2.0]


def test_conditional_304_uses_validated_cached_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://api.github.com/repos/o/r/releases?per_page=100"
    first, _, _ = client(
        tmp_path,
        monkeypatch,
        [response(body=b'[{"tag_name":"v1"}]', headers={"ETag": '"one"'})],
    )
    first.get_metadata(url)
    second, transport, _ = client(tmp_path, monkeypatch, [response(304, body=b"")])

    result = second.get_metadata(url)

    assert result.status == 200
    assert result.body == b'[{"tag_name":"v1"}]'
    assert transport.requests[0].get_header("If-none-match") == '"one"'


def test_network_failure_never_accepts_stale_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://api.github.com/repos/o/r/releases?per_page=100"
    first, _, _ = client(
        tmp_path, monkeypatch, [response(body=b"old", headers={"ETag": '"one"'})]
    )
    first.get_metadata(url)
    second, _, _ = client(
        tmp_path,
        monkeypatch,
        [OSError("offline"), OSError("offline"), OSError("offline")],
    )

    with pytest.raises(HttpError, match="failed after 3 attempts"):
        second.get_metadata(url)


def test_rate_limit_suppresses_host_without_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live, transport, clock = client(
        tmp_path,
        monkeypatch,
        [
            response(429, headers={"Retry-After": "5"}),
            response(url="https://unrelated.example/page"),
        ],
    )

    with pytest.raises(HttpError, match="rate limited"):
        live.get_metadata("https://api.github.com/repos/o/r/releases")
    with pytest.raises(HttpError, match="suppressed"):
        live.get_metadata("https://api.github.com/repos/a/b/releases")

    assert live.get_metadata("https://unrelated.example/page").status == 200
    assert len(transport.requests) == 2
    assert clock.sleeps == []


def test_server_wait_beyond_cap_suppresses_without_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live, transport, clock = client(
        tmp_path,
        monkeypatch,
        [response(503, headers={"Retry-After": "120"})],
        max_server_wait=60,
    )

    with pytest.raises(HttpError, match="rate limited"):
        live.get_metadata("https://api.github.com/repos/o/r/releases")

    assert len(transport.requests) == 1
    assert clock.sleeps == []


def test_transient_retry_after_is_honored_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live, transport, clock = client(
        tmp_path,
        monkeypatch,
        [response(503, headers={"Retry-After": "5"}), response()],
    )

    assert live.get_metadata("https://api.github.com/repos/o/r/releases").status == 200

    assert len(transport.requests) == 2
    assert clock.sleeps == [5.0]


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_nonfinite_server_wait_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    live, transport, clock = client(
        tmp_path,
        monkeypatch,
        [response(503, headers={"Retry-After": value}), response()],
    )

    assert live.get_metadata("https://api.github.com/repos/o/r/releases").status == 200

    assert len(transport.requests) == 2
    assert clock.sleeps == [2.0]


def test_successful_exhausting_response_suppresses_next_host_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live, transport, _ = client(
        tmp_path,
        monkeypatch,
        [response(headers={"X-RateLimit-Remaining": "0"})],
    )

    assert live.get_metadata("https://api.github.com/repos/o/r/releases").status == 200
    with pytest.raises(HttpError, match="suppressed"):
        live.get_metadata("https://api.github.com/repos/a/b/releases")

    assert len(transport.requests) == 1


@pytest.mark.parametrize("corruption", ["malformed", "mismatched"])
def test_corrupt_or_mismatched_cache_is_not_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    url = "https://api.github.com/repos/o/r/releases?per_page=100"
    first, _, _ = client(tmp_path, monkeypatch, [response(headers={"ETag": '"one"'})])
    first.get_metadata(url)
    paths = list(tmp_path.glob("*.json"))
    assert len(paths) == 1
    expected_key = hashlib.sha256(
        json.dumps([url, []], separators=(",", ":")).encode()
    ).hexdigest()
    assert paths[0].name == f"{expected_key}.json"
    document = json.loads(paths[0].read_text())
    assert set(document) == {
        "version",
        "url",
        "headers",
        "etag",
        "last_modified",
        "body",
    }
    assert document["url"] == url
    assert "secret" not in paths[0].read_text()
    assert "GH_TOKEN" not in paths[0].read_text()
    monkeypatch.setenv("GH_TOKEN", "replacement-token")
    assert first._cache_path(url, None) == paths[0]
    document["url"] = "https://evil.invalid"
    paths[0].write_text(
        "not json" if corruption == "malformed" else json.dumps(document)
    )
    live, transport, _ = client(tmp_path, monkeypatch, [response(body=b"fresh")])
    assert live.get_metadata(url).body == b"fresh"
    assert transport.requests[0].get_header("If-none-match") is None
    assert transport.requests[0].get_header("If-modified-since") is None


def test_final_transient_excessive_wait_suppresses_host(tmp_path, monkeypatch) -> None:
    live, transport, clock = client(
        tmp_path,
        monkeypatch,
        [response(503), response(503), response(503, headers={"Retry-After": "120"})],
    )
    with pytest.raises(HttpError, match="rate limited"):
        live.get_metadata("https://api.github.com/repos/o/r/releases")
    with pytest.raises(HttpError, match="suppressed"):
        live.get_metadata("https://api.github.com/repos/a/b/releases")
    assert len(transport.requests) == 3
    assert clock.sleeps == [2.0, 2.0]


@pytest.mark.parametrize("operation", ["get_metadata", "probe"])
def test_final_retry_delay_applies_to_next_same_host_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    live, transport, clock = client(
        tmp_path,
        monkeypatch,
        [
            response(503),
            response(503),
            response(503, headers={"Retry-After": "30"}),
            response(url="https://unrelated.example/page"),
            response(url="https://api.github.com/repos/a/b/releases"),
        ],
    )
    with pytest.raises(HttpError, match="after 3 attempts"):
        getattr(live, operation)("https://api.github.com/repos/o/r/releases")

    assert clock.now == 104.0
    assert live.get_metadata("https://unrelated.example/page").status == 200
    assert clock.now == 104.0
    clock.now += 10.0
    assert live.get_metadata("https://api.github.com/repos/a/b/releases").status == 200
    assert clock.now == 134.0
    assert clock.sleeps == [2.0, 2.0, 20.0]
    assert len(transport.requests) == 5


def test_permanent_failure_is_not_retried(tmp_path, monkeypatch) -> None:
    from urllib.error import HTTPError

    url = "https://example.com/missing"
    live, transport, _ = client(
        tmp_path, monkeypatch, [HTTPError(url, 404, "missing", Message(), None)] * 3
    )
    with pytest.raises(HttpError, match="after 1 attempts"):
        live.get_metadata(url)
    assert len(transport.requests) == 1


def test_transient_acquisition_retries_then_succeeds(tmp_path, monkeypatch) -> None:
    live, transport, clock = client(
        tmp_path, monkeypatch, [OSError("temporary"), response()]
    )
    assert live.get_metadata("https://api.github.com/repos/o/r/releases").status == 200
    assert len(transport.requests) == 2
    assert clock.sleeps == [2.0]


def test_oversized_real_metadata_is_not_retried(tmp_path, monkeypatch) -> None:
    from io import BytesIO
    from urllib.request import HTTPSHandler
    from urllib.response import addinfourl

    from omnipack.http import METADATA_MAX_BYTES

    requests = []

    class FixtureResponse(addinfourl):
        msg = "fixture"

    def open_fixture(handler, request):
        requests.append(request)
        return FixtureResponse(
            BytesIO(b"x" * (METADATA_MAX_BYTES + 1)), Message(), request.full_url, 200
        )

    monkeypatch.setattr(HTTPSHandler, "https_open", open_fixture)
    live = LiveHttpClient(HttpConfig({}), cache_dir=tmp_path, minimum_interval=0)
    with pytest.raises(HttpError, match="exceeds"):
        live.get_metadata("https://example.com/oversized")
    assert len(requests) == 1


@pytest.mark.parametrize("operation", ["get_metadata", "probe"])
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_real_redirects_are_paced_and_bodies_closed_without_draining(
    tmp_path, monkeypatch, operation, status
) -> None:
    from io import BytesIO
    from urllib.request import HTTPSHandler
    from urllib.response import addinfourl

    from omnipack.http import METADATA_MAX_BYTES, PROBE_BYTES

    clock = Clock()
    requests = []
    streams = []

    class Body(BytesIO):
        def __init__(self, data):
            super().__init__(data)
            self.read_sizes = []

        def read(self, size=-1):
            self.read_sizes.append(size)
            return super().read(size)

    class FixtureResponse(addinfourl):
        msg = "fixture"

    def open_fixture(handler, request):
        requests.append((request, clock.now))
        redirect = request.full_url.endswith("/start")
        headers = Message()
        if redirect:
            headers["Location"] = "https://example.com/end"
        body = Body(b"x" * 100_000 if redirect else b"payload")
        streams.append(body)
        return FixtureResponse(
            body, headers, request.full_url, status if redirect else 200
        )

    monkeypatch.setattr(HTTPSHandler, "https_open", open_fixture)
    live = LiveHttpClient(
        HttpConfig({}), cache_dir=tmp_path, clock=clock.monotonic, sleep=clock.sleep
    )
    assert getattr(live, operation)("https://example.com/start").body == b"payload"
    assert [time for _, time in requests] == [100.0, 102.0]
    assert streams[0].read_sizes == []
    assert streams[1].read_sizes == [
        PROBE_BYTES if operation == "probe" else METADATA_MAX_BYTES + 1
    ]
    assert all(stream.closed for stream in streams)
