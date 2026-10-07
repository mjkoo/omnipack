"""Shared composition fixture for the committed configuration and captured inputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from omnipack.composition_policy import load_composition_policy
from omnipack.merge import CompositionResult, compose
from omnipack.model import App
from omnipack.source_catalog import render_catalog
from omnipack.source_registry import GENERATED
from omnipack.sources import bboi, generated, rjny
from omnipack.sources.extras import fetch as fetch_extras
from tests.http_support import FakeHttp

ROOT = Path(__file__).parents[1]
CAPTURED = ROOT / "tests/fixtures/reconciliation"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def assert_canonical_catalog(catalog: Path) -> None:
    """Fail unless a committed source catalog is its entries' canonical bytes."""
    entries = json.loads(catalog.read_bytes())["apps"]
    assert catalog.read_bytes() == render_catalog(entries), (
        f"{catalog} differs from the canonical rendering of its entries"
    )


@dataclass(frozen=True, slots=True)
class CurrentConfiguration:
    extras: list[dict[str, Any]]
    policy: dict[str, Any]
    catalog: dict[str, Any]
    candidates: list[App]
    result: CompositionResult


def build_current_configuration() -> CurrentConfiguration:
    sources = load_json(ROOT / "config/sources.json")
    release = load_json(CAPTURED / "bboi-release.json")
    standard_url, dual_url = (
        asset["browser_download_url"] for asset in release["assets"]
    )
    bboi_api = (
        "https://codeberg.org/api/v1/repos/"
        f"{sources['bboi']['codeberg_repo']}/releases/latest"
    )
    rjny_url = (
        f"https://raw.githubusercontent.com/{sources['rjny']['repo']}/"
        f"{sources['rjny']['branch']}/{sources['rjny']['path']}"
    )
    http = FakeHttp(
        {
            bboi_api: json.dumps(release),
            standard_url: (CAPTURED / "bboi-standard.json").read_text(),
            dual_url: (CAPTURED / "bboi-dual.json").read_text(),
            rjny_url: (CAPTURED / "rjny.json").read_text(),
        }
    )
    extras = load_json(ROOT / "config/extras.json")
    higher = [
        *rjny.fetch(http, sources["rjny"]),
        *bboi.fetch(http, sources["bboi"]),
        *fetch_extras(extras),
    ]
    generated_apps = [
        app
        for source in GENERATED
        for app in generated.fetch_generated(source, ROOT, sources[source])
    ]
    candidates = [*higher, *generated_apps]
    composition = (ROOT / "config/composition.json").read_bytes()
    policy = json.loads(composition)
    denials = load_json(ROOT / "config/deny.json")
    overlay = load_json(ROOT / "config/overlay.json")
    catalog = load_json(ROOT / sources["codm"]["catalog"])
    result = compose(
        candidates,
        denials,
        overlay,
        policy=load_composition_policy(composition),
    )
    return CurrentConfiguration(
        extras,
        policy,
        catalog,
        candidates,
        result,
    )


@pytest.fixture(name="current_configuration", scope="session")
def current_configuration_fixture() -> CurrentConfiguration:
    return build_current_configuration()
