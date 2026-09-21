from __future__ import annotations

import json
from dataclasses import replace

import pytest

from omnipack.composition_policy import (
    CompositionPolicyError,
    apply_composition_policy,
    load_composition_policy,
    parse_composition_policy,
)
from omnipack.merge import _import_data
from omnipack.model import App, Provenance, SourceType, Variant
from omnipack.overlay import ComposedApp
from omnipack.render import render


def candidate(**changes: object) -> App:
    base = App(
        "org.example.old",
        "https://github.com/Example/App.git/",
        "Example",
        SourceType.GITHUB,
        (),
        Provenance("rjny", "catalog"),
        eligibility=frozenset(Variant),
        origin="rjny-catalog",
    )
    return replace(base, **changes)


def policy(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {"schemaVersion": 1, "candidates": [], "pins": []}
    value.update(changes)
    return value


def rule(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "match": {
            "source": "rjny",
            "origin": "rjny-catalog",
            "id": "org.example.old",
            "url": "https://github.com/example/app",
        },
        "rationale": "Primary APK manifest records the corrected identity.",
    }
    value.update(changes)
    return value


def test_policy_applies_one_original_selector_without_recursive_matching() -> None:
    parsed = parse_composition_policy(
        policy(
            candidates=[
                rule(packageId="org.example.new", family="app:example"),
                rule(
                    match={
                        "source": "rjny",
                        "origin": "rjny-catalog",
                        "id": "org.example.new",
                        "url": "https://github.com/example/app",
                    },
                    family="app:example",
                ),
            ]
        )
    )

    with pytest.raises(CompositionPolicyError, match="org.example.new.*matched no"):
        apply_composition_policy(parsed, [candidate()])


def test_policy_correction_retains_original_identity_and_internal_fields() -> None:
    parsed = parse_composition_policy(
        policy(candidates=[rule(packageId="org.example.new", family="app:example")])
    )
    [result] = apply_composition_policy(
        parsed, [candidate(raw={"futureField": {"retained": True}})]
    )

    assert result.id == "org.example.new"
    assert result.original_id == "org.example.old"
    assert result.family == "app:example"
    assert result.eligibility == frozenset(Variant)
    assert result.dual_preferred is False
    assert result.raw == {"futureField": {"retained": True}}

    rendered = json.loads(
        render(
            [ComposedApp("app:example", _import_data(result))],
        )
    )["apps"][0]
    assert rendered["id"] == "org.example.new"
    assert rendered["futureField"] == {"retained": True}
    assert set(rendered).isdisjoint({"family", "packageId", "variant"})


def test_identical_candidates_collapse_but_ambiguous_identity_fails() -> None:
    parsed = parse_composition_policy(policy())
    assert len(apply_composition_policy(parsed, [candidate(), candidate()])) == 1

    with pytest.raises(
        CompositionPolicyError, match="ambiguous original candidate identity"
    ):
        apply_composition_policy(
            parsed, [candidate(), candidate(name="Different payload")]
        )


@pytest.mark.parametrize(
    "document, message",
    [
        ({"schemaVersion": True, "candidates": [], "pins": []}, "schemaVersion"),
        (policy(history=[]), "unknown field 'history'"),
        (policy(candidates=[rule(family="package:forbidden")]), "family"),
        (policy(candidates=[rule(family="app:bad family")]), "family"),
        (
            policy(candidates=[rule(), rule(unexpected=True)]),
            r"candidates\[1\] has unknown field 'unexpected'",
        ),
        (policy(candidates=[rule(rationale="  ")]), "rationale"),
        (
            policy(
                candidates=[
                    rule(
                        match={
                            "source": "other",
                            "origin": "rjny-catalog",
                            "id": "x",
                            "url": "https://x/y",
                        }
                    )
                ]
            ),
            "source",
        ),
    ],
)
def test_policy_rejects_invalid_shapes(document: object, message: str) -> None:
    with pytest.raises(CompositionPolicyError, match=message):
        parse_composition_policy(document)


def test_duplicate_selectors_and_conflicting_pins_fail() -> None:
    with pytest.raises(CompositionPolicyError, match="duplicate candidate selector"):
        parse_composition_policy(policy(candidates=[rule(), rule()]))

    pin = {
        "family": "app:example",
        "variant": "dual",
        "match": rule()["match"],
        "rationale": "Prefer the tested dual build.",
    }
    with pytest.raises(CompositionPolicyError, match="multiple pins"):
        parse_composition_policy(
            policy(candidates=[rule(family="app:example")], pins=[pin, pin])
        )


def test_unknown_pin_target_and_malformed_json_fail() -> None:
    invalid_pin = {
        "family": "package:org.example.old",
        "variant": "tablet",
        "match": rule()["match"],
        "rationale": "Prefer this build.",
    }
    with pytest.raises(CompositionPolicyError, match="unknown target.*tablet"):
        parse_composition_policy(policy(pins=[invalid_pin]))
    with pytest.raises(CompositionPolicyError, match="invalid JSON"):
        load_composition_policy(b'{"schemaVersion": 1,')


def test_policy_application_leaves_pins_to_composition() -> None:
    parsed = parse_composition_policy(
        policy(
            pins=[
                {
                    "family": "package:org.example.old",
                    "variant": "dual",
                    "match": rule()["match"],
                    "rationale": "Require the selected dual build.",
                }
            ]
        )
    )
    single_only = candidate(eligibility=frozenset({Variant.SINGLE}))
    assert apply_composition_policy(parsed, []) == ()
    assert apply_composition_policy(parsed, [single_only]) == (
        replace(single_only, family="package:org.example.old"),
    )


def test_projection_conflicts_and_unruled_candidate_conflicts_fail() -> None:
    other = rule(
        match={
            "source": "bboi",
            "origin": "bboi-standard-asset",
            "id": "org.example.new",
            "url": "https://github.com/example/app",
        },
        family="app:other",
    )
    with pytest.raises(CompositionPolicyError, match="rendered key.*org.example.new"):
        parse_composition_policy(
            policy(
                candidates=[
                    rule(packageId="org.example.new", family="app:example"),
                    other,
                ]
            )
        )

    parsed = parse_composition_policy(
        policy(candidates=[rule(packageId="org.example.new", family="app:example")])
    )
    unruled = candidate(
        id="org.example.new",
        original_id="org.example.new",
        provenance=Provenance("bboi", "asset"),
        origin="bboi-standard-asset",
    )
    with pytest.raises(
        CompositionPolicyError, match="unruled candidate.*rendered projection"
    ):
        apply_composition_policy(parsed, [candidate(), unruled])


def test_agreeing_rules_share_one_projected_family() -> None:
    other = rule(
        match={
            "source": "bboi",
            "origin": "bboi-standard-asset",
            "id": "org.example.new",
            "url": "https://github.com/example/app",
        },
        family="app:example",
    )
    parsed = parse_composition_policy(
        policy(
            candidates=[
                rule(packageId="org.example.new", family="app:example"),
                other,
            ]
        )
    )
    applied = apply_composition_policy(
        parsed,
        [
            candidate(),
            candidate(
                id="org.example.new",
                original_id="org.example.new",
                provenance=Provenance("bboi", "asset"),
                origin="bboi-standard-asset",
            ),
        ],
    )
    assert [(app.id, app.family) for app in applied] == [
        ("org.example.new", "app:example"),
        ("org.example.new", "app:example"),
    ]


def test_pin_family_must_match_its_projected_candidate_family() -> None:
    with pytest.raises(CompositionPolicyError, match="pin family.*conflicts"):
        parse_composition_policy(
            policy(
                pins=[
                    {
                        "family": "app:wrong",
                        "variant": "dual",
                        "match": rule()["match"],
                        "rationale": "Prefer this build.",
                    }
                ]
            )
        )


@pytest.mark.parametrize(
    "assignment",
    [
        {"family": "app:example"},
        {"packageId": "changed"},
        {"packageId": "org.example.old"},
    ],
)
def test_track_only_assignments_fail_with_original_selector(
    assignment: dict[str, str],
) -> None:
    parsed = parse_composition_policy(policy(candidates=[rule(**assignment)]))
    with pytest.raises(
        CompositionPolicyError, match="track-only.*rjny.*org.example.old"
    ):
        apply_composition_policy(
            parsed, [candidate(additional_settings={"trackOnly": True})]
        )


@pytest.mark.parametrize(
    "ordinary, rules",
    [
        (candidate(), [rule(packageId="tracker")]),
        (candidate(id="tracker", original_id="tracker"), []),
        (
            candidate(id="tracker", original_id="tracker"),
            [
                rule(
                    match={
                        "source": "rjny",
                        "origin": "rjny-catalog",
                        "id": "tracker",
                        "url": "https://github.com/example/app",
                    }
                )
            ],
        ),
    ],
    ids=["corrected", "ingested", "descriptive"],
)
def test_ordinary_effective_id_cannot_take_track_only_id(
    ordinary: App, rules: list[dict[str, object]]
) -> None:
    tracker = candidate(
        id="tracker",
        original_id="tracker",
        url="https://example.com/tracker",
        additional_settings={"trackOnly": True},
    )
    with pytest.raises(
        CompositionPolicyError, match="reserved track-only.*example/app"
    ):
        apply_composition_policy(
            parse_composition_policy(policy(candidates=rules)), [ordinary, tracker]
        )


def test_track_only_violation_precedes_earlier_rendered_projection_conflict() -> None:
    earlier = candidate(
        id="tracker",
        original_id="tracker",
        provenance=Provenance("extras", "catalog"),
        origin="extras",
        additional_settings={"trackOnly": True},
    )
    parsed = parse_composition_policy(
        policy(candidates=[rule(packageId="tracker", family="app:example")])
    )
    with pytest.raises(
        CompositionPolicyError, match="reserved track-only.*rjny.*org.example.old"
    ):
        apply_composition_policy(parsed, [earlier, candidate()])


def test_descriptive_track_only_rules_and_duplicate_tracker_ids_are_allowed() -> None:
    tracker = candidate(additional_settings={"trackOnly": True})
    other = replace(tracker, url="https://example.com/other")
    results = apply_composition_policy(
        parse_composition_policy(policy(candidates=[rule()])), [tracker, other]
    )
    assert [(app.id, app.family) for app in results] == [
        (tracker.id, f"package:{tracker.id}")
    ] * 2


@pytest.mark.parametrize("setting", [False, "true", 1])
def test_non_boolean_track_only_does_not_block_apk_rules(setting: object) -> None:
    parsed = parse_composition_policy(
        policy(candidates=[rule(packageId="corrected", family="app:example")])
    )
    [result] = apply_composition_policy(
        parsed, [candidate(additional_settings={"trackOnly": setting})]
    )
    assert (result.id, result.family) == ("corrected", "app:example")


def test_ordinary_identity_can_be_corrected_away_from_reserved_id() -> None:
    tracker = candidate(
        additional_settings={"trackOnly": True}, url="https://example.com/tracker"
    )
    parsed = parse_composition_policy(policy(candidates=[rule(packageId="corrected")]))
    results = apply_composition_policy(parsed, [candidate(), tracker])
    assert [app.id for app in results] == ["corrected", tracker.id]


@pytest.mark.parametrize("kind", ["candidates", "pins"])
def test_selector_origin_must_belong_to_its_source_before_matching(kind: str) -> None:
    record = rule(
        match={
            "source": "rjny",
            "origin": "bboi-standard-asset",
            "id": "org.example.old",
            "url": "https://github.com/example/app",
        }
    )
    if kind == "pins":
        record.update(family="package:org.example.old", variant="dual")
    with pytest.raises(CompositionPolicyError) as error:
        parse_composition_policy(policy(**{kind: [record]}))
    assert (
        str(error.value)
        == f"{kind}[0].match.origin 'bboi-standard-asset' is invalid for source 'rjny'"
    )


@pytest.mark.parametrize("kind", ["candidates", "pins"])
@pytest.mark.parametrize(
    "url",
    [
        pytest.param("/owner/repo", id="no-host"),
        pytest.param("https://example.com/owner /repo", id="whitespace"),
        pytest.param("https://example.com:abc/owner/repo", id="bad-port"),
    ],
)
def test_selector_url_must_be_normalizable_before_candidate_matching(
    kind: str, url: str
) -> None:
    record = rule(
        match={
            "source": "rjny",
            "origin": "rjny-catalog",
            "id": "org.example.old",
            "url": url,
        }
    )
    if kind == "pins":
        record.update(family="package:org.example.old", variant="dual")

    with pytest.raises(CompositionPolicyError) as error:
        parse_composition_policy(policy(**{kind: [record]}))

    assert str(error.value) == f"{kind}[0].match.url is not a project URL: {url!r}"
