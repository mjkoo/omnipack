from __future__ import annotations

import json
from dataclasses import replace
from itertools import permutations

import pytest

from omnipack.composition_policy import (
    CandidateRule,
    CompositionPolicy,
    CompositionPolicyError,
    Pin,
    build_policy,
    candidate_selector,
    parse_composition_policy,
)
from omnipack.merge import (
    CompositionError,
    CompositionReport,
    CompositionResult,
    ConsideredCandidate,
    Removal,
    RepeatedEntry,
    RepeatedId,
    SameRankTie,
    SingleOnlyFamily,
    StaleExclusion,
    UncategorizedFamily,
)
from omnipack.merge import (
    compose as compose_apps,
)
from omnipack.model import App, Category, Provenance, SourceType, Variant
from omnipack.render import render_pack
from omnipack.urls import normalize_project_url

SINGLE_ONLY = frozenset({Variant.SINGLE})
DUAL_ONLY = frozenset({Variant.DUAL})


def app(
    package_id: str,
    source: str = "rjny",
    *,
    family: str | None = None,
    eligibility: frozenset[Variant] = frozenset(Variant),
    url: str | None = None,
    name: str | None = None,
    origin: str | None = None,
    additional_settings: dict[str, object] | None = None,
    categories: tuple[str, ...] = (),
) -> App:
    """A candidate; `family`, when given, is the `app:` family a rule assigns it."""
    url = url or f"https://example.com/{source}/{package_id}"
    origins = {
        "rjny": "rjny-catalog",
        "bboi": "bboi-standard-asset",
        "extras": "extras",
        "codm2000": "codm-generated",
        "quiver": "quiver-generated",
    }
    return App(
        package_id,
        url,
        name or f"{source} {package_id}",
        SourceType.HTML,
        categories,
        Provenance(source, url),
        eligibility=eligibility,
        origin=origin or origins[source],
        family=family,
        additional_settings=additional_settings or {},
    )


def url_family(candidate: App) -> str:
    return normalize_project_url(candidate.url)


def rules_for(candidates: tuple[App, ...] | list[App]) -> list[CandidateRule]:
    return [
        CandidateRule(candidate_selector(item), "test", family=item.family)
        for item in candidates
        if item.family is not None
    ]


def overlays(*records: tuple[str, dict[str, object]]) -> list[dict[str, object]]:
    return [{"url": url, "patch": patch} for url, patch in records]


def deny(*urls: str, reason: str = "broken") -> list[dict[str, str]]:
    return [{"url": url, "reason": reason} for url in urls]


def pin_policy(
    candidate: App,
    family: str,
    variant: Variant,
    *alternatives: App,
) -> CompositionPolicy:
    return build_policy(
        rules_for((candidate, *alternatives)),
        (Pin(family, variant, candidate_selector(candidate), "test"),),
    )


def ids(result: CompositionResult, variant: Variant) -> set[str]:
    return {item.id for item in result.apps[variant]}


def category_policy(categories: dict[str, Category]) -> CompositionPolicy:
    return build_policy((), (), categories)


def final_categories(result: CompositionResult) -> dict[tuple[str, Variant], list[str]]:
    return {
        (item.id, variant): item.data["categories"]
        for variant, values in result.apps.items()
        for item in values
    }


TRACK_ONLY: dict[str, object] = {"trackOnly": True}


def compose(
    candidates: list[App],
    denylist: list[dict[str, str]],
    overlay: object,
    *,
    policy: CompositionPolicy | None = None,
    report: CompositionReport | None = None,
) -> CompositionResult:
    return compose_apps(
        candidates,
        denylist,
        overlay,
        policy=build_policy(rules_for(candidates)) if policy is None else policy,
        report=report,
    )


def test_dual_prefers_suitable_candidate_before_higher_source() -> None:
    ordinary = app("ordinary", "extras", family="app:shared")
    preferred = app("dual", "bboi", family="app:shared", eligibility=DUAL_ONLY)
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
    assert dual_selection.id == "dual"
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
        compose([high, pinned], deny(pinned.url), [], policy=policy)
    with pytest.raises(CompositionError, match=r"pin.*ineligible"):
        compose([high, replace(pinned, eligibility=SINGLE_ONLY)], [], [], policy=policy)


def test_pin_uses_original_provenance_when_rendered_identity_is_shared() -> None:
    url = "https://example.com/project"
    high = app("shared", "extras", family="app:shared", url=url)
    pinned = app("shared", "bboi", family="app:shared", url=url)
    policy = pin_policy(pinned, "app:shared", Variant.DUAL, high)
    result = compose([high, pinned], [], [], policy=policy)
    assert [
        item.source for item in result.report.selections if item.variant is Variant.DUAL
    ] == ["bboi"]


@pytest.mark.parametrize("present", [False, True], ids=["missing", "ineligible"])
def test_pin_failure_preserves_independent_exclusion_diagnostics(present: bool) -> None:
    pinned = app("pinned", eligibility=SINGLE_ONLY)
    removed = app("removed")
    policy = parse_composition_policy(
        {
            "schemaVersion": 1,
            "candidates": [],
            "pins": [
                {
                    "family": url_family(pinned),
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
            [removed, *([pinned] if present else [])],
            [
                *deny(removed.url, reason="unsupported"),
                *deny("https://example.com/retired", reason="obsolete"),
            ],
            [],
            policy=policy,
            report=report,
        )
    assert report.removals == [
        Removal(url_family(removed), "unsupported", (url_family(removed),))
    ]
    assert report.stale_exclusions == [
        StaleExclusion("example.com/retired", "obsolete")
    ]


def test_denial_of_a_build_eligible_for_neither_pack_is_not_stale() -> None:
    unexported = app("unexported", eligibility=frozenset())
    result = compose([unexported], deny(unexported.url, reason="retired"), [])
    assert result.apps == {Variant.SINGLE: [], Variant.DUAL: []}
    assert result.report.removals == []
    assert result.report.stale_exclusions == []


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({"reason": "x"}, r"denylist\[0\]\.url must be a nonempty string"),
        ({"url": None, "reason": "x"}, r"denylist\[0\]\.url must be a nonempty string"),
        ({"url": "https://x.test/a"}, r"denylist\[0\]\.reason must be a nonempty"),
        (
            {"url": "https://x.test/a", "unexpected": True, "reason": "x"},
            r"denylist\[0\] has unknown field 'unexpected'",
        ),
        (
            {"id": "x", "url": "https://x.test/a", "reason": "x"},
            r"denylist\[0\] has unknown field 'id'",
        ),
        (
            {"url": "/owner/repo", "reason": "x"},
            r"denylist\[0\]\.url is not a project URL: '/owner/repo'",
        ),
        (
            {"url": "https://x.test/a b", "reason": "x"},
            r"denylist\[0\]\.url is not a project URL: 'https://x.test/a b'",
        ),
    ],
)
def test_denylist_entries_hold_exactly_a_url_and_reason(
    entry: dict[str, str], message: str
) -> None:
    with pytest.raises(CompositionError, match=message):
        compose([], [entry], [])


def test_denial_removes_every_candidate_at_a_differently_spelled_url() -> None:
    candidates = [
        app("one", "extras", url="https://github.com/Owner/Repo"),
        app("two", "rjny", url="https://www.github.com/owner/repo.git/"),
        app("three", "bboi", url="https://github.com/OWNER/repo/releases"),
    ]
    result = compose(
        candidates, deny("github.com/owner/REPO", "https://x.test/gone"), []
    )
    assert result.apps == {Variant.SINGLE: [], Variant.DUAL: []}
    assert result.report.removals == [
        Removal("github.com/owner/repo", "broken", ("github.com/owner/repo",))
    ]
    assert result.report.stale_exclusions == [StaleExclusion("x.test/gone", "broken")]


def test_denial_permits_an_alternative_at_another_url() -> None:
    standard = app("standard", "extras", family="app:x")
    preferred = app("preferred", "bboi", family="app:x", eligibility=DUAL_ONLY)
    result = compose([standard, preferred], deny(preferred.url), [])
    assert ids(result, Variant.DUAL) == {"standard"}
    [dual] = [item for item in result.report.selections if item.variant is Variant.DUAL]
    assert dual.reason == "ordinary-fallback"


def test_denial_of_a_dual_build_falls_back_to_a_bboi_standard_build() -> None:
    standard = app("standard", "bboi", family="app:x")
    preferred = app(
        "preferred",
        "bboi",
        family="app:x",
        eligibility=DUAL_ONLY,
        origin="bboi-dual-asset",
    )
    assert ids(compose([standard, preferred], [], []), Variant.DUAL) == {"preferred"}
    result = compose([standard, preferred], deny(preferred.url), [])
    assert ids(result, Variant.DUAL) == {"standard"}
    [dual] = [item for item in result.report.selections if item.variant is Variant.DUAL]
    assert (dual.origin, dual.reason) == ("bboi-standard-asset", "ordinary-fallback")


def test_denied_url_shared_by_both_builds_leaves_other_projects_selectable() -> None:
    url = "https://example.com/denied"
    standard = app("standard", "bboi", family="app:x", url=url)
    dual = app(
        "dual",
        "bboi",
        family="app:x",
        url=url,
        eligibility=DUAL_ONLY,
        origin="bboi-dual-asset",
    )
    other = app("other", "rjny", family="app:x")
    result = compose([standard, dual, other], deny(url), [])
    assert ids(result, Variant.SINGLE) == ids(result, Variant.DUAL) == {"other"}


def test_denial_keeps_another_repository_with_the_same_package_id() -> None:
    denied = app("shared.pkg", "rjny", url="https://example.com/denied")
    kept = app("shared.pkg", "bboi", url="https://example.com/kept")
    result = compose([denied, kept], deny(denied.url), [])
    for variant in Variant:
        assert [item.url for item in result.apps[variant]] == [kept.url]


def test_denial_is_reported_once_under_its_url_with_every_family() -> None:
    url = "https://example.com/split"
    first = app("a", family="app:a", url=url)
    second = app("b", family="app:b", url=url)
    rule_less = app("c", "bboi", url=url)
    result = compose([first, second, rule_less], deny(url), [])
    assert result.report.removals == [
        Removal("example.com/split", "broken", ("app:a", "app:b", "example.com/split"))
    ]


def shared_package_builds() -> tuple[App, App]:
    """A family's baseline and dual-screen builds carrying one package id."""
    standard = app("shared.pkg", "bboi")
    dual = app("shared.pkg", "bboi", eligibility=DUAL_ONLY, origin="bboi-dual-asset")
    return standard, dual


def test_dual_pin_keeps_a_standard_build_over_its_shared_package_dual_build() -> None:
    standard, dual = shared_package_builds()
    policy = pin_policy(standard, url_family(standard), Variant.DUAL, dual)
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


MELONDS = "https://github.com/rafaelvcaetano/melonDS-android"


def stable_and_nightly() -> list[App]:
    """Two builds one source lists at one repository URL, tied at one rank."""
    return [
        app("me.magnum.melonds", url=MELONDS, name="melonDS"),
        app("me.magnum.melonds.nightly", url=MELONDS, name="melonDS Nightly"),
    ]


def test_winning_rank_tie_publishes_the_canonically_first_and_records_it() -> None:
    family = "github.com/rafaelvcaetano/melonds-android"
    outcomes = []
    for ordered in permutations(stable_and_nightly()):
        result = compose(list(ordered), [], [])
        outcomes.append((result.apps, result.report.same_rank_ties))
    assert all(outcome == outcomes[0] for outcome in outcomes)
    apps, ties = outcomes[0]
    # The serialized records first differ at their ids, and the stable id sorts
    # before the nightly one.
    assert [item.id for item in apps[Variant.SINGLE]] == ["me.magnum.melonds"]
    stable, nightly = (candidate_selector(item) for item in stable_and_nightly())
    assert ties == [
        SameRankTie(family, Variant.SINGLE, (stable, nightly), stable),
        SameRankTie(family, Variant.DUAL, (stable, nightly), stable),
    ]
    reasons = compose(stable_and_nightly(), [], []).report.selections
    assert [(item.variant, item.reason) for item in reasons] == [
        (Variant.SINGLE, "source"),
        (Variant.DUAL, "ordinary-fallback"),
    ]


def test_a_same_rank_tie_follows_serialization_not_id_or_selector_order() -> None:
    url = "https://example.com/project"
    # The serialized records first differ inside additionalSettings, which sorts
    # before id, so the later id and later selector wins.
    first = app(
        "a.pkg", url=url, name="App", additional_settings={"apkFilterRegEx": "z"}
    )
    second = app(
        "b.pkg", url=url, name="App", additional_settings={"apkFilterRegEx": "a"}
    )
    tied = (candidate_selector(first), candidate_selector(second))
    assert tied[0].key < tied[1].key
    for ordered in permutations([first, second]):
        result = compose(list(ordered), [], [])
        assert ids(result, Variant.SINGLE) == ids(result, Variant.DUAL) == {"b.pkg"}
        assert result.report.same_rank_ties == [
            SameRankTie(url_family(first), variant, tied, tied[1])
            for variant in Variant
        ]
        assert [item.reason for item in result.report.selections] == [
            "source",
            "ordinary-fallback",
        ]


def test_a_pin_or_split_rules_resolve_a_same_rank_tie() -> None:
    stable, nightly = stable_and_nightly()
    pinned = compose(
        [stable, nightly],
        [],
        [],
        policy=build_policy(
            (),
            [
                Pin(url_family(nightly), variant, candidate_selector(nightly), "test")
                for variant in Variant
            ],
        ),
    )
    assert ids(pinned, Variant.SINGLE) == ids(pinned, Variant.DUAL) == {nightly.id}
    assert pinned.report.same_rank_ties == []

    split = compose(
        [replace(stable, family="app:melonds"), replace(nightly, family="app:nightly")],
        [],
        [],
    )
    assert ids(split, Variant.SINGLE) == {stable.id, nightly.id}
    assert split.report.same_rank_ties == []


def test_a_tie_among_nonwinning_candidates_is_not_recorded() -> None:
    tied = [app("one", "rjny", family="app:x"), app("two", "rjny", family="app:x")]
    winner = app("winner", "extras", family="app:x")
    result = compose([*reversed(tied), winner], [], [])
    assert ids(result, Variant.SINGLE) == {"winner"}
    assert result.report.same_rank_ties == []


def test_rjny_outranks_bboi_and_the_winner_keeps_its_whole_entry() -> None:
    url = "https://example.com/project"
    entries = [
        app("bboi.pkg", "bboi", name="bboi build", url=url),
        app("rjny.pkg", "rjny", name="rjny build", url=url),
    ]
    result = compose(entries, [], [])
    for variant in Variant:
        selected = result.apps[variant]
        assert [(item.data["name"], item.id, item.url) for item in selected] == [
            ("rjny build", "rjny.pkg", url)
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


def test_explicit_rules_join_repositories_and_each_keeps_its_own_id() -> None:
    single = app("single", family="app:x", eligibility=SINGLE_ONLY)
    dual = app("dual", "bboi", family="app:x", eligibility=DUAL_ONLY)
    result = compose([single, dual], [], [])
    assert ids(result, Variant.SINGLE) == {"single"}
    assert ids(result, Variant.DUAL) == {"dual"}
    assert result.report.single_only_families == []


def test_different_repositories_sharing_a_package_id_stay_separate() -> None:
    first = app("shared.pkg", "rjny", url="https://example.com/first")
    second = app("shared.pkg", "bboi", url="https://example.com/second")
    result = compose([first, second], [], [])
    for variant in Variant:
        assert sorted(item.family for item in result.apps[variant]) == [
            "example.com/first",
            "example.com/second",
        ]


def test_one_project_from_several_sources_forms_its_url_family() -> None:
    url = "https://github.com/Owner/Project"
    result = compose(
        [app("rjny.pkg", "rjny", url=url), app("bboi.pkg", "bboi", url=url + ".git")],
        [],
        [],
    )
    assert [
        (item.family, item.variant, item.id, item.considered[0].id)
        for item in result.report.selections
    ] == [
        ("github.com/owner/project", Variant.SINGLE, "rjny.pkg", "bboi.pkg"),
        ("github.com/owner/project", Variant.DUAL, "rjny.pkg", "bboi.pkg"),
    ]


def test_a_family_rule_covers_rule_less_builds_at_its_url() -> None:
    url = "https://github.com/owner/project"
    ruled = app("bboi.pkg", "bboi", family="app:x", url=url)
    quiver = app("quiver.pkg", "quiver", url=url)
    codm = app("codm.pkg", "codm2000", url=url, eligibility=DUAL_ONLY)
    result = compose(
        [ruled, quiver, codm], [], [], policy=build_policy(rules_for([ruled]))
    )
    assert {
        (item.family, item.variant, item.id) for item in result.report.selections
    } == {
        ("app:x", Variant.SINGLE, "quiver.pkg"),
        ("app:x", Variant.DUAL, "codm.pkg"),
    }


def test_two_rules_split_one_repository_and_leave_a_third_build_in_the_url_family() -> (
    None
):
    url = "https://github.com/owner/project"
    first = app("a.pkg", family="app:a", url=url)
    second = app("b.pkg", family="app:b", url=url)
    third = app("c.pkg", "bboi", url=url)
    result = compose([first, second, third], [], [])
    for variant in Variant:
        assert sorted((item.family, item.id) for item in result.apps[variant]) == [
            ("app:a", "a.pkg"),
            ("app:b", "b.pkg"),
            ("github.com/owner/project", "c.pkg"),
        ]


def test_rule_less_tracker_joins_the_family_ruled_onto_its_url() -> None:
    url = "https://github.com/owner/project"
    installable = app("app.pkg", family="app:x", url=url)
    tracker = app(
        "1234",
        "codm2000",
        url=url,
        eligibility=DUAL_ONLY,
        additional_settings=TRACK_ONLY,
    )
    result = compose([installable, tracker], [], [])
    assert ids(result, Variant.SINGLE) == {"app.pkg"}
    assert ids(result, Variant.DUAL) == {"1234"}
    assert {item.family for values in result.apps.values() for item in values} == {
        "app:x"
    }


def test_split_rules_let_a_tracker_and_an_installable_build_both_ship() -> None:
    url = "https://github.com/owner/project"
    installable = app("app.pkg", family="app:a", url=url)
    tracker = app(
        "1234",
        "codm2000",
        family="app:a-tracker",
        url=url,
        eligibility=DUAL_ONLY,
        additional_settings=TRACK_ONLY,
    )
    result = compose([installable, tracker], [], [])
    assert ids(result, Variant.SINGLE) == {"app.pkg"}
    assert ids(result, Variant.DUAL) == {"app.pkg", "1234"}


def test_owner_rules_join_an_app_and_a_tracker_at_different_urls() -> None:
    installable = app("app.pkg", family="app:x")
    tracker = app(
        "1234",
        "codm2000",
        family="app:x",
        eligibility=DUAL_ONLY,
        additional_settings=TRACK_ONLY,
    )
    result = compose([installable, tracker], [], [])
    assert ids(result, Variant.SINGLE) == {"app.pkg"}
    assert ids(result, Variant.DUAL) == {"1234"}


def test_an_app_missing_from_dual_is_published_and_reported() -> None:
    single = app("single", family="app:x", eligibility=SINGLE_ONLY)
    result = compose([single], [], [])
    assert ids(result, Variant.SINGLE) == {"single"}
    assert result.apps[Variant.DUAL] == []
    assert result.report.single_only_families == [
        SingleOnlyFamily("app:x", "single", url_family(single))
    ]


def test_a_family_with_only_a_dual_build_is_absent_from_single() -> None:
    dual = app("dual", "bboi", family="app:x", eligibility=DUAL_ONLY)
    other = app("other", "extras")
    result = compose([dual, other], [], [])
    assert {item.family for item in result.apps[Variant.SINGLE]} == {url_family(other)}
    assert {item.family for item in result.apps[Variant.DUAL]} == {
        "app:x",
        url_family(other),
    }
    assert result.report.single_only_families == []


def test_a_denied_only_dual_build_leaves_a_single_only_finding() -> None:
    single = app("single", family="app:x", eligibility=SINGLE_ONLY)
    dual = app("dual", "bboi", family="app:x", eligibility=DUAL_ONLY)
    assert compose([single, dual], [], []).report.single_only_families == []
    result = compose([single, dual], deny(dual.url), [])
    assert ids(result, Variant.SINGLE) == {"single"}
    assert result.report.single_only_families == [
        SingleOnlyFamily("app:x", "single", url_family(single))
    ]


def test_a_single_only_original_and_a_dual_only_fork_pair_only_by_rule() -> None:
    original = app("shared.pkg", "rjny", eligibility=SINGLE_ONLY)
    fork = app(
        "shared.pkg",
        "rjny",
        url="https://example.com/fork",
        eligibility=DUAL_ONLY,
    )
    apart = compose([original, fork], [], [])
    assert [item.family for item in apart.apps[Variant.SINGLE]] == [
        url_family(original)
    ]
    assert [item.family for item in apart.apps[Variant.DUAL]] == ["example.com/fork"]
    assert apart.report.single_only_families == [
        SingleOnlyFamily(url_family(original), "shared.pkg", url_family(original))
    ]

    joined = compose(
        [replace(original, family="app:x"), replace(fork, family="app:x")], [], []
    )
    assert [item.url for item in joined.apps[Variant.SINGLE]] == [original.url]
    assert [item.url for item in joined.apps[Variant.DUAL]] == [fork.url]
    assert joined.report.single_only_families == []


def test_two_url_families_sharing_a_package_id_are_reported_in_their_variant() -> None:
    first = app("shared.pkg", "rjny", url="https://example.com/first")
    second = app("shared.pkg", "bboi", url="https://example.com/second")
    result = compose([first, second], [], [])
    entries = (
        RepeatedEntry("example.com/first", "example.com/first"),
        RepeatedEntry("example.com/second", "example.com/second"),
    )
    assert result.report.repeated_ids == [
        RepeatedId(Variant.SINGLE, "shared.pkg", entries),
        RepeatedId(Variant.DUAL, "shared.pkg", entries),
    ]

    joined = compose(
        [replace(first, family="app:x"), replace(second, family="app:x")], [], []
    )
    assert ids(joined, Variant.SINGLE) == {"shared.pkg"}
    assert joined.report.repeated_ids == []


def test_a_package_id_repeated_across_variants_only_is_not_reported() -> None:
    single = app("shared.pkg", "rjny", eligibility=SINGLE_ONLY)
    dual = app("shared.pkg", "bboi", eligibility=DUAL_ONLY)
    assert compose([single, dual], [], []).report.repeated_ids == []


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


def test_overlay_record_matching_only_dual_applies_only_there() -> None:
    single = app("single", family="app:x", eligibility=SINGLE_ONLY)
    dual = app("dual", "bboi", family="app:x", eligibility=DUAL_ONLY)
    result = compose([single, dual], [], overlays((dual.url, {"name": "patched"})))
    assert [item.data["name"] for item in result.apps[Variant.DUAL]] == ["patched"]
    assert [item.data["name"] for item in result.apps[Variant.SINGLE]] == [
        "rjny single"
    ]


def test_overlay_record_names_one_repository_of_a_family() -> None:
    single_only = app(
        "shared.pkg",
        "extras",
        family="app:shared",
        eligibility=SINGLE_ONLY,
        url="https://github.com/Owner/A",
    )
    dual_only = app(
        "shared.pkg",
        "bboi",
        family="app:shared",
        eligibility=DUAL_ONLY,
        url="https://github.com/Owner/B",
    )
    patches = overlays((single_only.url, {"name": "patched"}))
    result = compose([single_only, dual_only], [], patches)
    [single_entry] = result.apps[Variant.SINGLE]
    [dual_entry] = result.apps[Variant.DUAL]
    assert single_entry.data["name"] == "patched"
    assert dual_entry.data["name"] != "patched"


def test_overlay_for_a_replaced_fork_s_old_url_fails_as_stale() -> None:
    current = app("pkg", family="app:x", url="https://github.com/Owner/New")
    patches = overlays(("https://github.com/Owner/Old", {"name": "stale"}))
    with pytest.raises(CompositionError, match="no selected target"):
        compose([current], [], patches)


def test_denial_removing_an_overlay_s_only_target_fails_as_stale() -> None:
    target = app("denied", family="app:x")
    other = app("other", "bboi", family="app:x")
    report = CompositionReport()
    with pytest.raises(CompositionError, match="no selected target"):
        compose(
            [target, other],
            deny(target.url),
            overlays((target.url, {"name": "patched"})),
            report=report,
        )
    assert report.removals == [Removal(url_family(target), "broken", ("app:x",))]


def test_stale_losing_overlay_fails_after_selection_diagnostics_survive() -> None:
    winner = app("winner", "extras", family="app:x")
    loser = app("loser", "rjny", family="app:x")
    report = CompositionReport()
    with pytest.raises(CompositionError, match="no selected target"):
        compose(
            [winner, loser],
            [],
            overlays((loser.url, {"name": "stale"})),
            report=report,
        )
    assert [item.id for item in report.selections[0].considered] == ["loser"]


def test_nonarray_overlay_error_identifies_the_overlay() -> None:
    with pytest.raises(
        CompositionError,
        match=r"^overlay must be an array of URL patch records$",
    ):
        compose([], [], {"not": "an array"})


def test_two_overlay_records_for_one_project_and_a_nonobject_patch_fail() -> None:
    candidate = app("x", url="https://github.com/Owner/Repo")
    records = [
        {"url": "https://github.com/Owner/Repo", "patch": {}},
        {"url": "github.com/owner/repo.git/", "patch": {}},
    ]
    with pytest.raises(CompositionError) as duplicate:
        compose([candidate], [], records)
    assert str(duplicate.value) == (
        "overlay[1] names the same project URL 'github.com/owner/repo' as overlay[0]"
    )
    with pytest.raises(CompositionError) as null_patch:
        compose([candidate], [], [{**records[0], "patch": None}])
    assert str(null_patch.value) == (
        "overlay[0].patch must be an object (url 'github.com/owner/repo')"
    )


@pytest.mark.parametrize("value", [None, "assigned"], ids=["deleted", "assigned"])
@pytest.mark.parametrize(
    "field", ["url", "overrideSource", "family", "variant", "categories"]
)
def test_overlay_rejects_assigning_or_deleting_protected_fields(
    field: str, value: object
) -> None:
    candidate = app("x")
    with pytest.raises(CompositionError, match=r"protected field") as raised:
        compose([candidate], [], overlays((candidate.url, {field: value})))
    message = str(raised.value)
    assert repr(url_family(candidate)) in message
    assert message.endswith(f"protected field {field}")


def test_an_overlay_cannot_stop_a_published_entry_adopting_its_apk_id() -> None:
    candidate = app("pkg")
    result = compose(
        [candidate], [], overlays((candidate.url, {"allowIdChange": False}))
    )
    for variant in Variant:
        [composed] = result.apps[variant]
        assert composed.data["allowIdChange"] is False
        [rendered] = json.loads(render_pack(result.apps[variant]))["apps"]
        assert rendered["allowIdChange"] is True


def test_overlay_patches_unmodeled_fields_including_package_id() -> None:
    candidate = app("x")
    result = compose(
        [candidate],
        [],
        overlays((candidate.url, {"origin": "overlay-value", "packageId": "kept"})),
    )
    for variant in Variant:
        [rendered] = result.apps[variant]
        assert rendered.data["origin"] == "overlay-value"
        assert rendered.data["packageId"] == "kept"


def test_overlay_fixes_a_wrong_source_id_in_every_variant() -> None:
    wrong = app("wrong.source.id", url="https://github.com/owner/project")
    other = app("other", "bboi", url="https://github.com/owner/other")
    result = compose(
        [wrong, other],
        [],
        overlays((wrong.url, {"id": "apk.package.id"})),
    )
    for variant in Variant:
        assert sorted((item.family, item.id) for item in result.apps[variant]) == [
            ("github.com/owner/other", "other"),
            ("github.com/owner/project", "apk.package.id"),
        ]
    assert {item.id for item in result.report.selections} == {
        "wrong.source.id",
        "other",
    }


def test_a_pin_names_the_source_id_at_a_url_whose_id_an_overlay_patches() -> None:
    url = "https://example.com/project"
    pinned = app("p", "rjny", url=url)
    rival = app("r", "extras", url=url)
    family = url_family(pinned)
    result = compose(
        [pinned, rival],
        [],
        overlays((url, {"id": "q"})),
        policy=build_policy(
            (),
            [
                Pin(family, variant, candidate_selector(pinned), "test")
                for variant in Variant
            ],
        ),
    )
    for variant in Variant:
        assert [item.id for item in result.apps[variant]] == ["q"]
    assert {(item.id, item.reason) for item in result.report.selections} == {
        ("p", "pin")
    }


@pytest.mark.parametrize("value", [None, "", "  ", 7])
def test_overlay_id_patch_must_be_a_nonempty_string(value: object) -> None:
    candidate = app("x")
    with pytest.raises(CompositionError) as error:
        compose([candidate], [], overlays((candidate.url, {"id": value})))
    assert str(error.value) == (
        f"overlay[0].patch for {url_family(candidate)!r} must set id to a "
        "nonempty string"
    )


def test_an_id_patch_does_not_move_an_entry_between_families() -> None:
    patched = app("p", url="https://example.com/patched")
    holder = app("q", "bboi", url="https://example.com/holder")
    result = compose([patched, holder], [], overlays((patched.url, {"id": "q"})))
    entries = (
        RepeatedEntry("example.com/holder", "example.com/holder"),
        RepeatedEntry("example.com/patched", "example.com/patched"),
    )
    assert result.report.repeated_ids == [
        RepeatedId(Variant.SINGLE, "q", entries),
        RepeatedId(Variant.DUAL, "q", entries),
    ]
    assert {item.family for item in result.report.selections} == {
        "example.com/patched",
        "example.com/holder",
    }


def test_a_denial_never_reads_an_overlay_patched_id() -> None:
    patched = app("p", url="https://example.com/patched")
    holder = app("q", "bboi", url="https://example.com/holder")
    patch = overlays((patched.url, {"id": "q"}))
    kept = compose([patched, holder], deny(holder.url), patch)
    for variant in Variant:
        assert ids(kept, variant) == {"q"}
        assert {item.family for item in kept.apps[variant]} == {"example.com/patched"}
    assert [item.families for item in kept.report.removals] == [("example.com/holder",)]


def test_an_id_patch_at_a_url_whose_rules_name_two_families_fails() -> None:
    url = "https://github.com/owner/split"
    first = app("a", family="app:a", url=url)
    second = app("b", family="app:b", url=url)
    other = app("other", "bboi")
    with pytest.raises(CompositionError) as error:
        compose(
            [first, second, other],
            [],
            overlays((other.url, {"name": "y"}), (url, {"id": "c", "name": "x"})),
        )
    assert str(error.value) == (
        "overlay[1] for 'github.com/owner/split' patches id at a URL whose "
        "rules name families 'app:a', 'app:b'"
    )
    result = compose([first, second], [], overlays((url, {"name": "patched"})))
    for variant in Variant:
        assert {(item.family, item.data["name"]) for item in result.apps[variant]} == {
            ("app:a", "patched"),
            ("app:b", "patched"),
        }


def test_an_id_patch_at_a_url_whose_rules_agree_applies() -> None:
    url = "https://github.com/owner/agreed"
    ruled = app("a", family="app:a", url=url)
    result = compose([ruled], [], overlays((url, {"id": "fixed"})))
    assert ids(result, Variant.SINGLE) == {"fixed"}


def test_selection_report_names_the_winner_s_package_id_and_origin() -> None:
    winner = app("winner", "extras", family="app:x")
    loser = app("other", "rjny", family="app:x", name="different")
    selection = compose([winner, loser], [], []).report.selections[0]
    assert (selection.id, selection.origin, selection.reason) == (
        "winner",
        "extras",
        "source",
    )
    assert selection.considered == (
        ConsideredCandidate("rjny", "rjny-catalog", "other", loser.url),
    )


def test_similar_forks_without_a_family_rule_stay_separate_families() -> None:
    upstream = app("org.a.dolphin", url="https://github.com/a/dolphin", name="Dolphin")
    fork = app("org.b.dolphin", url="https://github.com/b/dolphin", name="Dolphin MMJR")
    result = compose([upstream, fork], [], [])
    for variant in Variant:
        assert {(item.family, item.id) for item in result.apps[variant]} == {
            ("github.com/a/dolphin", "org.a.dolphin"),
            ("github.com/b/dolphin", "org.b.dolphin"),
        }


def test_dual_falls_back_to_source_precedence_among_several_baseline_builds() -> None:
    builds = [
        app(f"{source}.pkg", source, family="app:x")
        for source in ("bboi", "rjny", "extras")
    ]
    selections = compose(builds, [], []).report.selections
    assert [
        (
            item.variant,
            item.id,
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
    assert selection.id == "bboi.pkg"
    assert selection.reason == "pin"


def test_considered_lists_only_other_available_candidates() -> None:
    winner = app("winner", "extras", family="app:x")
    loser = app("loser", "rjny", family="app:x")
    denied = app("denied", "bboi", family="app:x")
    single_only = app(
        "single.only", "codm2000", family="app:x", eligibility=SINGLE_ONLY
    )
    result = compose([winner, loser, denied, single_only], deny(denied.url), [])
    considered = {
        item.variant: [candidate.id for candidate in item.considered]
        for item in result.report.selections
    }
    assert considered == {
        Variant.SINGLE: ["single.only", "loser"],
        Variant.DUAL: ["loser"],
    }


def test_overlay_unknown_field_identifies_record_and_field() -> None:
    candidate = app("app.id")
    record = {"id": candidate.id, "url": candidate.url, "patch": {}}
    with pytest.raises(CompositionError) as error:
        compose([candidate], [], [record])
    assert str(error.value) == (
        f"overlay[0] has unknown field 'id' (url {url_family(candidate)!r})"
    )


@pytest.mark.parametrize("value", ["", "  ", 731, None])
def test_overlay_blank_or_nonstring_url_identifies_the_field(value: object) -> None:
    with pytest.raises(CompositionError) as error:
        compose([app("app.id")], [], [{"url": value, "patch": {}}])
    assert str(error.value) == "overlay[0].url must be a nonempty project URL"


@pytest.mark.parametrize("url", ["/owner/repo", "https://x.test/a b"])
def test_overlay_url_that_is_not_a_project_url_identifies_record_field_and_value(
    url: str,
) -> None:
    with pytest.raises(CompositionError) as error:
        compose([app("app.id")], [], [{"url": url, "patch": {}}])
    assert str(error.value) == f"overlay[0].url is not a project URL: {url!r}"


def test_overlay_record_that_is_not_an_object_fails() -> None:
    with pytest.raises(CompositionError) as error:
        compose([app("x")], [], ["not a record"])
    assert str(error.value) == "overlay[0] must be an object"


def match(candidate: App) -> dict[str, str]:
    return {
        "source": candidate.provenance.source,
        "origin": candidate.origin,
        "id": candidate.id,
        "url": candidate.url,
    }


def family_rule(candidate: App, family: str) -> dict[str, object]:
    return {"match": match(candidate), "family": family, "rationale": "test"}


def pin(candidate: App, family: str, variant: Variant) -> dict[str, object]:
    return {
        "family": family,
        "variant": variant.value,
        "match": match(candidate),
        "rationale": "test",
    }


def policy_of(
    rules: list[dict[str, object]], pins: list[dict[str, object]] | None = None
) -> CompositionPolicy:
    return parse_composition_policy(
        {"schemaVersion": 1, "candidates": rules, "pins": pins or []}
    )


def families(result: CompositionResult) -> set[tuple[str, str, str]]:
    return {
        (item.family, item.variant.value, item.source)
        for item in result.report.selections
    }


def test_a_disappeared_pinned_build_selects_no_other_build_of_its_family() -> None:
    pinned = app("pinned", "bboi", family="app:x")
    other = app("other", "rjny", family="app:x")
    policy = policy_of(
        [family_rule(pinned, "app:x"), family_rule(other, "app:x")],
        [pin(pinned, "app:x", Variant.SINGLE)],
    )
    assert ids(compose([pinned, other], [], [], policy=policy), Variant.SINGLE) == {
        "pinned"
    }
    # The pinned build's own family rule goes with it; a rule left behind would
    # fail earlier as a selector that matches no candidate.
    report = CompositionReport()
    with pytest.raises(CompositionError, match="is missing"):
        compose(
            [other],
            [],
            [],
            policy=build_policy(
                rules_for([replace(other, family="app:x")]), policy.pins
            ),
            report=report,
        )
    assert report.selections == []


def test_two_records_sharing_a_pinned_identity_fail_before_the_pin_is_read() -> None:
    first = app("pinned", "rjny", additional_settings={"about": "one"})
    second = replace(first, additional_settings={"about": "two"})
    policy = policy_of([], [pin(first, url_family(first), Variant.DUAL)])
    with pytest.raises(CompositionError) as error:
        compose([first, second], [], [], policy=policy)
    assert str(error.value) == (
        f"ambiguous original candidate identity {candidate_selector(first).key!r}"
    )
    result = compose(
        [first, replace(second, additional_settings={"about": "one"})],
        [],
        [],
        policy=policy,
    )
    assert ids(result, Variant.DUAL) == {"pinned"}


def test_a_denied_ruled_candidate_names_no_family_and_joins_no_other_url() -> None:
    denied = app("denied", "rjny", family="app:x")
    member = app("member", "bboi", family="app:x")
    rule_less = app("rule.less", "extras")
    result = compose([denied, member, rule_less], deny(denied.url), [])
    assert result.report.removals == [Removal(url_family(denied), "broken", ("app:x",))]
    assert families(result) == {
        ("app:x", "single", "bboi"),
        ("app:x", "dual", "bboi"),
        (url_family(rule_less), "single", "extras"),
        (url_family(rule_less), "dual", "extras"),
    }


def test_candidate_eligible_for_no_variant_names_no_family() -> None:
    ruled = app("ruled", "rjny", eligibility=frozenset())
    other = app("other", "bboi")
    result = compose(
        [ruled, other], [], [], policy=policy_of([family_rule(ruled, "app:x")])
    )
    assert families(result) == {
        (url_family(other), "single", "bboi"),
        (url_family(other), "dual", "bboi"),
    }


def test_rule_on_a_candidate_eligible_for_no_variant_still_covers_its_url() -> None:
    url = "https://example.com/shared"
    ruled = app("ruled", "rjny", url=url, eligibility=frozenset())
    rule_less = app("rule.less", "bboi", url=url)
    member = app("member", "extras", eligibility=DUAL_ONLY)
    policy = policy_of(
        [family_rule(ruled, "app:x"), family_rule(member, "app:x")],
        [pin(rule_less, "app:x", Variant.SINGLE)],
    )
    result = compose([ruled, rule_less, member], [], [], policy=policy)
    assert families(result) == {
        ("app:x", "single", "bboi"),
        ("app:x", "dual", "extras"),
    }
    assert [item.reason for item in result.report.selections] == [
        "pin",
        "dual-preferred",
    ]


def test_pin_on_a_rule_less_candidate_names_the_family_it_joins() -> None:
    url = "https://example.com/x"
    ruled = app("ruled", "rjny", url=url)
    rule_less = app("rule.less", "bboi", url=url)
    rules = [family_rule(ruled, "app:x")]
    result = compose(
        [ruled, rule_less],
        [],
        [],
        policy=policy_of(rules, [pin(rule_less, "app:x", Variant.DUAL)]),
    )
    assert [
        (item.family, item.variant, item.source, item.reason)
        for item in result.report.selections
    ] == [
        ("app:x", Variant.SINGLE, "rjny", "source"),
        ("app:x", Variant.DUAL, "bboi", "pin"),
    ]
    with pytest.raises(CompositionPolicyError, match="projected family 'app:x'"):
        policy_of(rules, [pin(rule_less, "example.com/x", Variant.DUAL)])


def test_pin_naming_another_family_fails_the_build_as_wrong_family() -> None:
    candidate = app("plain", "bboi")
    with pytest.raises(CompositionError) as error:
        compose(
            [candidate],
            [],
            [],
            policy=policy_of([], [pin(candidate, "app:other", Variant.DUAL)]),
        )
    assert str(error.value) == (
        "pin for family 'app:other' target 'dual' names a candidate of "
        f"family {url_family(candidate)!r}"
    )


@pytest.mark.parametrize("removal", ["denial", "ineligibility"])
def test_pin_on_a_removed_candidate_fails_on_the_removal(removal: str) -> None:
    pinned = app(
        "pinned",
        eligibility=frozenset() if removal == "ineligibility" else frozenset(Variant),
    )
    denials = deny(pinned.url) if removal == "denial" else []
    report = CompositionReport()
    family = url_family(pinned)
    with pytest.raises(CompositionError) as error:
        compose(
            [pinned, app("other", "bboi")],
            [*denials, *deny("https://example.com/retired", reason="obsolete")],
            [],
            policy=policy_of([], [pin(pinned, family, Variant.DUAL)]),
            report=report,
        )
    label = f"pin for family {family!r} target 'dual'"
    assert str(error.value) == (
        f"{label} is denied at {normalize_project_url(pinned.url)!r}: broken"
        if removal == "denial"
        else f"{label} is ineligible for every variant"
    )
    assert report.stale_exclusions == [
        StaleExclusion("example.com/retired", "obsolete")
    ]


def test_pin_on_a_denied_candidate_eligible_for_no_variant_fails_as_ineligible() -> (
    None
):
    pinned = app("pinned", eligibility=frozenset())
    family = url_family(pinned)
    report = CompositionReport()
    with pytest.raises(CompositionError) as error:
        compose(
            [pinned, app("other", "bboi")],
            deny(pinned.url),
            [],
            policy=policy_of([], [pin(pinned, family, Variant.DUAL)]),
            report=report,
        )
    assert str(error.value) == (
        f"pin for family {family!r} target 'dual' is ineligible for every variant"
    )
    # The denial removes nothing, since the candidate forms no family.
    assert report.removals == []


def test_dual_preference_outranks_precedence_inside_a_joined_family() -> None:
    ordinary = app("shared", "rjny", url="https://example.com/x")
    preferred = app(
        "shared", "bboi", url="https://example.com/y", eligibility=DUAL_ONLY
    )
    result = compose(
        [ordinary, preferred],
        [],
        [],
        policy=policy_of(
            [family_rule(ordinary, "app:x"), family_rule(preferred, "app:x")]
        ),
    )
    assert [
        (item.family, item.variant, item.source, item.reason)
        for item in result.report.selections
    ] == [
        ("app:x", Variant.SINGLE, "rjny", "source"),
        ("app:x", Variant.DUAL, "bboi", "dual-preferred"),
    ]


def test_mapped_family_carries_its_category_in_every_variant() -> None:
    candidate = app("x", categories=("Dual Screen",))
    result = compose(
        [candidate],
        [],
        [],
        policy=category_policy({url_family(candidate): Category.PC_PORTS}),
    )
    assert final_categories(result) == {
        ("x", Variant.SINGLE): ["PC Ports"],
        ("x", Variant.DUAL): ["PC Ports"],
    }


def test_url_family_key_maps_a_differently_spelled_project_url() -> None:
    candidate = app("x", url="https://github.com/Owner/Repo", categories=("Emulator",))
    result = compose(
        [candidate],
        [],
        [],
        policy=category_policy({"github.com/owner/repo": Category.UTILITIES}),
    )
    assert final_categories(result) == {
        ("x", Variant.SINGLE): ["Utilities"],
        ("x", Variant.DUAL): ["Utilities"],
    }


def test_explicit_family_key_categorizes_both_of_its_package_ids() -> None:
    single = app("x.single", eligibility=SINGLE_ONLY)
    dual = app("x.dual", "bboi", categories=("Dual Screen",), eligibility=DUAL_ONLY)
    policy = parse_composition_policy(
        {
            "schemaVersion": 1,
            "candidates": [family_rule(single, "app:x"), family_rule(dual, "app:x")],
            "pins": [],
            "categories": {"app:x": "PC Ports"},
        }
    )
    result = compose([single, dual], [], [], policy=policy)
    assert final_categories(result) == {
        ("x.single", Variant.SINGLE): ["PC Ports"],
        ("x.dual", Variant.DUAL): ["PC Ports"],
    }
    assert result.report.stale_category_assignments == []


@pytest.mark.parametrize("mapped", [False, True])
@pytest.mark.parametrize("source", [(), ("Utilities", "Dual Screen")])
def test_track_only_entry_carries_exactly_track_only(
    mapped: bool, source: tuple[str, ...]
) -> None:
    tracker = app("1", categories=source, additional_settings=TRACK_ONLY)
    categories = {url_family(tracker): Category.EMULATOR} if mapped else {}
    result = compose([tracker], [], [], policy=category_policy(categories))
    assert final_categories(result) == {
        ("1", Variant.SINGLE): ["Track Only"],
        ("1", Variant.DUAL): ["Track Only"],
    }
    assert result.report.uncategorized_families == []


def test_unmapped_entry_keeps_allowed_source_categories_in_source_order() -> None:
    result = compose(
        [
            app("x", categories=("Dual Screen", "Frontend", "Track Only", "Emulator")),
            app("y", categories=("Dual Screen", "Emulator")),
        ],
        [],
        [],
        policy=category_policy({}),
    )
    assert final_categories(result) == {
        ("x", Variant.SINGLE): ["Frontend", "Emulator"],
        ("x", Variant.DUAL): ["Frontend", "Emulator"],
        ("y", Variant.SINGLE): ["Emulator"],
        ("y", Variant.DUAL): ["Emulator"],
    }


def test_unmapped_entry_with_no_allowed_category_builds_without_one() -> None:
    x, y = app("x", categories=("Dual Screen",)), app("y")
    result = compose([x, y], [], [], policy=category_policy({}))
    assert final_categories(result) == {
        ("x", Variant.SINGLE): [],
        ("x", Variant.DUAL): [],
        ("y", Variant.SINGLE): [],
        ("y", Variant.DUAL): [],
    }
    both = (Variant.SINGLE, Variant.DUAL)
    assert result.report.uncategorized_families == [
        UncategorizedFamily(url_family(x), both),
        UncategorizedFamily(url_family(y), both),
    ]


def test_each_variant_assigns_its_own_winner_s_categories() -> None:
    url = "https://example.com/project"
    single = app("x", url=url, categories=("Emulator",), eligibility=SINGLE_ONLY)
    dual = app("x", "bboi", url=url, categories=("Dual Screen",), eligibility=DUAL_ONLY)
    result = compose([single, dual], [], [], policy=category_policy({}))
    assert final_categories(result) == {
        ("x", Variant.SINGLE): ["Emulator"],
        ("x", Variant.DUAL): [],
    }
    assert result.report.uncategorized_families == [
        UncategorizedFamily("example.com/project", (Variant.DUAL,))
    ]


def test_track_only_rule_reads_settings_after_overlays() -> None:
    candidate = app("x", categories=("Emulator",))
    family = url_family(candidate)
    result = compose(
        [candidate],
        [],
        overlays((candidate.url, {"additionalSettings": TRACK_ONLY})),
        policy=category_policy({family: Category.PC_PORTS}),
    )
    assert final_categories(result) == {
        ("x", Variant.SINGLE): ["Track Only"],
        ("x", Variant.DUAL): ["Track Only"],
    }
    assert result.report.stale_category_assignments == [family]


def test_non_object_settings_after_overlays_are_not_track_only() -> None:
    candidate = app("x", categories=("Emulator",), additional_settings=TRACK_ONLY)
    result = compose(
        [candidate],
        [],
        overlays((candidate.url, {"additionalSettings": "broken"})),
        policy=category_policy({}),
    )
    assert final_categories(result) == {
        ("x", Variant.SINGLE): ["Emulator"],
        ("x", Variant.DUAL): ["Emulator"],
    }


def test_category_keys_that_set_no_selected_category_are_stale() -> None:
    used = app("used", categories=("Dual Screen",))
    tracker = app("1", additional_settings=TRACK_ONLY)
    denied = app("denied")
    result = compose(
        [used, tracker, denied],
        deny(denied.url, reason="test"),
        [],
        policy=category_policy(
            {
                url_family(used): Category.PC_PORTS,
                url_family(tracker): Category.UTILITIES,
                url_family(denied): Category.EMULATOR,
                "app:absent": Category.EMULATOR,
            }
        ),
    )
    assert result.report.stale_category_assignments == [
        "app:absent",
        url_family(tracker),
        url_family(denied),
    ]
    assert result.report.uncategorized_families == []


def test_key_used_in_one_variant_only_is_not_stale() -> None:
    single = app("x", family="app:x", eligibility=SINGLE_ONLY)
    dual = app("y", "bboi", family="app:x", eligibility=DUAL_ONLY)
    result = compose(
        [single, dual],
        [],
        overlays((dual.url, {"additionalSettings": TRACK_ONLY})),
        policy=build_policy(
            rules_for([single, dual]), (), {"app:x": Category.EMULATOR}
        ),
    )
    assert final_categories(result) == {
        ("x", Variant.SINGLE): ["Emulator"],
        ("y", Variant.DUAL): ["Track Only"],
    }
    assert result.report.stale_category_assignments == []
