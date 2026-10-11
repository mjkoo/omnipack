from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from email.message import Message
from io import BytesIO
from pathlib import Path
from urllib.request import Request
from urllib.response import addinfourl

import pytest

from omnipack import live_check
from omnipack.cli import main
from omnipack.http import HttpClient, HttpResponse
from omnipack.live_check import (
    NOT_CHECKED,
    REPORT,
    SUMMARY,
    check_live,
    render_summary,
    write_live_report,
)
from omnipack.report_model import Status

REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_USER_AGENT = "omnipack/0.1"
OBTAINIUM_SETTINGS = json.dumps(
    {"requestHeader": [{"requestHeader": "User-Agent: Obtainium/1.0"}]}
)


def entry(url: str, settings: object = "{}") -> dict[str, object]:
    return {"id": "fixture", "url": url, "additionalSettings": settings}


def write_packs(
    root: Path,
    single: list[dict[str, object]],
    dual: list[dict[str, object]] | None = None,
) -> None:
    (root / "dist").mkdir(exist_ok=True)
    for name, apps in (("single-screen.json", single), ("dual-screen.json", dual)):
        document = {"settings": {}, "apps": apps or []}
        (root / "dist" / name).write_text(json.dumps(document))


def http_error(url: str, status: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, status, "fixture", Message(), None)


class Transport:
    """Answer each URL with its outcomes in turn, repeating the last one, and
    record every request."""

    def __init__(self, outcomes: dict[str, list[object]]) -> None:
        self.outcomes = {url: iter(values) for url, values in outcomes.items()}
        self.last: dict[str, object] = {}
        self.requests: list[Request] = []

    def __call__(self, request: Request, timeout: float) -> HttpResponse:
        self.requests.append(request)
        url = request.full_url
        outcome = next(self.outcomes.get(url, iter(())), self.last.get(url, 200))
        self.last[url] = outcome
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, int)
        if outcome >= 400:
            raise http_error(url, outcome)
        return HttpResponse(url, outcome, Message(), b"")

    def urls(self) -> list[str]:
        return [request.full_url for request in self.requests]


def client(transport: Transport) -> HttpClient:
    return HttpClient(transport=transport, sleep=lambda _seconds: None)


def test_answering_projects_are_left_out_of_a_success_report(tmp_path: Path) -> None:
    write_packs(tmp_path, [entry("https://github.com/a/one")])
    transport = Transport({"https://github.com/a/one": [200]})

    report = check_live(tmp_path, http=client(transport))

    assert report == {"status": Status.SUCCESS, "unreachable": [], "inconclusive": []}
    assert transport.urls() == ["https://github.com/a/one"]


class FixtureResponse(addinfourl):
    msg = "fixture response"


def serve_https(
    monkeypatch: pytest.MonkeyPatch, routes: dict[str, tuple[int, str | None]]
) -> list[Request]:
    """Answer HTTPS requests through the real urllib opener from `routes`, a
    status and optional redirect target per URL, and record each request.

    A URL without a route goes through urllib's own handler, whose header
    validation runs before any connection; connecting fails the test.
    """
    requests: list[Request] = []
    real_open = urllib.request.HTTPSHandler.https_open

    def open_fixture(handler: urllib.request.HTTPSHandler, request: Request):
        requests.append(request)
        if request.full_url not in routes:
            return real_open(handler, request)
        status, location = routes[request.full_url]
        headers = Message()
        if location is not None:
            headers["Location"] = location
        return FixtureResponse(BytesIO(b""), headers, request.full_url, status)

    def refuse_connection(_connection: http.client.HTTPConnection) -> None:
        raise AssertionError("the test opened a real connection")

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", open_fixture)
    monkeypatch.setattr(http.client.HTTPSConnection, "connect", refuse_connection)
    return requests


def test_redirects_are_followed_to_the_final_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_packs(
        tmp_path,
        [
            entry("https://example.com/moved", OBTAINIUM_SETTINGS),
            entry("https://example.com/moved-away"),
        ],
    )
    requests = serve_https(
        monkeypatch,
        {
            "https://example.com/moved": (302, "https://example.com/new-home"),
            "https://example.com/new-home": (200, None),
            "https://example.com/moved-away": (302, "https://example.com/missing"),
            "https://example.com/missing": (404, None),
        },
    )

    report = check_live(tmp_path, http=HttpClient(sleep=lambda _seconds: None))

    assert report == {
        "status": Status.SUCCESS,
        "unreachable": [{"url": "https://example.com/moved-away", "status": 404}],
        "inconclusive": [],
    }
    assert [request.full_url for request in requests] == [
        "https://example.com/moved",
        "https://example.com/new-home",
        "https://example.com/moved-away",
        "https://example.com/missing",
    ]
    # The declared user agent rides both hops of its redirect.
    assert [request.get_header("User-agent") for request in requests[:2]] == [
        "Obtainium/1.0",
        "Obtainium/1.0",
    ]


def test_a_header_rejected_at_send_time_leaves_only_that_url_inconclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    injected = json.dumps(
        {"requestHeader": [{"requestHeader": "X-Test: a\r\nInjected: b"}]}
    )
    write_packs(
        tmp_path,
        [entry("https://bad.example/app", injected), entry("https://github.com/a/ok")],
    )
    requests = serve_https(monkeypatch, {"https://github.com/a/ok": (200, None)})

    report = check_live(tmp_path, http=HttpClient(sleep=lambda _seconds: None))

    (finding,) = report["inconclusive"]
    assert finding["url"] == "https://bad.example/app"
    assert finding["reason"].startswith("Invalid header value")
    assert report["unreachable"] == []
    assert [request.full_url for request in requests] == [
        "https://bad.example/app",
        "https://github.com/a/ok",
    ]


def test_404_and_410_are_unreachable_with_their_statuses(tmp_path: Path) -> None:
    write_packs(
        tmp_path,
        [entry("https://github.com/a/gone"), entry("https://github.com/a/removed")],
    )
    transport = Transport(
        {"https://github.com/a/gone": [404], "https://github.com/a/removed": [410]}
    )

    report = check_live(tmp_path, http=client(transport))

    assert report["unreachable"] == [
        {"url": "https://github.com/a/gone", "status": 404},
        {"url": "https://github.com/a/removed", "status": 410},
    ]
    assert report["inconclusive"] == []


def test_other_outcomes_are_inconclusive_with_their_cause(tmp_path: Path) -> None:
    write_packs(
        tmp_path,
        [
            entry("https://gitlab.com/a/private"),
            entry("https://github.com/a/limited"),
            entry("https://slow.example/app"),
        ],
    )
    transport = Transport(
        {
            "https://gitlab.com/a/private": [403],
            "https://github.com/a/limited": [429],
            "https://slow.example/app": [TimeoutError("timed out")],
        }
    )

    report = check_live(tmp_path, http=client(transport))

    assert report["status"] == Status.SUCCESS
    assert report["unreachable"] == []
    assert report["inconclusive"] == [
        {"url": "https://gitlab.com/a/private", "reason": "HTTP 403"},
        {"url": "https://github.com/a/limited", "reason": "HTTP 429"},
        {"url": "https://slow.example/app", "reason": "timed out"},
    ]
    # The 429 and the timeout were each retried before giving up.
    assert transport.urls().count("https://github.com/a/limited") == 3
    assert transport.urls().count("https://slow.example/app") == 3


def test_the_reason_names_the_last_attempts_status(tmp_path: Path) -> None:
    write_packs(tmp_path, [entry("https://flaky.example/app")])
    timeout = TimeoutError("timed out")
    transport = Transport({"https://flaky.example/app": [timeout, timeout, 503]})

    report = check_live(tmp_path, http=client(transport))

    assert report["inconclusive"] == [
        {"url": "https://flaky.example/app", "reason": "HTTP 503"}
    ]


def test_entry_request_headers_reach_the_request(tmp_path: Path) -> None:
    write_packs(
        tmp_path,
        [
            entry("https://emulator.example/download/", OBTAINIUM_SETTINGS),
            entry("https://github.com/a/plain", json.dumps({"trackOnly": False})),
        ],
    )
    transport = Transport({})

    check_live(tmp_path, http=client(transport))

    assert transport.urls() == [
        "https://emulator.example/download/",
        "https://github.com/a/plain",
    ]
    declared, plain = transport.requests
    assert declared.get_header("User-agent") == "Obtainium/1.0"
    assert plain.get_header("User-agent") == DEFAULT_USER_AGENT


def test_committed_dolphin_settings_send_the_obtainium_user_agent(
    tmp_path: Path,
) -> None:
    committed = json.loads((REPOSITORY / "dist/single-screen.json").read_bytes())
    dolphin = next(app for app in committed["apps"] if "dolphin-emu.org" in app["url"])
    assert isinstance(dolphin["additionalSettings"], str)
    write_packs(tmp_path, [dolphin])
    transport = Transport({})

    report = check_live(tmp_path, http=client(transport))

    assert report["inconclusive"] == []
    (request,) = transport.requests
    assert request.full_url == dolphin["url"]
    assert request.get_header("User-agent") == "Obtainium/1.0"


@pytest.mark.parametrize(
    ("settings", "problem"),
    [
        ("{not json", "additionalSettings is not valid JSON"),
        ("[]", "additionalSettings is not a JSON object"),
        ({"requestHeader": []}, "additionalSettings is not a JSON string"),
        (
            json.dumps({"requestHeader": "User-Agent: Obtainium/1.0"}),
            "requestHeader is not a list of objects",
        ),
        (
            json.dumps({"requestHeader": ["User-Agent: Obtainium/1.0"]}),
            "requestHeader is not a list of objects",
        ),
        (
            json.dumps({"requestHeader": [{"requestHeader": 1}]}),
            "requestHeader is not a list of objects",
        ),
        (
            json.dumps({"requestHeader": [{"requestHeader": "no colon here"}]}),
            "request header line 'no colon here' has no header name and colon",
        ),
        (
            json.dumps({"requestHeader": [{"requestHeader": ": value"}]}),
            "request header line ': value' has no header name and colon",
        ),
    ],
)
def test_malformed_settings_leave_only_that_url_inconclusive(
    tmp_path: Path, settings: object, problem: str
) -> None:
    write_packs(
        tmp_path,
        [entry("https://bad.example/app", settings), entry("https://github.com/a/ok")],
    )
    transport = Transport({})

    report = check_live(tmp_path, http=client(transport))

    (finding,) = report["inconclusive"]
    assert finding["url"] == "https://bad.example/app"
    assert problem in finding["reason"]
    assert transport.urls() == ["https://github.com/a/ok"]


def test_a_url_in_both_packs_or_twice_in_one_is_requested_and_listed_once(
    tmp_path: Path,
) -> None:
    gone = "https://github.com/a/gone"
    write_packs(
        tmp_path,
        [entry(gone, OBTAINIUM_SETTINGS), entry(gone)],
        [entry("https://github.com/a/dual-only"), entry(gone)],
    )
    transport = Transport({gone: [404]})

    report = check_live(tmp_path, http=client(transport))

    assert report["unreachable"] == [{"url": gone, "status": 404}]
    assert transport.urls() == [gone, "https://github.com/a/dual-only"]
    # The first entry in pack order supplies the headers.
    assert transport.requests[0].get_header("User-agent") == "Obtainium/1.0"


def test_spent_budget_starts_no_further_request(tmp_path: Path) -> None:
    urls = [f"https://github.com/a/app{index}" for index in range(4)]
    write_packs(tmp_path, [entry(url) for url in urls])
    transport = Transport({urls[1]: [404]})
    ticks: Iterator[float] = iter([0.0, 0.0, 600.0, 1200.0, 1500.0])

    report = check_live(tmp_path, http=client(transport), clock=lambda: next(ticks))

    assert transport.urls() == urls[:2]
    assert report["status"] == Status.SUCCESS
    assert report["unreachable"] == [{"url": urls[1], "status": 404}]
    assert report["inconclusive"] == [
        {"url": urls[2], "reason": NOT_CHECKED},
        {"url": urls[3], "reason": NOT_CHECKED},
    ]


def test_unusable_urls_are_inconclusive_and_the_rest_still_checked(
    tmp_path: Path,
) -> None:
    write_packs(
        tmp_path,
        [
            entry("https://user:secret@example.com/app"),
            entry("example.com/no-scheme"),
            entry("https://github.com/a/gone"),
        ],
    )
    transport = Transport({"https://github.com/a/gone": [404]})

    report = check_live(tmp_path, http=client(transport))

    credentialed, scheme_less = report["inconclusive"]
    assert credentialed == {
        "url": "https://user:secret@example.com/app",
        "reason": "embedded URL credentials are not allowed",
    }
    assert scheme_less["url"] == "example.com/no-scheme"
    assert scheme_less["reason"]
    assert report["unreachable"] == [
        {"url": "https://github.com/a/gone", "status": 404}
    ]
    assert transport.urls() == ["https://github.com/a/gone"]


@pytest.mark.parametrize(
    ("single", "problem"),
    [
        ("{", "pack single-screen.json is unreadable"),
        ('{"apps": {}}', "pack single-screen.json is malformed"),
        ('{"apps": [{"url": 1}]}', "pack single-screen.json is malformed"),
    ],
)
def test_unreadable_packs_give_a_failure_report(
    tmp_path: Path, single: str, problem: str
) -> None:
    write_packs(tmp_path, [entry("https://github.com/a/one")])
    (tmp_path / "dist/single-screen.json").write_text(single)
    transport = Transport({})

    report = check_live(tmp_path, http=client(transport))

    assert report["status"] == Status.FAILED
    assert problem in report.get("error", "")
    assert transport.requests == []


def test_summary_escapes_urls_reasons_and_errors() -> None:
    success = render_summary(
        {
            "status": Status.SUCCESS,
            "unreachable": [{"url": "https://x.example/<gone>", "status": 404}],
            "inconclusive": [{"url": "https://x.example/a&b", "reason": "<b>bad</b>"}],
        }
    )
    failure = render_summary(
        {
            "status": Status.FAILED,
            "unreachable": [],
            "inconclusive": [],
            "error": "pack </pre><script>",
        }
    )

    assert "https://x.example/&lt;gone&gt; (HTTP 404)" in success
    assert "https://x.example/a&amp;b: &lt;b&gt;bad&lt;/b&gt;" in success
    assert "Error: pack &lt;/pre&gt;&lt;script&gt;" in failure
    for text in (success, failure):
        assert text.count("<pre>") == 1
        assert text.count("</pre>") == 1


def test_report_replaces_an_earlier_pair(tmp_path: Path) -> None:
    (tmp_path / REPORT).parent.mkdir(parents=True)
    (tmp_path / REPORT).write_text("stale")
    (tmp_path / SUMMARY).write_text("stale")
    report: live_check.LiveCheckReport = {
        "status": Status.SUCCESS,
        "unreachable": [],
        "inconclusive": [],
    }

    write_live_report(tmp_path, report)

    assert json.loads((tmp_path / REPORT).read_text()) == report
    assert (tmp_path / SUMMARY).read_text() == render_summary(report)
    assert sorted(path.name for path in (tmp_path / REPORT).parent.iterdir()) == [
        "report.json",
        "summary.md",
    ]


@pytest.mark.parametrize("failing", ["report.json", "summary.md"])
def test_write_failure_leaves_neither_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing: str
) -> None:
    output = (tmp_path / REPORT).parent
    output.mkdir(parents=True)
    (tmp_path / REPORT).write_text("stale")
    (tmp_path / SUMMARY).write_text("stale")
    original = Path.write_text

    def write_text(path: Path, *args: object, **kwargs: object) -> int:
        if path.name == f"{failing}.partial":
            original(path, "half")
            raise OSError("disk full")
        return original(path, *args, **kwargs)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(Path, "write_text", write_text)

    with pytest.raises(OSError, match="disk full"):
        write_live_report(
            tmp_path,
            {"status": Status.SUCCESS, "unreachable": [], "inconclusive": []},
        )

    assert list(output.iterdir()) == []


def test_an_unencodable_url_leaves_neither_file(tmp_path: Path) -> None:
    output = (tmp_path / REPORT).parent
    output.mkdir(parents=True)
    (tmp_path / REPORT).write_text("stale")
    (tmp_path / SUMMARY).write_text("stale")

    with pytest.raises(ValueError, match="surrogate"):
        write_live_report(
            tmp_path,
            {
                "status": Status.SUCCESS,
                "unreachable": [{"url": "https://x.example/\ud800", "status": 404}],
                "inconclusive": [],
            },
        )

    assert list(output.iterdir()) == []


def fixture_transport(
    monkeypatch: pytest.MonkeyPatch, outcomes: dict[str, list[object]]
) -> Transport:
    transport = Transport(outcomes)

    def urllib_transport(
        _client: HttpClient, request: Request, timeout: float
    ) -> HttpResponse:
        return transport(request, timeout)

    monkeypatch.setattr(HttpClient, "_urllib_transport", urllib_transport)
    return transport


def test_cli_exits_zero_when_every_url_answers_or_is_inconclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_packs(
        tmp_path,
        [entry("https://github.com/a/ok"), entry("https://github.com/a/limited")],
    )
    fixture_transport(monkeypatch, {"https://github.com/a/limited": [403]})
    monkeypatch.chdir(tmp_path)

    assert main(["check-live"]) == 0

    out = capsys.readouterr().out
    assert "inconclusive: https://github.com/a/limited: HTTP 403" in out
    assert "https://github.com/a/ok" not in out
    report = json.loads((tmp_path / REPORT).read_text())
    assert report["status"] == "success"
    assert (tmp_path / SUMMARY).exists()


def test_cli_exits_nonzero_on_an_unreachable_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_packs(tmp_path, [entry("https://github.com/a/gone")])
    fixture_transport(monkeypatch, {"https://github.com/a/gone": [404]})
    monkeypatch.chdir(tmp_path)

    assert main(["check-live"]) == 1

    assert (
        "unreachable: https://github.com/a/gone (HTTP 404)" in capsys.readouterr().out
    )
    report = json.loads((tmp_path / REPORT).read_text())
    assert report["status"] == "success"
    assert report["unreachable"] == [
        {"url": "https://github.com/a/gone", "status": 404}
    ]


def test_cli_exits_nonzero_on_unreadable_packs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["check-live"]) == 1

    assert "check-live failed: pack single-screen.json is unreadable" in (
        capsys.readouterr().err
    )
    report = json.loads((tmp_path / REPORT).read_text())
    assert report["status"] == "failed"
    assert "single-screen.json" in report["error"]
    assert "single-screen.json" in (tmp_path / SUMMARY).read_text()


def test_cli_exits_nonzero_when_the_report_cannot_be_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_packs(tmp_path, [entry("https://github.com/a/limited")])
    fixture_transport(monkeypatch, {"https://github.com/a/limited": [403]})
    # A file where the output directory belongs makes both writes fail.
    (tmp_path / ".build").mkdir()
    (tmp_path / REPORT).parent.write_text("not a directory")
    monkeypatch.chdir(tmp_path)

    assert main(["check-live"]) == 1

    out, err = capsys.readouterr()
    assert err.startswith("check-live failed: cannot write report:")
    assert len(err.splitlines()) == 1
    # The findings printed before the write still reached the owner.
    assert out == "inconclusive: https://github.com/a/limited: HTTP 403\n"
