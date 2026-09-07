"""Shared values returned by device-independent source resolvers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ResolutionError(RuntimeError):
    """A source cannot be resolved within the supported compatibility boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class Candidate:
    """One ordered download candidate selected from source metadata."""

    name: str
    url: str


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    """Source evidence produced before any download reachability probe."""

    raw_version: str
    effective_version: str
    version_origin: str
    candidates: tuple[Candidate, ...]
    selected: dict[str, Any] | None = None
    inspected_count: int | None = None
    window_limit: int | None = None
