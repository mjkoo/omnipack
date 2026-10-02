"""Normalized representation of a pack entry, independent of its upstream source."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any


class Variant(str, Enum):
    """Which rendered pack an entry belongs to."""

    SINGLE = "single"
    DUAL = "dual"


class SourceType(str, Enum):
    """Obtainium source implementations supported by the pack."""

    GITHUB = "GitHub"
    HTML = "HTML"
    GITLAB = "GitLab"


class Category(StrEnum):
    """The closed set of categories a rendered pack entry may carry.

    The spellings are RJNY's and BBoi's, so imported categories merge with
    the ones users already have. Only track-only entries carry Track Only.
    """

    EMULATOR = "Emulator"
    PC_EMULATION = "PC Emulation"
    DECOMPS = "Decomps/Recomps"
    PC_PORTS = "PC Ports"
    FRONTEND = "Frontend"
    UTILITIES = "Utilities"
    STREAMING = "Streaming"
    TRACK_ONLY = "Track Only"


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
    their Obtainium field name. `eligibility` holds the packs the build's
    source offers it to. An unset `origin` or `original_id` defaults to the
    source and the package id.
    """

    id: str
    url: str
    name: str
    source_type: SourceType
    categories: tuple[str, ...]
    provenance: Provenance
    eligibility: frozenset[Variant]
    additional_settings: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    origin: str = ""
    original_id: str = ""
    family: str | None = None

    def __post_init__(self) -> None:
        if not self.origin:
            object.__setattr__(self, "origin", self.provenance.source)
        if not self.original_id:
            object.__setattr__(self, "original_id", self.id)

    @property
    def dual_preferred(self) -> bool:
        """A dual-screen build: eligible for dual only, and preferred there."""
        return self.eligibility == frozenset({Variant.DUAL})
