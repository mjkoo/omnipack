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
from omnipack.urls import normalize_project_url


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
    [dual_selection] = [
        item for item in result.report.selections if item.variant is Variant.DUAL
    ]
    assert dual_selection.effective_id == "dual"
    assert dual_selection.considered == (
        ConsideredCandidate("extras", "extras", "ordinary", ordinary.url),
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
            {"id": "x", "unexpected": True, "reason": "x"},
            r"denylist\[0\] has unknown field 'unexpected'",
        ),
    ],
)
def test_denylist_entries_hold_exactly_a_package_id_and_reason(
    entry: dict[str, str], message: str
) -> None:
    with pytest.raises(CompositionError, match=message):
        compose([], [entry], [])


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


@pytest.mark.parametrize(
    "outcome",
    ["all-carriers", "different-package-fallback", "empty-family"],
)
def test_package_denial_outcomes(outcome: str) -> None:
    denials = [{"id": "shared.pkg", "reason": "broken"}]
    if outcome == "all-carriers":
        carriers = [
            app("shared.pkg", source, family="app:x")
            for source in ("extras", "rjny", "bboi")
        ]
        candidates = [*carriers, app("other.pkg", "bboi", family="app:x")]
        denials.append({"id": "old.package", "reason": "obsolete"})
        expected_ids = {"other.pkg"}
        expected_removals = 2 * len(carriers)
        expected_stale = [StaleExclusion("old.package", "obsolete")]
    elif outcome == "different-package-fallback":
        candidates = [
            app("standard", "extras", family="app:x"),
            app(
                "shared.pkg",
                "bboi",
                family="app:x",
                eligibility=frozenset({Variant.DUAL}),
            ),
        ]
        expected_ids = {"standard"}
        expected_removals = 1
        expected_stale = []
    else:
        candidates = list(shared_package_builds())
        expected_ids = set()
        expected_removals = 3
        expected_stale = []

    result = compose(candidates, denials, [])

    assert ids(result, Variant.SINGLE) == ids(result, Variant.DUAL) == expected_ids
    assert len(result.report.removals) == expected_removals
    assert {item.package_id for item in result.report.removals} == {"shared.pkg"}
    assert result.report.stale_exclusions == expected_stale
    if outcome == "empty-family":
        assert sorted(
            (item.package_id, item.variant.value) for item in result.report.removals
        ) == [
            ("shared.pkg", "dual"),
            ("shared.pkg", "dual"),
            ("shared.pkg", "single"),
        ]


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


def test_shared_package_builds_split_by_kind_without_a_pin() -> None:
    standard, dual = shared_package_builds()
    selections = compose([standard, dual], [], []).report.selections
    assert [(item.variant, item.origin, item.reason) for item in selections] == [
        (Variant.SINGLE, "bboi-standard-asset", "source"),
        (Variant.DUAL, "bboi-dual-asset", "dual-preferred"),
    ]
    assert selections[1].considered == (
        ConsideredCandidate("bboi", "bboi-standard-asset", "shared.pkg", standard.url),
    )


def test_winning_rank_tie_fails_but_losing_tier_tie_does_not() -> None:
    tied = [app("one", "rjny", family="app:x"), app("two", "rjny", family="app:x")]
    with pytest.raises(CompositionError, match="ambiguous"):
        compose(tied, [], [])
    winner = app("winner", "extras", family="app:x")
    assert ids(compose([*reversed(tied), winner], [], []), Variant.SINGLE) == {"winner"}


def test_rjny_outranks_bboi_and_the_winner_keeps_its_whole_entry() -> None:
    entries = [
        app("shared.pkg", "bboi", family="app:x", name="bboi build"),
        app("shared.pkg", "rjny", family="app:x", name="rjny build"),
    ]
    result = compose(entries, [], [])
    for variant in Variant:
        selected = result.apps[variant]
        assert [(item.data["name"], item.url) for item in selected] == [
            ("rjny build", "https://example.com/rjny/shared.pkg")
        ]
    assert [
        (item.variant, item.source, [c.source for c in item.considered])
        for item in result.report.selections
    ] == [
        (Variant.SINGLE, "rjny", ["bboi"]),
        (Variant.DUAL, "rjny", ["bboi"]),
    ]


def test_input_order_does_not_change_selection_or_report_order() -> None:
    candidates = [
        app("low", "bboi", family="app:x"),
        app("high", "rjny", family="app:x"),
    ]
    left = compose(candidates, [], [])
    right = compose(list(reversed(candidates)), [], [])
    assert left.apps == right.apps
    assert left.report == right.report


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


def test_nonarray_overlay_error_identifies_the_overlay() -> None:
    with pytest.raises(
        CompositionError,
        match=r"^overlay must be an array of id-and-URL patch records$",
    ):
        compose([], [], {"not": "an array"})


def test_duplicate_overlay_selector_and_nonobject_patch_fail() -> None:
    candidate = app("x")
    record = {"id": candidate.id, "url": candidate.url, "patch": {}}
    selector = repr(rendered_key(candidate.id, candidate.url))
    with pytest.raises(CompositionError) as duplicate:
        compose([candidate], [], [record, record])
    assert str(duplicate.value) == f"overlay[1] has duplicate selector {selector}"
    with pytest.raises(CompositionError) as null_patch:
        compose([candidate], [], [{**record, "patch": None}])
    assert str(null_patch.value) == (
        f"overlay[0].patch must be an object (id {candidate.id!r}, "
        f"url {normalize_project_url(candidate.url)!r})"
    )


@pytest.mark.parametrize("value", [None, "assigned"], ids=["deleted", "assigned"])
@pytest.mark.parametrize(
    "field",
    [
        "id",
        "url",
        "overrideSource",
        "family",
        "packageId",
        "variant",
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


def test_overlay_patches_unmodeled_origin() -> None:
    candidate = app("x")
    result = compose(
        [candidate],
        [],
        overlays((candidate.id, candidate.url, {"origin": "overlay-value"})),
    )
    for variant in Variant:
        [rendered] = result.apps[variant]
        assert rendered.data["origin"] == "overlay-value"


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


def test_similar_forks_without_a_family_rule_stay_separate_families() -> None:
    upstream = app("org.a.dolphin", url="https://github.com/a/dolphin", name="Dolphin")
    fork = app("org.b.dolphin", url="https://github.com/b/dolphin", name="Dolphin MMJR")
    result = compose(
        [replace(upstream, family=None), replace(fork, family=None)], [], []
    )
    for variant in Variant:
        assert {(item.family, item.id) for item in result.apps[variant]} == {
            ("package:org.a.dolphin", "org.a.dolphin"),
            ("package:org.b.dolphin", "org.b.dolphin"),
        }


def test_denials_and_package_collisions_see_the_corrected_package_id() -> None:
    corrected = app("original", "extras")
    policy = CompositionPolicy(
        (
            CandidateRule(
                candidate_selector(corrected),
                "test",
                family="app:x",
                package_id="taken.pkg",
            ),
        ),
        (),
        {rendered_key("taken.pkg", corrected.url): "app:x"},
        {},
    )
    denied = compose(
        [corrected],
        [
            {"id": "taken.pkg", "reason": "broken"},
            {"id": "original", "reason": "names the original id"},
        ],
        [],
        policy=policy,
    )
    assert denied.apps == {Variant.SINGLE: [], Variant.DUAL: []}
    assert {(item.package_id, item.family) for item in denied.report.removals} == {
        ("taken.pkg", "app:x")
    }
    assert denied.report.stale_exclusions == [
        StaleExclusion("original", "names the original id")
    ]
    other = app("taken.pkg", "rjny")
    with pytest.raises(
        CompositionError, match="selects package id 'taken.pkg' for distinct families"
    ):
        compose([corrected, other], [], [], policy=policy)


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


def test_pin_reason_is_reported_when_pin_selects_among_baseline_builds() -> None:
    builds = [
        app(f"{source}.pkg", source, family="app:x")
        for source in ("bboi", "rjny", "extras")
    ]
    pinned = builds[0]
    result = compose(
        builds,
        [],
        [],
        policy=pin_policy(pinned, "app:x", Variant.DUAL, *builds[1:]),
    )

    selection = next(
        item for item in result.report.selections if item.variant is Variant.DUAL
    )
    assert selection.effective_id == "bboi.pkg"
    assert selection.reason == "pin"


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


def test_track_only_rule_fails_before_a_pin_selects() -> None:
    tracker = app("tracker", additional_settings={"trackOnly": True})
    ordinary = app("ordinary", "extras")
    policy = pin_policy(ordinary, "app:shared", Variant.DUAL, tracker)
    with pytest.raises(CompositionError, match="track-only.*rjny.*tracker"):
        compose([ordinary, tracker], [], [], policy=policy)


def test_denial_cannot_hide_track_only_rule() -> None:
    tracker = app(
        "tracker", family="app:shared", additional_settings={"trackOnly": True}
    )
    with pytest.raises(CompositionError, match="track-only.*rjny.*tracker"):
        compose([tracker], [{"id": "tracker", "reason": "hidden"}], [])


@pytest.mark.parametrize(
    "pinned, denials",
    [(["dual"], []), ([], [{"id": "tracker", "reason": "hidden"}])],
    ids=["pin", "denial"],
)
def test_corrected_id_cannot_take_track_only_id_before_selection(
    pinned: list[str], denials: list[dict[str, str]]
) -> None:
    ordinary = app("ordinary", "extras")
    tracker = app("tracker", additional_settings={"trackOnly": True})
    match = {
        "source": "extras",
        "origin": "extras",
        "id": ordinary.id,
        "url": ordinary.url,
    }
    policy = parse_composition_policy(
        {
            "schemaVersion": 1,
            "candidates": [
                {
                    "match": match,
                    "family": "app:shared",
                    "packageId": "tracker",
                    "rationale": "Take the tracker's id.",
                }
            ],
            "pins": [
                {
                    "family": "app:shared",
                    "variant": variant,
                    "match": match,
                    "rationale": "Prefer the corrected build.",
                }
                for variant in pinned
            ],
        }
    )
    with pytest.raises(CompositionError, match="reserved track-only.*extras.*ordinary"):
        compose([ordinary, tracker], denials, [], policy=policy)


def test_denial_cannot_hide_ordinary_collision_with_track_only_id() -> None:
    tracker = app("tracker", additional_settings={"trackOnly": True})
    ordinary = app("tracker", "extras")
    with pytest.raises(CompositionError, match="reserved track-only.*extras"):
        compose([ordinary, tracker], [{"id": "tracker", "reason": "hidden"}], [])


def test_overlay_unknown_field_identifies_record_and_field() -> None:
    candidate = app("app.id")
    record = {"id": candidate.id, "url": candidate.url, "patch": {}, "unexpected": True}
    with pytest.raises(CompositionError) as error:
        compose([candidate], [], [record])
    assert str(error.value) == (
        "overlay[0] has unknown field 'unexpected' "
        f"(id 'app.id', url {normalize_project_url(candidate.url)!r})"
    )


@pytest.mark.parametrize("field", ["id", "url"])
@pytest.mark.parametrize("value", ["", "  ", 731, None])
def test_overlay_blank_or_nonstring_key_identifies_field_without_value(
    field: str, value: object
) -> None:
    candidate = app("app.id")
    record = {"id": candidate.id, "url": candidate.url, "patch": {}, field: value}
    with pytest.raises(CompositionError) as error:
        compose([candidate], [], [record])
    expected = "string" if field == "id" else "project URL"
    # The other selector component is still usable, so the error names it.
    context = (
        f"(url {normalize_project_url(candidate.url)!r})"
        if field == "id"
        else "(id 'app.id')"
    )
    assert (
        str(error.value)
        == f"overlay[0].{field} must be a nonempty {expected} {context}"
    )


def test_overlay_hostless_url_identifies_record_field_and_value() -> None:
    candidate = app("app.id")
    with pytest.raises(CompositionError) as error:
        compose(
            [candidate], [], [{"id": candidate.id, "url": "/owner/repo", "patch": {}}]
        )
    assert str(error.value) == (
        "overlay[0].url is not a project URL: '/owner/repo' (id 'app.id')"
    )


@pytest.mark.parametrize(
    ("record", "message"),
    [
        ("not a record", "overlay[0] must be an object"),
        (
            {"id": 731, "url": "/owner/repo", "patch": {}},
            "overlay[0].id must be a nonempty string",
        ),
        (
            {"id": "line\nbreak", "url": " ", "patch": {}},
            "overlay[0].url must be a nonempty project URL (id 'line\\nbreak')",
        ),
    ],
    ids=["non-object", "no-usable-selector", "multiline-id"],
)
def test_overlay_error_context_is_limited_to_usable_selector_parts(
    record: object, message: str
) -> None:
    with pytest.raises(CompositionError) as error:
        compose([app("x")], [], [record])
    assert str(error.value) == message
