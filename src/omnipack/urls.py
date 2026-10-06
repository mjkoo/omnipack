"""Canonical forms for comparing upstream project URLs."""

from __future__ import annotations

from urllib.parse import SplitResult, urlsplit, urlunsplit

_DEFAULT_PORTS = {"http": 80, "https": 443}


def project_url(url: str) -> str:
    """Reduce a link to the project URL that normalization identifies.

    The result keeps the scheme and the path's case, lowercases the host and
    drops a leading `www.`, drops the scheme's default port but keeps any
    other, and drops a trailing slash and `.git`. A GitHub link is reduced to
    its owner and repository, so a releases, tags, blob or release-asset link
    becomes the repository root, and a gitlab.com link to the project path
    before GitLab's reserved `-` route segment. On any other host the query
    and fragment are kept, since which parts of such a link identify the
    project cannot be known.
    """
    parsed = _split_url(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    host = host.removeprefix("www.")

    path = parsed.path.rstrip("/")
    query, fragment = parsed.query, parsed.fragment
    if host == "github.com":
        path = "/".join(path.split("/")[:3])
        query = fragment = ""
    elif host == "gitlab.com":
        segments = path.split("/")
        if "-" in segments:
            path = "/".join(segments[: segments.index("-")])
        query = fragment = ""
    # `.GIT` means `.git` only where path case is folded.
    if path.endswith(".git") or (
        host == "github.com" and path.lower().endswith(".git")
    ):
        path = path[:-4]

    authority = f"[{host}]" if ":" in host else host
    if parsed.port is not None and parsed.port != _DEFAULT_PORTS.get(scheme):
        authority = f"{authority}:{parsed.port}"
    return urlunsplit((scheme, authority, path, query, fragment))


def normalize_project_url(url: str) -> str:
    """Normalize the URL features that do not identify a different project."""
    parsed = urlsplit(project_url(url))
    path = parsed.path.lower() if parsed.hostname == "github.com" else parsed.path
    return urlunsplit(
        ("", parsed.netloc, path, parsed.query, parsed.fragment)
    ).removeprefix("//")


def parse_project_url(url: str) -> str:
    """Normalize a project URL a maintainer wrote in configuration.

    Configuration names a project by URL, so a URL holding whitespace or no
    host raises ValueError rather than naming a project nothing matches.
    """
    if any(character.isspace() for character in url):
        raise ValueError(f"project URL contains whitespace: {url!r}")
    return normalize_project_url(url)


def _split_url(url: str) -> SplitResult:
    parsed = urlsplit(url)
    if parsed.hostname is None:
        parsed = urlsplit(f"//{url}")
    if parsed.hostname is None:
        raise ValueError(f"project URL has no host: {url!r}")
    return parsed
