from __future__ import annotations

from dataclasses import replace

import pytest

from omnipack.composition_policy import (
    CandidateRule,
    CompositionPolicy,
    Pin,
    candidate_selector,
    parse_composition_policy,
    rendered_key,
)
from omnipack.merge import (
    CompositionError,
    CompositionReport,
    CompositionResult,
    ConsideredCandidate,
    StaleExclusion,
)
from omnipack.merge import (
    compose as compose_apps,
)
from omnipack.model import App, Provenance, SourceType, Variant


def app(
    package_id: str,
    source: str = "rjny",
    *,
    family: str | None = None,
    eligibility: frozenset[Variant] = frozenset(Variant),
    url: str | None = None,
    name: str | None = None,
    original_id: str | None = None,
    origin: str | None = None,
    additional_settings: dict[str, object] | None = None,
) -> App:
    url = url or f"https://example.com/{source}/{package_id}"
    origins = {
        "rjny": "rjny-catalog",
        "bboi": "bboi-standard-asset",
        "extras": "extras",
        "codm2000": "codm-generated",
    }
    return App(
        package_id,
        url,
        name or f"{source} {package_id}",
        SourceType.HTML,
        (),
        Provenance(source, url),
        eligibility=eligibility,
        origin=origin or origins[source],
        original_id=original_id or package_id,
        family=family or f"package:{package_id}",
        additional_settings=additional_settings or {},
    )


def overlays(*records: tuple[str, str, dict[str, object]]) -> list[dict[str, object]]:
    return [
        {"id": package_id, "url": url, "patch": patch}
        for package_id, url, patch in records
    ]


def pin_policy(
    candidate: App,
    family: str,
    variant: Variant,
    *alternatives: App,
) -> CompositionPolicy:
    pinned_selector = candidate_selector(candidate)
    candidates = (candidate, *alternatives)
    projections = {rendered_key(item.id, item.url): family for item in candidates}
    rules = tuple(
        CandidateRule(candidate_selector(item), "test", family=family)
        for item in candidates
    )
    key = rendered_key(candidate.id, candidate.url)
    return CompositionPolicy(
        rules,
        (Pin(family, variant, pinned_selector, "test"),),
        projections,
        {(family, variant): key},
    )


def ids(result: CompositionResult, variant: Variant) -> set[str]:
    return {item.id for item in result.apps[variant]}


def compose(
    candidates: list[App],
    denylist: list[dict[str, str]],
    overlay: object,
    *,
    policy: CompositionPolicy | None = None,
    report: CompositionReport | None = None,
) -> CompositionResult:
    if policy is None:
        rules: list[CandidateRule] = []
        projections: dict[tuple[str, str], str] = {}
        for candidate in candidates:
            family = candidate.family or f"package:{candidate.id}"
            if family.startswith("app:"):
                rules.append(
                    CandidateRule(candidate_selector(candidate), "test", family=family)
                )
                projections[rendered_key(candidate.id, candidate.url)] = family
        policy = CompositionPolicy(tuple(rules), (), projections, {})
    return compose_apps(
        candidates,
        denylist,
        overlay,
        policy=policy,
        report=report,
    )


def test_dual_prefers_suitable_candidate_before_higher_source() -> None:
    ordinary = app("ordinary", "extras", family="app:shared")
    preferred = app(
        "dual",
        "bboi",
        family="app:shared",
        eligibility=frozenset({Variant.DUAL}),
    )
    result = compose([ordinary, preferred], [], [])
    assert ids(result, Variant.SINGLE) == {"ordinary"}
    assert ids(result, Variant.DUAL) == {"dual"}
    assert [item.reason for item in result.report.selections] == [
        "source",
        "dual-preferred",
    ]


def test_dual_preferred_bboi_reports_the_ordinary_rjny_entry_as_considered() -> None:
    ordinary = app("ordinary.app", "rjny", family="app:shared")
    preferred = app(
        "dual.app",
        "bboi",
        family="app:shared",
        eligibility=frozenset({Variant.DUAL}),
        origin="bboi-dual-asset",
    )
    result = compose([ordinary, preferred], [], [])
    [dual_selection] = [
        item for item in result.report.selections if item.variant is Variant.DUAL
    ]
    assert dual_selection.reason == "dual-preferred"
    assert dual_selection.effective_id == "dual.app"
    assert dual_selection.considered == (
        ConsideredCandidate("rjny", "rjny-catalog", "ordinary.app", ordinary.url),
    )


def test_pin_wins_and_denied_or_ineligible_pin_fails() -> None:
    high = app("high", "extras", family="app:shared")
    pinned = app("pinned", "bboi", family="app:shared")
    policy = pin_policy(pinned, "app:shared", Variant.DUAL, high)
    assert ids(compose([high, pinned], [], [], policy=policy), Variant.DUAL) == {
        "pinned"
    }
    with pytest.raises(CompositionError, match=r"pin.*denied"):
        compose(
            [high, pinned],
            [{"id": "pinned", "reason": "bad"}],
            [],
            policy=policy,
        )
    with pytest.raises(CompositionError, match=r"pin.*ineligible"):
        compose(
            [high, replace(pinned, eligibility=frozenset({Variant.SINGLE}))],
            [],
            [],
            policy=policy,
        )


def test_pin_uses_original_provenance_when_rendered_identity_is_shared() -> None:
    high = app(
        "shared", "extras", family="app:shared", url="https://example.com/project"
    )
    pinned = app(
        "shared", "bboi", family="app:shared", url="https://example.com/project"
    )
    policy = pin_policy(pinned, "app:shared", Variant.DUAL, high)
    result = compose([high, pinned], [], [], policy=policy)
    assert [
        item.source for item in result.report.selections if item.variant is Variant.DUAL
    ] == ["bboi"]


@pytest.mark.parametrize("present", [False, True], ids=["missing", "ineligible"])
def test_pin_failure_preserves_independent_exclusion_diagnostics(present: bool) -> None:
    pinned = app("pinned", eligibility=frozenset({Variant.SINGLE}))
    policy = parse_composition_policy(
        {
            "schemaVersion": 1,
            "candidates": [],
            "pins": [
                {
                    "family": "package:pinned",
                    "variant": "dual",
                    "match": {
                        "source": "rjny",
                        "origin": "rjny-catalog",
                        "id": pinned.id,
                        "url": pinned.url,
                    },
                    "rationale": "Require this build for dual.",
                }
            ],
        }
    )
    report = CompositionReport()
    with pytest.raises(CompositionError, match=r"pin.*(?:missing|ineligible)"):
        compose(
            [app("removed"), *([pinned] if present else [])],
            [
                {"id": "removed", "reason": "unsupported"},
                {"id": "retired", "reason": "obsolete"},
            ],
            [],
            policy=policy,
            report=report,
        )
    assert [
        (item.package_id, item.variant, item.reason) for item in report.removals
    ] == [
        ("removed", Variant.SINGLE, "unsupported"),
        ("removed", Variant.DUAL, "unsupported"),
    ]
    assert [(item.package_id, item.reason) for item in report.stale_exclusions] == [
        ("retired", "obsolete")
    ]


def test_exclusions_apply_to_candidates_before_selection_and_stale_is_nonfatal() -> (
    None
):
    denied = app("same", "extras", family="app:shared")
    alternative = app("other", "rjny", family="app:shared")
    result = compose(
        [denied, alternative],
        [
            {"id": "same", "reason": "broken"},
            {"id": "old.package", "reason": "obsolete"},
        ],
        [],
    )
    assert ids(result, Variant.SINGLE) == {"other"}
    assert ids(result, Variant.DUAL) == {"other"}
    assert result.report.stale_exclusions == [StaleExclusion("old.package", "obsolete")]


def test_denial_of_a_build_eligible_for_neither_pack_is_not_stale() -> None:
    unexported = app("unexported", eligibility=frozenset())
    result = compose([unexported], [{"id": "unexported", "reason": "retired"}], [])
    assert result.apps == {Variant.SINGLE: [], Variant.DUAL: []}
    assert result.report.removals == []
    assert result.report.stale_exclusions == []


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({"reason": "x"}, r"denylist\[0\]\.id must be a nonempty string"),
        ({"id": None, "reason": "x"}, r"denylist\[0\]\.id must be a nonempty string"),
        ({"id": "x"}, r"denylist\[0\]\.reason must be a nonempty string"),
        (
            {"id": "x", "family": "app:x", "reason": "x"},
            r"denylist\[0\] has unknown field 'family'",
        ),
        (
            {"family": "app:x", "reason": "x"},
            r"denylist\[0\] has unknown field 'family'",
        ),
        (
            {"id": "x", "variant": "dual", "reason": "x"},
            r"denylist\[0\] has unknown field 'variant'",
        ),
    ],
)
def test_denylist_entries_hold_exactly_a_package_id_and_reason(
    entry: dict[str, str], message: str
) -> None:
    with pytest.raises(CompositionError, match=message):
        compose([], [entry], [])


def test_package_denial_leaves_a_different_package_alternative_selectable() -> None:
    standard = app("standard", "extras", family="app:x")
    preferred = app(
        "dual.denied",
        "bboi",
        family="app:x",
        eligibility=frozenset({Variant.DUAL}),
    )
    result = compose(
        [standard, preferred], [{"id": "dual.denied", "reason": "broken"}], []
    )
    assert ids(result, Variant.SINGLE) == ids(result, Variant.DUAL) == {"standard"}
    assert [(item.package_id, item.variant) for item in result.report.removals] == [
        ("dual.denied", Variant.DUAL)
    ]


def test_package_denial_removes_the_package_from_every_source() -> None:
    carriers = [
        app("shared.pkg", source, family="app:x")
        for source in ("extras", "rjny", "bboi")
    ]
    other = app("other.pkg", "bboi", family="app:x")
    result = compose([*carriers, other], [{"id": "shared.pkg", "reason": "broken"}], [])
    assert ids(result, Variant.SINGLE) == ids(result, Variant.DUAL) == {"other.pkg"}
    assert len(result.report.removals) == 2 * len(carriers)
    assert {item.package_id for item in result.report.removals} == {"shared.pkg"}
    assert result.report.stale_exclusions == []


def shared_package_builds() -> tuple[App, App]:
    """A family's baseline and dual-screen builds carrying one package id."""
    standard = app("shared.pkg", "bboi", family="app:x")
    dual = replace(
        app(
            "shared.pkg",
            "bboi",
            family="app:x",
            eligibility=frozenset({Variant.DUAL}),
        ),
        origin="bboi-dual-asset",
    )
    return standard, dual


def test_denied_shared_package_removes_a_family_with_no_other_build() -> None:
    result = compose(
        list(shared_package_builds()),
        [{"id": "shared.pkg", "reason": "broken"}],
        [],
    )
    assert result.apps == {Variant.SINGLE: [], Variant.DUAL: []}
    assert sorted(
        (item.package_id, item.variant.value) for item in result.report.removals
    ) == [("shared.pkg", "dual"), ("shared.pkg", "dual"), ("shared.pkg", "single")]
    assert result.report.stale_exclusions == []


def test_denied_shared_package_leaves_the_family_s_other_package_selected() -> None:
    other = app("other.pkg", "rjny", family="app:x")
    result = compose(
        [*shared_package_builds(), other],
        [{"id": "shared.pkg", "reason": "broken"}],
        [],
    )
    assert ids(result, Variant.SINGLE) == ids(result, Variant.DUAL) == {"other.pkg"}


def test_dual_pin_keeps_a_standard_build_over_its_shared_package_dual_build() -> None:
    standard, dual = shared_package_builds()
    policy = pin_policy(standard, "app:x", Variant.DUAL, dual)
    result = compose([standard, dual], [], [], policy=policy)
    assert [
        (item.variant, item.origin, item.reason) for item in result.report.selections
    ] == [
        (Variant.SINGLE, "bboi-standard-asset", "source"),
        (Variant.DUAL, "bboi-standard-asset", "pin"),
    ]


def test_winning_rank_tie_fails_but_losing_tier_tie_does_not() -> None:
    tied = [app("one", "rjny", family="app:x"), app("two", "rjny", family="app:x")]
    with pytest.raises(CompositionError, match="ambiguous"):
        compose(tied, [], [])
    winner = app("winner", "extras", family="app:x")
    assert ids(compose([*reversed(tied), winner], [], []), Variant.SINGLE) == {"winner"}


def test_input_order_does_not_change_selection_or_report_order() -> None:
    candidates = [
        app("low", "bboi", family="app:x"),
        app("high", "rjny", family="app:x"),
    ]
    left = compose(candidates, [], [])
    right = compose(list(reversed(candidates)), [], [])
    assert left.apps == right.apps
    assert left.report == right.report


def test_compose_rejects_differing_records_with_one_original_identity() -> None:
    first = app("same")
    with pytest.raises(CompositionError, match="ambiguous original candidate identity"):
        compose([first, replace(first, name="different")], [], [])


def test_cross_package_family_coverage_passes_and_package_collision_fails() -> None:
    single = app("single", family="app:x", eligibility=frozenset({Variant.SINGLE}))
    dual = app(
        "dual",
        "bboi",
        family="app:x",
        eligibility=frozenset({Variant.DUAL}),
    )
    assert ids(compose([single, dual], [], []), Variant.DUAL) == {"dual"}
    collision = app("single", "bboi", family="app:y")
    with pytest.raises(CompositionError, match="distinct families"):
        compose([single, collision], [], [])


def test_neither_ineligibility_nor_a_denied_only_dual_build_waives_coverage() -> None:
    single = app("single", family="app:x", eligibility=frozenset({Variant.SINGLE}))
    with pytest.raises(CompositionError, match="missing app family"):
        compose([single], [], [])
    dual = app(
        "dual",
        "bboi",
        family="app:x",
        eligibility=frozenset({Variant.DUAL}),
    )
    assert ids(compose([single, dual], [], []), Variant.DUAL) == {"dual"}
    with pytest.raises(CompositionError, match="missing app family.*app:x"):
        compose([single, dual], [{"id": "dual", "reason": "unsupported"}], [])


def test_one_overlay_record_patches_its_pair_in_both_variants() -> None:
    first = app(
        "same",
        family="app:first",
        url="https://github.com/Owner/One/",
        additional_settings={"remove": "was set", "keep": 0},
    )
    second = app("other", family="app:second", url="https://github.com/Owner/Two")
    patches = overlays(
        (
            "same",
            "https://github.com/OWNER/one",
            {"name": "patched", "additionalSettings": {"remove": None, "keep": 1}},
        )
    )
    result = compose([first, second], [], patches)
    for variant in Variant:
        by_id = {item.id: item for item in result.apps[variant]}
        assert by_id["same"].data["name"] == "patched"
        assert by_id["same"].data["additionalSettings"] == {"keep": 1}
        assert by_id["same"].family == "app:first"
        assert by_id["other"].data["name"] == "rjny other"


def test_overlay_selector_matching_only_dual_applies_only_there() -> None:
    single = app("single", family="app:x", eligibility=frozenset({Variant.SINGLE}))
    dual = app(
        "dual",
        "bboi",
        family="app:x",
        eligibility=frozenset({Variant.DUAL}),
    )
    result = compose(
        [single, dual], [], overlays((dual.id, dual.url, {"name": "patched"}))
    )
    assert [item.data["name"] for item in result.apps[Variant.DUAL]] == ["patched"]
    assert [item.data["name"] for item in result.apps[Variant.SINGLE]] == [
        "rjny single"
    ]


def test_overlay_selector_url_distinguishes_a_shared_package_id() -> None:
    single_only = app(
        "shared.pkg",
        "extras",
        family="app:shared",
        eligibility=frozenset({Variant.SINGLE}),
        url="https://github.com/Owner/A",
    )
    dual_only = app(
        "shared.pkg",
        "bboi",
        family="app:shared",
        eligibility=frozenset({Variant.DUAL}),
        url="https://github.com/Owner/B",
    )
    patches = overlays((single_only.id, single_only.url, {"name": "patched"}))
    result = compose([single_only, dual_only], [], patches)
    [single_entry] = result.apps[Variant.SINGLE]
    [dual_entry] = result.apps[Variant.DUAL]
    assert single_entry.data["name"] == "patched"
    assert dual_entry.data["name"] != "patched"


def test_overlay_for_a_replaced_fork_s_old_url_fails_as_stale() -> None:
    current = app("pkg", family="app:x", url="https://github.com/Owner/New")
    patches = overlays(("pkg", "https://github.com/Owner/Old", {"name": "stale"}))
    with pytest.raises(CompositionError, match="no selected target"):
        compose([current], [], patches)


def test_denial_removing_an_overlay_s_only_target_fails_as_stale() -> None:
    target = app("denied", family="app:x")
    other = app("other", "bboi", family="app:x")
    report = CompositionReport()
    with pytest.raises(CompositionError, match="no selected target"):
        compose(
            [target, other],
            [{"id": "denied", "reason": "broken"}],
            overlays((target.id, target.url, {"name": "patched"})),
            report=report,
        )
    assert [(item.package_id, item.variant) for item in report.removals] == [
        ("denied", Variant.SINGLE),
        ("denied", Variant.DUAL),
    ]


def test_stale_losing_overlay_fails_after_selection_diagnostics_survive() -> None:
    winner = app("winner", "extras", family="app:x")
    loser = app("loser", "rjny", family="app:x")
    report = CompositionReport()
    with pytest.raises(CompositionError, match="no selected target"):
        compose(
            [winner, loser],
            [],
            overlays((loser.id, loser.url, {"name": "stale"})),
            report=report,
        )
    assert [item.original_id for item in report.selections[0].considered] == ["loser"]


@pytest.mark.parametrize("document", [{}, {"x": {"name": "old"}}])
def test_legacy_overlay_objects_fail_actionably(document: object) -> None:
    with pytest.raises(CompositionError, match=r"array.*legacy"):
        compose([], [], document)


def test_duplicate_overlay_selector_and_nonobject_patch_fail() -> None:
    candidate = app("x")
    record = {"id": candidate.id, "url": candidate.url, "patch": {}}
    with pytest.raises(CompositionError, match="duplicate selector"):
        compose([candidate], [], [record, record])
    with pytest.raises(CompositionError, match=r"patch must be an object"):
        compose([candidate], [], [{**record, "patch": None}])


@pytest.mark.parametrize("value", [None, "assigned"], ids=["deleted", "assigned"])
@pytest.mark.parametrize(
    "field",
    [
        "id",
        "url",
        "overrideSource",
        "family",
        "origin",
        "eligibility",
        "dualPreferred",
        "dualScreen",
    ],
)
def test_overlay_rejects_assigning_or_deleting_identity_and_composition_fields(
    field: str, value: object
) -> None:
    candidate = app("x")
    with pytest.raises(CompositionError, match=r"protected field") as raised:
        compose(
            [candidate], [], overlays((candidate.id, candidate.url, {field: value}))
        )
    message = str(raised.value)
    assert repr(rendered_key(candidate.id, candidate.url)) in message
    assert message.endswith(f"protected field {field}")


def test_selection_report_preserves_corrected_identity_and_origin() -> None:
    winner = app("effective", "extras", family="app:x", original_id="original")
    loser = app("other", "rjny", family="app:x", name="different")
    selection = compose([winner, loser], [], []).report.selections[0]
    assert (
        selection.original_id,
        selection.effective_id,
        selection.origin,
        selection.reason,
    ) == ("original", "effective", "extras", "source")
    assert selection.considered == (
        ConsideredCandidate("rjny", "rjny-catalog", "other", loser.url),
    )


def test_selection_reasons_name_pin_preference_fallback_and_source() -> None:
    ordinary = app("ordinary", "extras", family="app:preferred")
    preferred = app(
        "preferred",
        "bboi",
        family="app:preferred",
        eligibility=frozenset({Variant.DUAL}),
    )
    fallback = app("fallback", family="app:fallback")
    reasons = {
        (item.family, item.variant): item.reason
        for item in compose([ordinary, preferred, fallback], [], []).report.selections
    }
    assert reasons == {
        ("app:preferred", Variant.SINGLE): "source",
        ("app:preferred", Variant.DUAL): "dual-preferred",
        ("app:fallback", Variant.SINGLE): "source",
        ("app:fallback", Variant.DUAL): "ordinary-fallback",
    }
    high = app("high", "extras", family="app:pinned")
    pinned = app("pinned", "bboi", family="app:pinned")
    policy = pin_policy(pinned, "app:pinned", Variant.DUAL, high)
    assert {
        item.variant: item.reason
        for item in compose([high, pinned], [], [], policy=policy).report.selections
    } == {Variant.SINGLE: "source", Variant.DUAL: "pin"}


def test_dual_falls_back_to_source_precedence_among_several_baseline_builds() -> None:
    builds = [
        app(f"{source}.pkg", source, family="app:x")
        for source in ("bboi", "rjny", "extras")
    ]
    selections = compose(builds, [], []).report.selections
    assert [
        (
            item.variant,
            item.effective_id,
            item.reason,
            [candidate.source for candidate in item.considered],
        )
        for item in selections
    ] == [
        (Variant.SINGLE, "extras.pkg", "source", ["bboi", "rjny"]),
        (Variant.DUAL, "extras.pkg", "ordinary-fallback", ["bboi", "rjny"]),
    ]


def test_considered_lists_only_other_available_candidates() -> None:
    winner = app("winner", "extras", family="app:x")
    loser = app("loser", "rjny", family="app:x")
    denied = app("denied", "bboi", family="app:x")
    single_only = app(
        "single.only",
        "codm2000",
        family="app:x",
        eligibility=frozenset({Variant.SINGLE}),
    )
    result = compose(
        [winner, loser, denied, single_only],
        [{"id": "denied", "reason": "broken"}],
        [],
    )
    considered = {
        item.variant: [candidate.original_id for candidate in item.considered]
        for item in result.report.selections
    }
    assert considered == {
        Variant.SINGLE: ["single.only", "loser"],
        Variant.DUAL: ["loser"],
    }
