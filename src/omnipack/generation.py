"""Turn a generated source's upstream list into a candidate committed catalog.

Each project discovery keeps becomes one minimal Obtainium entry. An entry the
committed catalog already holds at the same normalized URL keeps its id and
URL, so composition rules, pins and installed apps that know it keep working;
a new one gets an Obtainium placeholder id. Per-app settings and categories
are overlay records and category map keys, never catalog content.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NotRequired, TypedDict
from urllib.parse import urlsplit

from omnipack.discovery import (
    DiscoveryError,
    GeneratedSource,
    LinkSkip,
    Listing,
    Skip,
    SkippedLink,
    SkippedRow,
    SkipReason,
    discover,
)
from omnipack.http import HttpClient, HttpResponse
from omnipack.report_model import Status
from omnipack.source_catalog import render_catalog, rendered_entry
from omnipack.sources import load_json
from omnipack.sources.common import HttpGetter, derived_source_type
from omnipack.sources.generated import catalog_urls
from omnipack.urls import normalize_project_url, project_url


class GenerationError(ValueError):
    """The source configuration or the committed catalog cannot be used."""


class InputRecord(TypedDict):
    """An input generation read, with the SHA-256 of its bytes once read."""

    url: str
    sha256: NotRequired[str]


class SkippedRowRecord(SkippedRow):
    """A skipped list row as the report records it, with the reason."""

    reason: SkipReason


class SkippedLinkRecord(SkippedLink):
    """A skipped README link as the report records it, with the reason."""

    reason: SkipReason


SkippedListing = SkippedRowRecord | SkippedLinkRecord


class Changes(TypedDict):
    """Entries added, removed and changed in place, each by its catalog URL."""

    added: list[str]
    removed: list[str]
    changed: list[str]


class GenerationReport(TypedDict):
    status: Status
    source: GeneratedSource
    inputs: list[InputRecord]
    skipped: list[SkippedListing]
    changes: NotRequired[Changes]
    error: NotRequired[str]


def _output_directory(root: Path, source: GeneratedSource) -> Path:
    return root / ".build/source-generation" / source


def generate(
    root: Path, source: GeneratedSource, *, http: HttpGetter | None = None
) -> GenerationReport:
    """Write a candidate catalog and its report, or only the report on failure.

    No earlier candidate survives a run, so a failed run never leaves one to be
    mistaken for current, and a failed report never lists changes. An output
    directory that cannot be prepared leaves nowhere to write even the report,
    so that failure is only returned.
    """
    output = _output_directory(root, source)
    try:
        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True)
    except OSError as error:
        return {
            "status": Status.FAILED,
            "source": source,
            "inputs": [],
            "skipped": [],
            "error": f"cannot prepare {output}: {error}",
        }
    reader = _RecordingHttp(http or HttpClient())
    report: GenerationReport = {
        "status": Status.FAILED,
        "source": source,
        "inputs": reader.inputs,
        "skipped": [],
    }
    try:
        sources = load_json(root / "config/sources.json", "source configuration")
        config = sources.get(source) if isinstance(sources, dict) else None
        if not isinstance(config, dict):
            raise GenerationError(f"{source} source configuration must be an object")
        catalog_path = config.get("catalog")
        if not isinstance(catalog_path, str) or not catalog_path.strip():
            raise GenerationError(
                f"{source} source configuration catalog must be a nonempty string"
            )
        committed = load_committed(root / catalog_path)
        discovery = discover(source, config, reader, frozenset(committed))
        report["skipped"] = _skipped(discovery.skipped)
        if not discovery.listings:
            raise DiscoveryError(
                f"discovery keeps no project ({len(discovery.skipped)} listed rows "
                "or projects skipped)"
            )
        entries = render_entries(discovery.listings, committed)
        # Render and compare first: either can raise on a committed entry, and
        # a failed run must leave no candidate.
        catalog = render_catalog(list(entries.values()))
        changes = _changes(entries, committed)
        _write_whole(output / "catalog.json", catalog)
        report["changes"] = changes
        report["status"] = Status.SUCCESS
    except Exception as error:  # noqa: BLE001 - the report records every failure
        report["error"] = str(error) or type(error).__name__
    (output / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def _write_whole(path: Path, data: bytes) -> None:
    """Write a file whole or not at all, so a failed write leaves no partial
    candidate behind."""
    partial = path.with_name(path.name + ".partial")
    try:
        partial.write_bytes(data)
        partial.replace(path)
    except OSError:
        partial.unlink(missing_ok=True)
        raise


def load_committed(path: Path) -> dict[str, dict[str, Any]]:
    """Read the committed catalog's entries by normalized URL.

    A missing catalog holds nothing. One that cannot be read or is malformed
    fails, because guessing would change published ids, and so does one
    holding two entries at one normalized URL, since either id could be kept.
    """
    if not path.exists():
        return {}
    try:
        document = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GenerationError(f"committed catalog {path.name} is unreadable") from error
    apps = document.get("apps") if isinstance(document, dict) else None
    if not isinstance(apps, list) or not all(
        isinstance(entry, dict)
        and isinstance(entry.get("id"), str)
        and isinstance(entry.get("url"), str)
        for entry in apps
    ):
        raise GenerationError(f"committed catalog {path.name} is malformed")
    try:
        urls = catalog_urls([(entry["id"], entry["url"]) for entry in apps])
    except ValueError as error:
        raise GenerationError(
            f"committed catalog {path.name} is malformed: {error}"
        ) from error
    return dict(zip(urls, apps, strict=True))


def render_entries(
    listings: Sequence[Listing], committed: Mapping[str, Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    """One minimal entry per normalized URL, in normalized URL order and
    independent of listing order."""
    grouped: dict[str, list[Listing]] = {}
    for listing in listings:
        grouped.setdefault(normalize_project_url(listing.url), []).append(listing)
    return {
        normalized: minimal_entry(normalized, group, committed.get(normalized))
        for normalized, group in sorted(grouped.items())
    }


def minimal_entry(
    normalized: str,
    listings: Sequence[Listing],
    committed: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if committed is not None:
        url, identifier = committed["url"], committed["id"]
    else:
        # An https spelling wins over an http one, then the smallest.
        url = min(
            (project_url(listing.url) for listing in listings),
            key=lambda url: (not url.startswith("https:"), url),
        )
        identifier = placeholder_id(normalized)
    names = sorted(
        {trimmed for listing in listings if (trimmed := trim_name(listing.name))},
        key=lambda name: (name.casefold(), name),
    )
    source_type = derived_source_type(url)
    segments = [part for part in urlsplit(url).path.split("/") if part]
    entry: dict[str, Any] = {
        "id": identifier,
        "url": url,
        "author": segments[0] if source_type is not None else "",
        "name": names[0] if names else _fallback_name(url, segments),
        "additionalSettings": {},
        "categories": [],
    }
    if source_type is not None:
        entry["overrideSource"] = source_type
    return entry


def placeholder_id(normalized: str) -> str:
    """An id Obtainium treats as a placeholder: twelve lowercase hex characters.

    Obtainium replaces it with the APK's package id on first install. Hashing
    the normalized URL keeps it stable across runs without any lookup.
    """
    return hashlib.sha256(normalized.encode()).hexdigest()[:12]


# The joiner, variation selectors and keycap that complete an emoji without
# being symbols themselves; skin tones and tag characters are ranges below.
_EMOJI_PARTS = frozenset("\u200d\ufe0e\ufe0f\u20e3")


def trim_name(name: str | None) -> str:
    """Trim trailing emoji, other symbols and surrounding whitespace.

    Only "other symbol" characters count, so punctuation, math and currency
    signs that may be part of a name, such as `A.I.R.` or `C++`, are kept.
    """
    text = (name or "").strip()
    while text and (_decoration(text[-1]) or text[-1].isspace()):
        text = text[:-1]
    return text


def _decoration(character: str) -> bool:
    return (
        unicodedata.category(character) == "So"
        or character in _EMOJI_PARTS
        or "\U0001f3fb" <= character <= "\U0001f3ff"
        or "\U000e0020" <= character <= "\U000e007f"
    )


def _fallback_name(url: str, segments: list[str]) -> str:
    return segments[-1] if segments else urlsplit(url).hostname or url


def _changes(
    candidate: Mapping[str, dict[str, Any]],
    committed: Mapping[str, Mapping[str, Any]],
) -> Changes:
    return {
        "added": sorted(
            entry["url"] for key, entry in candidate.items() if key not in committed
        ),
        "removed": sorted(
            entry["url"] for key, entry in committed.items() if key not in candidate
        ),
        "changed": sorted(
            entry["url"]
            for key, entry in candidate.items()
            if key in committed
            and rendered_entry(entry) != rendered_entry(dict(committed[key]))
        ),
    }


def _skipped(skipped: tuple[Skip | LinkSkip, ...]) -> list[SkippedListing]:
    return [_skip_record(skip) for skip in skipped]


def _skip_record(skip: Skip | LinkSkip) -> SkippedListing:
    if isinstance(skip, LinkSkip):
        return {
            "name": skip.link["name"],
            "url": skip.link["url"],
            "reason": skip.reason,
        }
    return {
        "list": skip.listing["list"],
        "project": skip.listing["project"],
        "repository": skip.listing["repository"],
        "repositorySource": skip.listing["repositorySource"],
        "reason": skip.reason,
    }


class _RecordingHttp:
    """Record each input generation reads, with the digest of its bytes once
    read, so a failed run's report still names the input that failed."""

    def __init__(self, http: HttpGetter) -> None:
        self.http = http
        self.inputs: list[InputRecord] = []

    def get(self, url: str) -> HttpResponse:
        record: InputRecord = {"url": url}
        self.inputs.append(record)
        response = self.http.get(url)
        record["sha256"] = hashlib.sha256(response.body).hexdigest()
        return response
