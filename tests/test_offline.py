from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from omnipack.offline import OfflineInputs, validate_offline
from omnipack.settings_defaults import SETTINGS_DEFAULTS

ROOT = Path(__file__).parents[1]


def encoded(value: object) -> bytes:
    return json.dumps(value, allow_nan=True).encode()


def app(package_id: str = "org.example.app", source: str = "GitHub") -> dict[str, Any]:
    return {
        "id": package_id,
        "url": "https://example.com/app",
        "author": "Example",
        "name": "Example",
        "additionalSettings": json.dumps(SETTINGS_DEFAULTS[source]),
        "categories": ["Emulator"],
        "overrideSource": source,
    }


def inputs(
    single_apps: list[dict[str, Any]] | None = None,
    dual_apps: list[dict[str, Any]] | None = None,
    *,
    deny: object = None,
    common: object = None,
    dual_overlay: object = None,
    settings: object = None,
    composition: object = None,
) -> OfflineInputs:
    single_apps = [app()] if single_apps is None else single_apps
    dual_apps = deepcopy(single_apps) if dual_apps is None else dual_apps
    configured = (
        {"categories": {"Emulator": 0xFF010203}} if settings is None else settings
    )

    def rendered(apps: list[dict[str, Any]]) -> dict[str, str]:
        names = sorted(
            {
                name
                for item in apps
                for name in item.get("categories", [])
                if isinstance(name, str)
            }
        )
        configured_colors = (
            configured.get("categories", {}) if isinstance(configured, dict) else {}
        )
        colors = {
            name: configured_colors.get(
                name,
                int.from_bytes(b"\xff" + hashlib.sha256(name.encode()).digest()[:3]),
            )
            for name in names
        }
        return {"categories": json.dumps(colors, separators=(",", ":"))}

    return OfflineInputs(
        single=encoded({"settings": rendered(single_apps), "apps": single_apps}),
        dual=encoded({"settings": rendered(dual_apps), "apps": dual_apps}),
        deny=encoded([] if deny is None else deny),
        common_overlay=encoded([] if common is None else common),
        dual_overlay=encoded([] if dual_overlay is None else dual_overlay),
        settings=encoded(configured),
        composition=encoded(
            {"schemaVersion": 1, "candidates": [], "pins": []}
            if composition is None
            else composition
        ),
    )


def codes(result) -> set[str]:
    return {finding.code for finding in result.findings}


def test_valid_entries_retain_raw_objects_and_decoded_settings() -> None:
    raw = app("release-notes")
    raw["futureField"] = {"retained": True}
    additional = json.loads(raw["additionalSettings"])
    additional["futureSetting"] = {"retained": True}
    additional["versionExtractionRegEx"] = "["
    raw["additionalSettings"] = json.dumps(additional)
    result = validate_offline(inputs([raw]))

    assert result.ok
    entry = result.entries["single"][0]
    assert entry.raw is raw or entry.raw == raw
    assert entry.raw["futureField"] == {"retained": True}
    assert entry.settings["futureSetting"] == {"retained": True}
    assert entry.settings["versionExtractionRegEx"] == "["


@pytest.mark.parametrize(
    "field",
    [
        "single",
        "dual",
        "deny",
        "common_overlay",
        "dual_overlay",
        "settings",
        "composition",
    ],
)
def test_missing_snapshots_are_reported(field: str) -> None:
    snapshots = inputs()
    object.__setattr__(snapshots, field, None)
    result = validate_offline(snapshots)
    assert "input_missing" in codes(result)


@pytest.mark.parametrize(
    ("document", "code"),
    [
        (b"{", "invalid_json"),
        (b"[]", "invalid_root"),
        (encoded({"settings": {}, "apps": {}}), "invalid_apps"),
        (encoded({"settings": [], "apps": []}), "invalid_document_settings"),
        (encoded({"settings": {}, "apps": [None]}), "invalid_entry"),
        (b'{"settings":{},"apps":[],"x":NaN}', "non_finite_number"),
        (b'{"settings":{},"apps":[],"x":1e999}', "non_finite_number"),
        (b"null", "invalid_root"),
    ],
)
def test_malformed_serialized_documents_are_rejected(
    document: bytes, code: str
) -> None:
    snapshots = inputs([], [])
    object.__setattr__(snapshots, "single", document)
    assert code in codes(validate_offline(snapshots))


def test_independent_variant_errors_are_collected() -> None:
    duplicate = app("same")
    wrong = app("other")
    values = json.loads(wrong["additionalSettings"])
    values["trackOnly"] = "yes"
    wrong["additionalSettings"] = json.dumps(values)
    result = validate_offline(inputs([duplicate, deepcopy(duplicate)], [wrong]))
    assert {("single", "duplicate_id"), ("dual", "wrong_setting_type")} <= {
        (finding.variant, finding.code) for finding in result.findings
    }


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda value: value.pop("name"), "missing_field"),
        (lambda value: value.update(id=""), "invalid_field"),
        (lambda value: value.update(url="ftp://example.com/a"), "invalid_url"),
        (lambda value: value.update(url="https://[invalid"), "invalid_url"),
        (lambda value: value.update(author=1), "invalid_field"),
        (lambda value: value.update(categories=[1]), "invalid_categories"),
        (
            lambda value: value.update(overrideSource="F-Droid Third Party Repo"),
            "unsupported_source",
        ),
        (
            lambda value: value.update(additionalSettings={}),
            "invalid_additional_settings",
        ),
        (
            lambda value: value.update(preferredApkIndex=True),
            "invalid_preferred_apk_index",
        ),
    ],
    ids=(
        "missing-name",
        "empty-id",
        "non-http-url",
        "malformed-http-url",
        "invalid-author",
        "invalid-categories",
        "source",
        "encoded-settings",
        "preferred-index",
    ),
)
def test_required_entry_fields_are_validated(mutate, code: str) -> None:
    value = app()
    mutate(value)
    assert code in codes(validate_offline(inputs([value], [])))


def test_track_only_id_need_not_be_an_android_package_name() -> None:
    value = app("Release Notes")
    settings = json.loads(value["additionalSettings"])
    settings["trackOnly"] = True
    value["additionalSettings"] = json.dumps(settings)
    assert validate_offline(inputs([value])).ok


@pytest.mark.parametrize("source", [{}, [], None, 1, True])
def test_malformed_source_produces_findings_without_stopping_other_entries(
    source: object,
) -> None:
    malformed = app("malformed")
    malformed["overrideSource"] = source
    other = app("other")
    other.pop("name")
    result = validate_offline(inputs([malformed], [other]))
    assert {
        ("single", "malformed", "overrideSource", "unsupported_source"),
        ("dual", "other", "name", "missing_field"),
    } <= {
        (finding.variant, finding.entry_id, finding.field, finding.code)
        for finding in result.findings
    }


@pytest.mark.parametrize("field", ["overrideSource", "additionalSettings"])
def test_raw_ids_and_categories_survive_other_entry_errors(field: str) -> None:
    malformed = app("present")
    malformed[field] = None
    result = validate_offline(
        inputs(
            [malformed, deepcopy(malformed)],
            [deepcopy(malformed)],
            common=[{"id": "present", "url": "https://example.com/app", "patch": {}}],
            dual_overlay=[
                {"id": "present", "url": "https://example.com/app", "patch": {}}
            ],
            deny=[{"id": "present", "reason": "excluded"}],
        )
    )
    assert {
        ("single", "duplicate_id"),
        ("single", "denied_output_present"),
        ("dual", "denied_output_present"),
    } <= {(finding.variant, finding.code) for finding in result.findings}
    assert not {
        "stale_common_overlay",
        "stale_dual_overlay",
        "category_mapping_mismatch",
        "dual_coverage_gap",
    } & codes(result)
    assert result.entries == {"single": (), "dual": ()}

    missing_dual = validate_offline(inputs([malformed], []))
    assert "dual_coverage_gap" in codes(missing_dual)


def test_defaults_are_required_and_known_types_are_checked() -> None:
    missing = app("missing")
    missing_settings = json.loads(missing["additionalSettings"])
    missing_settings.pop("about")
    missing["additionalSettings"] = json.dumps(missing_settings)
    wrong = app("wrong")
    wrong_settings = json.loads(wrong["additionalSettings"])
    wrong_settings["trackOnly"] = 1
    wrong["additionalSettings"] = json.dumps(wrong_settings)
    result = validate_offline(inputs([missing, wrong], []))
    assert {"missing_setting_default", "wrong_setting_type"} <= codes(result)


def test_complete_native_gitlab_entry_passes_offline_validation() -> None:
    value = app("aurora", source="GitLab")
    value["url"] = "https://gitlab.com/AuroraOSS/AuroraStore"
    result = validate_offline(inputs([value], [dict(value)]))
    assert result.ok
    assert [entry.source for entry in result.entries["single"]] == ["GitLab"]


@pytest.mark.parametrize(
    "url",
    [
        "http://gitlab.com/a/b",
        "https://other.test/a/b",
        "https://gitlab.com/one",
        "https://gitlab.com/" + "/".join(f"Group{i}" for i in range(22)),
        "https://gitlab.com:invalid/a/b",
    ],
)
def test_native_gitlab_url_boundary_is_checked_offline(url: str) -> None:
    value = app(source="GitLab")
    value["url"] = url
    assert "invalid_gitlab_url" in codes(validate_offline(inputs([value], [])))


@pytest.mark.parametrize(
    ("field", "nested", "code"),
    [
        ("intermediateLink", [{"customLinkFilterRegex": 1}], "invalid_html_step"),
        ("requestHeader", [{"requestHeader": False}], "invalid_request_header"),
    ],
)
def test_nested_html_steps_and_headers_are_validated(
    field: str, nested: object, code: str
) -> None:
    value = app(source="HTML")
    settings = json.loads(value["additionalSettings"])
    settings[field] = nested
    value["additionalSettings"] = json.dumps(settings)
    result = validate_offline(inputs([value], []))
    assert ("single", "org.example.app", field, code) in {
        (finding.variant, finding.entry_id, finding.field, finding.code)
        for finding in result.findings
    }


def test_categories_must_exactly_match_observed_names_and_valid_colors() -> None:
    snapshots = inputs()
    assert snapshots.single is not None
    single = json.loads(snapshots.single)
    single["settings"]["categories"] = json.dumps(
        {"Extra": 0xFF000000, "Emulator": True}
    )
    object.__setattr__(snapshots, "single", encoded(single))
    result = validate_offline(snapshots)
    assert {"category_mapping_mismatch", "invalid_category_color"} <= codes(result)


def test_configured_argb_color_rejects_boolean_and_out_of_range_values() -> None:
    result = validate_offline(inputs(settings={"categories": {"Unused": True}}))
    assert "invalid_category_color" in codes(result)


def test_configured_and_derived_category_colors_and_other_settings_agree() -> None:
    configured = {"categories": {"Configured": 0xFF123456}, "groupByCategory": True}
    apps = [app("a"), app("b")]
    apps[0]["categories"] = ["Configured"]
    apps[1]["categories"] = ["Derived"]
    snapshots = inputs(apps, settings=configured)
    derived = int.from_bytes(b"\xff" + hashlib.sha256(b"Derived").digest()[:3])
    rendered = {
        "categories": json.dumps(
            {"Configured": 0xFF123456, "Derived": derived}, separators=(",", ":")
        ),
        "groupByCategory": False,
    }
    for field in ("single", "dual"):
        document = json.loads(getattr(snapshots, field))
        document["settings"] = rendered
        object.__setattr__(snapshots, field, encoded(document))
    assert "configured_setting_mismatch" in codes(validate_offline(snapshots))


@pytest.mark.parametrize(
    ("configured", "rendered", "mismatch"),
    [
        ({}, {"unexpected": True}, "unexpected"),
        ({"nullable": None}, {}, "nullable"),
        (
            {"futureSetting": {"enabled": True}},
            {"futureSetting": {"enabled": True}},
            None,
        ),
    ],
)
def test_non_category_pack_settings_match_configured_keys_and_values(
    configured: dict[str, Any], rendered: dict[str, Any], mismatch: str | None
) -> None:
    snapshots = inputs(settings=configured)
    assert snapshots.single is not None
    document = json.loads(snapshots.single)
    document["settings"].update(rendered)
    object.__setattr__(snapshots, "single", encoded(document))
    result = validate_offline(snapshots)
    mismatched_fields = {
        finding.field
        for finding in result.findings
        if finding.variant == "single" and finding.code == "configured_setting_mismatch"
    }
    assert mismatched_fields == ({mismatch} if mismatch is not None else set())


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        (
            {"common": [{"id": "x", "url": "https://example.com/app", "patch": None}]},
            "invalid_composition_config",
        ),
        (
            {
                "common": [
                    {
                        "id": "x",
                        "url": "https://example.com/app",
                        "patch": {"id": "changed"},
                    }
                ]
            },
            "invalid_composition_config",
        ),
        (
            {
                "common": [
                    {
                        "id": "missing",
                        "url": "https://example.com/missing",
                        "patch": {"name": "x"},
                    }
                ]
            },
            "stale_common_overlay",
        ),
        (
            {
                "dual_overlay": [
                    {
                        "id": "missing",
                        "url": "https://example.com/missing",
                        "patch": {"name": "x"},
                    }
                ]
            },
            "stale_dual_overlay",
        ),
        ({"deny": [{"id": "org.example.app", "reason": "x"}]}, "denied_output_present"),
    ],
)
def test_local_composition_constraints(kwargs: dict[str, Any], code: str) -> None:
    assert code in codes(validate_offline(inputs(**kwargs)))


def test_common_overlay_target_may_exist_in_only_one_variant() -> None:
    assert validate_offline(
        inputs(
            [],
            [app()],
            common=[
                {
                    "id": "org.example.app",
                    "url": "https://example.com/app",
                    "patch": {"name": "x"},
                }
            ],
        )
    ).ok


@pytest.mark.parametrize(
    "entry",
    [
        {"id": "org.example.app", "reason": "excluded", "variant": "dual"},
        {"id": "org.example.app", "reason": "excluded", "family": "app:example"},
        {"family": "app:example", "reason": "excluded"},
    ],
)
def test_retired_denial_selectors_are_reported(entry: dict[str, str]) -> None:
    result = validate_offline(inputs(deny=[entry]))
    assert "invalid_composition_config" in codes(result)


def test_stale_denial_is_allowed_and_a_denied_dual_build_leaves_a_gap() -> None:
    assert validate_offline(inputs(deny=[{"id": "stale", "reason": "gone"}])).ok
    result = validate_offline(
        inputs([app("single")], [], deny=[{"id": "dual", "reason": "excluded"}])
    )
    assert codes(result) == {"dual_coverage_gap"}


def test_unexempted_dual_coverage_gap_fails() -> None:
    result = validate_offline(inputs([app("single")], []))
    assert "dual_coverage_gap" in codes(result)


def test_family_projection_and_pin_are_distinct() -> None:
    policy = {
        "schemaVersion": 1,
        "candidates": [
            {
                "match": {
                    "source": "extras",
                    "origin": "extras",
                    "id": "old",
                    "url": "https://example.com/app",
                },
                "family": "app:shared",
                "packageId": "single.pkg",
                "rationale": "fixture",
            },
            {
                "match": {
                    "source": "extras",
                    "origin": "extras",
                    "id": "dual.pkg",
                    "url": "https://example.com/dual",
                },
                "family": "app:shared",
                "rationale": "fixture",
            },
        ],
        "pins": [
            {
                "family": "app:shared",
                "variant": "dual",
                "match": {
                    "source": "extras",
                    "origin": "extras",
                    "id": "dual.pkg",
                    "url": "https://example.com/dual",
                },
                "rationale": "fixture",
            }
        ],
    }
    single = app("single.pkg")
    dual = app("dual.pkg")
    dual["url"] = "https://example.com/dual/"
    assert validate_offline(inputs([single], [dual], composition=policy)).ok
    missing = validate_offline(inputs([], [], composition=policy))
    assert "pin_mismatch" in codes(missing)
    denied = validate_offline(
        inputs(
            [],
            [],
            composition=policy,
            deny=[{"id": "dual.pkg", "reason": "retired"}],
        )
    )
    assert "pin_mismatch" in codes(denied)
    wrong = deepcopy(dual)
    wrong["url"] = "https://example.com/other"
    result = validate_offline(inputs([single], [wrong], composition=policy))
    assert "dual_coverage_gap" in codes(result)
    assert "pin_mismatch" in codes(result)


def test_package_denial_neither_exempts_coverage_nor_remains_selected() -> None:
    denial = [{"id": "one", "reason": "unsupported"}]
    single_only = validate_offline(inputs([app("one")], [], deny=denial))
    assert {("single", "denied_output_present"), ("dual", "dual_coverage_gap")} <= {
        (finding.variant, finding.code) for finding in single_only.findings
    }
    both = validate_offline(inputs([app("one")], [app("one")], deny=denial))
    assert {
        finding.variant
        for finding in both.findings
        if finding.code == "denied_output_present"
    } == {"single", "dual"}


def test_committed_pair_passes_without_network_or_rewriting(monkeypatch) -> None:
    import urllib.request

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *args, **kwargs: pytest.fail("network used")
    )
    snapshots = OfflineInputs(
        single=(ROOT / "dist/single-screen.json").read_bytes(),
        dual=(ROOT / "dist/dual-screen.json").read_bytes(),
        deny=(ROOT / "config/deny.json").read_bytes(),
        common_overlay=(ROOT / "config/overlay.json").read_bytes(),
        dual_overlay=(ROOT / "config/overlay.dual.json").read_bytes(),
        settings=(ROOT / "config/settings.json").read_bytes(),
        composition=(ROOT / "config/composition.json").read_bytes(),
    )
    before = snapshots.single, snapshots.dual
    result = validate_offline(snapshots)
    assert result.ok, result.findings
    assert (snapshots.single, snapshots.dual) == before


def test_request_header_unknown_fields_are_preserved() -> None:
    raw = app(source="HTML")
    settings = json.loads(raw["additionalSettings"])
    settings["requestHeader"] = [{"requestHeader": "X-Channel: stable", "future": True}]
    raw["additionalSettings"] = json.dumps(settings)
    result = validate_offline(inputs([raw]))
    assert result.ok
    assert result.entries["single"][0].settings["requestHeader"][0]["future"] is True


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("fallbackToOlderReleases", None, "missing_setting_default"),
        ("fallbackToOlderReleases", 1, "wrong_setting_type"),
        ("apkFilterRegEx", False, "wrong_setting_type"),
    ],
)
def test_native_gitlab_defaults_rejected_without_repair(
    field: str, value: object, code: str
) -> None:
    raw = app("aurora", source="GitLab")
    raw["url"] = "https://gitlab.com/AuroraOSS/AuroraStore"
    settings = json.loads(raw["additionalSettings"])
    if value is None:
        del settings[field]
    else:
        settings[field] = value
    raw["additionalSettings"] = json.dumps(settings)
    snapshots = inputs([raw])
    before = deepcopy(snapshots)
    result = validate_offline(snapshots)
    assert not result.ok
    assert {
        (finding.variant, finding.entry_id, finding.field, finding.code)
        for finding in result.findings
    } == {(variant, "aurora", field, code) for variant in ("single", "dual")}
    assert snapshots == before


def test_native_gitlab_maximum_subgroups_preserved_offline() -> None:
    raw = app(source="GitLab")
    raw["url"] = "https://gitlab.com/" + "/".join(f"Group{i}" for i in range(21))
    result = validate_offline(inputs([raw]))
    assert result.ok
    assert all(
        entries[0].raw["url"] == raw["url"] for entries in result.entries.values()
    )
