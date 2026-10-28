"""The one request wrapper the resolvers share."""

from __future__ import annotations

from collections.abc import Mapping

from omnipack.archive import UnreachableError
from omnipack.http import HttpClient, HttpResponse, HttpStatusError

UNREACHABLE_STATUSES = frozenset({404, 410})


def fetch(
    http: HttpClient,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    credential: str | None = None,
    deadline: float | None = None,
) -> HttpResponse:
    """GET a resolution request, reading a 404 or 410 as the project being
    gone. Every other failure propagates as the client raised it."""
    try:
        return http.get(url, headers, credential=credential, deadline=deadline)
    except HttpStatusError as error:
        if error.status in UNREACHABLE_STATUSES:
            raise UnreachableError(str(error)) from error
        raise
