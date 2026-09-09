from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures/composition-baseline"


@pytest.mark.parametrize(
    ("variant", "count"), [("single-screen", 88), ("dual-screen", 111)]
)
def test_baseline_output_fixture_preserves_committed_pack(
    variant: str, count: int
) -> None:
    baseline = (FIXTURES / f"{variant}.json").read_bytes()
    rendered = json.loads(baseline)
    assert len(rendered["apps"]) == count
    assert rendered["settings"]["categories"]
    assert all(
        {"id", "url", "additionalSettings"} <= app.keys() for app in rendered["apps"]
    )


def test_baseline_index_records_output_integrity_and_source_origins() -> None:
    index = json.loads((FIXTURES / "index.json").read_text())

    for output in index["outputs"]:
        contents = (FIXTURES / output["file"]).read_bytes()
        rendered = json.loads(contents)
        assert hashlib.sha256(contents).hexdigest() == output["sha256"]
        assert len(rendered["apps"]) == output["appCount"]
        assert rendered["settings"] == output["settings"]

    candidates = index["representativeCandidates"]
    assert {candidate["origin"] for candidate in candidates} == {
        "rjny-catalog",
        "bboi-standard-asset",
        "bboi-dual-asset",
        "extras",
        "codm-generated",
    }
    assert {candidate["origin"]: candidate["source"] for candidate in candidates} == {
        "rjny-catalog": "rjny",
        "bboi-standard-asset": "bboi",
        "bboi-dual-asset": "bboi",
        "extras": "extras",
        "codm-generated": "codm2000",
    }
    assert all(
        {"source", "origin", "id", "url", "eligible", "selectedIn"} <= candidate.keys()
        for candidate in candidates
    )

    selected = {
        variant: {
            (app["id"], app["url"])
            for app in json.loads((FIXTURES / f"{variant}-screen.json").read_text())[
                "apps"
            ]
        }
        for variant in ("single", "dual")
    }
    for candidate in candidates:
        for variant in candidate["selectedIn"]:
            assert (candidate["id"], candidate["url"]) in selected[variant]

    ludashi = next(
        candidate
        for candidate in candidates
        if candidate["id"] == "com.winlator.ludashi"
    )
    assert ludashi["selectedRelease"] == "v3.1.h"
    assert ludashi["selectedAsset"] == "bionic-vanilla.apk"
    assert ludashi["settings"]["apkFilterRegEx"] == "bionic-vanilla"
    assert ludashi["settings"]["versionDetection"] is False
