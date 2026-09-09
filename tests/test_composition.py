from __future__ import annotations

from dataclasses import replace

import pytest

from omnipack.composition_policy import (
    CandidateRule,
    CandidateSelector,
    CompositionPolicy,
    Pin,
    Projection,
    parse_composition_policy,
    rendered_key,
)
from omnipack.merge import (
    CompositionError,
    CompositionReport,
    CompositionResult,
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
    dual_preferred: bool = False,
    url: str | None = None,
    name: str | None = None,
    original_id: str | None = None,
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
        Variant.SINGLE,
        Provenance(source, url),
        eligibility=eligibility,
        dual_preferred=dual_preferred,
        origin=origins[source],
        original_id=original_id or package_id,
        family=family or f"package:{package_id}",
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
    def selector(item: App) -> CandidateSelector:
        return CandidateSelector(
            item.provenance.source,
            item.origin or item.provenance.source,
            item.original_id or item.id,
            rendered_key(item.id, item.url)[1],
        )

    pinned_selector = selector(candidate)
    candidates = (candidate, *alternatives)
    projections = {
        rendered_key(item.id, item.url): Projection(family, None) for item in candidates
    }
    rules = tuple(
        CandidateRule(selector(item), "test", family=family) for item in candidates
    )
    key = rendered_key(candidate.id, candidate.url)
    return CompositionPolicy(
        rules,
        (Pin(family, variant, pinned_selector, "test"),),
        {},
        projections,
        {(family, variant): key},
    )


def ids(result: CompositionResult, variant: Variant) -> set[str]:
    return {item.id for item in result.apps[variant]}


def compose(
    candidates: list[App],
    denylist: list[dict[str, str]],
    common_overlay: object,
    dual_overlay: object,
    *,
    policy: CompositionPolicy | None = None,
    report: CompositionReport | None = None,
) -> CompositionResult:
    if policy is None:
        rules: list[CandidateRule] = []
        projections: dict[tuple[str, str], Projection] = {}
        for candidate in candidates:
            family = candidate.family or f"package:{candidate.id}"
            if family.startswith("app:"):
                selector = CandidateSelector(
                    candidate.provenance.source,
                    candidate.origin or candidate.provenance.source,
                    candidate.original_id or candidate.id,
                    rendered_key(candidate.id, candidate.url)[1],
                )
                rules.append(CandidateRule(selector, "test", family=family))
                projections[rendered_key(candidate.id, candidate.url)] = Projection(
                    family, None
                )
        policy = CompositionPolicy(tuple(rules), (), {}, projections, {})
    return compose_apps(
        candidates,
        denylist,
        common_overlay,
        dual_overlay,
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
        dual_preferred=True,
    )
    result = compose([ordinary, preferred], [], [], [])
    assert ids(result, Variant.SINGLE) == {"ordinary"}
    assert ids(result, Variant.DUAL) == {"dual"}
    assert [item.reason for item in result.report.selections] == [
        "source",
        "dual-preferred",
    ]


def test_pin_wins_and_denied_or_ineligible_pin_fails() -> None:
    high = app("high", "extras", family="app:shared")
    pinned = app("pinned", "bboi", family="app:shared")
    policy = pin_policy(pinned, "app:shared", Variant.DUAL, high)
    assert ids(compose([high, pinned], [], [], [], policy=policy), Variant.DUAL) == {
        "pinned"
    }
    with pytest.raises(CompositionError, match=r"pin.*denied"):
        compose(
            [high, pinned],
            [{"id": "pinned", "variant": "dual", "reason": "bad"}],
            [],
            [],
            policy=policy,
        )
    with pytest.raises(CompositionError, match=r"pin.*ineligible"):
        compose(
            [high, replace(pinned, eligibility=frozenset({Variant.SINGLE}))],
            [],
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
    result = compose([high, pinned], [], [], [], policy=policy)
    assert result.apps[Variant.DUAL][0].provenance.source == "bboi"


def test_family_denial_cannot_hide_missing_pin() -> None:
    missing = app("missing", family="app:gone")
    policy = pin_policy(missing, "app:gone", Variant.DUAL)
    with pytest.raises(CompositionError, match=r"selector.*missing"):
        compose([], [{"family": "app:gone", "reason": "gone"}], [], [], policy=policy)


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
                {"id": "removed", "variant": "dual", "reason": "unsupported"},
                {"id": "retired", "reason": "obsolete"},
            ],
            [],
            [],
            policy=policy,
            report=report,
        )
    assert [
        (item.package_id, item.variant, item.reason) for item in report.removals
    ] == [("removed", Variant.DUAL, "unsupported")]
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
            {"family": "app:old", "variant": "dual", "reason": "obsolete"},
        ],
        [],
        [],
    )
    assert ids(result, Variant.SINGLE) == {"other"}
    assert ids(result, Variant.DUAL) == {"other"}
    assert result.report.stale_exclusions[0].family == "app:old"
    assert result.report.selections[0].alternatives[0].excluded_reason == "broken"


@pytest.mark.parametrize(
    "entry",
    [
        {"reason": "x"},
        {"id": "x", "family": "app:x", "reason": "x"},
        {"id": None, "family": "app:x", "reason": "x"},
    ],
)
def test_exclusion_requires_exactly_one_selector(entry: dict[str, str]) -> None:
    with pytest.raises(CompositionError, match="exactly one"):
        compose([], [entry], [], [])


def test_winning_rank_tie_fails_but_losing_tier_tie_does_not() -> None:
    tied = [app("one", "rjny", family="app:x"), app("two", "rjny", family="app:x")]
    with pytest.raises(CompositionError, match="ambiguous"):
        compose(tied, [], [], [])
    winner = app("winner", "extras", family="app:x")
    assert ids(compose([*reversed(tied), winner], [], [], []), Variant.SINGLE) == {
        "winner"
    }


def test_input_order_does_not_change_selection_or_report_order() -> None:
    candidates = [
        app("low", "bboi", family="app:x"),
        app("high", "rjny", family="app:x"),
    ]
    left = compose(candidates, [], [], [])
    right = compose(list(reversed(candidates)), [], [], [])
    assert left.apps == right.apps
    assert left.report == right.report


def test_compose_rejects_differing_records_with_one_original_identity() -> None:
    first = app("same")
    with pytest.raises(CompositionError, match="ambiguous original candidate identity"):
        compose([first, replace(first, name="different")], [], [], [])


def test_cross_package_family_coverage_passes_and_package_collision_fails() -> None:
    single = app("single", family="app:x", eligibility=frozenset({Variant.SINGLE}))
    dual = app(
        "dual",
        "bboi",
        family="app:x",
        eligibility=frozenset({Variant.DUAL}),
        dual_preferred=True,
    )
    assert ids(compose([single, dual], [], [], []), Variant.DUAL) == {"dual"}
    collision = app("single", "bboi", family="app:y")
    with pytest.raises(CompositionError, match="distinct families"):
        compose(
            [single, collision],
            [{"family": "app:x", "variant": "dual", "reason": "no dual"}],
            [],
            [],
        )


def test_ineligibility_does_not_waive_coverage_but_exact_dual_denial_does() -> None:
    single = app("single", eligibility=frozenset({Variant.SINGLE}))
    with pytest.raises(CompositionError, match="missing app family"):
        compose([single], [], [], [])
    result = compose(
        [single], [{"id": "single", "variant": "dual", "reason": "unsupported"}], [], []
    )
    assert ids(result, Variant.SINGLE) == {"single"}


def test_overlays_bind_to_id_and_normalized_url_and_layer_common_then_dual() -> None:
    first = app("same", family="app:first", url="https://github.com/Owner/One/")
    second = app("other", family="app:second", url="https://github.com/Owner/Two")
    common = overlays(
        (
            "same",
            "https://github.com/owner/one",
            {"name": "common", "additionalSettings": {"remove": None, "keep": 1}},
        )
    )
    dual = overlays(("same", "https://github.com/OWNER/ONE", {"name": "dual"}))
    result = compose([first, second], [], common, dual)
    single = next(item for item in result.apps[Variant.SINGLE] if item.id == "same")
    dual_app = next(item for item in result.apps[Variant.DUAL] if item.id == "same")
    assert single.data["name"] == "common"
    assert dual_app.data["name"] == "dual"
    assert dual_app.family == "app:first"


def test_stale_losing_overlay_fails_after_selection_diagnostics_survive() -> None:
    winner = app("winner", "extras", family="app:x")
    loser = app("loser", "rjny", family="app:x")
    report = CompositionReport()
    with pytest.raises(CompositionError, match="no selected target"):
        compose(
            [winner, loser],
            [],
            overlays((loser.id, loser.url, {"name": "stale"})),
            [],
            report=report,
        )
    assert report.selections
    assert report.displacements


@pytest.mark.parametrize("document", [{}, {"x": {"name": "old"}}])
def test_legacy_overlay_objects_fail_actionably(document: object) -> None:
    with pytest.raises(CompositionError, match=r"array.*legacy"):
        compose([], [], document, [])


def test_duplicate_overlay_selector_and_nonobject_patch_fail() -> None:
    candidate = app("x")
    record = {"id": candidate.id, "url": candidate.url, "patch": {}}
    with pytest.raises(CompositionError, match="duplicate selector"):
        compose([candidate], [], [record, record], [])
    with pytest.raises(CompositionError, match=r"patch must be an object"):
        compose([candidate], [], [{**record, "patch": None}], [])


@pytest.mark.parametrize(
    "field",
    ["id", "url", "overrideSource", "family", "origin", "eligibility", "dualPreferred"],
)
def test_overlay_rejects_identity_and_composition_fields_even_when_null(
    field: str,
) -> None:
    candidate = app("x")
    with pytest.raises(CompositionError, match=r"protected field"):
        compose(
            [candidate], [], overlays((candidate.id, candidate.url, {field: None})), []
        )


def test_selection_report_preserves_corrected_identity_origin_and_differences() -> None:
    winner = app("effective", "extras", family="app:x", original_id="original")
    loser = app("other", "rjny", family="app:x", name="different")
    report = compose([winner, loser], [], [], []).report
    selection = report.selections[0]
    assert (selection.original_id, selection.effective_id, selection.origin) == (
        "original",
        "effective",
        "extras",
    )
    assert selection.alternatives[0].effective_id == "other"
    assert {"id", "name", "url"}.issubset(selection.alternatives[0].differing_fields)
    assert selection.reason == "source"
    assert selection.alternatives[0].loss_reason == "lower-source-precedence"


def test_selection_report_includes_target_ineligible_alternatives() -> None:
    winner = app("winner", family="app:x")
    ineligible = app(
        "single",
        "bboi",
        family="app:x",
        eligibility=frozenset({Variant.SINGLE}),
    )
    selection = next(
        item
        for item in compose([winner, ineligible], [], [], []).report.selections
        if item.variant is Variant.DUAL
    )
    assert selection.reason == "ordinary-fallback"
    assert selection.alternatives[0].effective_id == "single"
    assert selection.alternatives[0].loss_reason == "ineligible"
