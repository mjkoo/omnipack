"""Fetch BBoi34's latest Codeberg release assets.

The single-screen asset (`Decomp-Recomp.V<x>.json`) maps to both variants;
the dual-screen asset (`Dual-Screen-Decomp-Recomp.V<x>.json`) maps to dual
only. `additionalSettings` is already a JSON string on this source.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Mapping

from omnipack.model import App, Variant
from omnipack.sources.common import HttpGetter, SourceError, normalize_record


def fetch(http: HttpGetter, config: Mapping[str, object]) -> list[App]:
    """Return BBoi34's applications from its latest Codeberg release."""
    try:
        repo = _configured(config, "codeberg_repo")
        single_pattern = _configured(config, "single_asset_pattern")
        dual_pattern = _configured(config, "dual_asset_pattern")
        release = http.get(
            f"https://codeberg.org/api/v1/repos/{repo}/releases/latest"
        ).json()
        assets = release.get("assets") if isinstance(release, dict) else None
        if not isinstance(assets, list):
            raise TypeError("latest release must contain an assets list")

        def matching(pattern: str) -> tuple[str, str]:
            matches = [
                (asset.get("name"), asset.get("browser_download_url"))
                for asset in assets
                if isinstance(asset, dict)
                and isinstance(asset.get("name"), str)
                and fnmatch.fnmatchcase(asset["name"], pattern)
            ]
            if len(matches) != 1 or not isinstance(matches[0][1], str):
                raise ValueError(
                    f"expected exactly one release asset matching {pattern!r}"
                )
            return matches[0]  # type: ignore[return-value]

        _, single_url = matching(single_pattern)
        _, dual_url = matching(dual_pattern)
        single = _catalog(http, single_url)
        dual = _catalog(http, dual_url)
        result = [
            normalize_record(
                record,
                source="bboi",
                variant=Variant.SINGLE,
                eligibility=frozenset(Variant),
                origin="bboi-standard-asset",
            )
            for record in single
        ]
        result.extend(
            normalize_record(
                record,
                source="bboi",
                variant=Variant.DUAL,
                eligibility=frozenset({Variant.DUAL}),
                dual_preferred=True,
                origin="bboi-dual-asset",
            )
            for record in dual
        )
        return result
    except SourceError:
        raise
    except Exception as error:
        raise SourceError("bboi", str(error)) from error


def _configured(config: Mapping[str, object], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SourceError("bboi", "configured location is empty")
    return value


def _catalog(http: HttpGetter, url: str) -> list[dict[str, object]]:
    document = http.get(url).json()
    records = document.get("apps") if isinstance(document, dict) else None
    if not isinstance(records, list) or not all(
        isinstance(record, dict) for record in records
    ):
        raise TypeError("asset must contain an apps list of objects")
    return records
