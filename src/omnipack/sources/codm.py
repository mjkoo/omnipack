"""Load the committed codm2000 catalog: dual-screen builds, preferred in dual."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from omnipack.model import App, Variant
from omnipack.sources.generated import fetch_generated


def fetch(
    root: Path,
    config: Mapping[str, object],
    report: Any | None = None,
) -> list[App]:
    return fetch_generated(
        root,
        config,
        report,
        source="codm",
        provenance="codm2000",
        origin="codm-generated",
        eligibility=frozenset({Variant.DUAL}),
    )
