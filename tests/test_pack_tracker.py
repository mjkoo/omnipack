from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from omnipack.model import Variant
from omnipack.overlay import ComposedApp
from omnipack.render import render
from omnipack.sources.extras import fetch

ROOT = Path(__file__).parents[1]
TRACKER_ID = "809443320"


def _tracker():
    entries = fetch(json.loads((ROOT / "config/extras.json").read_text()))
    return next(entry for entry in entries if entry.id == TRACKER_ID)


def _render_tracker(variant: Variant) -> str:
    tracker = _tracker()
    data = deepcopy(tracker.raw)
    data.update(
        id=tracker.id,
        url=tracker.url,
        name=tracker.name,
        categories=list(tracker.categories),
        overrideSource=tracker.source_type.value,
        additionalSettings=tracker.additional_settings,
    )
    return render([ComposedApp(variant, tracker.provenance, data)], {})


def test_tracker_id_does_not_collide_with_any_source_or_output_fixture() -> None:
    paths = [ROOT / "config/extras.json", *ROOT.glob("tests/fixtures/**/*.json")]
    occurrences: list[Path] = []
    for path in paths:
        if TRACKER_ID in path.read_text():
            occurrences.append(path.relative_to(ROOT))
    assert occurrences == [Path("config/extras.json")]


def test_tracker_is_identical_and_present_once_in_both_variants() -> None:
    rendered = {}
    for variant in Variant:
        document = json.loads(_render_tracker(variant))
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


def test_observed_revision_is_not_rendered_state() -> None:
    tracker = _tracker()
    data = dict(tracker.raw)
    data.update(
        id=tracker.id,
        url=tracker.url,
        name=tracker.name,
        categories=list(tracker.categories),
        overrideSource=tracker.source_type.value,
        additionalSettings=tracker.additional_settings,
    )
    original = deepcopy(data)
    records = {
        variant: ComposedApp(variant, tracker.provenance, data) for variant in Variant
    }
    before = {variant: render([record], {}) for variant, record in records.items()}
    after = {variant: render([record], {}) for variant, record in records.items()}
    assert data == original
    assert data["additionalSettings"] is tracker.additional_settings
    assert before == after
    for document in after.values():
        [entry] = json.loads(document)["apps"]
        assert "installedVersion" not in entry
        assert "latestVersion" not in entry
