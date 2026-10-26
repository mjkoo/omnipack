import pytest

from omnipack.discovery import DiscoveryError, discover
from omnipack.model import Source
from omnipack.source_registry import GENERATED, ORIGINS, PRECEDENCE, GeneratedSource
from tests.http_support import FakeHttp


def test_every_source_has_origins_and_one_precedence_rank() -> None:
    assert set(ORIGINS) == set(Source)
    assert sorted(PRECEDENCE) == sorted(Source)


def test_generated_sources_have_their_catalog_origin() -> None:
    for source, catalog in GENERATED.items():
        assert ORIGINS[source] == {catalog.origin}


def test_codm_lists_dual_screen_builds_and_quiver_baseline_builds() -> None:
    assert {source: catalog.dual_screen for source, catalog in GENERATED.items()} == {
        Source.CODM: True,
        Source.QUIVER: False,
    }


@pytest.mark.parametrize("source", list(GENERATED))
def test_every_generated_source_has_discovery(source: GeneratedSource) -> None:
    # A source without discovery would fail the lookup before reading its
    # configuration.
    with pytest.raises(DiscoveryError, match="source configuration"):
        discover(source, {}, FakeHttp({}), frozenset())
