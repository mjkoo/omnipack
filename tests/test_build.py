from __future__ import annotations

import json
from pathlib import Path

import pytest

from obtainium_pack import build as build_module
from obtainium_pack.merge import (
    CompositionReport,
    CompositionResult,
    Displacement,
    Removal,
    StaleExclusion,
)
from obtainium_pack.model import Provenance, Variant
from obtainium_pack.overlay import ComposedApp
from obtainium_pack.sources import IngestionReport


def app(package_id: str, variant: Variant) -> ComposedApp:
    return ComposedApp(
        variant,
        Provenance("extras", f"https://example.test/{package_id}"),
        {
            "id": package_id,
            "url": f"https://example.test/{package_id}",
            "name": package_id,
            "overrideSource": "HTML",
            "categories": [],
        },
    )


def composition(*ids: str) -> CompositionResult:
    return CompositionResult(
        {
            variant: [app(package_id, variant) for package_id in ids]
            for variant in Variant
        },
        CompositionReport(
            [Displacement("old.id", Variant.SINGLE, "extras", "rjny", ("url",))],
            [Removal("denied.id", Variant.DUAL, "curated")],
            [StaleExclusion("stale.id", None, "gone")],
        ),
    )


def write_previous(root: Path, single: object | None, dual: object | None) -> None:
    (root / "dist").mkdir()
    for name, value in (("single-screen.json", single), ("dual-screen.json", dual)):
        if value is not None:
            (root / "dist" / name).write_text(json.dumps(value), encoding="utf-8")


def test_report_compares_with_previous_output_and_keeps_source_details(
    tmp_path: Path,
) -> None:
    write_previous(
        tmp_path,
        {"apps": [{"id": "old.id"}, {"id": "kept.id"}]},
        {"apps": [{"id": "kept.id"}]},
    )
    ingestion = IngestionReport(
        skipped=[{"source": "codm2000", "url": "https://covered"}],
        unresolved=[
            {"source": "codm2000", "url": "https://missing", "failure": "no APK"}
        ],
        generated=[
            {
                "source": "codm2000",
                "url": "https://kept",
                "id": "kept.id",
                "status": "reused",
            }
        ],
        retained_failures=[
            {
                "source": "codm2000",
                "url": "https://kept",
                "id": "kept.id",
                "failure": "HTTP 503",
            }
        ],
    )
    build_module.publish_build(
        tmp_path, composition("kept.id", "new.id"), {}, ingestion
    )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["changes"]["single"] == {"added": ["new.id"], "removed": ["old.id"]}
    assert report["changes"]["dual"] == {"added": ["new.id"], "removed": []}
    assert report["generated"] == ingestion.generated
    assert report["unresolved"] == ingestion.unresolved
    assert report["retainedFailures"] == ingestion.retained_failures
    assert report["displacements"][0]["id"] == "old.id"
    assert report["denylistRemovals"][0]["id"] == "denied.id"
    assert report["staleExclusions"][0]["id"] == "stale.id"


def test_first_build_reports_every_app_added(tmp_path: Path) -> None:
    build_module.publish_build(
        tmp_path, composition("one", "two"), {}, IngestionReport()
    )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["changes"]["single"]["added"] == ["one", "two"]
    assert report["changes"]["dual"]["added"] == ["one", "two"]


@pytest.mark.parametrize("existing", [True, False])
def test_second_replacement_failure_restores_previous_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: bool
) -> None:
    if existing:
        write_previous(
            tmp_path,
            {"apps": [{"id": "before.single"}]},
            {"apps": [{"id": "before.dual"}]},
        )
    real_replace = Path.replace
    replacements = 0

    def fail_second(source: Path, target: Path) -> Path:
        nonlocal replacements
        if target.parent.name == "dist" and target.name.endswith("screen.json"):
            replacements += 1
            if replacements == 2:
                raise OSError("injected replacement failure")
        return real_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_second)
    with pytest.raises(OSError, match="injected"):
        build_module.publish_build(
            tmp_path, composition("new.id"), {}, IngestionReport()
        )
    if existing:
        assert (
            json.loads((tmp_path / "dist/single-screen.json").read_text())["apps"][0][
                "id"
            ]
            == "before.single"
        )
        assert (
            json.loads((tmp_path / "dist/dual-screen.json").read_text())["apps"][0][
                "id"
            ]
            == "before.dual"
        )
    else:
        assert not (tmp_path / "dist/single-screen.json").exists()
        assert not (tmp_path / "dist/dual-screen.json").exists()


def test_second_render_failure_never_publishes_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_previous(
        tmp_path, {"apps": [{"id": "before.single"}]}, {"apps": [{"id": "before.dual"}]}
    )
    calls = 0

    def fail_render(_apps: list[ComposedApp], _settings: dict[str, object]) -> str:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("dual render failed")
        return '{"apps":[]}\n'

    monkeypatch.setattr(build_module, "render", fail_render)
    with pytest.raises(ValueError, match="dual"):
        build_module.publish_build(
            tmp_path, composition("new.id"), {}, IngestionReport()
        )
    assert "before.single" in (tmp_path / "dist/single-screen.json").read_text()
    assert "before.dual" in (tmp_path / "dist/dual-screen.json").read_text()
