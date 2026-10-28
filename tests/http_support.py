"""An in-memory HTTP getter for tests that must make no real request."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from email.message import Message
from typing import Any

from omnipack.http import HttpError, HttpResponse


class FakeHttp:
    """Answer each URL from `responses` and record every URL requested.

    A response may be text, bytes, a JSON-serializable value or an exception
    to raise; a URL without a response fails like an unavailable one.
    """

    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def get(self, url: str) -> HttpResponse:
        self.urls.append(url)
        value = self.responses.get(url, HttpError(f"no response for {url}"))
        if isinstance(value, Exception):
            raise value
        if not isinstance(value, (str, bytes)):
            value = json.dumps(value)
        body = value if isinstance(value, bytes) else value.encode()
        return HttpResponse(url, 200, Message(), body)


class RoutedTransport:
    """A `Transport` that answers each URL from `answers` and records every
    request.

    An answer is a JSON-serializable value, text or bytes served with status
    200, or an int for an HTTP error status. A URL without an answer fails the
    test that asked for it.
    """

    def __init__(self, answers: dict[str, Any]) -> None:
        self.answers = answers
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> HttpResponse:
        self.requests.append(request)
        answer = self.answers[request.full_url]
        if isinstance(answer, int) and not isinstance(answer, bool):
            raise urllib.error.HTTPError(
                request.full_url, answer, "fixture", Message(), None
            )
        if isinstance(answer, (str, bytes)):
            body = answer if isinstance(answer, bytes) else answer.encode()
        else:
            body = json.dumps(answer).encode()
        return HttpResponse(request.full_url, 200, Message(), body)
