"""Read each generated source's upstream list without inspecting what it lists.

Discovery reads only the inputs a source publishes: the codm README, or the
Quiver index, its lists and the release asset-name file the index names. It
never queries a repository host or downloads an APK; Obtainium decides what a
listed link can track.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

from omnipack.sources.common import HttpGetter
from omnipack.urls import normalize_project_url


class GeneratedSource(StrEnum):
    """The sources whose committed catalogs are generated from an upstream list."""

    CODM = "codm"
    QUIVER = "quiver"


class SkipReason(StrEnum):
    """Why a listed row or project contributes no entry."""

    UNKNOWN_FORGE = "names a forge no project URL can be formed for"
    INVALID_REPOSITORY = "has a missing or invalid repository"
    NO_ASSET_ENTRY = "has no entry in the release asset-name file"
    NO_APK_ASSET = "latest release lists no APK asset"


@dataclass(frozen=True, slots=True)
class Listing:
    """One upstream link to a project, with the name the listing gives it."""

    url: str
    name: str | None


@dataclass(frozen=True, slots=True)
class Skip:
    """A listed row or project that contributes no entry, and why."""

    listing: dict[str, Any]
    reason: SkipReason


@dataclass(frozen=True, slots=True)
class Discovery:
    """The listings a source keeps and the rows or projects it skipped."""

    listings: tuple[Listing, ...]
    skipped: tuple[Skip, ...]


class DiscoveryError(ValueError):
    """A discovery input cannot be read or is not the shape its source publishes."""


class EmptyDiscovery(DiscoveryError):
    """Discovery keeps no project, so the candidate would remove every entry."""

    def __init__(self, skipped: tuple[Skip, ...]) -> None:
        self.skipped = skipped
        super().__init__(
            f"discovery keeps no project ({len(skipped)} listed rows or projects skipped)"
        )


def discover(
    source: GeneratedSource,
    config: Mapping[str, object],
    http: HttpGetter,
    committed: frozenset[str],
) -> Discovery:
    """Read a source's upstream list.

    `committed` holds the normalized URLs of the committed catalog's entries.
    Where a source publishes release asset names, a listed project those URLs
    hold is kept whatever its latest release lists, so screening only gates
    admission and never removes a committed entry the upstream still lists.
    """
    discovery = _DISCOVERERS[source](config, http, committed)
    if not discovery.listings:
        raise EmptyDiscovery(discovery.skipped)
    return discovery


def config_text(config: Mapping[str, object], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DiscoveryError(f"source configuration {key} must be a nonempty string")
    return value


# --- codm: links inside the README's Project tables -----------------------

_LINK = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_DELIMITER = re.compile(r"^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$")
_PROJECT_HEADER = re.compile(r"^\s*\|\s*Project\s*\|", re.IGNORECASE)


def _discover_codm(
    config: Mapping[str, object], http: HttpGetter, _committed: frozenset[str]
) -> Discovery:
    readme = http.get(config_text(config, "readme_url")).body
    return Discovery(tuple(project_table_links(readme)), ())


def project_table_links(readme: bytes) -> Iterator[Listing]:
    """Yield every link inside the README's Project tables.

    Every Project table must be well formed: a partial read would propose
    removing the projects of a table it could not read.
    """
    try:
        lines = _outside_code(readme.decode("utf-8").splitlines())
    except UnicodeDecodeError as error:
        raise DiscoveryError("README is not UTF-8") from error
    found = False
    index = 0
    while index < len(lines):
        header = lines[index]
        if not _PROJECT_HEADER.match(header):
            index += 1
            continue
        delimiter = lines[index + 1] if index + 1 < len(lines) else ""
        if _DELIMITER.fullmatch(delimiter) is None:
            raise DiscoveryError("a Project table has a missing or invalid delimiter")
        # Escaped pipes are cell content, including pipes in inline code.
        pipes = list(re.finditer(r"(?<!\\)(?:\\\\)*\|", header.rstrip()))
        columns = len(pipes) - (pipes[-1].end() == len(header.rstrip()))
        if columns != delimiter.count("|") - 1:
            raise DiscoveryError("a Project table's header and delimiter disagree")
        found = True
        index += 2
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            # A badge image inside a link is decoration, not a project.
            for text, url in _LINK.findall(_IMAGE.sub("", lines[index])):
                yield Listing(url, text)
            index += 1
    if not found:
        raise DiscoveryError("README has no Project table")


def _outside_code(lines: list[str]) -> list[str]:
    """Keep line boundaries while hiding fenced and indented code examples."""
    visible: list[str] = []
    fence = ""
    for line in lines:
        expanded = line.expandtabs(4)
        if fence:
            if re.fullmatch(
                r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*",
                expanded,
            ):
                fence = ""
            visible.append("")
        elif expanded.startswith("    "):
            visible.append("")
        elif match := re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", expanded):
            delimiter, info = match.groups()
            if delimiter[0] == "~" or "`" not in info:
                fence = delimiter
            visible.append("")
        else:
            visible.append(line)
    return visible


# --- Quiver: index, lists and the release asset-name file ---------------

_FORGE_HOSTS = {"github": "github.com", "gitlab": "gitlab.com"}


def _discover_quiver(
    config: Mapping[str, object], http: HttpGetter, committed: frozenset[str]
) -> Discovery:
    index_url = config_text(config, "index_url")
    root = _catalog_root(index_url)
    if root is None:
        raise DiscoveryError("quiver index_url must be an HTTPS catalog JSON URL")
    index = _read_json(http, index_url, "quiver index")
    lists, assets_url = _index_locations(index, root)
    has_apk = _asset_index(_read_json(http, assets_url, "release asset-name file"))
    listings: list[Listing] = []
    skipped: list[Skip] = []
    for list_id, list_url in lists:
        document = _read_json(http, list_url, f"quiver list {list_id}")
        if not isinstance(document, dict) or not isinstance(document.get("apps"), list):
            raise DiscoveryError(f"quiver list {list_id} is malformed")
        for row in document["apps"]:
            if not isinstance(row, dict):
                raise DiscoveryError(f"quiver list {list_id} has a malformed row")
            name = row.get("project")
            listing = {
                "list": list_id,
                "project": name,
                "repository": row.get("repository"),
                "repositorySource": row.get("repositorySource"),
            }
            url = forge_url(row.get("repositorySource"), row.get("repository"))
            if isinstance(url, SkipReason):
                skipped.append(Skip(listing, url))
                continue
            normalized = normalize_project_url(url)
            if normalized not in committed:
                if normalized not in has_apk:
                    skipped.append(Skip(listing, SkipReason.NO_ASSET_ENTRY))
                    continue
                if not has_apk[normalized]:
                    skipped.append(Skip(listing, SkipReason.NO_APK_ASSET))
                    continue
            listings.append(Listing(url, name if isinstance(name, str) else None))
    return Discovery(tuple(listings), tuple(skipped))


def forge_url(forge: object, repository: object) -> str | SkipReason:
    """Form a project URL from a forge name and repository path.

    An absent forge means GitHub, and forge names match without regard to
    case. A GitHub repository is exactly an owner and a name; a GitLab one is
    one or more namespaces and a project.
    """
    if forge is None:
        forge = "github"
    host = _FORGE_HOSTS.get(forge.lower()) if isinstance(forge, str) else None
    if host is None:
        return SkipReason.UNKNOWN_FORGE
    if not isinstance(repository, str):
        return SkipReason.INVALID_REPOSITORY
    segments = repository.split("/")
    if (
        any(not segment or re.search(r"\s", segment) for segment in segments)
        or len(segments) < 2
        or (host == "github.com" and len(segments) != 2)
    ):
        return SkipReason.INVALID_REPOSITORY
    return f"https://{host}/{repository}"


def _index_locations(
    index: object, root: tuple[str, str]
) -> tuple[list[tuple[str, str]], str]:
    if (
        not isinstance(index, dict)
        or index.get("version") != 2
        or not isinstance(index.get("lists"), list)
    ):
        raise DiscoveryError("quiver index is malformed")
    lists: list[tuple[str, str]] = []
    for item in index["lists"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not item["id"]
            or not isinstance(item.get("remoteLocation"), str)
        ):
            raise DiscoveryError("quiver index has a malformed list reference")
        if item["id"] in {list_id for list_id, _ in lists}:
            raise DiscoveryError(f"quiver index repeats list {item['id']!r}")
        lists.append((item["id"], _within(item["remoteLocation"], root)))
    assets = index.get("platformMetadataUrl")
    if not isinstance(assets, str):
        raise DiscoveryError("quiver index names no release asset-name file")
    return lists, _within(assets, root)


def _asset_index(document: object) -> dict[str, bool]:
    """Map each normalized project URL the file names to whether its latest
    release lists an asset ending in `.apk`."""
    if not isinstance(document, dict) or not isinstance(document.get("entries"), list):
        raise DiscoveryError("release asset-name file is malformed")
    has_apk: dict[str, bool] = {}
    for entry in document["entries"]:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("provider"), str)
            or not isinstance(entry.get("repository"), str)
            or not isinstance(entry.get("assetNames"), list)
            or not all(isinstance(name, str) for name in entry["assetNames"])
        ):
            raise DiscoveryError("release asset-name file has a malformed entry")
        url = forge_url(entry["provider"], entry["repository"])
        if isinstance(url, SkipReason):
            continue
        normalized = normalize_project_url(url)
        apk = any(name.lower().endswith(".apk") for name in entry["assetNames"])
        has_apk[normalized] = has_apk.get(normalized, False) or apk
    return has_apk


def _catalog_root(index_url: str) -> tuple[str, str] | None:
    """The host and directory every location the index names must fall within."""
    parsed = urlsplit(index_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.endswith(".json")
        or "%" in parsed.path
        or any(part in {".", ".."} for part in parsed.path.split("/"))
    ):
        return None
    return parsed.hostname.lower(), parsed.path.rpartition("/")[0] + "/"


def _within(url: str, root: tuple[str, str]) -> str:
    try:
        parsed = urlsplit(url)
        inside = (
            parsed.scheme == "https"
            and parsed.hostname == root[0]
            and parsed.username is None
            and parsed.port is None
            and not parsed.query
            and not parsed.fragment
            and "%" not in parsed.path
            and all(part not in {".", ".."} for part in parsed.path.split("/"))
            and parsed.path.startswith(root[1])
        )
    except ValueError:
        inside = False
    if not inside:
        raise DiscoveryError(
            f"quiver index names a location outside its host and directory: {url!r}"
        )
    return url


def _read_json(http: HttpGetter, url: str, label: str) -> object:
    body = http.get(url).body
    try:
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DiscoveryError(f"{label} is not JSON: {error}") from error


_DISCOVERERS: dict[
    GeneratedSource,
    Callable[[Mapping[str, object], HttpGetter, frozenset[str]], Discovery],
] = {
    GeneratedSource.CODM: _discover_codm,
    GeneratedSource.QUIVER: _discover_quiver,
}
