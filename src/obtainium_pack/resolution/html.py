"""Resolve HTML sources within the supported Obtainium compatibility boundary."""

from __future__ import annotations

import html as html_module
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit

from obtainium_pack.http import HttpClient, HttpError

from .support import SupportClass, classify_settings
from .types import Candidate, ResolutionError, ResolutionResult
from .version import compile_compatible_regex, extract_version

_URL = re.compile(r"(?:https?|ftp)://\S+")
_CONTAINER_EXTENSIONS = (".apk", ".xapk", ".apkm", ".apks")
_NATURAL_PART = re.compile(r"(\d+)")
MAX_INTERMEDIATE_DEPTH = 10


@dataclass(frozen=True, slots=True)
class _Link:
    url: str
    text: str


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[_Link] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = "".join(self._text).strip() or self._href.rsplit("/", 1)[-1]
            self.links.append(_Link(self._href, text))
            self._href = None
            self._text = []


def resolve_html(app: Mapping[str, object], http: HttpClient) -> ResolutionResult:
    """Resolve one validated HTML entry without probing its selected candidate."""
    current_url = _required_string(app, "url")
    settings = _settings(app.get("additionalSettings"))
    _validate_support(settings)
    headers = _request_headers(settings.get("requestHeader"))

    steps = [
        step
        for step in settings.get("intermediateLink", [])
        if isinstance(step, dict)
        and isinstance(step.get("customLinkFilterRegex"), str)
        and step["customLinkFilterRegex"]
    ]
    if len(steps) > MAX_INTERMEDIATE_DEPTH:
        raise ResolutionError(
            "html-depth-exceeded",
            f"HTML traversal exceeds {MAX_INTERMEDIATE_DEPTH} intermediate steps",
        )

    for index, step in enumerate(steps):
        response = _fetch(http, current_url, headers)
        links = _select_links(response.body.decode(), response.url, step)
        if not links:
            raise ResolutionError(
                "html-intermediate-empty",
                f"intermediate step {index + 1} selected no link from {response.url}",
            )
        current_url = links[-1].url

    response = _fetch(http, current_url, headers)
    body = response.body.decode()
    links = _select_links(body, response.url, settings)
    links = _filter_apks(links, settings)
    track_only_whole_page = (
        settings.get("trackOnly") is True
        and settings.get("versionExtractWholePage") is True
    )
    if not links and not track_only_whole_page:
        raise ResolutionError(
            "html-final-empty", f"final page selected no download from {response.url}"
        )

    selected_url = links[-1].url if links else None
    version_input = (
        _normalize_page(body)
        if settings.get("versionExtractWholePage") is True
        else unquote(selected_url or "")
    )
    pattern = settings.get("versionExtractionRegEx")
    if not isinstance(pattern, str) or not pattern:
        raise ResolutionError(
            "unsupported-setting", "HTML pseudo-versioning is unsupported"
        )
    effective = extract_version(version_input, pattern, settings.get("matchGroupToUse"))
    candidates = (
        (Candidate(_filename(selected_url), selected_url),) if selected_url else ()
    )
    return ResolutionResult(
        version_input,
        effective,
        "whole-page" if settings.get("versionExtractWholePage") is True else "url",
        candidates,
        {"kind": "page", "url": response.url, "selected_url": selected_url},
    )


def _settings(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ResolutionError(
                "settings-invalid", "additionalSettings is invalid JSON"
            ) from error
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ResolutionError(
            "settings-invalid", "additionalSettings must be an object"
        )
    return value


def _validate_support(settings: dict[str, Any]) -> None:
    for name, support in classify_settings("HTML", settings).items():
        if support.classification is SupportClass.LIVE_ERROR:
            raise ResolutionError(
                "unsupported-setting", f"unsupported setting {name}: {support.reason}"
            )


def _request_headers(value: object) -> dict[str, str]:
    headers: dict[str, str] = {}
    if not isinstance(value, list):
        return headers
    for item in value:
        if not isinstance(item, dict):
            continue
        line = item.get("requestHeader")
        if not isinstance(line, str) or not line:
            continue
        name, separator, header_value = line.partition(":")
        if not separator or not name.strip():
            raise ResolutionError("html-header-invalid", "invalid HTML request header")
        headers[name.strip()] = header_value.strip()
    return headers


def _fetch(http: HttpClient, url: str, headers: Mapping[str, str]):
    try:
        response = http.get_metadata(url, headers=headers)
    except (HttpError, OSError, ValueError) as error:
        raise ResolutionError(
            "html-request-failed", f"HTML metadata request failed for {url}"
        ) from error
    if response.status != 200:
        raise ResolutionError(
            "html-request-failed", f"HTML metadata returned {response.status} for {url}"
        )
    return response


def _select_links(body: str, base_url: str, settings: Mapping[str, Any]) -> list[_Link]:
    parser = _AnchorParser()
    parser.feed(body)
    links = [
        _Link(urljoin(base_url, item.url), item.text)
        for item in parser.links
        if item.url
    ]
    outside = settings.get("matchLinksOutsideATags") is True
    if not links or outside:
        links = _raw_links(body, base_url, prefer_json=not links)

    pattern_value = settings.get("customLinkFilterRegex")
    if isinstance(pattern_value, str) and pattern_value:
        pattern = compile_compatible_regex(pattern_value)
        by_text = settings.get("filterByLinkText") is True
        links = [
            item
            for item in links
            if pattern.search(item.text if by_text else unquote(item.url)) is not None
        ]
    else:
        links = [
            item
            for item in links
            if urlsplit(
                unquote(item.text if settings.get("filterByLinkText") else item.url)
            )
            .path.lower()
            .endswith(_CONTAINER_EXTENSIONS)
        ]

    if settings.get("skipSort") is not True:
        last_segment = settings.get("sortByLastLinkSegment") is True
        links.sort(
            key=lambda item: _natural_key(
                _filename(item.url) if last_segment else item.url
            )
        )
    if settings.get("reverseSort") is True:
        links.reverse()
    return links


def _raw_links(body: str, base_url: str, *, prefer_json: bool) -> list[_Link]:
    values: list[str]
    if prefer_json:
        try:
            values = _json_strings(json.loads(body))
        except json.JSONDecodeError:
            values = [body]
    else:
        values = [body]
    result: list[_Link] = []
    for value in values:
        absolute = urljoin(base_url, value)
        candidates = [absolute] if absolute != value and not _URL.search(value) else []
        candidates.extend(match.group(0) for match in _URL.finditer(value))
        for candidate in candidates:
            candidate = html_module.unescape(candidate).rstrip("'\"],}")
            result.append(_Link(candidate, _filename(candidate)))
    return result


def _json_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in _json_strings(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _json_strings(child)]
    return []


def _filter_apks(links: list[_Link], settings: Mapping[str, Any]) -> list[_Link]:
    value = settings.get("apkFilterRegEx")
    if not isinstance(value, str) or not value:
        return links
    pattern = compile_compatible_regex(value)
    invert = settings.get("invertAPKFilter") is True
    return [item for item in links if (pattern.search(item.url) is not None) != invert]


def _natural_key(value: str) -> tuple[tuple[int, object], ...]:
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.casefold())
        for part in _NATURAL_PART.split(value)
    )


def _filename(url: str) -> str:
    parts = [part for part in urlsplit(url).path.split("/") if part]
    return parts[-1] if parts else urlsplit(url).netloc


def _normalize_page(body: str) -> str:
    return body.replace("\r\n", "\n").replace("\n", "\\n")


def _required_string(values: Mapping[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ResolutionError("entry-invalid", f"entry {key} must be a nonempty string")
    return value
