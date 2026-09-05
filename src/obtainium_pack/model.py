"""Normalized representation of a pack entry, independent of its upstream source."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Variant(str, Enum):
    """Which rendered pack an entry belongs to."""

    SINGLE = "single"
    DUAL = "dual"


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where an entry came from, for the build report."""

    source: str
    url: str


@dataclass(slots=True)
class App:
    """One Obtainium app entry, normalized across upstream sources.

    `additional_settings` is always a dict here; sources.render is
    responsible for the Obtainium export's string-encoded form.
    `raw` carries any Obtainium fields not otherwise modeled, keyed by
    their Obtainium field name.
    """

    id: str
    url: str
    additional_settings: dict[str, Any]
    variants: frozenset[Variant]
    provenance: Provenance
    raw: dict[str, Any] = field(default_factory=dict)
