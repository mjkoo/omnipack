"""Upstream source fetchers and their shared ingestion diagnostics."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from os import PathLike
from typing import Any

from omnipack.model import App
from omnipack.package_id import ProjectResolver, ResolutionStatus

from .common import HttpGetter, SourceError


@dataclass(slots=True)
class IngestionReport:
    """Structured source outcomes consumed by the eventual build report."""

    skipped: list[dict[str, Any]] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    generated: list[dict[str, Any]] = field(default_factory=list)
    retained_failures: list[dict[str, Any]] = field(default_factory=list)

    def record_resolution(
        self, url: str, app: App | None, status: ResolutionStatus, failure: str | None
    ) -> None:
        item = {"source": "codm2000", "url": url}
        if app is None:
            self.unresolved.append({**item, "failure": failure})
        else:
            self.generated.append({**item, "id": app.id, "status": status.value})
            if failure:
                self.retained_failures.append(
                    {**item, "id": app.id, "failure": failure}
                )


__all__ = ["IngestionReport", "SourceError"]


@dataclass(frozen=True, slots=True)
class IngestionResult:
    apps: list[App]
    report: IngestionReport


def ingest_all(
    http: HttpGetter,
    source_config: Mapping[str, object],
    extras_config: object,
    resolver: ProjectResolver,
    report: IngestionReport | None = None,
) -> IngestionResult:
    """Fetch every source in precedence order and retain structured outcomes."""
    from . import bboi, codm, extras, rjny

    def section(name: str) -> Mapping[str, object]:
        value = source_config.get(name)
        if not isinstance(value, dict):
            raise SourceError(name, "source configuration must be an object")
        return value

    if not isinstance(extras_config, list):
        raise SourceError("extras", "configuration must be a list")
    report = report or IngestionReport()
    rjny_apps = rjny.fetch(http, section("rjny"))
    bboi_apps = bboi.fetch(http, section("bboi"))
    extra_apps = extras.fetch(extras_config)
    higher = [*extra_apps, *rjny_apps, *bboi_apps]
    generated = codm.fetch(http, section("codm"), resolver, higher, report)
    return IngestionResult([*rjny_apps, *bboi_apps, *generated, *extra_apps], report)


def load_json(path: str | PathLike[str], source: str) -> object:
    """Read a JSON source configuration with a source-named error."""
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except Exception as error:
        raise SourceError(source, str(error)) from error


__all__ += ["IngestionResult", "ingest_all", "load_json"]
