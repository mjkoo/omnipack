"""An in-memory HTTP getter for tests that must make no real request."""

from __future__ import annotations

import json
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
