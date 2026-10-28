"""Choose what a run archives from the committed packs.

Each distinct project across both packs is one target, the single-screen
entry winning. A target's source type is decided as Obtainium decides it: the
entry's `overrideSource` when set, otherwise by the URL's host. Obtainium tries
many other hosted and hostless sources before it falls back to scraping HTML,
so an entry with no override on a host other than github.com or gitlab.com is
not guessed at and is skipped as unsupported.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from omnipack.forge_health import SettingsError, decode_settings
from omnipack.live_check import read_targets
from omnipack.model import SourceType
from omnipack.urls import normalize_project_url

HTML_PREFIX = "html/"
# Object keys may run to 1024 bytes; the per-version paths below a source key
# need room, so a longer key is cut and tagged with a digest of the whole.
MAX_KEY_LENGTH = 600
KEPT_LENGTH = 500
_HOSTS = {"github.com": SourceType.GITHUB, "gitlab.com": SourceType.GITLAB}


class SkipReason(StrEnum):
    """Why a pack entry is reported skipped and archives nothing."""

    TRACK_ONLY = "track only"
    UNSUPPORTED_SOURCE = "unsupported source"


@dataclass(frozen=True, slots=True)
class ArchiveTarget:
    """One distinct project: its bucket key, the pack entry that configures
    it and, unless skipped, its source type."""

    key: str
    entry: dict[str, Any]
    source: SourceType | None
    skip: SkipReason | None = None


def select_targets(root: Path) -> list[ArchiveTarget]:
    """Every distinct normalized project URL in pack order, single-screen first.

    Raises `PackReadError` when a pack cannot be read.
    """
    targets: dict[str, ArchiveTarget] = {}
    for pack_target in read_targets(root):
        entry = pack_target.entry
        normalized = normalize_project_url(entry["url"])
        if normalized in targets:
            continue
        source = classify_source(entry)
        skip = None
        if _track_only(entry):
            skip = SkipReason.TRACK_ONLY
        elif source is None:
            skip = SkipReason.UNSUPPORTED_SOURCE
        targets[normalized] = ArchiveTarget(
            key=source_key(entry["url"], source), entry=entry, source=source, skip=skip
        )
    return list(targets.values())


def classify_source(entry: dict[str, Any]) -> SourceType | None:
    """The archivable source Obtainium would use for an entry, or None."""
    override = entry.get("overrideSource")
    if override is not None:
        try:
            return SourceType(override)
        except ValueError:
            return None
    url = entry["url"]
    host = (urlsplit(url if "://" in url else f"https://{url}").hostname or "").lower()
    return _HOSTS.get(host.removeprefix("www."))


def _track_only(entry: dict[str, Any]) -> bool:
    try:
        return decode_settings(entry.get("additionalSettings")).get("trackOnly") is True
    except SettingsError:
        return False


def source_key(url: str, source: SourceType | None) -> str:
    """The bucket path segment naming a project: its normalized URL, prefixed
    `html/` for an HTML source.

    Every segment is percent-escaped to unreserved characters, so a query,
    fragment, port or odd path can neither escape the key nor collide with
    another; a `.`, `..` or empty segment is escaped too. A key too long for
    an object key is cut and ends in a digest of the full one.
    """
    segments = [_escape(part) for part in normalize_project_url(url).split("/")]
    prefix = HTML_PREFIX if source is SourceType.HTML else ""
    key = prefix + "/".join(segments)
    if len(key) <= MAX_KEY_LENGTH:
        return key
    kept = key[:KEPT_LENGTH]
    if "%" in kept[-2:]:
        kept = kept[: kept.rindex("%")]
    return f"{kept}-{hashlib.sha256(key.encode()).hexdigest()[:16]}"


def _escape(segment: str) -> str:
    if segment == "":
        return "%2F"
    if set(segment) == {"."}:
        return segment.replace(".", "%2E")
    return quote(segment, safe="-._~")
