from dataclasses import fields
from typing import Any

import pytest

from omnipack.model import App, Provenance, SourceType, Variant


def app(eligibility: frozenset[Variant]) -> App:
    return App(
        id="org.example.app",
        url="https://github.com/example/app",
        name="Example",
        source_type=SourceType.GITHUB,
        categories=("Emulator",),
        provenance=Provenance(source="fixture", url="https://example.com/c.json"),
        eligibility=eligibility,
    )


def test_eligibility_is_required_and_no_variant_field_remains() -> None:
    names = {field.name for field in fields(App)}
    assert "variant" not in names and "dual_preferred" not in names
    incomplete: dict[str, Any] = {
        "id": "org.example.app",
        "url": "https://github.com/example/app",
        "name": "Example",
        "source_type": SourceType.GITHUB,
        "categories": (),
        "provenance": Provenance(source="fixture", url="https://example.com"),
    }
    with pytest.raises(TypeError, match="eligibility"):
        App(**incomplete)


@pytest.mark.parametrize(
    ("eligibility", "preferred"),
    [
        (frozenset({Variant.DUAL}), True),
        (frozenset(Variant), False),
        (frozenset({Variant.SINGLE}), False),
        (frozenset(), False),
    ],
)
def test_dual_preference_is_derived_from_dual_only_eligibility(
    eligibility: frozenset[Variant], preferred: bool
) -> None:
    assert app(eligibility).dual_preferred is preferred


def test_origin_and_original_id_default_from_provenance_and_id() -> None:
    built = app(frozenset(Variant))
    assert (built.origin, built.original_id) == ("fixture", "org.example.app")
