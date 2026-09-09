"""Reconcile the automation-owned nightly failure issue through an injected API."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

# Keep the ownership token stable so existing bot issues remain discoverable.
MARKER = "<!-- obtainium-pack:nightly-publishing -->"
TITLE = "Nightly build failing"
BOT_LOGIN = "github-actions[bot]"
_JSON_ERRORS = (UnicodeDecodeError, json.JSONDecodeError)


class ApiResponse(Protocol):
    @property
    def status(self) -> int: ...

    @property
    def headers(self) -> Mapping[str, str]: ...

    @property
    def body(self) -> bytes: ...


class GitHubApi(Protocol):
    def request(
        self, method: str, path: str, body: Mapping[str, object] | None = None
    ) -> ApiResponse: ...


@dataclass(frozen=True)
class IssueResult:
    status: str
    issue_number: int | None = None
    detail: str = ""


@dataclass(frozen=True)
class _Issue:
    number: int
    state: str


class IssueReconciler:
    """Maintain one marked issue without relying on its human-readable title."""

    def __init__(self, api: GitHubApi, repository: str) -> None:
        self.api = api
        self.repository = repository

    def report_failure(self, body: str) -> IssueResult:
        body = _ensure_marker(body)
        discovered = self._discover()
        if isinstance(discovered, IssueResult):
            return discovered
        if not discovered:
            created = self._create(body)
            if created is not None:
                return created
            # A failed create may have reached GitHub. Rediscover ownership before
            # deciding whether another create is safe.
            discovered = self._discover()
            if isinstance(discovered, IssueResult):
                return discovered
            if not discovered:
                return IssueResult(
                    "failed", detail="issue creation outcome is ambiguous"
                )

        canonical = min(discovered, key=lambda issue: issue.number)
        updated = self._patch(canonical.number, {"body": body, "state": "open"})
        if updated is not None:
            return updated
        for duplicate in discovered:
            if duplicate.number == canonical.number or duplicate.state != "open":
                continue
            failed = self._patch(duplicate.number, {"state": "closed"})
            if failed is not None:
                return failed
        return IssueResult("updated", canonical.number)

    def report_recovery(self, body: str) -> IssueResult:
        body = _ensure_marker(body)
        discovered = self._discover()
        if isinstance(discovered, IssueResult):
            return discovered
        open_issues = [issue for issue in discovered if issue.state == "open"]
        if not open_issues:
            return IssueResult("unchanged")
        canonical = min(open_issues, key=lambda issue: issue.number)
        for issue in open_issues:
            failed = self._patch(issue.number, {"body": body, "state": "closed"})
            if failed is not None:
                return failed
        return IssueResult("closed", canonical.number)

    def _discover(self) -> list[_Issue] | IssueResult:
        owned: list[_Issue] = []
        page = 1
        while True:
            path = f"/repos/{self.repository}/issues?state=all&per_page=100&page={page}"
            try:
                response = self.api.request("GET", path)
            except OSError:
                return IssueResult("failed", detail="issue discovery request failed")
            if response.status != 200:
                return IssueResult(
                    "failed", detail=f"issue discovery returned HTTP {response.status}"
                )
            try:
                values = json.loads(response.body)
            except _JSON_ERRORS:
                return IssueResult(
                    "failed", detail="issue discovery returned invalid JSON"
                )
            if not isinstance(values, list):
                return IssueResult(
                    "failed", detail="issue discovery returned invalid data"
                )
            for value in values:
                issue = _parse_owned_issue(value)
                if issue is not None:
                    owned.append(issue)
            if len(values) < 100:
                return owned
            page += 1

    def _create(self, body: str) -> IssueResult | None:
        try:
            response = self.api.request(
                "POST",
                f"/repos/{self.repository}/issues",
                {"title": TITLE, "body": body},
            )
        except OSError:
            return None
        if response.status != 201:
            return None
        try:
            value = json.loads(response.body)
        except _JSON_ERRORS:
            return None
        issue = _parse_owned_issue(value)
        if issue is None:
            return None
        return IssueResult("created", issue.number)

    def _patch(self, number: int, body: Mapping[str, object]) -> IssueResult | None:
        try:
            response = self.api.request(
                "PATCH", f"/repos/{self.repository}/issues/{number}", body
            )
        except OSError:
            return IssueResult("failed", number, "issue update request failed")
        if response.status != 200:
            return IssueResult(
                "failed", number, f"issue update returned HTTP {response.status}"
            )
        return None


def _parse_owned_issue(value: object) -> _Issue | None:
    if not isinstance(value, dict) or "pull_request" in value:
        return None
    user = value.get("user")
    body = value.get("body")
    number = value.get("number")
    state = value.get("state")
    if not isinstance(user, dict) or user.get("login") != BOT_LOGIN:
        return None
    if not isinstance(body, str) or MARKER not in body:
        return None
    if not isinstance(number, int) or isinstance(number, bool):
        return None
    if state not in ("open", "closed"):
        return None
    return _Issue(number, state)


def _ensure_marker(body: str) -> str:
    if MARKER in body:
        return body
    return f"{body.rstrip()}\n\n{MARKER}"
