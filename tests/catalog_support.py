"""Construct a current README for integration fixtures with serialized packs."""

from pathlib import Path

from omnipack.catalog import generate_catalog, replace_catalog
from omnipack.composition_policy import load_composition_policy


def write_catalog(root: Path) -> None:
    readme = root / "README.md"
    template = (
        readme.read_bytes()
        if readme.exists()
        else b"Fixture guide\n<!-- omnipack:catalog:start -->\n<!-- omnipack:catalog:end -->\n"
    )
    catalog = generate_catalog(
        (root / "dist/single-screen.json").read_bytes(),
        (root / "dist/dual-screen.json").read_bytes(),
        load_composition_policy((root / "config/composition.json").read_bytes()),
    )
    readme.write_bytes(replace_catalog(template, catalog))
