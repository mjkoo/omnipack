from __future__ import annotations

import json

from omnipack.model import Variant
from omnipack.render import render
from tests.current_config_support import (
    CurrentConfiguration,
    current_configuration_fixture,  # noqa: F401
)

TRACKER_ID = "809443320"


def test_tracker_id_does_not_collide_with_any_current_candidate(
    current_configuration: CurrentConfiguration,
) -> None:
    matches = [
        candidate
        for candidate in current_configuration.candidates
        if candidate.id == TRACKER_ID
    ]
    assert [(candidate.provenance.source, candidate.url) for candidate in matches] == [
        ("extras", "https://github.com/mjkoo/omnipack")
    ]


def test_tracker_is_identical_and_present_once_in_both_variants(
    current_configuration: CurrentConfiguration,
) -> None:
    rendered = {}
    for variant in Variant:
        document = json.loads(render(current_configuration.result.apps[variant]))
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


def test_current_candidates_include_track_only_ids_for_composition_to_reserve(
    current_configuration: CurrentConfiguration,
) -> None:
    # Composing the fixture fails if any other candidate takes one of these ids, so
    # this only guards against the reservation being checked against nothing.
    track_only = {
        app.id
        for app in current_configuration.candidates
        if app.additional_settings.get("trackOnly") is True
    }
    assert TRACKER_ID in track_only
