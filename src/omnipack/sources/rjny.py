"""Fetch RJNY's `src/applications.json` from its main branch.

RJNY entries carry `meta` flags (`includeInStandard`, `includeInDualScreen`,
`excludeFromExport`, `nameOverride`, `urlOverride`). The export flags decide
whether an entry is kept and its build kind, never which packs it reaches; `additionalSettings` is an object on this source (a JSON string
in the rendered Obtainium export).
"""

from __future__ import annotations

from collections.abc import Mapping

from omnipack.model import App, Source
from omnipack.sources.common import HttpGetter, SourceError, normalize_record


def fetch(http: HttpGetter, config: Mapping[str, object]) -> list[App]:
    """Return RJNY's applications, normalized.

    An entry excluded from export, or marked out of both exports, is dropped.
    One in the dual-screen export alone is a dual-screen build; every other
    kept entry is a baseline build.
    """
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
            standard = meta.get("includeInStandard") is not False
            dual = meta.get("includeInDualScreen") is not False
            if meta.get("excludeFromExport") is True or not (standard or dual):
                continue
            result.append(
                normalize_record(
                    record,
                    source=Source.RJNY,
                    dual_screen=not standard,
                    origin="rjny-catalog",
                )
            )
        return result
    except SourceError:
        raise
    except Exception as error:
        raise SourceError("rjny", str(error)) from error
