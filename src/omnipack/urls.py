"""Canonical forms for comparing upstream project URLs."""

from __future__ import annotations

from urllib.parse import SplitResult, urlsplit, urlunsplit


def normalize_project_url(url: str) -> str:
    """Normalize the URL features that do not identify a different project."""
    parsed = _split_url(url)
    host = (parsed.hostname or "").lower()
    host = host.removeprefix("www.")

    path = parsed.path.rstrip("/")
    query, fragment = parsed.query, parsed.fragment
    if host == "github.com":
        path = "/".join(path.split("/")[:3]).lower()
        query = fragment = ""
    if path.lower().endswith(".git"):
        path = path[:-4]

    authority = host
    if parsed.port is not None:
        authority = f"{authority}:{parsed.port}"
    return urlunsplit(("", authority, path, query, fragment)).removeprefix("//")


def project_urls_equal(left: str, right: str) -> bool:
    """Return whether two URLs identify the same normalized project."""
    return normalize_project_url(left) == normalize_project_url(right)


def _split_url(url: str) -> SplitResult:
    parsed = urlsplit(url)
    if parsed.hostname is None:
        parsed = urlsplit(f"//{url}")
    if parsed.hostname is None:
        raise ValueError(f"project URL has no host: {url!r}")
    return parsed


def gitlab_project_path(url: str) -> str:
    """Return the case-sensitive path of a supported public GitLab project.

    The bounded native adapter accepts up to twenty namespace components and
    one project component. Invalid URLs raise ValueError for caller diagnostics.
    """
    parsed = urlsplit(url)
    parts = [part for part in parsed.path.split("/") if part]
    if (
        parsed.scheme != "https"
        or parsed.hostname != "gitlab.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or not 2 <= len(parts) <= 21
        or "-" in parts
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("URL must identify one public gitlab.com project")
    return "/".join(parts)
