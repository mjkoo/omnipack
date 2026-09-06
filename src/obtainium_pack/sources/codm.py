"""Scrape codm2000's README table for GitHub links and generate entries.

Each GitHub link not already present by URL in a higher-precedence source
has its package id resolved from its latest release APK (see
`obtainium_pack.package_id`) and cached in `config/package-ids.json` so
nightly runs stay cheap. Non-GitHub rows have no APK feed and are skipped.
Generated entries map to the dual variant only.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from itertools import pairwise
from urllib.parse import urlsplit

from obtainium_pack.model import App, SourceType, Variant
from obtainium_pack.package_id import ProjectResolver, generated_project_entry
from obtainium_pack.sources import IngestionReport
from obtainium_pack.sources.common import HttpGetter, SourceError, derived_source_type
from obtainium_pack.urls import normalize_project_url

LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)\s]+)\)")


def fetch(
    http: HttpGetter,
    config: Mapping[str, object],
    resolver: ProjectResolver,
    higher_precedence: Sequence[App],
    report: IngestionReport,
) -> list[App]:
    """Return generated entries for codm2000's GitHub-hosted catalog rows."""
    try:
        readme_url = config.get("readme_url")
        if not isinstance(readme_url, str) or not readme_url.strip():
            raise SourceError("codm", "configured location is empty")
        text = http.get(readme_url).body.decode("utf-8")
        lines = text.splitlines()
        if not any(
            re.match(r"^\s*\|\s*Project\s*\|", header, re.IGNORECASE)
            and re.fullmatch(r"\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*", separator)
            for header, separator in pairwise(lines)
        ):
            raise SourceError("codm", "README lacks a Project catalog table")
        covered = {
            normalize_project_url(app.url)
            for app in higher_precedence
            if app.variant is Variant.DUAL
        }
        result: list[App] = []
        seen: set[str] = set()
        for url in LINK_RE.findall(text):
            parsed = urlsplit(url)
            parts = [part for part in parsed.path.split("/") if part]
            if derived_source_type(url) is not SourceType.GITHUB or len(parts) != 2:
                report.skipped.append(
                    {
                        "source": "codm2000",
                        "url": url,
                        "reason": "not a GitHub repository",
                    }
                )
                continue
            normalized = normalize_project_url(url)
            if normalized in covered or normalized in seen:
                continue
            seen.add(normalized)
            generated = generated_project_entry(url, resolver)
            report.record_resolution(
                url,
                generated.app,
                generated.resolution.status,
                generated.resolution.failure,
            )
            if generated.app is not None:
                result.append(generated.app)
        return result
    except SourceError:
        raise
    except Exception as error:
        raise SourceError("codm", str(error)) from error
