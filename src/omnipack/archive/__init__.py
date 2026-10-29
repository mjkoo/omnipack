"""Mirror each packed app's current release, notes and source history.

The package holds the vocabulary every stage shares: the outcome a target
ends a run with, and the release a resolver selected for it.

Release resolution ports ImranR98/Obtainium at commit
fcd1807c8f8d2b8a5e27d4214ac4d472ed045598: the GitHub, GitLab and HTML sources
(`lib/app_sources/github.dart`, `gitlab.dart`, `html.dart`) and the shared
version and APK filtering (`source_provider.dart`, `version_service.dart`,
`apk_filter_service.dart`). A later re-sync diffs against that commit. The
resolvers raise `UnreachableError` or `NoReleaseError` for a target that ends
a run as such; any other exception means the target failed.
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


class ResolutionError(Exception):
    """A target the resolver could not turn into a release; `outcome` is how
    the target ends the run."""

    outcome: Outcome


class UnreachableError(ResolutionError):
    """The project answers HTTP 404 or 410."""

    outcome = Outcome.UNREACHABLE


class NoReleaseError(ResolutionError):
    """No release qualifies under the entry's settings."""

    outcome = Outcome.NO_RELEASE


@dataclass(frozen=True, slots=True)
class Asset:
    """A file a release offers, named as the source names it."""

    name: str
    url: str


@dataclass(frozen=True, slots=True)
class ResolvedRelease:
    """The release a resolver selected for one target.

    `version` is the string Obtainium would display for the entry. `raw_record`
    is a forge's own release record, empty for an HTML source; `fetched_urls`
    are the pages an HTML source fetched while resolving, in order.
    """

    version: str
    tag: str | None = None
    date: datetime | None = None
    notes: str | None = None
    raw_record: dict[str, Any] = field(default_factory=dict)
    assets: tuple[Asset, ...] = ()
    fetched_urls: tuple[str, ...] = ()
