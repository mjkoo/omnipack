from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from omnipack.urls import normalize_project_url

ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures/source-generation/codm"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def test_migration_inventory_maps_captured_projects_and_cache_entries() -> None:
    inventory = load_fixture("migration-inventory.json")
    captured_cache = json.loads((ROOT / "config/package-ids.json").read_text())
    projects = inventory["projects"]

    assert len(projects) == 24
    assert len({project["url"] for project in projects}) == len(projects)
    captured_urls = {
        normalize_project_url(url)
        for url in re.findall(
            r"\[[^\]]+\]\((https?://[^)\s]+)\)",
            (ROOT / inventory["capturedReadme"]).read_text(),
        )
        if normalize_project_url(url).startswith("github.com/")
    }
    assert {project["url"] for project in projects} == captured_urls
    assert {project["status"] for project in projects} == {
        "previously-admitted",
        "higher-source-dual-coverage",
        "unresolved-unadmitted",
    }
    for project in projects:
        cache = project["packageIdCache"]
        if cache is None:
            assert project["url"] not in captured_cache
        else:
            assert cache == captured_cache[project["url"]]

    unresolved = {
        project["url"]
        for project in projects
        if project["status"] == "unresolved-unadmitted"
    }
    assert unresolved == {
        "github.com/averageconsumer/kanto-gear",
        "github.com/castdrian/showdown-ds",
        "github.com/emulnk/emulnk",
        "github.com/mastercook777/heimdall-ayn-thor-assistant",
    }

    captured_higher_urls: set[str] = set()
    for name in ("rjny-applications.json", "bboi-single.json", "bboi-dual.json"):
        document = json.loads((ROOT / "tests/fixtures" / name).read_text())
        captured_higher_urls.update(
            normalize_project_url(app["url"]) for app in document["apps"]
        )
    replacements = json.loads(
        (
            ROOT / "tests/fixtures/composition-baseline/replacement-candidates.json"
        ).read_text()
    )
    for pair in replacements["pairs"]:
        captured_higher_urls.update(
            normalize_project_url(pair[side]["url"]) for side in ("standard", "dual")
        )
    assert {
        project["url"] for project in projects if project["higherSource"] is not None
    } <= captured_higher_urls


def test_migration_inventory_pins_reproducible_exports_and_family_winners() -> None:
    inventory = load_fixture("migration-inventory.json")
    baseline = ROOT / "tests/fixtures/composition-baseline"
    index = json.loads((baseline / "index.json").read_text())

    recorded_outputs = {item["variant"]: item for item in inventory["baselineOutputs"]}
    for output in index["outputs"]:
        contents = (baseline / output["file"]).read_bytes()
        assert recorded_outputs[output["variant"]] == {
            "variant": output["variant"],
            "file": output["file"],
            "appCount": output["appCount"],
            "sha256": hashlib.sha256(contents).hexdigest(),
        }

    assert inventory["familyWinners"] == {
        "app:ctr": {
            "single": "github.com/simon358/ctr-native-android",
            "dual": "github.com/igawa6/ctr-native-android",
        },
        "app:dusklight": {
            "single": "github.com/twilitrealm/dusklight",
            "dual": "github.com/igawa6/dusklight",
        },
        "app:openmw": {
            "single": "github.com/xyzz/openmw-android",
            "dual": "github.com/josh-daniels/openmw-ds",
        },
        "app:super-metroid": {
            "single": "github.com/raekwon1603/super_metroid-android",
            "dual": "github.com/raekwon1603/retroarch",
        },
    }


def test_accepted_state_fixtures_are_bound_and_define_candidate_layout() -> None:
    catalog_bytes = (FIXTURES / "accepted/catalog.json").read_bytes()
    catalog = json.loads(catalog_bytes)
    metadata = load_fixture("accepted/source.json")
    state = load_fixture("accepted/resolution-state.json")
    layout = load_fixture("candidate-layout.json")

    assert metadata == {
        "schemaVersion": 1,
        "sourceUrl": "https://example.invalid/codm/README.md",
        "readmeSha256": hashlib.sha256(
            (FIXTURES / "accepted/README.md").read_bytes()
        ).hexdigest(),
        "catalogSha256": hashlib.sha256(catalog_bytes).hexdigest(),
    }
    by_url = {
        app["url"].removeprefix("https://").lower(): app for app in catalog["apps"]
    }
    assert set(by_url) == set(state)
    assert all(state[url]["packageId"] == app["id"] for url, app in by_url.items())
    assert layout["root"] == ".build/source-generation/codm"
    assert set(layout["currentRunFiles"]) == {
        "catalog.json",
        "source.json",
        "resolution-state.json",
        "report.json",
    }


def test_generation_cases_cover_required_migration_boundaries() -> None:
    cases = load_fixture("cases.json")
    assert set(cases) == {
        "newProject",
        "acceptedFallback",
        "coveredDualProject",
        "singleOnlyCoverage",
        "removal",
        "conflictingPackageIds",
    }
    assert cases["newProject"]["accepted"] is False
    assert cases["acceptedFallback"]["accepted"] is True
    assert cases["coveredDualProject"]["higherSourceEligibility"] == ["dual"]
    assert cases["singleOnlyCoverage"]["higherSourceEligibility"] == ["single"]
    assert cases["removal"]["accepted"] is True
    conflict = cases["conflictingPackageIds"]
    assert conflict["projects"][0]["packageId"] == conflict["projects"][1]["packageId"]
    assert conflict["projects"][0]["url"] != conflict["projects"][1]["url"]
