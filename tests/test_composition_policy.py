from __future__ import annotations

import json
from dataclasses import replace

import pytest

from omnipack.composition_policy import (
    CompositionPolicy,
    CompositionPolicyError,
    apply_composition_policy,
    load_composition_policy,
    parse_composition_policy,
)
from omnipack.merge import CompositionError, _import_data, compose
from omnipack.model import App, Category, Provenance, SourceType, Variant
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
        "rationale": "Group the project's builds.",
    }
    value.update(changes)
    return value


URL = "github.com/example/app"


def test_rule_matches_its_own_selector_without_recursive_matching() -> None:
    parsed = parse_composition_policy(
        policy(
            candidates=[
                rule(family="app:example"),
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


def test_family_rule_keeps_the_source_identity_and_internal_fields() -> None:
    parsed = parse_composition_policy(policy(candidates=[rule(family="app:example")]))
    [result] = apply_composition_policy(
        parsed, [candidate(raw={"futureField": {"retained": True}})]
    )

    assert result.id == "org.example.old"
    assert result.family == "app:example"
    assert result.eligibility == frozenset(Variant)
    assert result.dual_preferred is False
    assert result.raw == {"futureField": {"retained": True}}

    rendered = json.loads(
        render(
            [ComposedApp("app:example", _import_data(result))],
        )
    )["apps"][0]
    assert rendered["id"] == "org.example.old"
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
        (policy(candidates=[rule(family=URL)]), "family"),
        (policy(candidates=[rule(family="app:bad family")]), "family"),
        (
            policy(candidates=[rule(), rule(unexpected=True)]),
            r"candidates\[1\] has unknown field 'unexpected'",
        ),
        (
            policy(candidates=[rule(packageId="org.example.new")]),
            r"candidates\[0\] has unknown field 'packageId'",
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
        "family": URL,
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
                    "family": URL,
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
        replace(single_only, family=URL),
    )


def other_source(**changes: object) -> App:
    """A candidate from another source, by default at the same project URL."""
    values: dict[str, object] = {
        "id": "org.example.new",
        "provenance": Provenance("bboi", "asset"),
        "origin": "bboi-standard-asset",
    }
    return candidate(**{**values, **changes})


def other_rule(package_id: str, url: str, **changes: object) -> dict[str, object]:
    return rule(
        match={
            "source": "bboi",
            "origin": "bboi-standard-asset",
            "id": package_id,
            "url": url,
        },
        **changes,
    )


def families(
    parsed: CompositionPolicy, candidates: list[App]
) -> list[tuple[str, str | None]]:
    return [
        (app.id, app.family) for app in apply_composition_policy(parsed, candidates)
    ]


def test_family_rule_covers_every_build_at_its_url() -> None:
    parsed = parse_composition_policy(
        policy(candidates=[other_rule("org.example.new", URL, family="app:x")])
    )
    quiver = candidate(
        id="org.example.quiver",
        provenance=Provenance("quiver", "catalog"),
        origin="quiver-generated",
    )
    codm = candidate(
        id="org.example.codm",
        provenance=Provenance("codm2000", "catalog"),
        origin="codm-generated",
    )
    assert families(parsed, [other_source(), quiver, codm]) == [
        ("org.example.new", "app:x"),
        ("org.example.quiver", "app:x"),
        ("org.example.codm", "app:x"),
    ]
    assert parsed.url_rule_families("https://github.com/Example/App") == ("app:x",)


def test_rules_naming_different_families_split_one_repository() -> None:
    parsed = parse_composition_policy(
        policy(
            candidates=[
                rule(family="app:a"),
                other_rule("org.example.new", URL, family="app:b"),
            ]
        )
    )
    third = candidate(
        id="org.example.third",
        provenance=Provenance("extras", "catalog"),
        origin="extras",
    )
    assert families(parsed, [candidate(), other_source(), third]) == [
        ("org.example.old", "app:a"),
        ("org.example.new", "app:b"),
        ("org.example.third", URL),
    ]
    assert parsed.url_rule_families(URL) == ("app:a", "app:b")


def test_rules_projecting_one_id_and_url_onto_different_families_fail() -> None:
    with pytest.raises(CompositionPolicyError) as error:
        parse_composition_policy(
            policy(
                candidates=[
                    rule(family="app:a"),
                    other_rule("org.example.old", URL, family="app:b"),
                ]
            )
        )
    assert str(error.value) == (
        "rules ('rjny', 'rjny-catalog', 'org.example.old', 'github.com/example/app') "
        "and ('bboi', 'bboi-standard-asset', 'org.example.old', "
        "'github.com/example/app') project conflicting families 'app:a' and "
        "'app:b' onto ('org.example.old', 'github.com/example/app')"
    )


def test_agreeing_rules_on_one_id_and_url_load() -> None:
    parsed = parse_composition_policy(
        policy(
            candidates=[
                rule(family="app:a"),
                other_rule("org.example.old", URL, family="app:a"),
            ]
        )
    )
    assert parsed.url_families == {URL: "app:a"}


def test_rule_assigning_a_family_to_a_track_only_candidate_loads() -> None:
    tracker = candidate(id="1234", additional_settings={"trackOnly": True})
    parsed = parse_composition_policy(
        policy(
            candidates=[
                rule(
                    match={
                        "source": "rjny",
                        "origin": "rjny-catalog",
                        "id": "1234",
                        "url": URL,
                    },
                    family="app:tracker",
                ),
                other_rule("org.example.new", URL, family="app:x"),
            ]
        )
    )
    assert families(parsed, [tracker, other_source()]) == [
        ("1234", "app:tracker"),
        ("org.example.new", "app:x"),
    ]


def test_descriptive_rules_and_shared_tracker_ids_are_allowed() -> None:
    tracker = candidate(additional_settings={"trackOnly": True})
    other = replace(tracker, url="https://example.com/other")
    ordinary = replace(candidate(), url="https://example.com/ordinary")
    parsed = parse_composition_policy(policy(candidates=[rule()]))
    assert families(parsed, [tracker, other, ordinary]) == [
        (tracker.id, URL),
        (tracker.id, "example.com/other"),
        (tracker.id, "example.com/ordinary"),
    ]


def test_pin_family_must_match_an_explicit_projection_at_load() -> None:
    pin = {
        "family": "app:wrong",
        "variant": "dual",
        "match": rule()["match"],
        "rationale": "Prefer this build.",
    }
    with pytest.raises(
        CompositionPolicyError,
        match="pin family 'app:wrong' target 'dual' conflicts with projected "
        "family 'app:example'",
    ):
        parse_composition_policy(
            policy(candidates=[rule(family="app:example")], pins=[pin])
        )
    # A rule elsewhere at the pin's URL projects the family onto it too.
    with pytest.raises(CompositionPolicyError, match="projected family 'app:x'"):
        parse_composition_policy(
            policy(
                candidates=[other_rule("org.example.new", URL, family="app:x")],
                pins=[{**pin, "family": URL}],
            )
        )
    # Without an explicit projection the family forms at build time.
    assert parse_composition_policy(policy(pins=[pin])).pins[0].family == "app:wrong"


def test_pin_family_is_checked_at_load_and_its_denial_at_compose() -> None:
    pin = {
        "family": "app:wrong",
        "variant": "dual",
        "match": rule()["match"],
        "rationale": "Prefer this build.",
    }
    denylist = [{"url": "https://github.com/example/app", "reason": "broken"}]
    with pytest.raises(CompositionPolicyError, match="pin family 'app:wrong'"):
        parse_composition_policy(
            policy(candidates=[rule(family="app:example")], pins=[pin])
        )
    # With the family corrected, the same denial is what fails the build.
    parsed = parse_composition_policy(
        policy(
            candidates=[rule(family="app:example")],
            pins=[{**pin, "family": "app:example"}],
        )
    )
    with pytest.raises(CompositionError, match=f"is denied at '{URL}': broken"):
        compose([candidate()], denylist, [], policy=parsed)


def test_pin_may_name_a_url_family() -> None:
    pin = {
        "family": URL,
        "variant": "dual",
        "match": rule()["match"],
        "rationale": "Prefer this build.",
    }
    parsed = parse_composition_policy(policy(pins=[pin]))
    assert parsed.projected_pins == {(URL, Variant.DUAL): ("org.example.old", URL)}


@pytest.mark.parametrize(
    "family", ["melonds", "com.dishii.zelda3", "https://github.com/example/app"]
)
def test_pin_family_must_be_an_app_name_or_a_normalized_url(family: str) -> None:
    pin = {
        "family": family,
        "variant": "dual",
        "match": rule()["match"],
        "rationale": "Prefer this build.",
    }
    with pytest.raises(CompositionPolicyError, match=rf"pins\[0\]\.family.*{family!r}"):
        parse_composition_policy(policy(pins=[pin]))


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
        record.update(family="github.com/example/app", variant="dual")
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
        pytest.param("https://example.com:99999/owner/repo", id="out-of-range-port"),
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
        record.update(family="github.com/example/app", variant="dual")

    with pytest.raises(CompositionPolicyError) as error:
        parse_composition_policy(policy(**{kind: [record]}))

    assert str(error.value) == f"{kind}[0].match.url is not a project URL: {url!r}"


def test_category_map_assigns_one_category_per_family() -> None:
    parsed = parse_composition_policy(
        policy(categories={"app:ctr": "Decomps/Recomps", URL: "PC Ports"})
    )
    assert parsed.categories == {
        "app:ctr": Category.DECOMPS,
        URL: Category.PC_PORTS,
    }
    assert parse_composition_policy(policy()).categories == {}


@pytest.mark.parametrize(
    ("categories", "message"),
    [
        ({"app:x": "Dual Screen"}, r"categories\['app:x'\].*'Dual Screen'"),
        ({"app:x": "Track Only"}, r"categories\['app:x'\].*'Track Only'"),
        ({"app:x": ["PC Ports"]}, r"categories\['app:x'\]"),
        ({"app:x": 7}, r"categories\['app:x'\]"),
        ({"melonds": "PC Ports"}, r"categories key 'melonds' must be an app: family"),
        (
            {"com.dishii.zelda3": "PC Ports"},
            r"categories key 'com.dishii.zelda3' must be an app: family",
        ),
        (
            {"https://github.com/Owner/Repo": "PC Ports"},
            r"categories key 'https://github.com/Owner/Repo' must be an app: family",
        ),
        (
            {"github.com/Owner/Repo": "PC Ports"},
            r"categories key 'github.com/Owner/Repo' must be an app: family",
        ),
        ({"app:": "PC Ports"}, r"categories key 'app:' must use a nonempty"),
        ({"package:x": "PC Ports"}, r"categories key 'package:x' must be an app:"),
        (["app:x"], "categories must be an object"),
    ],
)
def test_invalid_category_map_fails_with_the_key_identified(
    categories: object, message: str
) -> None:
    with pytest.raises(CompositionPolicyError, match=message):
        parse_composition_policy(policy(categories=categories))


@pytest.mark.parametrize("second", ["PC Ports", "Emulator"])
def test_family_key_repeated_in_the_category_map_fails(second: str) -> None:
    document = (
        '{"schemaVersion": 1, "candidates": [], "pins": [], "categories": '
        f'{{"app:x": "PC Ports", "app:x": "{second}"}}}}'
    )
    with pytest.raises(CompositionPolicyError, match="duplicate JSON key 'app:x'"):
        load_composition_policy(document)


def test_key_repeated_anywhere_in_the_policy_fails() -> None:
    document = json.dumps(policy(candidates=[rule()]))
    repeated = document.replace('"rationale":', '"rationale": "first", "rationale":', 1)
    with pytest.raises(CompositionPolicyError, match="duplicate JSON key 'rationale'"):
        load_composition_policy(repeated)
