"""Resolve an HTML entry to the link Obtainium would offer.

Obtainium scrapes a page for download links, optionally following
intermediate pages first, and versions the release from the chosen link or
the page text. Its pseudo versions for a page with no version pattern hash
the link (reproduced here as a link digest) or the start of the download or
its ETag, which would need a download to compute and are not supported.
Release dates scraped from a page are not read.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from functools import cmp_to_key
from html.parser import HTMLParser
from typing import Any, NamedTuple
from urllib.parse import unquote, urljoin, urlsplit

from omnipack.archive import Asset, HtmlRecord, NoReleaseError, ResolvedRelease
from omnipack.archive.fetch import fetch
from omnipack.archive.selection import (
    SettingsError,
    compare_alphanumeric,
    extract_version,
    is_installable,
    pattern,
)
from omnipack.forge_health import decode_settings
from omnipack.http import HttpClient, HttpResponse

MAX_INTERMEDIATE_LINKS = 10
_LINK_SCHEMES = ("http", "https", "ftp")
_URL_IN_TEXT = re.compile(r"""(?:http|https|ftp)://[^\s"'<>()\[\]{}]+""")
_TRAILING_PUNCTUATION = re.compile(r"[.,;:!?]+$")


class Link(NamedTuple):
    url: str
    text: str


def resolve_html(
    entry: dict[str, Any],
    http: HttpClient,
    *,
    deadline: float | None = None,
) -> ResolvedRelease:
    """The link Obtainium offers for an HTML pack entry, as a release whose
    only asset is that file and whose record lists the pages fetched.

    `deadline` is a reading of `http`'s clock that bounds every request.
    Raises `UnreachableError` for a page that answers 404 or 410 and
    `NoReleaseError` when a page has no matching link; anything else is a
    failure.
    """
    options = decode_settings(entry.get("additionalSettings"))
    headers = _request_headers(options)
    fetched: list[str] = []

    def load(url: str) -> tuple[HttpResponse, str]:
        fetched.append(url)
        response = fetch(http, url, headers=headers, deadline=deadline)
        return response, _text(response)

    url = entry["url"] if "://" in entry["url"] else f"https://{entry['url']}"
    listed = options.get("intermediateLink")
    steps = [
        step
        for step in (listed if isinstance(listed, list) else [])
        if isinstance(step, dict) and step.get("customLinkFilterRegex")
    ]
    for step in steps[:MAX_INTERMEDIATE_LINKS]:
        response, body = load(url)
        links = grab_links(body, response.url, step)
        if not links:
            raise NoReleaseError(f"no link matches on {url}")
        url = links[-1].url

    response, body = load(url)
    links = grab_links(body, response.url, options)
    apk_filter = pattern(options, "apkFilterRegEx")
    if apk_filter is not None:
        invert = options.get("invertAPKFilter") is True
        links = [l for l in links if (apk_filter.search(l.url) is not None) != invert]
    if not links:
        raise NoReleaseError(f"no link matches on {url}")
    link = links[-1].url

    record = HtmlRecord(fetched_urls=fetched)
    name = unquote(urlsplit(link).path.rsplit("/", 1)[-1]) or urlsplit(link).netloc
    return ResolvedRelease(
        version=_version(options, link, body),
        raw_record=record,
        assets=(Asset(name, link),),
    )


def _version(options: Mapping[str, Any], link: str, body: str) -> str:
    regex = pattern(options, "versionExtractionRegEx")
    if regex is not None:
        match_group = options.get("matchGroupToUse")
        text = (
            body.replace("\r\n", "\n").replace("\n", "\\n")
            if options.get("versionExtractWholePage") is True
            else unquote(link)
        )
        return extract_version(
            regex, match_group if isinstance(match_group, str) else "", text
        )
    method = options.get("defaultPseudoVersioningMethod", "partialAPKHash")
    if method != "APKLinkHash":
        raise SettingsError(
            f"{method} versioning needs a download; set versionExtractionRegEx"
        )
    return hashlib.sha256(link.encode()).hexdigest()[:16]


def _request_headers(options: Mapping[str, Any]) -> dict[str, str]:
    """The headers an entry's `requestHeader` list sets, each `Name: value`."""
    headers: dict[str, str] = {}
    entries = options.get("requestHeader")
    for item in entries if isinstance(entries, list) else []:
        line = item.get("requestHeader") if isinstance(item, dict) else None
        if isinstance(line, str) and line:
            name, _, value = line.partition(":")
            headers[name.strip()] = value.strip()
    return headers


def _text(response: HttpResponse) -> str:
    charset = response.headers.get_content_charset() or "utf-8"
    try:
        return response.body.decode(charset, errors="replace")
    except LookupError:
        return response.body.decode("utf-8", errors="replace")


def grab_links(body: str, base: str, options: Mapping[str, Any]) -> list[Link]:
    """The links a page offers under the entry's link options, sorted so the
    last is the one Obtainium follows.

    Candidates are the page's anchors; when it has none, or the entry matches
    links outside anchors, also the URLs in its text (its strings, when it is
    JSON) and in element attributes. They are kept when they match
    `customLinkFilterRegex`, or when none is set when they name an APK.
    """
    page = _Page()
    page.feed(body)
    page.close()
    found: dict[str, Link] = {}
    for href, text in page.anchors:
        url = urljoin(base, href)
        found.setdefault(url, Link(url, text or href.split("/")[-1]))

    def add(links: list[Link]) -> None:
        for link in links:
            found.setdefault(link.url, link)

    outside = options.get("matchLinksOutsideATags") is True
    if not found or outside:
        if not found:
            try:
                strings = _json_strings(json.loads(body))
            except ValueError:
                add(_links_in_text(body))
            else:
                links = _links_in_text("\n".join(strings))
                add(
                    links
                    or _links_in_text("\n".join(urljoin(base, s) for s in strings))
                )
        if outside:
            add(_links_in_text(body))
            add(_links_in_attributes(page.attribute_values, base))

    by_text = options.get("filterByLinkText") is True
    custom = pattern(options, "customLinkFilterRegex")
    links = []
    for link in found.values():
        target = link.text if by_text else unquote(link.url)
        if custom is not None:
            matches = custom.search(target) is not None
        else:
            try:
                matches = is_installable(urlsplit(target.strip()).path)
            except ValueError:
                matches = False
        if matches:
            links.append(link)
    if options.get("skipSort") is not True:
        last_segment = options.get("sortByLastLinkSegment") is True
        links.sort(key=cmp_to_key(lambda a, b: _compare(a, b, last_segment)))
    if options.get("reverseSort") is True:
        links.reverse()
    return links


def _compare(a: Link, b: Link, last_segment: bool) -> int:
    if last_segment:
        return compare_alphanumeric(_last_segment(a.url), _last_segment(b.url))
    return compare_alphanumeric(a.url, b.url)


def _last_segment(url: str) -> str:
    return [s for s in url.split("/") if s][-1] if url.strip("/") else url


def _json_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [s for item in value for s in _json_strings(item)]
    if isinstance(value, dict):
        return [s for item in value.values() for s in _json_strings(item)]
    return []


def _links_in_text(text: str) -> list[Link]:
    links = []
    for match in _URL_IN_TEXT.finditer(text):
        # Trailing punctuation belongs to the sentence, not the URL.
        url = _TRAILING_PUNCTUATION.sub("", match.group(0))
        if url:
            links.append(Link(url, url.split("/")[-1]))
    return links


def _links_in_attributes(values: list[str], base: str) -> list[Link]:
    links = []
    for value in values:
        value = value.strip()
        lowered = value.lower()
        if not (
            lowered.startswith(("http://", "https://", "ftp://"))
            or value.startswith("/")
        ):
            continue
        url = urljoin(base, value)
        if urlsplit(url).scheme.lower() in _LINK_SCHEMES:
            links.append(Link(url, url.split("/")[-1]))
    return links


class _Page(HTMLParser):
    """The anchors of a page, with their text, and every attribute value."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self.attribute_values: list[str] = []
        self._open: list[tuple[str, list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.attribute_values.extend(v for _, v in attrs if v)
        href = dict(attrs).get("href")
        if tag == "a" and href:
            self._open.append((href, []))

    def handle_data(self, data: str) -> None:
        for _, parts in self._open:
            parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._open:
            href, parts = self._open.pop()
            self.anchors.append((href, "".join(parts)))

    def close(self) -> None:
        super().close()
        while self._open:
            href, parts = self._open.pop()
            self.anchors.append((href, "".join(parts)))
