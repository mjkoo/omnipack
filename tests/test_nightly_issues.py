from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from scripts.nightly_issues import MARKER, IssueReconciler


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes


class FakeIssues:
    def __init__(self, issues: list[dict[str, Any]]) -> None:
        self.issues = issues
        self.requests: list[tuple[str, str, dict[str, object] | None]] = []
        self.fail_next_patch = False
        self.ambiguous_create = False

    def request(
        self, method: str, path: str, body: Mapping[str, object] | None = None
    ) -> Response:
        recorded_body = dict(body) if body is not None else None
        self.requests.append((method, path, recorded_body))
        if method == "GET":
            page = int(path.rsplit("page=", 1)[1])
            start = (page - 1) * 100
            return self._response(200, self.issues[start : start + 100])
        if method == "POST":
            assert body is not None
            number = max((issue["number"] for issue in self.issues), default=0) + 1
            issue = _issue(number, "open", str(body["body"]))
            self.issues.append(issue)
            if self.ambiguous_create:
                self.ambiguous_create = False
                return self._response(502, {"message": "lost response"})
            return self._response(201, issue)
        number = int(path.rsplit("/", 1)[1])
        if self.fail_next_patch:
            self.fail_next_patch = False
            return self._response(500, {"message": "no"})
        issue = next(item for item in self.issues if item["number"] == number)
        issue.update(body or {})
        return self._response(200, issue)

    @staticmethod
    def _response(status: int, value: object) -> Response:
        return Response(status, {}, json.dumps(value).encode())


def _issue(
    number: int,
    state: str = "open",
    body: str = MARKER,
    *,
    author: str = "github-actions[bot]",
    pull_request: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "number": number,
        "state": state,
        "title": "Nightly build failing",
        "body": body,
        "user": {"login": author},
    }
    if pull_request:
        result["pull_request"] = {"url": "https://example.test/pulls/1"}
    return result


def test_failure_discovers_every_page_and_normalizes_owned_issues() -> None:
    fillers = [_issue(index, author="person") for index in range(1, 101)]
    api = FakeIssues(
        fillers
        + [
            _issue(104, "open"),
            _issue(102, "closed"),
            _issue(103, "open"),
            _issue(101, "open", "same title, no marker"),
            _issue(105, "open", pull_request=True),
        ]
    )

    result = IssueReconciler(api, "owner/repo").report_failure("new body")

    assert result.status == "updated"
    assert result.issue_number == 102
    assert [request[1] for request in api.requests if request[0] == "GET"] == [
        "/repos/owner/repo/issues?state=all&per_page=100&page=1",
        "/repos/owner/repo/issues?state=all&per_page=100&page=2",
    ]
    assert (
        next(issue for issue in api.issues if issue["number"] == 102)["state"] == "open"
    )
    assert next(issue for issue in api.issues if issue["number"] == 102)["body"] == (
        "new body\n\n" + MARKER
    )
    assert (
        next(issue for issue in api.issues if issue["number"] == 103)["state"]
        == "closed"
    )
    assert (
        next(issue for issue in api.issues if issue["number"] == 104)["state"]
        == "closed"
    )
    assert (
        next(issue for issue in api.issues if issue["number"] == 101)["state"] == "open"
    )


def test_failure_creates_owned_issue_when_none_exists() -> None:
    api = FakeIssues([_issue(4, author="person")])

    result = IssueReconciler(api, "owner/repo").report_failure("failure\n" + MARKER)

    assert result.status == "created"
    assert result.issue_number == 5
    create = next(request for request in api.requests if request[0] == "POST")
    assert create[2] == {"title": "Nightly build failing", "body": "failure\n" + MARKER}


def test_ambiguous_create_rediscovers_before_any_retry() -> None:
    api = FakeIssues([])
    api.ambiguous_create = True

    result = IssueReconciler(api, "owner/repo").report_failure("failure\n" + MARKER)

    assert result.status == "updated"
    methods = [request[0] for request in api.requests]
    assert methods == ["GET", "POST", "GET", "PATCH"]
    assert methods.count("POST") == 1


def test_success_closes_open_owned_issues_without_creating() -> None:
    api = FakeIssues([_issue(9, "closed"), _issue(7, "open"), _issue(8, "open")])

    result = IssueReconciler(api, "owner/repo").report_recovery("recovered\n" + MARKER)

    assert result.status == "closed"
    assert result.issue_number == 7
    assert not any(method == "POST" for method, _, _ in api.requests)
    for number in (7, 8):
        issue = next(item for item in api.issues if item["number"] == number)
        assert issue["state"] == "closed"
        assert issue["body"] == "recovered\n" + MARKER


def test_success_with_no_open_owned_issue_is_unchanged() -> None:
    api = FakeIssues([_issue(9, "closed")])

    result = IssueReconciler(api, "owner/repo").report_recovery("recovered")

    assert result.status == "unchanged"
    assert [method for method, _, _ in api.requests] == ["GET"]


def test_issue_api_errors_are_reported_without_raising() -> None:
    api = FakeIssues([_issue(2)])
    api.fail_next_patch = True

    result = IssueReconciler(api, "owner/repo").report_failure("failure")

    assert result.status == "failed"
    assert result.detail
