from __future__ import annotations

import json
from email.message import Message
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from obtainium_pack.http import HttpConfig, HttpError, HttpResponse
from obtainium_pack.live_http import LiveHttpClient

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

    with pytest.raises(HttpError, match="failed after 1 attempts"):
        second.get_metadata(url)


def test_rate_limit_suppresses_host_without_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live, transport, clock = client(
        tmp_path,
        monkeypatch,
        [response(429, headers={"Retry-After": "5"})],
    )

    with pytest.raises(HttpError, match="rate limited"):
        live.get_metadata("https://api.github.com/repos/o/r/releases")
    with pytest.raises(HttpError, match="suppressed"):
        live.get_metadata("https://api.github.com/repos/a/b/releases")

    assert len(transport.requests) == 1
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


def test_corrupt_or_mismatched_cache_is_not_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "bad.json").write_text(json.dumps({"url": "https://evil.invalid"}))
    live, _, _ = client(tmp_path, monkeypatch, [response(304, body=b"")])

    with pytest.raises(HttpError, match="without a valid cached response"):
        live.get_metadata("https://api.github.com/repos/o/r/releases")
