"""Fetch RJNY's `src/applications.json` from its main branch.

RJNY entries carry `meta` flags (`includeInStandard`, `includeInDualScreen`,
`excludeFromExport`, `nameOverride`, `urlOverride`) that map to variant
membership; `additionalSettings` is an object on this source (a JSON string
in the rendered Obtainium export).
"""

from __future__ import annotations

from collections.abc import Mapping

from omnipack.model import App, Variant
from omnipack.sources.common import HttpGetter, SourceError, normalize_record


def fetch(http: HttpGetter, config: Mapping[str, object]) -> list[App]:
    """Return RJNY's applications, normalized, honoring `excludeFromExport`."""
    try:
        repo, branch, path = (config.get(key) for key in ("repo", "branch", "path"))
        if not all(
            isinstance(value, str) and value.strip() for value in (repo, branch, path)
        ):
            raise SourceError("rjny", "configured location is empty")
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
        document = http.get(url).json()
        records = document.get("apps") if isinstance(document, dict) else None
        if not isinstance(records, list):
            raise TypeError("catalog must contain an apps list")
        result: list[App] = []
        for record in records:
            if not isinstance(record, dict):
                raise TypeError("catalog entry must be an object")
            meta = record.get("meta", {})
            if not isinstance(meta, dict):
                raise TypeError("entry meta must be an object")
            if meta.get("excludeFromExport") is True:
                continue
            eligibility = frozenset(
                variant
                for variant, included in (
                    (Variant.SINGLE, meta.get("includeInStandard")),
                    (Variant.DUAL, meta.get("includeInDualScreen")),
                )
                if included is not False
            )
            result.append(
                normalize_record(
                    record,
                    source="rjny",
                    eligibility=eligibility,
                    origin="rjny-catalog",
                )
            )
        return result
    except SourceError:
        raise
    except Exception as error:
        raise SourceError("rjny", str(error)) from error
