from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from omnipack.composition_policy import parse_composition_policy
from omnipack.merge import compose
from omnipack.model import Variant
from omnipack.urls import normalize_project_url
from tests.current_config_support import (
    CurrentConfiguration,
    current_configuration_fixture,  # noqa: F401
)

ROOT = Path(__file__).parents[1]
PICORI = "github.com/999sian/tmc"
SAM = "github.com/samyost1/tmc-android"


@pytest.mark.parametrize("refresh", [False, True], ids=["current", "refreshed"])
def test_minish_cap_variant_selection_survives_upstream_settings_refresh(
    current_configuration: CurrentConfiguration, refresh: bool
) -> None:
    candidates = current_configuration.candidates
    if refresh:
        candidates = [
            replace(
                app,
                additional_settings={
                    **app.additional_settings,
                    "apkFilterRegEx": "upstream-renamed.apk",
                    "versionDetection": False,
                },
            )
            if normalize_project_url(app.url) == SAM
            else app
            for app in candidates
        ]
    result = compose(
        candidates,
        json.loads((ROOT / "config/deny.json").read_text()),
        json.loads((ROOT / "config/overlay.json").read_text()),
        policy=parse_composition_policy(current_configuration.policy),
    )
    for variant, project in [(Variant.SINGLE, PICORI), (Variant.DUAL, SAM)]:
        [app] = [
            app
            for app in result.apps[variant]
            if normalize_project_url(app.url) in {PICORI, SAM}
        ]
        assert normalize_project_url(app.url) == project
        assert app.id == "dev.picori.tmc"
        [selection] = [
            item
            for item in result.report.selections
            if item.variant is variant and item.family == app.family
        ]
        if variant is Variant.SINGLE:
            assert any(
                item.origin == "bboi-standard-asset"
                and normalize_project_url(item.url) == SAM
                for item in selection.considered
            )
            settings = app.data["additionalSettings"]
            pattern = settings["apkFilterRegEx"]
            assert re.fullmatch(pattern, "tmc-multi-android-v0.9.3.apk")
            assert re.fullmatch(pattern, "tmc-multi-android-v0.10.0.apk")
            assert not re.fullmatch(pattern, "tmc-multi-linux-arm64-v0.9.3.tar.gz")
            assert settings["versionDetection"] is True
            assert settings["includePrereleases"] is False
            assert settings["trackOnly"] is False
            assert settings["includeZips"] is False
            assert "ROM" in settings["about"]
        else:
            assert selection.origin == "bboi-dual-asset"
            if refresh:
                assert (
                    app.data["additionalSettings"]["apkFilterRegEx"]
                    == "upstream-renamed.apk"
                )
