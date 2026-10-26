from omnipack.model import App, Provenance, Source, SourceType


def app() -> App:
    return App(
        id="org.example.app",
        url="https://github.com/example/app",
        name="Example",
        source_type=SourceType.GITHUB,
        categories=("Emulator",),
        provenance=Provenance(source=Source.RJNY, url="https://example.com/c.json"),
        dual_screen=False,
    )


def test_origin_defaults_from_provenance() -> None:
    assert app().origin == "rjny"
