import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "name",
    [
        "rjny-applications.json",
        "rjny-single.json",
        "rjny-dual.json",
        "bboi-single.json",
        "bboi-dual.json",
    ],
)
def test_json_fixture_loads(name: str) -> None:
    assert json.loads((FIXTURES / name).read_text())


def test_rjny_fixture_preserves_duplicate_and_differential_entries() -> None:
    source = json.loads((FIXTURES / "rjny-applications.json").read_text())
    entries_by_id: dict[str, list[dict[str, object]]] = {}
    for app in source["apps"]:
        entries_by_id.setdefault(app["id"], []).append(app)

    assert {app_id for app_id, apps in entries_by_id.items() if len(apps) > 1} == {
        "gamehub.lite",
        "info.cemu.cemu",
        "org.dolphinemu.dolphinemu",
        "xyz.aethersx2.android",
    }
    assert {app["url"] for app in entries_by_id["info.cemu.cemu"]} == {
        "https://github.com/SSimco/Cemu",
        "https://github.com/sapphirerhodonite/cemu",
    }

    single = json.loads((FIXTURES / "rjny-single.json").read_text())
    dual = json.loads((FIXTURES / "rjny-dual.json").read_text())
    single_cemu = next(app for app in single["apps"] if app["id"] == "info.cemu.cemu")
    dual_cemu = next(app for app in dual["apps"] if app["id"] == "info.cemu.cemu")
    assert single_cemu["url"] == "https://github.com/SSimco/Cemu"
    assert dual_cemu["url"] == "https://github.com/sapphirerhodonite/cemu"


def test_bboi_fixtures_preserve_all_cross_asset_ids() -> None:
    single = json.loads((FIXTURES / "bboi-single.json").read_text())
    dual = json.loads((FIXTURES / "bboi-dual.json").read_text())

    assert {app["id"] for app in single["apps"]} == {
        "com.aure.banjorecomp",
        "com.igawa6.harvestmoon64",
        "com.samyost1.zelda3android",
        "com.samyost1.tmcandroid",
    }
    assert {app["id"] for app in dual["apps"]} == {
        "com.aure.banjorecomp",
        "com.igawa6.harvestmoon64",
        "com.samyost1.zelda3android",
        "com.samyost1.tmcandroid",
    }


def test_codm_fixture_keeps_github_and_non_github_rows() -> None:
    readme = (FIXTURES / "codm-readme.md").read_text()

    assert "https://github.com/samyost1/zelda3-android" in readme
    assert "https://www.nexusmods.com/" in readme
    assert "https://modrinth.com/" in readme
    assert "https://christt105.itch.io/" in readme
    assert "https://play.google.com/" in readme
