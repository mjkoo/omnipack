"""Keep Python report vocabularies aligned with their serialized contracts."""

import json

import pytest

from omnipack.offline import Finding
from omnipack.report import _fingerprint
from omnipack.report_model import (
    BuildStage,
    InputState,
    OfflineStatus,
    Status,
    not_run_verdict,
)
from scripts.source_proposal import GENERATION_SUCCESS_STATUS


def test_generation_success_matches_the_standalone_script_boundary() -> None:
    assert GENERATION_SUCCESS_STATUS == Status.SUCCESS.value


@pytest.mark.parametrize("vocabulary", [Status, OfflineStatus, InputState, BuildStage])
def test_wire_values_round_trip_as_plain_strings(vocabulary) -> None:
    for member in vocabulary:
        decoded = json.loads(json.dumps(member))
        assert type(decoded) is str
        assert decoded == member.value == member


def test_default_verdict_does_not_share_mutable_findings() -> None:
    first = not_run_verdict()
    first["findings"].append(Finding("input", "missing", "missing input").to_record())
    assert not_run_verdict() == {"status": "not-run", "findings": []}


@pytest.mark.parametrize("state", [None, [], {}, 0, "unknown"])
def test_invalid_input_states_are_rejected(state: object) -> None:
    assert not _fingerprint({"state": state})


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
