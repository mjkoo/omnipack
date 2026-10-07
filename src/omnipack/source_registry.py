"""Every pack source: its name, origins, precedence and generated-catalog eligibility.

A source's name is its provenance. Every source but extras, which reads
`config/extras.json`, is configured by the `config/sources.json` section of
that name, and a generated source's name is also its `generate-source`
subcommand.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from omnipack.model import Variant


class Source(StrEnum):
    """Every source a build ingests."""

    RJNY = "rjny"
    BBOI = "bboi"
    EXTRAS = "extras"
    CODM = "codm"
    QUIVER = "quiver"


class GeneratedSource(StrEnum):
    """The sources whose committed catalogs are generated from an upstream list."""

    CODM = Source.CODM.value
    QUIVER = Source.QUIVER.value


@dataclass(frozen=True, slots=True)
class GeneratedCatalog:
    """How a generated source's committed entries enter composition."""

    origin: str
    eligibility: frozenset[Variant]


GENERATED: Mapping[GeneratedSource, GeneratedCatalog] = {
    # codm lists dual-screen builds only.
    GeneratedSource.CODM: GeneratedCatalog("codm-generated", frozenset({Variant.DUAL})),
    GeneratedSource.QUIVER: GeneratedCatalog("quiver-generated", frozenset(Variant)),
}

ORIGINS: Mapping[Source, frozenset[str]] = {
    Source.RJNY: frozenset({"rjny-catalog"}),
    Source.BBOI: frozenset({"bboi-standard-asset", "bboi-dual-asset"}),
    Source.EXTRAS: frozenset({"extras"}),
    **{
        Source(source): frozenset({catalog.origin})
        for source, catalog in GENERATED.items()
    },
}

# Lowest first: within a selection tier, the later source wins.
PRECEDENCE: tuple[Source, ...] = (
    Source.CODM,
    Source.BBOI,
    Source.QUIVER,
    Source.RJNY,
    Source.EXTRAS,
)
