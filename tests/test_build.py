from __future__ import annotations

import json
from pathlib import Path

import pytest

from omnipack import build as build_module
from omnipack.composition_policy import parse_composition_policy
from omnipack.merge import (
    CompositionReport,
    CompositionResult,
    Displacement,
    Removal,
    StaleExclusion,
)
from omnipack.model import Provenance, Variant
from omnipack.overlay import ComposedApp
from omnipack.sources import IngestionReport


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


def write_config(root: Path) -> None:
    (root / "README.md").write_bytes(
        b"<!-- omnipack:catalog:start -->\n<!-- omnipack:catalog:end -->\n"
    )
    (root / "config").mkdir(exist_ok=True)
    for name, value in (
        ("composition.json", {"schemaVersion": 1, "candidates": [], "pins": []}),
        ("deny.json", []),
        ("overlay.json", []),
        ("overlay.dual.json", []),
        ("settings.json", {}),
    ):
        (root / "config" / name).write_text(json.dumps(value), encoding="utf-8")


def test_report_compares_with_previous_output_and_keeps_source_details(
    tmp_path: Path,
) -> None:
    write_previous(
        tmp_path,
        {"apps": [{"id": "old.id"}, {"id": "kept.id"}]},
        {"apps": [{"id": "kept.id"}]},
    )
    write_config(tmp_path)
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
    write_config(tmp_path)
    build_module.publish_build(
        tmp_path, composition("one", "two"), {}, IngestionReport()
    )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["changes"]["single"]["added"] == ["one", "two"]
    assert report["changes"]["dual"]["added"] == ["one", "two"]


@pytest.mark.parametrize("mutation_stage", ["offline verification", "publication"])
def test_policy_byte_change_during_build_prevents_publication(
    tmp_path: Path, mutation_stage: str
) -> None:
    write_config(tmp_path)
    policy = tmp_path / "config/composition.json"
    consumed = policy.read_bytes()

    def mutate(stage: str) -> None:
        if stage == mutation_stage:
            policy.write_bytes(consumed + b"\n")

    try:
        build_module.publish_build(
            tmp_path,
            composition("one"),
            {},
            IngestionReport(),
            composition_bytes=consumed,
            on_stage=mutate,
        )
    except build_module.OfflineVerificationError as error:
        assert error.findings[0]["code"] == "input_changed"
    else:
        raise AssertionError("policy mutation was accepted")
    assert not (tmp_path / "dist/single-screen.json").exists()


def test_family_history_preserves_multiple_old_keys_and_reports_transition(
    tmp_path: Path,
) -> None:
    from omnipack.report import write_report

    current = composition("new.pkg")
    for variant in Variant:
        current.apps[variant][0] = ComposedApp(
            variant,
            current.apps[variant][0].provenance,
            current.apps[variant][0].data,
            "package:new.pkg",
        )
    for variant in Variant:
        current.apps[variant][0] = ComposedApp(
            variant,
            current.apps[variant][0].provenance,
            {**current.apps[variant][0].data, "url": "https://example.test/new"},
            "app:shared",
            "new.pkg",
            "extras",
        )
    previous = {
        variant: [
            {"id": "old.standard", "url": "https://example.test/standard"},
            {"id": "old.dual", "url": "https://example.test/dual"},
        ]
        for variant in Variant
    }
    policy = parse_composition_policy(
        {
            "schemaVersion": 1,
            "candidates": [],
            "pins": [],
            "history": [
                {
                    "id": "old.standard",
                    "url": "https://example.test/standard",
                    "family": "app:shared",
                    "rationale": "published",
                },
                {
                    "id": "old.dual",
                    "url": "https://example.test/dual",
                    "family": "app:shared",
                    "rationale": "published",
                },
            ],
        }
    )
    write_report(tmp_path, previous, current, IngestionReport(), policy=policy)
    report = json.loads((tmp_path / ".build/report.json").read_text())
    retained = report["familyChanges"]["single"]["retained"]
    assert retained == [
        {
            "family": "app:shared",
            "previous": [
                {"id": "old.standard", "url": "https://example.test/standard"},
                {"id": "old.dual", "url": "https://example.test/dual"},
            ],
            "current": {"id": "new.pkg", "url": "https://example.test/new"},
        }
    ]
    assert report["familyChanges"]["single"]["removed"] == []


def test_unknown_history_makes_unmatched_additions_unknown(tmp_path: Path) -> None:
    from omnipack.report import write_report

    current = composition("new.pkg")
    for variant in Variant:
        current.apps[variant][0] = ComposedApp(
            variant,
            current.apps[variant][0].provenance,
            current.apps[variant][0].data,
            "package:new.pkg",
        )
    previous = {
        variant: [{"id": "mystery", "url": "https://example.test/old"}]
        for variant in Variant
    }
    policy = parse_composition_policy(
        {"schemaVersion": 1, "candidates": [], "pins": []}
    )
    write_report(tmp_path, previous, current, IngestionReport(), policy=policy)
    changes = json.loads((tmp_path / ".build/report.json").read_text())[
        "familyChanges"
    ]["single"]
    assert changes["added"] == []
    assert changes["unknownAdditions"] == ["package:new.pkg"]
    assert changes["unmappedPrevious"] == [
        {"id": "mystery", "url": "https://example.test/old"}
    ]


def test_fresh_checkout_retired_candidate_history_survives_rule_removal(
    tmp_path: Path,
) -> None:
    from omnipack.merge import CompositionError, compose
    from omnipack.model import App, SourceType

    write_config(tmp_path)
    old = {"id": "old.pkg", "url": "https://example.test/old/"}
    removed = {"id": "retired.pkg", "url": "https://example.test/retired"}
    write_previous(tmp_path, {"apps": [old, removed]}, {"apps": [old, removed]})
    assert not (tmp_path / ".build/report.json").exists()
    current_url = "https://example.test/new"
    candidate = App(
        "new.pkg",
        current_url,
        "Replacement",
        SourceType.HTML,
        (),
        Variant.SINGLE,
        Provenance("extras", current_url),
        eligibility=frozenset(Variant),
    )
    rules = [
        {
            "match": {
                "source": "extras",
                "origin": "extras",
                "id": package_id,
                "url": url,
            },
            "family": "app:shared",
            "rationale": "curated replacement",
        }
        for package_id, url in (
            ("old.pkg", "https://example.test/old"),
            ("new.pkg", current_url),
        )
    ]
    policy_data = {
        "schemaVersion": 1,
        "candidates": rules,
        "pins": [],
        "history": [
            {
                "id": "old.pkg",
                "url": "https://example.test/old",
                "family": "app:shared",
                "rationale": "published",
            },
            {**removed, "family": "package:retired.pkg", "rationale": "published"},
        ],
    }
    with pytest.raises(CompositionError, match="old.pkg"):
        compose([candidate], [], [], [], policy=parse_composition_policy(policy_data))
    rules.pop(0)
    policy_bytes = json.dumps(policy_data).encode()
    (tmp_path / "config/composition.json").write_bytes(policy_bytes)
    current = compose(
        [candidate], [], [], [], policy=parse_composition_policy(policy_data)
    )
    build_module.publish_build(
        tmp_path, current, {}, IngestionReport(), composition_bytes=policy_bytes
    )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    for variant in Variant:
        changes = report["familyChanges"][variant.value]
        assert changes["retained"] == [
            {
                "family": "app:shared",
                "previous": [old],
                "current": {"id": "new.pkg", "url": current_url},
            }
        ]
        assert changes["removed"] == ["package:retired.pkg"]
        assert (
            changes["added"]
            == changes["unknownAdditions"]
            == changes["unmappedPrevious"]
            == []
        )
        assert changes["unknownReason"] is None
        assert report["changes"][variant.value] == {
            "added": ["new.pkg"],
            "removed": ["old.pkg", "retired.pkg"],
        }


def test_first_composed_build_reports_definite_family_additions(tmp_path: Path) -> None:
    from omnipack.merge import compose
    from omnipack.model import App, SourceType

    write_config(tmp_path)
    url = "https://example.test/first"
    candidate = App(
        "first.pkg",
        url,
        "First",
        SourceType.HTML,
        (),
        Variant.SINGLE,
        Provenance("extras", url),
        eligibility=frozenset(Variant),
    )
    policy = parse_composition_policy(
        {"schemaVersion": 1, "candidates": [], "pins": []}
    )
    current = compose([candidate], [], [], [], policy=policy)
    build_module.publish_build(tmp_path, current, {}, IngestionReport())
    report = json.loads((tmp_path / ".build/report.json").read_text())
    for variant in Variant:
        assert report["familyChanges"][variant.value] == {
            "retained": [],
            "removed": [],
            "added": ["package:first.pkg"],
            "unknownAdditions": [],
            "unmappedPrevious": [],
            "unknownReason": None,
        }
