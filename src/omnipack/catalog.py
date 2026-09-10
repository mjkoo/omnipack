"""Deterministic README catalog generation from rendered Obtainium packs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import escape
from typing import Any
from urllib.parse import quote, urlencode

from omnipack.composition_policy import CompositionPolicy

START_MARKER = b"<!-- omnipack:catalog:start -->"
END_MARKER = b"<!-- omnipack:catalog:end -->"
REDIRECT_URL = "https://apps.obtainium.imranr.dev/redirect"


class CatalogError(ValueError):
    """Rendered packs or README markers cannot produce a safe catalog."""


@dataclass(frozen=True, slots=True)
class _Row:
    family: str
    name: str
    category: str
    single: dict[str, Any] | None
    dual: dict[str, Any] | None


def generate_catalog(single: bytes, dual: bytes, policy: CompositionPolicy) -> bytes:
    """Generate deterministic LF-delimited catalog bytes from serialized packs."""
    variants = (
        ("single-screen", _apps(single, "single-screen")),
        ("dual-screen", _apps(dual, "dual-screen")),
    )
    families: dict[str, dict[str, dict[str, Any]]] = {}
    for variant, apps in variants:
        for index, record in enumerate(apps):
            package_id = _text(record, "id", variant, index)
            url = _text(record, "url", variant, index)
            _text(record, "name", variant, index)
            categories = record.get("categories", [])
            if not isinstance(categories, list) or not all(
                isinstance(category, str) for category in categories
            ):
                raise CatalogError(
                    f"{variant} app {package_id!r} has invalid categories"
                )
            family = policy.rendered_family(package_id, url)
            projected = families.setdefault(family, {})
            if variant in projected:
                raise CatalogError(
                    f"{variant} contains duplicate projected family {family!r}"
                )
            projected[variant] = record

    rows: list[_Row] = []
    for family, projected in families.items():
        single_record = projected.get("single-screen")
        dual_record = projected.get("dual-screen")
        presenter = single_record or dual_record
        assert presenter is not None
        categories = presenter.get("categories", [])
        category = categories[0] if categories else "Other"
        rows.append(
            _Row(
                family,
                presenter["name"],
                category or "Other",
                single_record,
                dual_record,
            )
        )

    rows.sort(
        key=lambda row: (
            row.category.casefold(),
            row.category,
            row.name.casefold(),
            row.name,
            row.family,
        )
    )
    lines: list[str] = []
    current_category: str | None = None
    for row in rows:
        if row.category != current_category:
            if current_category is not None:
                lines.extend(("", "</details>", ""))
            current_category = row.category
            lines.extend(
                (
                    "<details>",
                    f"<summary>{_inline_html_text(row.category)}</summary>",
                    "",
                    "| Program | Single-screen | Dual-screen |",
                    "| --- | --- | --- |",
                )
            )
        lines.append(
            f"| {_markdown_text(row.name)} | {_cell(row.single)} | {_cell(row.dual)} |"
        )
    if current_category is not None:
        lines.extend(("", "</details>", ""))
    return "\n".join(lines).encode("utf-8")


def split_catalog(readme: bytes) -> tuple[bytes, bytes, bytes]:
    """Split README bytes while retaining marker lines in prefix and suffix."""
    if readme.count(START_MARKER) != 1 or readme.count(END_MARKER) != 1:
        raise CatalogError("README must contain exactly one of each catalog marker")
    start = _standalone_line(readme, START_MARKER)
    end = _standalone_line(readme, END_MARKER)
    if start is None or end is None or start[0] >= end[0]:
        raise CatalogError("README catalog markers must be standalone and ordered")
    return readme[: start[1]], readme[start[1] : end[0]], readme[end[0] :]


def replace_catalog(readme: bytes, catalog: bytes) -> bytes:
    """Replace only the bytes inside the README catalog markers."""
    prefix, _, suffix = split_catalog(readme)
    return prefix + catalog + suffix


def _apps(serialized: bytes, variant: str) -> list[dict[str, Any]]:
    try:
        document = json.loads(serialized)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise CatalogError(f"{variant} pack is invalid JSON: {error}") from error
    if not isinstance(document, dict):
        raise CatalogError(f"{variant} pack must be an object")
    apps = document.get("apps")
    if not isinstance(apps, list) or not all(isinstance(app, dict) for app in apps):
        raise CatalogError(f"{variant} pack must contain an apps list of objects")
    return apps


def _text(record: dict[str, Any], field: str, variant: str, index: int) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise CatalogError(f"{variant} apps[{index}].{field} must be nonempty text")
    return value


def _html_text(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value).strip()
    return escape(collapsed, quote=False)


def _markdown_text(value: str) -> str:
    escaped = _html_text(value)
    return re.sub(r"([\\`*{}\[\]()#+.!|_~-])", r"\\\1", escaped)


def _inline_html_text(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value).strip()
    markdown = frozenset(r"\`*{}[]()#+.!|_~-")
    return "".join(
        f"&#{ord(character)};"
        if character in markdown
        else escape(character, quote=True)
        for character in collapsed
    )


def _cell(record: dict[str, Any] | None) -> str:
    if record is None:
        return "-"
    source = record.get("overrideSource")
    if not isinstance(source, str) or not source:
        raise CatalogError(f"app {record.get('id')!r} has invalid source label")
    source_url = escape(quote(record["url"], safe=":/?&=#%+@;,"), quote=True)
    try:
        compact = json.dumps(
            record,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except ValueError as error:
        raise CatalogError(
            f"app {record.get('id')!r} is not valid JSON data"
        ) from error
    deep_link = "obtainium://app/" + quote(compact, safe="")
    redirect = REDIRECT_URL + "?" + urlencode({"r": deep_link})
    redirect_url = escape(redirect, quote=True)
    return (
        f'<a href="{source_url}">{_inline_html_text(source)}</a> · '
        f'<a href="{redirect_url}">Add to Obtainium</a>'
    )


def _standalone_line(data: bytes, marker: bytes) -> tuple[int, int] | None:
    pattern = re.compile(rb"(?:\A|(?<=\n))" + re.escape(marker) + rb"(?:\r?\n|\Z)")
    match = pattern.search(data)
    return match.span() if match is not None else None
