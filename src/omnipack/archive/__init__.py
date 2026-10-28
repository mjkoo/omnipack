"""Mirror each packed app's current release, notes and source history.

The package holds the vocabulary every stage shares: the outcome a target
ends a run with, and the release a resolver selected for it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Outcome(StrEnum):
    """How one target's archive attempt ended."""

    ARCHIVED = "archived"
    UNCHANGED = "unchanged"
    UNREACHABLE = "unreachable"
    NO_RELEASE = "no release"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_CHECKED = "not checked"


@dataclass(frozen=True, slots=True)
class Asset:
    """A file a release offers, named as the source names it."""

    name: str
    url: str


@dataclass(frozen=True, slots=True)
class ResolvedRelease:
    """The release a resolver selected for one target.

    `version` is the string Obtainium would display for the entry. `raw_record`
    is the forge's own release record, empty for a source that has none.
    """

    version: str
    tag: str | None = None
    date: datetime | None = None
    notes: str | None = None
    raw_record: dict[str, Any] = field(default_factory=dict)
    assets: tuple[Asset, ...] = ()
