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
    """Fetch every source and return its candidates in precedence order,
    lowest first, recording generated admissions in `report`.

    Candidates come back as their sources describe them; composition applies
    the policy. Every committed generated entry joins the candidate set.
    """
    from omnipack.source_registry import GENERATED, PRECEDENCE, Source

    from . import bboi, extras, rjny
    from .generated import fetch_generated

    def section(name: str) -> Mapping[str, object]:
        value = source_config.get(name)
        if not isinstance(value, dict):
            raise SourceError(name, "source configuration must be an object")
        return value

    if not isinstance(extras_config, list):
        raise SourceError("extras", "configuration must be a list")
    candidates: dict[Source, list[App]] = {
        Source.RJNY: rjny.fetch(http, section(Source.RJNY)),
        Source.BBOI: bboi.fetch(http, section(Source.BBOI)),
        Source.EXTRAS: extras.fetch(extras_config),
    }
    for source in GENERATED:
        candidates[Source(source)] = fetch_generated(
            source, root, section(source), report
        )
    return [app for source in PRECEDENCE for app in candidates[source]]


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
