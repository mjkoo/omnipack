from __future__ import annotations

from dataclasses import replace

import pytest

from omnipack.composition_policy import (
    CompositionPolicyError,
    apply_composition_policy,
    parse_composition_policy,
)
from omnipack.model import App, Provenance, SourceType, Variant


def candidate(**changes: object) -> App:
    base = App(
        "org.example.old",
        "https://github.com/Example/App.git/",
        "Example",
        SourceType.GITHUB,
        (),
        Variant.SINGLE,
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
        policy(
            candidates=[
                rule(
                    packageId="org.example.new",
                    family="app:example",
                    eligible=["dual"],
                    dualPreferred=True,
                )
            ]
        )
    )
    applied = apply_composition_policy(parsed, [candidate()])
    result = applied.candidates[0]

    assert result.id == "org.example.new"
    assert result.original_id == "org.example.old"
    assert result.family == "app:example"
    assert result.eligibility == frozenset({Variant.DUAL})
    assert result.dual_preferred is True
    assert set(result.raw).isdisjoint(
        {"family", "eligible", "eligibility", "dualPreferred", "origin", "originalId"}
    )


def test_identical_candidates_collapse_but_ambiguous_identity_fails() -> None:
    parsed = parse_composition_policy(policy())
    assert (
        len(apply_composition_policy(parsed, [candidate(), candidate()]).candidates)
        == 1
    )

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
        (policy(extra=[]), "unknown field"),
        (policy(candidates=[rule(extra=True)]), "unknown field"),
        (policy(candidates=[rule(family="package:forbidden")]), "family"),
        (policy(candidates=[rule(family="app:bad family")]), "family"),
        (policy(candidates=[rule(eligible=[])]), "eligible"),
        (
            policy(candidates=[rule(eligible=["single"], dualPreferred=True)]),
            "dualPreferred",
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


def test_projection_supports_offline_family_and_corrected_pin_lookup() -> None:
    parsed = parse_composition_policy(
        policy(
            candidates=[rule(packageId="org.example.new", family="app:example")],
            pins=[
                {
                    "family": "app:example",
                    "variant": "dual",
                    "match": rule()["match"],
                    "rationale": "Prefer the tested dual build.",
                }
            ],
        )
    )
    applied = apply_composition_policy(parsed, [candidate()])
    key = ("org.example.new", "github.com/example/app")

    assert parsed.projections[key].family == "app:example"
    assert parsed.projections[key].eligibility is None
    assert parsed.projected_pins[("app:example", Variant.DUAL)] == key
    assert applied.projected_pins[("app:example", Variant.DUAL)] == key


def test_staged_application_defers_only_missing_selector_presence() -> None:
    parsed = parse_composition_policy(
        policy(
            candidates=[rule(packageId="org.example.new", family="app:example")],
            pins=[
                {
                    "family": "app:example",
                    "variant": "dual",
                    "match": rule()["match"],
                    "rationale": "Prefer the tested dual build.",
                }
            ],
        )
    )
    assert apply_composition_policy(parsed, [], require_all=False).candidates == ()
    assert (
        apply_composition_policy(parsed, [], require_all=False).projected_pins
        == parsed.projected_pins
    )
    with pytest.raises(CompositionPolicyError, match="matched no candidate"):
        apply_composition_policy(parsed, [])

    conflicting = candidate(
        id="org.example.new",
        original_id="org.example.new",
        provenance=Provenance("bboi", "asset"),
        origin="bboi-standard-asset",
    )
    with pytest.raises(CompositionPolicyError, match="rendered projection"):
        apply_composition_policy(parsed, [conflicting], require_all=False)


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


def test_projection_adopts_the_only_explicit_eligibility() -> None:
    other = rule(
        match={
            "source": "bboi",
            "origin": "bboi-standard-asset",
            "id": "org.example.new",
            "url": "https://github.com/example/app",
        },
        family="app:example",
        eligible=["dual"],
    )
    parsed = parse_composition_policy(
        policy(
            candidates=[
                rule(packageId="org.example.new", family="app:example"),
                other,
            ]
        )
    )
    assert parsed.projections[
        ("org.example.new", "github.com/example/app")
    ].eligibility == frozenset({Variant.DUAL})


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


def test_history_is_normalized_independent_and_conflict_checked() -> None:
    parsed = parse_composition_policy(
        policy(
            history=[
                {
                    "id": "org.retired",
                    "url": "HTTPS://WWW.GITHUB.COM/Example/Retired.git/",
                    "family": "app:retired",
                    "rationale": "Previously published identity.",
                }
            ]
        )
    )
    assert (
        parsed.history[("org.retired", "github.com/example/retired")] == "app:retired"
    )
    assert apply_composition_policy(parsed, []).candidates == ()

    with pytest.raises(CompositionPolicyError, match="duplicate history key"):
        parse_composition_policy(
            policy(
                history=[
                    {
                        "id": "x",
                        "url": "https://github.com/a/b",
                        "family": "package:x",
                        "rationale": "Old output.",
                    },
                    {
                        "id": "x",
                        "url": "https://www.github.com/A/B.git/",
                        "family": "package:x",
                        "rationale": "Old output.",
                    },
                ]
            )
        )

    with pytest.raises(CompositionPolicyError, match="history.*conflicts"):
        parse_composition_policy(
            policy(
                candidates=[rule(packageId="org.example.new", family="app:example")],
                history=[
                    {
                        "id": "org.example.new",
                        "url": "https://github.com/example/app",
                        "family": "app:other",
                        "rationale": "Old output.",
                    }
                ],
            )
        )
