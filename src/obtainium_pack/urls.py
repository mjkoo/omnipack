"""Canonical forms for comparing upstream project URLs."""

from __future__ import annotations

from urllib.parse import SplitResult, urlsplit, urlunsplit


def normalize_project_url(url: str) -> str:
    """Normalize the URL features that do not identify a different project."""
    parsed = _split_url(url)
    host = (parsed.hostname or "").lower()
    host = host.removeprefix("www.")

    path = parsed.path.rstrip("/")
    if path.lower().endswith(".git"):
        path = path[:-4]
    if host == "github.com":
        path = path.lower()

    authority = host
    if parsed.port is not None:
        authority = f"{authority}:{parsed.port}"
    return urlunsplit(
        ("", authority, path, parsed.query, parsed.fragment)
    ).removeprefix("//")


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
