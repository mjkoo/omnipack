from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta
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
NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)
OBTAINIUM_SETTINGS = json.dumps(
    {"requestHeader": [{"requestHeader": "User-Agent: Obtainium/1.0"}]}
)


def entry(
    url: str, settings: object = "{}", name: str = "Fixture"
) -> dict[str, object]:
    return {"id": "fixture", "name": name, "url": url, "additionalSettings": settings}


def success(**lists: list[object]) -> dict[str, object]:
    """A success report with the given lists and every other list empty."""
    empty = ("unreachable", "inconclusive", "stale", "archived", "healthInconclusive")
    return {"status": Status.SUCCESS, **{key: [] for key in empty}, **lists}


def api(repository: str) -> str:
    return f"https://api.github.com/repos/{repository}"


def releases_api(repository: str) -> str:
    return f"{api(repository)}/releases?per_page=100"


def ago(days: int) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def health(
    repository: str, *, archived: bool = False, days: int = 10, tag: str = "v1"
) -> dict[str, list[object]]:
    """GitHub API answers for a repository whose one release carries an APK."""
    release = {
        "tag_name": tag,
        "draft": False,
        "prerelease": False,
        "published_at": ago(days),
        "assets": [{"name": "app.apk", "updated_at": ago(days)}],
    }
    return {
        api(repository): [{"archived": archived, "disabled": False}],
        releases_api(repository): [[release]],
    }


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
    record every request. An outcome is an exception, an HTTP status, or a
    JSON body answered with 200; an unlisted URL answers 200 with no body."""

    def __init__(self, outcomes: Mapping[str, Sequence[object]]) -> None:
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
        if not isinstance(outcome, int):
            return HttpResponse(url, 200, Message(), json.dumps(outcome).encode())
        if outcome >= 400:
            raise http_error(url, outcome)
        return HttpResponse(url, outcome, Message(), b"")

    def urls(self) -> list[str]:
        return [request.full_url for request in self.requests]


def client(transport: Transport) -> HttpClient:
    return HttpClient(transport=transport, sleep=lambda _seconds: None)


def test_answering_projects_are_left_out_of_a_success_report(tmp_path: Path) -> None:
    write_packs(
        tmp_path, [entry("https://example.com/one"), entry("https://github.com/a/two")]
    )
    transport = Transport({"https://example.com/one": [200], **health("a/two")})

    report = check_live(tmp_path, http=client(transport), now=NOW)

    assert report == success()
    assert transport.urls() == [
        "https://example.com/one",
        "https://github.com/a/two",
        api("a/two"),
        releases_api("a/two"),
    ]


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

    assert report == success(
        unreachable=[{"url": "https://example.com/moved-away", "status": 404}]
    )
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
        [entry("https://bad.example/app", injected), entry("https://good.example/ok")],
    )
    requests = serve_https(monkeypatch, {"https://good.example/ok": (200, None)})

    report = check_live(tmp_path, http=HttpClient(sleep=lambda _seconds: None))

    (finding,) = report["inconclusive"]
    assert finding["url"] == "https://bad.example/app"
    assert finding["reason"].startswith("Invalid header value")
    assert report["unreachable"] == []
    assert [request.full_url for request in requests] == [
        "https://bad.example/app",
        "https://good.example/ok",
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

    assert report == success(
        unreachable=[
            {"url": "https://github.com/a/gone", "status": 404},
            {"url": "https://github.com/a/removed", "status": 410},
        ]
    )
    # A gone project gets no health lookup.
    assert transport.urls() == [
        "https://github.com/a/gone",
        "https://github.com/a/removed",
    ]


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
        {"url": "https://gitlab.com/a/private", "reason": "HTTP 403", "status": 403},
        {"url": "https://github.com/a/limited", "reason": "HTTP 429"},
        {"url": "https://slow.example/app", "reason": "timed out"},
    ]
    # The 429 and the timeout were each retried before giving up.
    assert transport.urls().count("https://github.com/a/limited") == 3
    assert transport.urls().count("https://slow.example/app") == 3


def test_only_a_non_retried_error_status_is_recorded_on_an_inconclusive_entry(
    tmp_path: Path,
) -> None:
    write_packs(
        tmp_path,
        [
            entry("https://a.example/forbidden"),
            entry("https://b.example/limited"),
            entry("https://c.example/slow"),
        ],
    )
    transport = Transport(
        {
            "https://a.example/forbidden": [403],
            "https://b.example/limited": [429],
            "https://c.example/slow": [TimeoutError("timed out")],
        }
    )

    report = check_live(tmp_path, http=client(transport))

    forbidden, limited, slow = report["inconclusive"]
    assert forbidden["status"] == 403
    assert "status" not in limited
    assert "status" not in slow


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
            entry("https://plain.example/app", json.dumps({"trackOnly": False})),
        ],
    )
    transport = Transport({})

    check_live(tmp_path, http=client(transport))

    assert transport.urls() == [
        "https://emulator.example/download/",
        "https://plain.example/app",
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
        [entry("https://bad.example/app", settings), entry("https://good.example/ok")],
    )
    transport = Transport({})

    report = check_live(tmp_path, http=client(transport))

    (finding,) = report["inconclusive"]
    assert finding["url"] == "https://bad.example/app"
    assert problem in finding["reason"]
    assert "status" not in finding
    assert transport.urls() == ["https://good.example/ok"]


def test_a_url_in_both_packs_or_twice_in_one_is_requested_and_listed_once(
    tmp_path: Path,
) -> None:
    gone = "https://github.com/a/gone"
    write_packs(
        tmp_path,
        [entry(gone, OBTAINIUM_SETTINGS), entry(gone)],
        [entry("https://dual.example/only"), entry(gone)],
    )
    transport = Transport({gone: [404]})

    report = check_live(tmp_path, http=client(transport))

    assert report["unreachable"] == [{"url": gone, "status": 404}]
    assert transport.urls() == [gone, "https://dual.example/only"]
    # The first entry in pack order supplies the headers.
    assert transport.requests[0].get_header("User-agent") == "Obtainium/1.0"


def test_spent_budget_starts_no_further_request(tmp_path: Path) -> None:
    urls = [f"https://example.com/app{index}" for index in range(4)]
    write_packs(tmp_path, [entry(url) for url in urls])
    transport = Transport({urls[1]: [404]})
    ticks: Iterator[float] = iter([0.0, 0.0, 600.0, 1200.0, 1500.0])

    report = check_live(tmp_path, http=client(transport), clock=lambda: next(ticks))

    assert transport.urls() == urls[:2]
    assert report == success(
        unreachable=[{"url": urls[1], "status": 404}],
        inconclusive=[
            {"url": urls[2], "reason": NOT_CHECKED},
            {"url": urls[3], "reason": NOT_CHECKED},
        ],
    )


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
        (
            '{"apps": [{"url": "https://github.com/a/one"}]}',
            "pack single-screen.json is malformed",
        ),
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
            "stale": [
                {
                    "url": "https://github.com/a/old",
                    "name": "Old <App>",
                    "tag": "v1<script>",
                    "date": "2026-01-02",
                },
                {"url": "https://github.com/a/none", "name": "A & B"},
            ],
            "archived": [{"url": "https://github.com/a/shut", "name": "<i>Shut</i>"}],
            "healthInconclusive": [
                {"url": "https://github.com/a/q", "name": "Q", "reason": "<HTTP 403>"}
            ],
        }
    )
    failure = render_summary(
        {
            "status": Status.FAILED,
            "unreachable": [],
            "inconclusive": [],
            "stale": [],
            "archived": [],
            "healthInconclusive": [],
            "error": "pack </pre><script>",
        }
    )

    assert "https://x.example/&lt;gone&gt; (HTTP 404)" in success
    assert "https://x.example/a&amp;b: &lt;b&gt;bad&lt;/b&gt;" in success
    assert (
        "https://github.com/a/old (Old &lt;App&gt;): v1&lt;script&gt; 2026-01-02"
        in success
    )
    assert "https://github.com/a/none (A &amp; B): no qualifying release" in success
    assert "https://github.com/a/shut (&lt;i&gt;Shut&lt;/i&gt;)" in success
    assert "https://github.com/a/q (Q): &lt;HTTP 403&gt;" in success
    assert "<script>" not in success
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
        "stale": [],
        "archived": [],
        "healthInconclusive": [],
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
            {
                "status": Status.SUCCESS,
                "unreachable": [],
                "inconclusive": [],
                "stale": [],
                "archived": [],
                "healthInconclusive": [],
            },
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
                "stale": [],
                "archived": [],
                "healthInconclusive": [],
            },
        )

    assert list(output.iterdir()) == []


def fixture_transport(
    monkeypatch: pytest.MonkeyPatch, outcomes: Mapping[str, Sequence[object]]
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
        [entry("https://example.com/ok"), entry("https://example.com/limited")],
    )
    fixture_transport(monkeypatch, {"https://example.com/limited": [403]})
    monkeypatch.chdir(tmp_path)

    assert main(["check-live"]) == 0

    out = capsys.readouterr().out
    assert "inconclusive: https://example.com/limited: HTTP 403" in out
    assert "https://example.com/ok" not in out
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
    write_packs(tmp_path, [entry("https://example.com/limited")])
    fixture_transport(monkeypatch, {"https://example.com/limited": [403]})
    # A file where the output directory belongs makes both writes fail.
    (tmp_path / ".build").mkdir()
    (tmp_path / REPORT).parent.write_text("not a directory")
    monkeypatch.chdir(tmp_path)

    assert main(["check-live"]) == 1

    out, err = capsys.readouterr()
    assert err.startswith("check-live failed: cannot write report:")
    assert len(err.splitlines()) == 1
    # The findings printed before the write still reached the owner.
    assert out == "inconclusive: https://example.com/limited: HTTP 403\n"


def test_a_reachable_project_is_listed_archived_and_stale(tmp_path: Path) -> None:
    url = "https://github.com/a/old"
    write_packs(tmp_path, [entry(url, name="Old App")])
    transport = Transport(health("a/old", archived=True, days=200, tag="v0.9"))

    report = check_live(tmp_path, http=client(transport), now=NOW)

    assert report == success(
        stale=[
            {
                "url": url,
                "name": "Old App",
                "tag": "v0.9",
                "date": (NOW - timedelta(days=200)).date().isoformat(),
            }
        ],
        archived=[{"url": url, "name": "Old App"}],
    )


def test_a_project_with_no_qualifying_release_is_stale_without_one(
    tmp_path: Path,
) -> None:
    url = "https://github.com/a/desktop"
    write_packs(tmp_path, [entry(url)])
    transport = Transport(
        {
            api("a/desktop"): [{"archived": False, "disabled": False}],
            releases_api("a/desktop"): [[]],
        }
    )

    report = check_live(tmp_path, http=client(transport), now=NOW)

    assert report["stale"] == [{"url": url, "name": "Fixture"}]


def test_a_rate_limited_lookup_is_health_inconclusive_only(tmp_path: Path) -> None:
    url = "https://github.com/a/limited"
    write_packs(tmp_path, [entry(url)])
    transport = Transport(health("a/limited") | {releases_api("a/limited"): [403]})

    report = check_live(tmp_path, http=client(transport), now=NOW)

    assert report == success(
        healthInconclusive=[{"url": url, "name": "Fixture", "reason": "HTTP 403"}]
    )


def test_undecodable_github_settings_are_inconclusive_without_a_request(
    tmp_path: Path,
) -> None:
    url = "https://github.com/a/broken"
    write_packs(tmp_path, [entry(url, "{not json")])
    transport = Transport(health("a/broken"))

    report = check_live(tmp_path, http=client(transport), now=NOW)

    (inconclusive,) = report["inconclusive"]
    (unknown,) = report["healthInconclusive"]
    assert inconclusive["url"] == unknown["url"] == url
    assert inconclusive["reason"].startswith("additionalSettings is not valid JSON")
    assert unknown["reason"] == inconclusive["reason"]
    assert report["stale"] == report["archived"] == []
    assert transport.requests == []


def test_a_release_date_is_reported_as_its_utc_calendar_date(tmp_path: Path) -> None:
    url = "https://github.com/a/late"
    write_packs(tmp_path, [entry(url)])
    release = {
        "tag_name": "v1",
        "draft": False,
        "prerelease": False,
        "published_at": "2025-01-31T22:00:00-05:00",
        "assets": [{"name": "app.apk", "updated_at": "2025-01-31T22:00:00-05:00"}],
    }
    transport = Transport(health("a/late") | {releases_api("a/late"): [[release]]})

    report = check_live(tmp_path, http=client(transport), now=NOW)

    assert report["stale"] == [
        {"url": url, "name": "Fixture", "tag": "v1", "date": "2025-02-01"}
    ]


def test_an_inconclusive_page_still_gets_its_health_result(tmp_path: Path) -> None:
    url = "https://github.com/a/blocked"
    write_packs(tmp_path, [entry(url)])
    transport = Transport({url: [403], **health("a/blocked", archived=True)})

    report = check_live(tmp_path, http=client(transport), now=NOW)

    assert report == success(
        inconclusive=[{"url": url, "reason": "HTTP 403", "status": 403}],
        archived=[{"url": url, "name": "Fixture"}],
    )


def test_other_hosts_and_gitlab_get_no_health_lookup(tmp_path: Path) -> None:
    urls = [
        "https://gitlab.com/AuroraOSS/AuroraStore",
        "https://f-droid.org/packages/app",
        "https://github.com/owner",
    ]
    write_packs(tmp_path, [entry(url) for url in urls])
    transport = Transport({})

    report = check_live(tmp_path, http=client(transport), now=NOW)

    assert report == success()
    assert transport.urls() == urls


def test_a_releases_page_url_is_looked_up_by_its_repository(tmp_path: Path) -> None:
    url = "https://github.com/A/App/releases"
    write_packs(tmp_path, [entry(url)])
    transport = Transport(health("a/app", days=300))

    report = check_live(tmp_path, http=client(transport), now=NOW)

    assert [item["url"] for item in report["stale"]] == [url]


def test_the_first_entry_at_a_shared_url_supplies_the_health_settings(
    tmp_path: Path,
) -> None:
    url = "https://github.com/a/shared"
    nightly = json.dumps({"includePrereleases": True})
    stable_first = [entry(url, name="Stable"), entry(url, nightly, name="Nightly")]
    releases = [
        {
            "tag_name": "nightly",
            "draft": False,
            "prerelease": True,
            "published_at": ago(2),
            "assets": [{"name": "app.apk", "updated_at": ago(2)}],
        },
        {
            "tag_name": "v1",
            "draft": False,
            "prerelease": False,
            "published_at": ago(300),
            "assets": [{"name": "app.apk", "updated_at": ago(300)}],
        },
    ]
    answers = health("a/shared") | {releases_api("a/shared"): [releases]}

    write_packs(tmp_path, stable_first)
    stable = check_live(tmp_path, http=client(Transport(answers)), now=NOW)
    write_packs(tmp_path, stable_first[::-1])
    transport = Transport(answers)
    reversed_order = check_live(tmp_path, http=client(transport), now=NOW)

    assert [(item["name"], item.get("tag")) for item in stable["stale"]] == [
        ("Stable", "v1")
    ]
    assert reversed_order["stale"] == []
    assert transport.urls().count(releases_api("a/shared")) == 1


def test_the_github_token_reaches_only_the_api(tmp_path: Path) -> None:
    write_packs(
        tmp_path,
        [entry("https://github.com/a/app"), entry("https://gitlab.com/a/app")],
    )
    transport = Transport(health("a/app"))

    check_live(tmp_path, http=client(transport), now=NOW, github_token="secret")

    page, repository, releases, other = transport.requests
    for request in (page, other):
        assert request.get_header("Authorization") is None
    for request in (repository, releases):
        assert request.unredirected_hdrs == {"Authorization": "Bearer secret"}
        assert "Authorization" not in request.headers


def test_a_spent_budget_leaves_unfinished_lookups_health_inconclusive(
    tmp_path: Path,
) -> None:
    urls = [f"https://github.com/a/app{index}" for index in range(3)]
    write_packs(tmp_path, [entry(url) for url in urls])
    transport = Transport(
        health("a/app0", archived=True) | health("a/app1", archived=True)
    )
    # Before: app0's page and its two lookups, app1's page and its
    # repository lookup; the budget is spent before app1's releases lookup.
    ticks: Iterator[float] = iter([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1200.0, 1200.0])

    report = check_live(
        tmp_path, http=client(transport), clock=lambda: next(ticks), now=NOW
    )

    assert transport.urls() == [
        urls[0],
        api("a/app0"),
        releases_api("a/app0"),
        urls[1],
        api("a/app1"),
    ]
    assert report == success(
        inconclusive=[{"url": urls[2], "reason": NOT_CHECKED}],
        archived=[{"url": urls[0], "name": "Fixture"}],
        healthInconclusive=[
            {"url": urls[1], "name": "Fixture", "reason": NOT_CHECKED},
            {"url": urls[2], "name": "Fixture", "reason": NOT_CHECKED},
        ],
    )


def test_cli_exits_zero_on_stale_and_archived_projects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_packs(
        tmp_path,
        [
            entry("https://github.com/a/old", name="Old"),
            entry("https://github.com/a/q"),
        ],
    )
    fixture_transport(
        monkeypatch,
        health("a/old", archived=True, days=4000, tag="v1") | {api("a/q"): [403]},
    )
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)

    assert main(["check-live"]) == 0

    out = capsys.readouterr().out.splitlines()
    released = (NOW - timedelta(days=4000)).date().isoformat()
    assert f"stale: https://github.com/a/old (Old): v1 {released}" in out
    assert "archived: https://github.com/a/old (Old)" in out
    assert "health inconclusive: https://github.com/a/q (Fixture): HTTP 403" in out
    report = json.loads((tmp_path / REPORT).read_text())
    assert [item["url"] for item in report["stale"]] == ["https://github.com/a/old"]


@pytest.mark.parametrize(
    ("token", "sent"),
    [
        ("secret", "secret"),
        ("secret\n", "secret"),
        ("", None),
        (" ", None),
        (None, None),
    ],
)
def test_cli_passes_the_environment_token_to_the_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    token: str | None,
    sent: str | None,
) -> None:
    write_packs(tmp_path, [entry("https://github.com/a/app")])
    transport = fixture_transport(monkeypatch, health("a/app"))
    if token is None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    else:
        monkeypatch.setenv("GITHUB_TOKEN", token)
    monkeypatch.chdir(tmp_path)

    main(["check-live"])

    page, *lookups = transport.requests
    assert page.get_header("Authorization") is None
    assert [request.get_header("Authorization") for request in lookups] == [
        f"Bearer {sent}" if sent else None
    ] * 2
