"""Upstream source fetchers and their shared ingestion diagnostics."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any

from omnipack.model import App

from .common import HttpGetter, SourceError


@dataclass(slots=True)
class IngestionReport:
    """Structured source outcomes consumed by the eventual build report."""

    admitted: list[dict[str, Any]] = field(default_factory=list)


__all__ = ["IngestionReport", "SourceError"]


def ingest_all(
    root: Path,
    http: HttpGetter,
    source_config: Mapping[str, object],
    extras_config: object,
    report: IngestionReport,
) -> list[App]:
    """Fetch every source in precedence order and retain structured outcomes.

    Candidates come back as their sources describe them; composition applies
    the policy. Every committed codm2000 entry joins the candidate set.
    """
    from . import bboi, codm, extras, rjny

    def section(name: str) -> Mapping[str, object]:
        value = source_config.get(name)
        if not isinstance(value, dict):
            raise SourceError(name, "source configuration must be an object")
        return value

    if not isinstance(extras_config, list):
        raise SourceError("extras", "configuration must be a list")
    rjny_apps = rjny.fetch(http, section("rjny"))
    bboi_apps = bboi.fetch(http, section("bboi"))
    extra_apps = extras.fetch(extras_config)
    generated = codm.fetch(root, section("codm"), report)
    return [*rjny_apps, *bboi_apps, *generated, *extra_apps]


def load_json(path: str | PathLike[str], source: str) -> object:
    """Read a JSON source configuration with a source-named error."""
    try:
        data = Path(path).read_bytes()
    except OSError as error:
        raise SourceError(source, str(error)) from error
    return parse_json(data, source)


def parse_json(data: bytes, source: str) -> object:
    """Decode captured JSON configuration bytes with a source-named error."""
    try:
        return json.loads(data)
    except Exception as error:
        raise SourceError(source, str(error)) from error


__all__ += ["ingest_all", "load_json", "parse_json"]
