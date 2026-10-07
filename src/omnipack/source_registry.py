"""Every pack source's origins, precedence and generated-catalog eligibility."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from omnipack.model import Source, Variant

type GeneratedSource = Literal[Source.CODM, Source.QUIVER]
"""The sources whose committed catalogs are generated from an upstream list."""


@dataclass(frozen=True, slots=True)
class GeneratedCatalog:
    """How a generated source's committed entries enter composition."""

    origin: str
    eligibility: frozenset[Variant]


GENERATED: Mapping[GeneratedSource, GeneratedCatalog] = {
    # codm lists dual-screen builds only.
    Source.CODM: GeneratedCatalog("codm-generated", frozenset({Variant.DUAL})),
    Source.QUIVER: GeneratedCatalog("quiver-generated", frozenset(Variant)),
}

ORIGINS: Mapping[Source, frozenset[str]] = {
    Source.RJNY: frozenset({"rjny-catalog"}),
    Source.BBOI: frozenset({"bboi-standard-asset", "bboi-dual-asset"}),
    Source.EXTRAS: frozenset({"extras"}),
    **{source: frozenset({catalog.origin}) for source, catalog in GENERATED.items()},
}

# Lowest first: within a selection tier, the later source wins.
PRECEDENCE: tuple[Source, ...] = (
    Source.CODM,
    Source.BBOI,
    Source.QUIVER,
    Source.RJNY,
    Source.EXTRAS,
)
