"""Keep Python report vocabularies aligned with their serialized contracts."""

import json
from enum import StrEnum
from typing import get_args

import pytest

from omnipack.offline import Finding
from omnipack.report_model import (
    BuildStage,
    InputState,
    OfflineStatus,
    Status,
)
from omnipack.source_registry import GeneratedSource
from scripts.source_proposal import GENERATION_SUCCESS_STATUS, SourceName


def test_generation_success_matches_the_standalone_script_boundary() -> None:
    assert GENERATION_SUCCESS_STATUS == Status.SUCCESS.value


def test_proposal_sources_match_the_generated_sources() -> None:
    assert set(get_args(SourceName)) == set(GeneratedSource)


@pytest.mark.parametrize("vocabulary", [Status, OfflineStatus, InputState, BuildStage])
def test_wire_values_round_trip_as_plain_strings(vocabulary: type[StrEnum]) -> None:
    for member in vocabulary:
        decoded = json.loads(json.dumps(member))
        assert type(decoded) is str
        assert decoded == member.value == member == str(member)


def test_finding_serialization_preserves_location_and_omits_absence() -> None:
    assert Finding("input", "missing", "missing input").to_record() == {
        "stage": "input",
        "code": "missing",
        "message": "missing input",
    }
    record = Finding(
        "pack", "invalid", "invalid field", "single", "app.id", 0, "url"
    ).to_record()
    assert record == {
        "stage": "pack",
        "code": "invalid",
        "message": "invalid field",
        "variant": "single",
        "entry_id": "app.id",
        "index": 0,
        "field": "url",
    }
