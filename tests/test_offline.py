from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from omnipack.offline import Finding, OfflineInputs, validate_offline
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
    overlay: object = None,
    composition: object = None,
) -> OfflineInputs:
    single_apps = [app()] if single_apps is None else single_apps
    dual_apps = deepcopy(single_apps) if dual_apps is None else dual_apps
    settings = {"categories": "{}"}
    return OfflineInputs(
        single=encoded({"settings": settings, "apps": single_apps}),
        dual=encoded({"settings": settings, "apps": dual_apps}),
        deny=encoded([] if deny is None else deny),
        overlay=encoded([] if overlay is None else overlay),
        composition=encoded(
            {"schemaVersion": 1, "candidates": [], "pins": []}
            if composition is None
            else composition
        ),
    )


def codes(findings: tuple[Finding, ...]) -> set[str]:
    return {finding.code for finding in findings}


def located(findings: tuple[Finding, ...]) -> set[tuple[object, ...]]:
    return {
        (finding.variant, finding.entry_id, finding.field, finding.code)
        for finding in findings
    }


def with_settings(value: dict[str, Any], **changes: object) -> dict[str, Any]:
    settings = json.loads(value["additionalSettings"])
    settings.update(changes)
    return {**value, "additionalSettings": json.dumps(settings)}


def test_unknown_fields_and_settings_are_accepted_without_repair() -> None:
    raw = with_settings(
        app("release-notes"),
        futureSetting={"retained": True},
        versionExtractionRegEx="[",
    )
    raw["futureField"] = {"retained": True}
    snapshots = inputs([raw])
    before = deepcopy(snapshots)
    assert validate_offline(snapshots) == ()
    assert snapshots == before


@pytest.mark.parametrize("field", ["single", "dual", "deny", "overlay", "composition"])
def test_missing_snapshots_are_reported(field: str) -> None:
    snapshots = inputs()
    object.__setattr__(snapshots, field, None)
    assert "input_missing" in codes(validate_offline(snapshots))


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
    wrong = with_settings(app("other"), trackOnly="yes")
    findings = validate_offline(inputs([duplicate, deepcopy(duplicate)], [wrong]))
    assert {("single", "duplicate_id"), ("dual", "wrong_setting_type")} <= {
        (finding.variant, finding.code) for finding in findings
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
    ],
    ids=(
        "missing-name",
        "empty-id",
        "non-http-url",
        "malformed-http-url",
        "invalid-author",
        "invalid-categories",
        "source",
    ),
)
def test_required_entry_fields_are_validated(mutate, code: str) -> None:
    value = app()
    mutate(value)
    assert code in codes(validate_offline(inputs([value], [])))


def test_object_additional_settings_names_variant_id_and_field() -> None:
    value = app()
    value["additionalSettings"] = SETTINGS_DEFAULTS["GitHub"]
    findings = validate_offline(inputs([value]))
    assert {
        (
            variant,
            "org.example.app",
            "additionalSettings",
            "invalid_additional_settings",
        )
        for variant in ("single", "dual")
    } <= located(findings)


@pytest.mark.parametrize("value", [True, "1", 1.5])
def test_non_integer_preferred_apk_index_is_rejected(value: object) -> None:
    entry = {**app(), "preferredApkIndex": value}
    assert ("single", "org.example.app", "preferredApkIndex") in {
        (finding.variant, finding.entry_id, finding.field)
        for finding in validate_offline(inputs([entry], []))
        if finding.code == "invalid_preferred_apk_index"
    }


def test_integer_preferred_apk_index_is_accepted() -> None:
    assert validate_offline(inputs([{**app(), "preferredApkIndex": 0}])) == ()


def test_track_only_id_need_not_be_an_android_package_name() -> None:
    value = with_settings(app("Release Notes"), trackOnly=True)
    assert validate_offline(inputs([value])) == ()


@pytest.mark.parametrize("source", [{}, [], None, 1, True])
def test_malformed_source_produces_findings_without_stopping_other_entries(
    source: object,
) -> None:
    malformed = app("malformed")
    malformed["overrideSource"] = source
    other = app("other")
    other.pop("name")
    assert {
        ("single", "malformed", "overrideSource", "unsupported_source"),
        ("dual", "other", "name", "missing_field"),
    } <= located(validate_offline(inputs([malformed], [other])))


@pytest.mark.parametrize("field", ["overrideSource", "additionalSettings"])
def test_raw_ids_survive_other_entry_errors(field: str) -> None:
    malformed = app("present")
    malformed[field] = None
    findings = validate_offline(
        inputs(
            [malformed, deepcopy(malformed)],
            [deepcopy(malformed)],
            overlay=[{"id": "present", "url": "https://example.com/app", "patch": {}}],
            deny=[{"id": "present", "reason": "excluded"}],
        )
    )
    assert {
        ("single", "duplicate_id"),
        ("single", "denied_output_present"),
        ("dual", "denied_output_present"),
    } <= {(finding.variant, finding.code) for finding in findings}
    assert not {"stale_overlay", "dual_coverage_gap"} & codes(findings)

    missing_dual = validate_offline(inputs([malformed], []))
    assert "dual_coverage_gap" in codes(missing_dual)


def test_entry_lacking_a_default_key_passes_when_every_other_check_passes() -> None:
    value = app()
    settings = json.loads(value["additionalSettings"])
    del settings["about"]
    value["additionalSettings"] = json.dumps(settings)
    assert validate_offline(inputs([value])) == ()


def test_complete_native_gitlab_entry_passes_offline_validation() -> None:
    value = app("aurora", source="GitLab")
    value["url"] = "https://gitlab.com/AuroraOSS/AuroraStore"
    assert validate_offline(inputs([value], [dict(value)])) == ()


def test_gitlab_url_rules_are_outside_offline_verification() -> None:
    value = app("deep", source="GitLab")
    # Deeper than ingestion accepts for a GitLab project.
    value["url"] = "https://gitlab.com/" + "/".join(f"Group{i}" for i in range(22))
    assert validate_offline(inputs([value], [dict(value)])) == ()


@pytest.mark.parametrize(
    ("field", "nested", "code"),
    [
        ("intermediateLink", [{"customLinkFilterRegex": 1}], "invalid_html_step"),
        ("intermediateLink", ["not an object"], "invalid_html_step"),
        ("requestHeader", [{"requestHeader": False}], "invalid_request_header"),
        ("requestHeader", [{"future": "no header"}], "invalid_request_header"),
    ],
)
def test_nested_html_steps_and_headers_are_validated(
    field: str, nested: object, code: str
) -> None:
    value = with_settings(app(source="HTML"), **{field: nested})
    assert ("single", "org.example.app", field, code) in located(
        validate_offline(inputs([value], []))
    )


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        (
            {"overlay": [{"id": "x", "url": "https://example.com/app", "patch": None}]},
            "invalid_composition_config",
        ),
        (
            {
                "overlay": [
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
                "overlay": [
                    {
                        "id": "missing",
                        "url": "https://example.com/missing",
                        "patch": {"name": "x"},
                    }
                ]
            },
            "stale_overlay",
        ),
        ({"deny": [{"id": "org.example.app", "reason": "x"}]}, "denied_output_present"),
    ],
)
def test_local_composition_constraints(kwargs: dict[str, Any], code: str) -> None:
    assert code in codes(validate_offline(inputs(**kwargs)))


def test_overlay_target_may_exist_in_only_one_variant() -> None:
    findings = validate_offline(
        inputs(
            [],
            [app()],
            overlay=[
                {
                    "id": "org.example.app",
                    "url": "https://example.com/app",
                    "patch": {"name": "x"},
                }
            ],
        )
    )
    assert findings == ()


def test_retired_denial_selectors_are_reported() -> None:
    entry = {"id": "org.example.app", "reason": "excluded", "variant": "dual"}
    assert "invalid_composition_config" in codes(validate_offline(inputs(deny=[entry])))


def test_stale_denial_is_allowed_and_a_denied_dual_build_leaves_a_gap() -> None:
    assert validate_offline(inputs(deny=[{"id": "stale", "reason": "gone"}])) == ()
    findings = validate_offline(
        inputs([app("single")], [], deny=[{"id": "dual", "reason": "excluded"}])
    )
    assert codes(findings) == {"dual_coverage_gap"}


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
    assert validate_offline(inputs([single], [dual], composition=policy)) == ()
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
        (finding.variant, finding.code) for finding in single_only
    }
    both = validate_offline(inputs([app("one")], [app("one")], deny=denial))
    assert {
        finding.variant for finding in both if finding.code == "denied_output_present"
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
        overlay=(ROOT / "config/overlay.json").read_bytes(),
        composition=(ROOT / "config/composition.json").read_bytes(),
    )
    before = snapshots.single, snapshots.dual
    findings = validate_offline(snapshots)
    assert findings == (), findings
    assert (snapshots.single, snapshots.dual) == before


def test_request_header_unknown_fields_are_accepted() -> None:
    raw = with_settings(
        app(source="HTML"),
        requestHeader=[{"requestHeader": "X-Channel: stable", "future": True}],
    )
    assert validate_offline(inputs([raw])) == ()


@pytest.mark.parametrize(
    ("field", "value"),
    [("fallbackToOlderReleases", 1), ("apkFilterRegEx", False)],
)
def test_native_gitlab_setting_types_rejected_without_repair(
    field: str, value: object
) -> None:
    raw = app("aurora", source="GitLab")
    raw["url"] = "https://gitlab.com/AuroraOSS/AuroraStore"
    raw = with_settings(raw, **{field: value})
    snapshots = inputs([raw])
    before = deepcopy(snapshots)
    assert located(validate_offline(snapshots)) == {
        (variant, "aurora", field, "wrong_setting_type")
        for variant in ("single", "dual")
    }
    assert snapshots == before
