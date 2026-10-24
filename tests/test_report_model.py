"""Keep Python report vocabularies aligned with their serialized contracts."""

import json
from enum import StrEnum
from pathlib import Path
from typing import get_args

import pytest

from omnipack.merge import CompositionReport, ListedExtra, ListingSource
from omnipack.model import Source
from omnipack.offline import Finding
from omnipack.overlay import RedundantOverlayKeys
from omnipack.report import BUILD_SCHEMA_VERSION, write_report
from omnipack.report_model import (
    BuildStage,
    InputState,
    OfflineStatus,
    Status,
)
from omnipack.source_registry import GENERATED
from omnipack.sources import IngestionReport
from scripts.source_proposal import GENERATION_SUCCESS_STATUS
from scripts.workflow_support import SourceName


def test_generation_success_matches_the_standalone_script_boundary() -> None:
    assert GENERATION_SUCCESS_STATUS == Status.SUCCESS.value


def test_proposal_sources_match_the_generated_sources() -> None:
    assert set(get_args(SourceName)) == set(GENERATED)


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


def test_override_records_round_trip_through_the_build_report(tmp_path: Path) -> None:
    records = CompositionReport()
    records.redundant_overlay_keys.append(
        RedundantOverlayKeys("github.com/o/z", ("name",))
    )
    records.redundant_overlay_keys.append(
        RedundantOverlayKeys("github.com/o/a", ("additionalSettings.about", "name"))
    )
    records.extras_listed_by_catalog.append(
        ListedExtra(
            "github.com/o/listed",
            "org.b",
            (ListingSource(Source.QUIVER, ("additionalSettings.apkFilterRegEx",)),),
        )
    )
    records.extras_listed_by_catalog.append(
        ListedExtra("github.com/o/listed", "org.a", (ListingSource(Source.RJNY, ()),))
    )
    write_report(tmp_path, {}, None, IngestionReport(), composition_report=records)
    document = json.loads((tmp_path / ".build/report.json").read_text())
    assert document["schemaVersion"] == BUILD_SCHEMA_VERSION == 6
    assert document["redundantOverlayKeys"] == [
        {"url": "github.com/o/a", "keys": ["additionalSettings.about", "name"]},
        {"url": "github.com/o/z", "keys": ["name"]},
    ]
    assert document["extrasListedByCatalog"] == [
        {
            "url": "github.com/o/listed",
            "id": "org.a",
            "sources": [{"source": "rjny", "fields": []}],
        },
        {
            "url": "github.com/o/listed",
            "id": "org.b",
            "sources": [
                {"source": "quiver", "fields": ["additionalSettings.apkFilterRegEx"]}
            ],
        },
    ]
