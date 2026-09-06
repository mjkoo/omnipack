from obtainium_pack.model import App, Provenance, SourceType, Variant


def test_candidates_for_the_same_id_stay_distinct_by_variant() -> None:
    provenance = Provenance(source="fixture", url="https://example.com/catalog.json")
    single = App(
        id="org.example.app",
        url="https://github.com/example/single",
        name="Example",
        source_type=SourceType.GITHUB,
        categories=("Emulator",),
        variant=Variant.SINGLE,
        provenance=provenance,
    )
    dual = App(
        id="org.example.app",
        url="https://github.com/example/dual",
        name="Example Dual",
        source_type=SourceType.GITHUB,
        categories=("Emulator",),
        variant=Variant.DUAL,
        provenance=provenance,
    )

    assert single.variant is Variant.SINGLE
    assert dual.variant is Variant.DUAL
    assert single != dual
