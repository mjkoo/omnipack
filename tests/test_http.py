from __future__ import annotations

import http.client
import urllib.error
import urllib.request
from email.message import Message
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Self
from urllib.response import addinfourl

import pytest

from omnipack.http import (
    DeadlineExceeded,
    HttpClient,
    HttpError,
    HttpResponse,
    HttpStatusError,
    RateLimitError,
    TransientHttpError,
    failure_reason,
    redact_url,
)

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


def test_get_stops_before_a_request_once_the_deadline_has_passed() -> None:
    transport = RecordingTransport([response()])

    with pytest.raises(DeadlineExceeded):
        HttpClient(transport=transport, clock=lambda: 100.0).get(
            "https://example.com/data", deadline=100.0
        )

    assert transport.requests == []


def test_get_abandons_a_retry_wait_that_outlasts_the_deadline() -> None:
    sleeps: list[float] = []
    transport = RecordingTransport([urllib.error.URLError("temporary"), response()])
    client = HttpClient(
        backoff=30.0, sleep=sleeps.append, transport=transport, clock=lambda: 50.0
    )

    with pytest.raises(DeadlineExceeded):
        client.get("https://example.com/data", deadline=60.0)

    assert sleeps == []
    assert len(transport.requests) == 1


def test_exhausted_retries_raise_http_error() -> None:
    transport = RecordingTransport([urllib.error.URLError("down")] * 3)
    client = HttpClient(retries=2, sleep=lambda _: None, transport=transport)

    with pytest.raises(HttpError, match="after 3 attempts"):
        client.get("https://example.com/data")


def test_exhausted_retries_name_the_last_attempts_status_and_detail() -> None:
    url = "https://example.com/data"
    rate_limited = urllib.error.HTTPError(url, 429, "limited", Message(), None)
    limited = RecordingTransport([TimeoutError("timed out"), rate_limited])
    timed_out = RecordingTransport([rate_limited, TimeoutError("timed out")])

    with pytest.raises(TransientHttpError) as last_limited:
        HttpClient(retries=1, sleep=lambda _: None, transport=limited).get(url)
    with pytest.raises(TransientHttpError) as last_timed_out:
        HttpClient(retries=1, sleep=lambda _: None, transport=timed_out).get(url)

    assert last_limited.value.status == 429
    assert last_limited.value.detail == "HTTP Error 429: limited"
    assert last_timed_out.value.status is None
    assert last_timed_out.value.detail == "timed out"
    assert "failed after 2 attempts" in str(last_timed_out.value)


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


def test_nontransient_status_preserves_attempt_count_after_a_retry() -> None:
    url = "https://example.com/data"
    transport = RecordingTransport(
        [
            OSError("connection interrupted"),
            urllib.error.HTTPError(url, 403, "forbidden", Message(), None),
        ]
    )

    with pytest.raises(HttpStatusError, match="HTTP 403 after 2 attempts") as caught:
        HttpClient(transport=transport, sleep=lambda _: None).get(url)

    assert caught.value.status == 403
    assert len(transport.requests) == 2


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


@pytest.mark.parametrize("status", [400, 401, 410, 422])
def test_every_nontransient_http_status_is_typed(status: int) -> None:
    url = "https://example.com/data"
    transport = RecordingTransport(
        [urllib.error.HTTPError(url, status, "rejected", Message(), None)]
    )

    with pytest.raises(
        HttpStatusError, match=f"returned HTTP {status} after 1 attempts"
    ) as caught:
        HttpClient(transport=transport).get(url)

    assert caught.value.status == status
    assert len(transport.requests) == 1


def test_given_headers_are_sent_and_may_replace_the_default_user_agent() -> None:
    transport = RecordingTransport([response(), response(), response()])
    client = HttpClient(transport=transport)

    client.get("https://example.com/data")
    client.get("https://example.com/data", headers={"user-agent": "Obtainium/1.0"})
    client.get("https://example.com/data", headers={"Referer": "https://example.com"})

    default, replaced, added = transport.requests
    assert default.get_header("User-agent") == "omnipack/0.1"
    assert replaced.get_header("User-agent") == "Obtainium/1.0"
    assert added.get_header("User-agent") == "omnipack/0.1"
    assert added.get_header("Referer") == "https://example.com"


def test_a_credential_is_sent_as_an_unredirected_authorization_header() -> None:
    transport = RecordingTransport([response(), response()])
    client = HttpClient(transport=transport)

    client.get("https://api.example/data", credential="Bearer secret")
    client.get("https://api.example/data")

    credentialed, plain = transport.requests
    assert credentialed.unredirected_hdrs == {"Authorization": "Bearer secret"}
    assert "Authorization" not in credentialed.headers
    assert plain.get_header("Authorization") is None


@pytest.mark.parametrize("secret", ["se\ncret", "se€cret"])
def test_a_credential_outside_printable_ascii_is_refused_without_echoing_it(
    secret: str,
) -> None:
    transport = RecordingTransport([response()])
    client = HttpClient(transport=transport)

    with pytest.raises(ValueError, match="credential") as raised:
        client.get("https://api.example/data", credential=f"Bearer {secret}")

    assert secret not in str(raised.value)
    assert transport.requests == []


@pytest.mark.parametrize("deadline", [None, 60.0])
def test_a_credential_is_not_forwarded_on_a_redirect(
    monkeypatch: pytest.MonkeyPatch, deadline: float | None
) -> None:
    requests: list[Request] = []

    class FixtureResponse(addinfourl):
        msg = "fixture response"

    def open_fixture(
        handler: urllib.request.HTTPSHandler, request: Request
    ) -> FixtureResponse:
        requests.append(request)
        headers = Message()
        if request.full_url == "https://api.example/old":
            headers["Location"] = "https://api.example/new"
            return FixtureResponse(BytesIO(b""), headers, request.full_url, 301)
        return FixtureResponse(BytesIO(b"payload"), headers, request.full_url, 200)

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)

    result = HttpClient(retries=0, clock=lambda: 0.0).get(
        "https://api.example/old", credential="Bearer secret", deadline=deadline
    )

    assert result.body == b"payload"
    first, redirected = requests
    assert first.get_header("Authorization") == "Bearer secret"
    assert redirected.full_url == "https://api.example/new"
    assert redirected.get_header("Authorization") is None


class FakeStream:
    """A streamed response: chunks served one per `read1`, then end of body.

    `length` is what a urllib response reports still owed by Content-Length.
    """

    def __init__(
        self,
        chunks: list[bytes],
        *,
        url: str = "https://example.com/file",
        status: int = 200,
        fail_after: Exception | None = None,
        length: int | None = None,
    ) -> None:
        self.chunks = list(chunks)
        self.url = url
        self.status = status
        self.headers = Message()
        self.fail_after = fail_after
        self.length = length

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read1(self, size: int = -1) -> bytes:
        if self.chunks:
            return self.chunks.pop(0)
        if self.fail_after is not None:
            raise self.fail_after
        return b""


class StreamingTransport:
    def __init__(self, outcomes: list[FakeStream | Exception]) -> None:
        self.outcomes = iter(outcomes)
        self.requests: list[Request] = []
        self.timeouts: list[float] = []

    def __call__(self, request: Request, timeout: float) -> FakeStream:
        self.requests.append(request)
        self.timeouts.append(timeout)
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def http_error(status: int, **headers: str) -> urllib.error.HTTPError:
    message = Message()
    for name, value in headers.items():
        message[name.replace("_", "-")] = value
    return urllib.error.HTTPError(
        "https://example.com/file", status, "error", message, None
    )


def trickle(now: list[float], chunks: list[bytes]) -> FakeStream:
    """A stream whose every read takes ten seconds on the `now` clock."""

    class Trickle(FakeStream):
        def read1(self, size: int = -1) -> bytes:
            now[0] += 10
            return super().read1(size)

    return Trickle(chunks)


def test_download_writes_every_chunk(tmp_path: Path) -> None:
    transport = StreamingTransport([FakeStream([b"abc", b"def", b"g"])])
    destination = tmp_path / "out.bin"

    HttpClient(stream_transport=transport).download(
        "https://example.com/file", destination
    )

    assert destination.read_bytes() == b"abcdefg"


def test_download_retries_a_transient_failure_from_the_start(tmp_path: Path) -> None:
    sleeps: list[float] = []
    transport = StreamingTransport(
        [
            FakeStream([b"par"], fail_after=OSError("reset")),
            FakeStream([b"whole"]),
        ]
    )
    destination = tmp_path / "out.bin"

    HttpClient(stream_transport=transport, sleep=sleeps.append).download(
        "https://example.com/file", destination
    )

    assert destination.read_bytes() == b"whole"
    assert sleeps == [0.5]


def test_download_cut_short_by_the_server_is_retried_then_reported(
    tmp_path: Path,
) -> None:
    transport = StreamingTransport(
        [FakeStream([b"par"], length=4), FakeStream([b"par"], length=4)]
    )
    destination = tmp_path / "out.bin"

    with pytest.raises(TransientHttpError):
        HttpClient(
            retries=1, stream_transport=transport, sleep=lambda _: None
        ).download("https://example.com/file", destination)

    assert len(transport.requests) == 2
    assert not destination.exists()


def test_download_of_a_missing_file_is_a_typed_status_and_leaves_nothing(
    tmp_path: Path,
) -> None:
    transport = StreamingTransport([http_error(404)])
    destination = tmp_path / "out.bin"

    with pytest.raises(HttpStatusError) as caught:
        HttpClient(stream_transport=transport).download(
            "https://example.com/file", destination
        )

    assert caught.value.status == 404
    assert not destination.exists()


def test_download_sleeps_until_a_rate_limit_resets_then_retries_once(
    tmp_path: Path,
) -> None:
    sleeps: list[float] = []
    transport = StreamingTransport(
        [
            http_error(403, X_RateLimit_Remaining="0", X_RateLimit_Reset="1060"),
            FakeStream([b"ok"]),
        ]
    )

    HttpClient(
        stream_transport=transport,
        sleep=sleeps.append,
        wall_clock=lambda: 1000.0,
    ).download("https://example.com/file", tmp_path / "out.bin", deadline=None)

    assert sleeps == [60.0]
    assert len(transport.requests) == 2


def test_download_honours_retry_after_on_429(tmp_path: Path) -> None:
    sleeps: list[float] = []
    transport = StreamingTransport(
        [http_error(429, Retry_After="7"), FakeStream([b"x"])]
    )

    HttpClient(stream_transport=transport, sleep=sleeps.append).download(
        "https://example.com/file", tmp_path / "out.bin"
    )

    assert sleeps == [7.0]


@pytest.mark.parametrize(
    "error",
    [
        http_error(429, Retry_After="121"),
        http_error(403, X_RateLimit_Remaining="0", X_RateLimit_Reset="8200"),
    ],
)
def test_download_fails_at_once_when_a_rate_limit_lifts_too_late(
    tmp_path: Path, error: urllib.error.HTTPError
) -> None:
    sleeps: list[float] = []
    transport = StreamingTransport([error])

    with pytest.raises(RateLimitError) as caught:
        HttpClient(
            stream_transport=transport,
            sleep=sleeps.append,
            wall_clock=lambda: 1000.0,
        ).download("https://example.com/file", tmp_path / "out.bin")

    assert sleeps == []
    assert len(transport.requests) == 1
    assert failure_reason(caught.value).startswith(f"HTTP {error.code}: rate limit")


def test_download_abandons_a_rate_limit_wait_that_outlasts_the_deadline(
    tmp_path: Path,
) -> None:
    sleeps: list[float] = []
    transport = StreamingTransport(
        [http_error(403, X_RateLimit_Remaining="0", X_RateLimit_Reset="1100")]
    )

    with pytest.raises(DeadlineExceeded):
        HttpClient(
            stream_transport=transport,
            sleep=sleeps.append,
            clock=lambda: 50.0,
            wall_clock=lambda: 1000.0,
        ).download("https://example.com/file", tmp_path / "out.bin", deadline=100.0)

    assert sleeps == []
    assert len(transport.requests) == 1


def test_download_stops_a_trickling_body_at_the_deadline(tmp_path: Path) -> None:
    now = [0.0]
    transport = StreamingTransport([trickle(now, [b"a", b"b", b"c"])])
    destination = tmp_path / "out.bin"

    with pytest.raises(DeadlineExceeded):
        HttpClient(stream_transport=transport, clock=lambda: now[0]).download(
            "https://example.com/file", destination, deadline=15.0
        )

    assert now[0] == 20.0
    assert not destination.exists()


def test_get_stops_a_trickling_page_at_the_deadline() -> None:
    now = [0.0]
    transport = StreamingTransport([trickle(now, [b"a", b"b", b"c"])])

    with pytest.raises(DeadlineExceeded):
        HttpClient(stream_transport=transport, clock=lambda: now[0]).get(
            "https://example.com/file", deadline=15.0
        )

    assert now[0] == 20.0


def test_get_with_a_deadline_reads_the_whole_page() -> None:
    transport = StreamingTransport([FakeStream([b"o", b"k"])])

    response = HttpClient(stream_transport=transport, clock=lambda: 0.0).get(
        "https://example.com/file", deadline=15.0
    )

    assert response.body == b"ok"


def test_download_bounds_each_attempt_by_the_remaining_time(tmp_path: Path) -> None:
    transport = StreamingTransport([FakeStream([b"x"])])

    HttpClient(stream_transport=transport, timeout=30.0, clock=lambda: 90.0).download(
        "https://example.com/file", tmp_path / "out.bin", deadline=100.0
    )

    assert transport.timeouts == [10.0]
