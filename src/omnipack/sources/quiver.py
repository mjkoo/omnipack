"""Load the committed Quiver catalog: baseline builds eligible for both packs."""

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
        source="quiver",
        provenance="quiver",
        origin="quiver-generated",
        eligibility=frozenset(Variant),
    )
