from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from omnipack.offline import Finding, OfflineInputs, validate_offline
from omnipack.report_model import Severity
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
        "allowIdChange": True,
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


def errors(findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
    return tuple(item for item in findings if item.severity is Severity.ERROR)


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


REPEATED_POLICY_KEYS = [
    pytest.param(
        b'{"schemaVersion": 1, "candidates": [], "pins": [], '
        b'"categories": {}, "categories": {}}',
        "categories",
        id="categories",
    ),
    pytest.param(
        b'{"schemaVersion": 1, "pins": [], "candidates": [{"match": {}, '
        b'"rationale": "a", "rationale": "b"}]}',
        "rationale",
        id="rule-rationale",
    ),
]


@pytest.mark.parametrize(("policy", "key"), REPEATED_POLICY_KEYS)
def test_repeated_policy_key_is_a_config_finding_naming_the_key(
    policy: bytes, key: str
) -> None:
    snapshots = inputs()
    object.__setattr__(snapshots, "composition", policy)
    findings = validate_offline(snapshots)
    assert [(item.code, item.message) for item in findings] == [
        ("invalid_composition_config", f"duplicate JSON key {key!r}")
    ]


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
    nameless = app("same")
    nameless.pop("name")
    wrong = with_settings(app("other"), trackOnly="yes")
    findings = validate_offline(inputs([nameless], [wrong]))
    assert {("single", "missing_field"), ("dual", "wrong_setting_type")} <= {
        (finding.variant, finding.code) for finding in findings
    }


@pytest.mark.parametrize(
    "value", [None, False, "true"], ids=["absent", "false", "string"]
)
def test_every_entry_must_allow_an_id_change(value: object) -> None:
    entry = app()
    if value is None:
        entry.pop("allowIdChange")
    else:
        entry["allowIdChange"] = value
    assert (
        "single",
        "org.example.app",
        "allowIdChange",
        "invalid_allow_id_change",
    ) in (located(validate_offline(inputs([entry], []))))


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


@pytest.mark.parametrize("source", [{}, None])
def test_malformed_source_produces_findings_without_stopping_other_entries(
    source: object,
) -> None:
    malformed = app("malformed")
    malformed["overrideSource"] = source
    other = app("other")
    other.pop("name")
    findings = validate_offline(inputs([malformed], [other]))
    assert {
        ("single", "malformed", "overrideSource", "unsupported_source"),
        ("dual", "other", "name", "missing_field"),
    } <= located(findings)
    [unsupported] = [item for item in findings if item.code == "unsupported_source"]
    assert repr(source) in unsupported.message


@pytest.mark.parametrize("field", ["overrideSource", "additionalSettings"])
def test_raw_ids_survive_other_entry_errors(field: str) -> None:
    malformed = app("present")
    malformed[field] = None
    findings = validate_offline(
        inputs(
            [malformed, deepcopy(malformed)],
            [deepcopy(malformed)],
            overlay=[{"url": "https://example.com/app", "patch": {}}],
            deny=[{"url": "https://example.com/app", "reason": "excluded"}],
        )
    )
    assert {
        ("single", "repeated_family_label"),
        ("single", "repeated_package_id"),
        ("single", "denied_output_present"),
        ("dual", "denied_output_present"),
    } <= {(finding.variant, finding.code) for finding in findings}
    assert not {"stale_overlay", "single_only_coverage"} & codes(findings)

    missing_dual = validate_offline(inputs([malformed], []))
    assert "single_only_coverage" in codes(missing_dual)


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
            {"overlay": [{"url": "https://example.com/app", "patch": None}]},
            "invalid_composition_config",
        ),
        (
            {"overlay": [{"url": "https://example.com/app", "patch": {"url": "x"}}]},
            "invalid_composition_config",
        ),
        (
            {"overlay": [{"url": "https://example.com/missing", "patch": {"x": 1}}]},
            "stale_overlay",
        ),
        (
            {"deny": [{"url": "https://EXAMPLE.com/app/", "reason": "x"}]},
            "denied_output_present",
        ),
    ],
)
def test_local_composition_constraints(kwargs: dict[str, Any], code: str) -> None:
    assert code in codes(validate_offline(inputs(**kwargs)))


def test_overlay_target_may_exist_in_only_one_variant() -> None:
    findings = validate_offline(
        inputs(
            [],
            [app()],
            overlay=[{"url": "https://example.com/app", "patch": {"name": "x"}}],
        )
    )
    assert findings == ()


def test_unknown_denial_field_is_reported() -> None:
    entry = {"url": "https://example.com/app", "reason": "excluded", "id": "x"}
    assert "invalid_composition_config" in codes(validate_offline(inputs(deny=[entry])))


def test_stale_denial_is_allowed_and_a_denied_dual_build_leaves_a_finding() -> None:
    stale = [{"url": "https://example.com/stale", "reason": "gone"}]
    assert validate_offline(inputs(deny=stale)) == ()
    findings = validate_offline(
        inputs(
            [app("single")],
            [],
            deny=[{"url": "https://example.com/dual", "reason": "excluded"}],
        )
    )
    assert [(item.code, item.severity) for item in findings] == [
        ("single_only_coverage", Severity.NONFATAL)
    ]


def rule(entry: dict[str, Any], family: str) -> dict[str, Any]:
    return {
        "match": {
            "source": "extras",
            "origin": "extras",
            "id": entry["id"],
            "url": entry["url"],
        },
        "family": family,
        "rationale": "fixture",
    }


def test_family_projection_and_pin_are_distinct() -> None:
    single = app("single.pkg")
    dual = app("dual.pkg")
    dual["url"] = "https://example.com/dual/"
    policy = {
        "schemaVersion": 1,
        "candidates": [rule(single, "app:shared"), rule(dual, "app:shared")],
        "pins": [
            {
                "family": "app:shared",
                "variant": "dual",
                "match": rule(dual, "app:shared")["match"],
                "rationale": "fixture",
            }
        ],
    }
    assert validate_offline(inputs([single], [dual], composition=policy)) == ()
    missing = validate_offline(inputs([], [], composition=policy))
    [mismatch] = [item for item in missing if item.code == "pin_mismatch"]
    assert mismatch.variant == "dual"
    assert "'app:shared'" in mismatch.message
    denied = validate_offline(
        inputs(
            [],
            [],
            composition=policy,
            deny=[{"url": dual["url"], "reason": "retired"}],
        )
    )
    assert "pin_mismatch" in codes(denied)
    wrong = deepcopy(dual)
    wrong["url"] = "https://example.com/other"
    result = validate_offline(inputs([single], [wrong], composition=policy))
    assert "single_only_coverage" in codes(result)
    assert "pin_mismatch" in codes(result)


def test_a_pin_is_checked_against_the_overlay_patched_id_at_its_url() -> None:
    pinned = app("p")
    policy = {
        "schemaVersion": 1,
        "candidates": [],
        "pins": [
            {
                "family": "example.com/app",
                "variant": "dual",
                "match": rule(pinned, "app:unused")["match"],
                "rationale": "fixture",
            }
        ],
    }
    patched = {**pinned, "id": "q"}
    overlay = [{"url": pinned["url"], "patch": {"id": "q"}}]
    assert (
        validate_offline(
            inputs([patched], [patched], overlay=overlay, composition=policy)
        )
        == ()
    )
    unpatched = validate_offline(
        inputs([pinned], [pinned], overlay=overlay, composition=policy)
    )
    assert "pin_mismatch" in codes(unpatched)


def test_an_id_patch_at_a_split_url_fails_while_loading_configuration() -> None:
    a, b = at("a", "split"), at("b", "split")
    policy = {
        "schemaVersion": 1,
        "candidates": [rule(a, "app:a"), rule(b, "app:b")],
        "pins": [],
    }
    findings = validate_offline(
        inputs(
            [a, b],
            [a, b],
            overlay=[{"url": a["url"], "patch": {"id": "c"}}],
            composition=policy,
        )
    )
    assert [(item.code, item.message) for item in findings] == [
        (
            "invalid_composition_config",
            (
                "overlay[0] for 'example.com/split' patches id at a URL whose "
                "rules name families 'app:a', 'app:b'"
            ),
        )
    ]
    named = validate_offline(
        inputs(
            [a, b],
            [a, b],
            overlay=[{"url": a["url"], "patch": {"name": "x"}}],
            composition=policy,
        )
    )
    assert named == ()


def test_denial_neither_exempts_coverage_nor_remains_selected() -> None:
    denial = [{"url": "https://example.com/one", "reason": "unsupported"}]
    single_only = validate_offline(inputs([at("one")], [], deny=denial))
    assert {
        ("single", "denied_output_present"),
        ("single", "single_only_coverage"),
    } <= {(finding.variant, finding.code) for finding in single_only}
    both = validate_offline(inputs([at("one")], [at("one")], deny=denial))
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
    assert errors(findings) == (), findings
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


def test_absent_unpinned_losing_candidate_cannot_be_assessed_offline() -> None:
    policy = {
        "schemaVersion": 1,
        "candidates": [
            {
                "match": {
                    "source": "extras",
                    "origin": "extras",
                    "id": "absent.pkg",
                    "url": "https://example.com/loser",
                },
                "family": "app:shared",
                "rationale": "An unselected alternative",
            }
        ],
        "pins": [],
    }
    assert validate_offline(inputs(composition=policy)) == ()


def at(package_id: str, path: str | None = None) -> dict[str, Any]:
    value = app(package_id)
    value["url"] = f"https://example.com/{path or package_id}"
    return value


def projecting(family: str, *entries: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "candidates": [
            {
                "match": {
                    "source": "extras",
                    "origin": "extras",
                    "id": entry["id"],
                    "url": entry["url"],
                },
                "family": family,
                "rationale": "fixture",
            }
            for entry in entries
        ],
        "pins": [],
    }


def test_one_repository_s_entries_pair_by_url() -> None:
    single, dual = at("stable", "app"), at("dual", "app/")
    assert validate_offline(inputs([single], [dual])) == ()


def test_a_label_repeated_within_a_variant_is_rejected() -> None:
    a, b = at("a"), at("b")
    [finding] = validate_offline(
        inputs([a, b], [], composition=projecting("app:x", a, b))
    )
    assert (finding.variant, finding.code, finding.severity) == (
        "single",
        "repeated_family_label",
        Severity.ERROR,
    )
    assert finding.message == (
        "family label 'app:x' is carried by more than one entry: "
        "('a', 'example.com/a'), ('b', 'example.com/b')"
    )
    [by_url] = errors(validate_offline(inputs([at("a", "one"), at("b", "one")], [])))
    assert by_url.message == (
        "family label 'example.com/one' is carried by more than one entry: "
        "('a', 'example.com/one'), ('b', 'example.com/one')"
    )


@pytest.mark.parametrize("repeated_in", ["single", "dual"])
@pytest.mark.parametrize("reverse", [False, True])
def test_repeated_label_leaves_both_variants_out_of_coverage(
    repeated_in: str, reverse: bool
) -> None:
    a, b, c = at("a"), at("b"), at("c")
    repeated, other = [a, b], [c]
    if reverse:
        repeated.reverse()
    single, dual = (repeated, other) if repeated_in == "single" else (other, repeated)
    findings = validate_offline(
        inputs(single, dual, composition=projecting("app:x", a, b, c))
    )
    assert [(item.variant, item.code) for item in findings] == [
        (repeated_in, "repeated_family_label")
    ]


def test_same_id_entries_of_different_explicit_families_leave_a_coverage_finding() -> (
    None
):
    single, dual = at("a", "one"), at("a", "two")
    policy = projecting("app:x", single)
    policy["candidates"] += projecting("app:y", dual)["candidates"]
    findings = validate_offline(inputs([single], [dual], composition=policy))
    assert [
        (item.variant, item.entry_id, item.code, item.severity) for item in findings
    ] == [("single", "a", "single_only_coverage", Severity.NONFATAL)]
    assert findings[0].message == (
        "family label 'app:x' ('a' at 'example.com/one') has no dual-screen entry"
    )


@pytest.mark.parametrize("repeated_in", ["single", "dual"])
@pytest.mark.parametrize("reverse", [False, True])
def test_repeated_package_id_is_nonfatal_and_each_entry_pairs_by_its_label(
    repeated_in: str, reverse: bool
) -> None:
    repeated = [at("a", "one"), at("a", "two")]
    if reverse:
        repeated.reverse()
    single, dual = (
        (repeated, [at("a", "one")])
        if repeated_in == "single"
        else ([at("a", "one")], repeated)
    )
    findings = validate_offline(inputs(single, dual))
    assert errors(findings) == ()
    expected = [(repeated_in, "a", "repeated_package_id")]
    if repeated_in == "single":
        # The entry at the other URL has no dual entry carrying its label, even
        # though a dual entry carries its package id.
        expected.append(("single", "a", "single_only_coverage"))
    assert sorted((item.variant, item.entry_id, item.code) for item in findings) == (
        sorted(expected)
    )
    assert {item.severity for item in findings} == {Severity.NONFATAL}
    [repeat] = [item for item in findings if item.code == "repeated_package_id"]
    assert repeat.message == (
        "package id 'a' is carried by more than one entry: "
        "'example.com/one' at 'example.com/one', 'example.com/two' at 'example.com/two'"
    )
    coverage = [item for item in findings if item.code == "single_only_coverage"]
    message = (
        "family label 'example.com/two' ('a' at 'example.com/two') has no "
        "dual-screen entry"
    )
    assert [item.message for item in coverage] == (
        [message] if repeated_in == "single" else []
    )


def test_tracker_and_installable_entry_at_one_ruled_url() -> None:
    installable = at("app.pkg", "project")
    tracker = with_settings(at("1234", "project"), trackOnly=True)
    split = {
        "schemaVersion": 1,
        "candidates": [rule(installable, "app:a"), rule(tracker, "app:a-tracker")],
        "pins": [],
    }
    findings = validate_offline(
        inputs([installable], [installable, tracker], composition=split)
    )
    assert findings == ()
    agreeing = {
        "schemaVersion": 1,
        "candidates": [rule(installable, "app:a")],
        "pins": [],
    }
    labelled = validate_offline(
        inputs([installable], [installable, tracker], composition=agreeing)
    )
    assert [(item.variant, item.code, item.message) for item in labelled] == [
        (
            "dual",
            "repeated_family_label",
            (
                "family label 'app:a' is carried by more than one entry: "
                "('1234', 'example.com/project'), ('app.pkg', 'example.com/project')"
            ),
        )
    ]


def test_denial_inside_a_repeated_label_is_still_reported() -> None:
    a, b = at("a"), at("b")
    findings = validate_offline(
        inputs(
            [a, b],
            [],
            composition=projecting("app:x", a, b),
            deny=[{"url": b["url"], "reason": "excluded"}],
        )
    )
    assert {(item.variant, item.entry_id, item.code) for item in findings} == {
        ("single", None, "repeated_family_label"),
        ("single", "b", "denied_output_present"),
    }


def test_entry_at_a_denied_url_is_reported_per_variant() -> None:
    entry = at("a", "one")
    findings = validate_offline(
        inputs(
            [entry],
            [deepcopy(entry)],
            deny=[{"url": "https://example.com/one", "reason": "excluded"}],
        )
    )
    denials = [item for item in findings if item.code == "denied_output_present"]
    assert [(item.variant, item.entry_id, item.message) for item in denials] == [
        (
            variant,
            "a",
            "entry 'a' at denied project URL 'example.com/one' remains present",
        )
        for variant in ("single", "dual")
    ]
