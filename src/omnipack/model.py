"""Normalized representation of a pack entry, independent of its upstream source."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

_ELIGIBILITY_UNSET = cast(frozenset["Variant"], object())


class Variant(str, Enum):
    """Which rendered pack an entry belongs to."""

    SINGLE = "single"
    DUAL = "dual"


class SourceType(str, Enum):
    """Obtainium source implementations supported by the pack."""

    GITHUB = "GitHub"
    HTML = "HTML"


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where an entry came from, for the build report."""

    source: str
    url: str


@dataclass(frozen=True, slots=True)
class App:
    """One Obtainium app entry, normalized across upstream sources.

    `additional_settings` is always a dict here; sources.render is
    responsible for the Obtainium export's string-encoded form.
    `raw` carries any Obtainium fields not otherwise modeled, keyed by
    their Obtainium field name.
    """

    id: str
    url: str
    name: str
    source_type: SourceType
    categories: tuple[str, ...]
    variant: Variant
    provenance: Provenance
    additional_settings: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    eligibility: frozenset[Variant] = field(default=_ELIGIBILITY_UNSET)
    dual_preferred: bool = False
    origin: str | None = None
    original_id: str | None = None
    family: str | None = None

    def __post_init__(self) -> None:
        # Adapters migrate to source-derived, multi-target eligibility separately.
        # These defaults keep the existing per-variant normalized record contract.
        if self.eligibility is _ELIGIBILITY_UNSET:
            object.__setattr__(self, "eligibility", frozenset({self.variant}))
        if self.origin is None:
            object.__setattr__(self, "origin", self.provenance.source)
        if self.original_id is None:
            object.__setattr__(self, "original_id", self.id)
