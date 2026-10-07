from omnipack import discovery
from omnipack.source_registry import (
    GENERATED,
    ORIGINS,
    PRECEDENCE,
    GeneratedSource,
    Source,
)


def test_every_source_has_origins_and_one_precedence_rank() -> None:
    assert set(ORIGINS) == set(Source)
    assert sorted(PRECEDENCE) == sorted(Source)


def test_generated_sources_are_sources_with_their_catalog_origin() -> None:
    assert set(GENERATED) == set(GeneratedSource)
    for source, catalog in GENERATED.items():
        assert ORIGINS[Source(source)] == {catalog.origin}


def test_every_generated_source_has_discovery() -> None:
    assert set(discovery._DISCOVERERS) == set(GeneratedSource)
