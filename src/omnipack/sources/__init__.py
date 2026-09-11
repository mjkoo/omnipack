"""Upstream source fetchers and their shared ingestion diagnostics."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any

from omnipack.composition_policy import (
    CompositionPolicy,
    apply_composition_policy,
)
from omnipack.model import App

from .common import HttpGetter, SourceError


@dataclass(slots=True)
class IngestionReport:
    """Structured source outcomes consumed by the eventual build report."""

    skipped: list[dict[str, Any]] = field(default_factory=list)
    admitted: list[dict[str, Any]] = field(default_factory=list)


__all__ = ["IngestionReport", "SourceError"]


@dataclass(frozen=True, slots=True)
class IngestionResult:
    apps: list[App]
    report: IngestionReport
    policy: CompositionPolicy | None = None
    policy_bytes: bytes | None = None


def ingest_all(
    root: Path,
    http: HttpGetter,
    source_config: Mapping[str, object],
    extras_config: object,
    policy: CompositionPolicy,
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
    applied_higher = apply_composition_policy(
        policy, higher, require_all=False
    ).candidates
    generated = codm.fetch(root, section("codm"), applied_higher, report)
    all_candidates = [*rjny_apps, *bboi_apps, *generated, *extra_apps]
    applied = apply_composition_policy(policy, all_candidates)
    return IngestionResult(list(applied.candidates), report, policy)


def load_json(path: str | PathLike[str], source: str) -> object:
    """Read a JSON source configuration with a source-named error."""
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except Exception as error:
        raise SourceError(source, str(error)) from error


__all__ += ["IngestionResult", "ingest_all", "load_json"]
