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
from typing import TypedDict
from urllib.parse import urlsplit

from omnipack.sources.common import HttpGetter, SourceType, derived_source_type
from omnipack.urls import normalize_project_url


class GeneratedSource(StrEnum):
    """The sources whose committed catalogs are generated from an upstream list."""

    CODM = "codm"
    QUIVER = "quiver"


class SkipReason(StrEnum):
    """Why a listed row or project contributes no entry."""

    UNKNOWN_FORGE = "names a forge no project URL can be formed for"
    INVALID_REPOSITORY = "has a missing or invalid repository"
    INVALID_URL = "links a URL no project URL can be formed from"
    NO_ASSET_ENTRY = "has no entry in the release asset-name file"
    NO_APK_ASSET = "latest release lists no APK asset"


@dataclass(frozen=True, slots=True)
class Listing:
    """One upstream link to a project, with the name the listing gives it."""

    url: str
    name: str | None


class SkippedRow(TypedDict):
    """A Quiver list row as discovery read it, before any URL was formed."""

    list: str
    project: object
    repository: object
    repositorySource: object


class SkippedLink(TypedDict):
    """A README link as discovery read it."""

    name: str
    url: str


@dataclass(frozen=True, slots=True)
class Skip:
    """A listed row or project that contributes no entry, and why."""

    listing: SkippedRow
    reason: SkipReason


@dataclass(frozen=True, slots=True)
class LinkSkip:
    """A README link that contributes no entry, and why."""

    link: SkippedLink
    reason: SkipReason


@dataclass(frozen=True, slots=True)
class Discovery:
    """The listings a source keeps and the rows or projects it skipped."""

    listings: tuple[Listing, ...]
    skipped: tuple[Skip | LinkSkip, ...]


class DiscoveryError(ValueError):
    """A discovery input cannot be read or is not the shape its source publishes."""


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
    return _DISCOVERERS[source](config, http, committed)


def _config_text(config: Mapping[str, object], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DiscoveryError(f"source configuration {key} must be a nonempty string")
    return value


# --- codm: links inside the README's Project tables -----------------------

# An inline link: its text may hold escapes and balanced brackets, and its
# destination is bare (balanced parentheses allowed) or in angle brackets, then
# an optional quoted title. A bracket escaped by a backslash opens no link.
_LINK = re.compile(
    r"(?<!\\)\[((?:[^\[\]\\]|\\.|\[(?:[^\[\]\\]|\\.)*\])*)\]\(\s*"
    r"(?:<((?i:https?)://[^<>\s]+)>|((?i:https?)://(?:[^()\s]|\([^()\s]*\))+))"
    r"""(?:\s+(?:"[^"]*"|'[^']*'))?\s*\)"""
)
_IMAGE = re.compile(r"(?<!\\)!\[[^\]]*\]\([^)]*\)")
# Markdown renders no link inside a code span or an HTML comment, though a code
# span's text still reads as text.
_CODE_SPAN = re.compile(r"(?<![`\\])(`+)(?!`)(.*?)(?<!`)\1(?!`)")
_COMMENT = re.compile(r"<!--.*?-->")
_ESCAPED = re.compile(r"\\([!-/:-@\[-`{-~])")
# A literal backslash, hidden while matching so it escapes nothing after it.
_BACKSLASH = "\ue000"
_DELIMITER_CELL = re.compile(r"\s*:?-+:?\s*")
# A line opening another block ends a table: a heading, a blockquote, a list
# item or a thematic break.
_BLOCK_START = re.compile(
    r"^ {0,3}(?:#{1,6}(?:[ \t]|$)|>|(?:[-+*]|\d{1,9}[.)])(?:\s|$)"
    r"|([-*_])(?:[ \t]*\1){2,}[ \t]*$)"
)
# A pipe not escaped by a backslash, including pipes in inline code.
_PIPE = re.compile(r"(?<!\\)(?:\\\\)*\|")


def _discover_codm(
    config: Mapping[str, object], http: HttpGetter, _committed: frozenset[str]
) -> Discovery:
    readme = http.get(_config_text(config, "readme_url")).body
    listings: list[Listing] = []
    skipped: list[LinkSkip] = []
    for listing in _project_table_links(readme):
        if _forms_project_url(listing.url):
            listings.append(listing)
        else:
            link: SkippedLink = {"name": listing.name or "", "url": listing.url}
            skipped.append(LinkSkip(link, SkipReason.INVALID_URL))
    return Discovery(tuple(listings), tuple(skipped))


def _forms_project_url(url: str) -> bool:
    """Whether a link names a host and normalizes to a project URL."""
    try:
        return bool(urlsplit(url).hostname) and bool(normalize_project_url(url))
    except ValueError:
        return False


def _project_table_links(readme: bytes) -> Iterator[Listing]:
    """Yield every link inside the README's Project tables.

    Every Project table must be well formed: a partial read would propose
    removing the projects of a table it could not read.
    """
    try:
        lines = _outside_code(readme.decode("utf-8-sig").splitlines())
    except UnicodeDecodeError as error:
        raise DiscoveryError("README is not UTF-8") from error
    found = False
    index = 0
    while index < len(lines):
        header = lines[index]
        delimiter = lines[index + 1] if index + 1 < len(lines) else ""
        project = "|" in header and _cells(header)[0].strip() == "Project"
        if project and (header.lstrip().startswith("|") or _is_delimiter(delimiter)):
            if not _is_delimiter(delimiter):
                raise DiscoveryError(
                    "a Project table has a missing or invalid delimiter"
                )
            if len(_cells(header)) != len(_cells(delimiter)):
                raise DiscoveryError("a Project table's header and delimiter disagree")
            found = True
            end = _table_end(lines, index + 2)
            for row in lines[index + 2 : end]:
                yield from _row_links(row)
            index = end
        elif "|" in header and _is_delimiter(delimiter):
            # Another table: none of its rows is a Project table header.
            index = _table_end(lines, index + 2)
        else:
            index += 1
    if not found:
        raise DiscoveryError("README has no Project table")


def _row_links(row: str) -> Iterator[Listing]:
    """Yield the links Markdown renders in a table row."""
    row = row.replace("\\\\", _BACKSLASH)
    row = _CODE_SPAN.sub(lambda span: re.sub(r"[][()\\\ue000]", "", span[2]), row)
    # A badge image inside a link is decoration, not a project.
    row = _IMAGE.sub("", _COMMENT.sub("", row))
    for text, angled, bare in _LINK.findall(row):
        name = _ESCAPED.sub(r"\1", text).replace(_BACKSLASH, "\\")
        yield Listing((angled or bare).replace(_BACKSLASH, "\\\\"), name)


def _is_delimiter(line: str) -> bool:
    cells = _cells(line)
    # A line opening another block, such as the list item `- | -`, is never
    # a delimiter row.
    return (
        "|" in line
        and not _BLOCK_START.match(line)
        and bool(cells)
        and all(_DELIMITER_CELL.fullmatch(cell) for cell in cells)
    )


def _table_end(lines: list[str], index: int) -> int:
    """The index after a table's last row: rows run until a blank line or
    another block starts, and hidden code and comment lines are blank."""
    while (
        index < len(lines)
        and lines[index].strip()
        and not _BLOCK_START.match(lines[index])
    ):
        index += 1
    return index


def _cells(line: str) -> list[str]:
    """Split a table row into cells; the outer pipes are optional."""
    text = line.strip()
    pipes = list(_PIPE.finditer(text))
    cells: list[str] = []
    start = 0
    for pipe in pipes:
        cells.append(text[start : pipe.end() - 1])
        start = pipe.end()
    cells.append(text[start:])
    if text.startswith("|"):
        cells.pop(0)
    if pipes and pipes[-1].end() == len(text) and cells:
        cells.pop()
    return cells


def _outside_code(lines: list[str]) -> list[str]:
    """Keep line boundaries while hiding code examples and HTML comments.

    As in Markdown, an indented line opens a code block only after a blank
    line, so an indented row continues the table or paragraph above it, and a
    line opening an HTML comment hides every line through the one closing it.
    """
    visible: list[str] = []
    fence = ""
    comment = False
    for line in lines:
        expanded = line.expandtabs(4)
        after_blank = not visible or not visible[-1].strip()
        if comment:
            comment = "-->" not in line
            visible.append("")
        elif match := re.match(r"^ {0,3}<!--(.*)$", expanded):
            comment = "-->" not in match.group(1)
            visible.append("")
        elif fence:
            if re.fullmatch(
                r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*",
                expanded,
            ):
                fence = ""
            visible.append("")
        elif expanded.startswith("    ") and after_blank:
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

_FORGES = {
    "github": ("github.com", SourceType.GITHUB),
    "gitlab": ("gitlab.com", SourceType.GITLAB),
}


def _discover_quiver(
    config: Mapping[str, object], http: HttpGetter, committed: frozenset[str]
) -> Discovery:
    index_url = _config_text(config, "index_url")
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
            listing: SkippedRow = {
                "list": list_id,
                "project": name,
                "repository": row.get("repository"),
                "repositorySource": row.get("repositorySource"),
            }
            url = _forge_url(row.get("repositorySource"), row.get("repository"))
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


def _forge_url(forge: object, repository: object) -> str | SkipReason:
    """Form a project URL from a forge name and repository path.

    An absent forge means GitHub, and forge names match without regard to
    case. A GitHub repository is exactly an owner and a name; a GitLab one is
    one or more namespaces and a project. The URL must be a repository of its
    forge as source type derivation reads it, so its entry carries that type.
    """
    if forge is None:
        forge = "github"
    found = _FORGES.get(forge.lower()) if isinstance(forge, str) else None
    if found is None:
        return SkipReason.UNKNOWN_FORGE
    host, source_type = found
    if not isinstance(repository, str):
        return SkipReason.INVALID_REPOSITORY
    segments = repository.split("/")
    url = f"https://{host}/{repository}"
    if (
        # URL syntax in a segment would change which project the URL names.
        any(
            not segment or segment in {".", ".."} or re.search(r"[\s?#%]", segment)
            for segment in segments
        )
        or len(segments) < 2
        or (host == "github.com" and len(segments) != 2)
        or derived_source_type(url) != source_type
    ):
        return SkipReason.INVALID_REPOSITORY
    return url


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
        url = _forge_url(entry["provider"], entry["repository"])
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
