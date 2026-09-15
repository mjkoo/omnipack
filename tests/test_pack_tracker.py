from __future__ import annotations

import json
from pathlib import Path

from omnipack.merge import CompositionResult
from omnipack.model import App, Variant
from omnipack.render import render
from omnipack.sources import codm
from tests.test_source_generation_fixtures import (
    _compose_with_codm_catalog,
    captured_higher,
    load_json,
)

ROOT = Path(__file__).parents[1]
TRACKER_ID = "809443320"


def _current_candidates(tmp_path: Path) -> tuple[list[App], CompositionResult]:
    higher = captured_higher(load_json(ROOT / "config/extras.json"))
    catalog = load_json(ROOT / "config/catalogs/codm.json")
    result = _compose_with_codm_catalog(catalog, tmp_path, higher)
    generated = codm.fetch(tmp_path, {"catalog": "codm.json"}, higher)
    return [*higher, *generated], result


def test_tracker_id_does_not_collide_with_any_current_candidate(
    tmp_path: Path,
) -> None:
    candidates, _ = _current_candidates(tmp_path)
    matches = [candidate for candidate in candidates if candidate.id == TRACKER_ID]
    assert [(candidate.provenance.source, candidate.url) for candidate in matches] == [
        ("extras", "https://github.com/mjkoo/omnipack")
    ]


def test_tracker_is_identical_and_present_once_in_both_variants(
    tmp_path: Path,
) -> None:
    _, result = _current_candidates(tmp_path)
    rendered = {}
    for variant in Variant:
        document = json.loads(render(result.apps[variant]))
        matches = [entry for entry in document["apps"] if entry["id"] == TRACKER_ID]
        assert len(matches) == 1
        rendered[variant] = matches[0]
    assert rendered[Variant.SINGLE] == rendered[Variant.DUAL]
    settings = json.loads(rendered[Variant.SINGLE]["additionalSettings"])
    assert settings["trackOnly"] is True
    assert settings["releaseTitleAsVersion"] is True
    assert settings["apkFilterRegEx"] == ""
    assert settings["versionExtractionRegEx"] == r"[0-9]+$"
    assert settings["matchGroupToUse"] == "0"
    assert settings["filterReleaseTitlesByRegEx"] == r"^omnipack revision [0-9]+$"
    assert settings["includePrereleases"] is True
    assert settings["fallbackToOlderReleases"] is True
    assert settings["versionDetection"] is False
    assert "installedVersion" not in rendered[Variant.SINGLE]
    assert "latestVersion" not in rendered[Variant.SINGLE]
