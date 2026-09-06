from __future__ import annotations

from dataclasses import replace

import pytest

from obtainium_pack.merge import CompositionError, CompositionResult, compose
from obtainium_pack.model import App, Provenance, SourceType, Variant
from obtainium_pack.overlay import ComposedApp


def app(
    package_id: str,
    source: str,
    variant: Variant,
    *,
    name: str | None = None,
    settings: dict[str, object] | None = None,
    raw: dict[str, object] | None = None,
) -> App:
    url = f"https://example.com/{source}/{package_id}"
    return App(
        id=package_id,
        url=url,
        name=name or f"{source} {package_id}",
        source_type=SourceType.HTML,
        categories=(source,),
        variant=variant,
        provenance=Provenance(source, url),
        additional_settings=settings or {},
        raw=raw or {},
    )


def by_variant(result: CompositionResult, variant: Variant) -> dict[str, ComposedApp]:
    return {entry.id: entry for entry in result.apps[variant]}


def test_composes_variants_independently_and_keeps_precedence_winner_whole() -> None:
    single_bboi = app("shared", "bboi", Variant.SINGLE)
    single_rjny = app("shared", "rjny", Variant.SINGLE)
    dual_bboi = replace(single_bboi, variant=Variant.DUAL, name="dual winner")

    result = compose([single_bboi, single_rjny, dual_bboi], [], {}, {})

    assert by_variant(result, Variant.SINGLE)["shared"].data["name"] == single_rjny.name
    assert by_variant(result, Variant.DUAL)["shared"].data["name"] == dual_bboi.name


def test_extras_has_highest_precedence() -> None:
    upstream = app("shared", "rjny", Variant.SINGLE)
    extra = app("shared", "extras", Variant.SINGLE)
    result = compose(
        [upstream, extra, replace(extra, variant=Variant.DUAL)], [], {}, {}
    )
    assert by_variant(result, Variant.SINGLE)["shared"].provenance == extra.provenance


def test_identical_same_source_duplicates_collapse() -> None:
    candidate = app("same", "codm2000", Variant.DUAL)
    result = compose([candidate, candidate], [], {}, {})
    assert len(result.apps[Variant.DUAL]) == 1
    assert result.apps[Variant.DUAL][0].id == candidate.id


def test_differing_same_source_duplicates_fail_even_when_source_would_lose() -> None:
    winner = app("same", "extras", Variant.SINGLE)
    duplicate = app("same", "bboi", Variant.SINGLE)
    differing = replace(duplicate, name="different")

    with pytest.raises(
        CompositionError, match=r"bboi.*single.*same|same.*single.*bboi"
    ):
        compose([winner, duplicate, differing], [], {}, {})


def test_displacement_reports_sources_and_differing_import_fields() -> None:
    winner = app("shared", "rjny", Variant.SINGLE, settings={"trackOnly": True})
    loser = app("shared", "bboi", Variant.SINGLE, settings={"trackOnly": False})

    report = compose(
        [loser, winner, replace(winner, variant=Variant.DUAL)], [], {}, {}
    ).report

    assert len(report.displacements) == 1
    displacement = report.displacements[0]
    assert displacement.package_id == "shared"
    assert displacement.variant is Variant.SINGLE
    assert displacement.winner_source == "rjny"
    assert displacement.loser_source == "bboi"
    assert "additionalSettings" in displacement.differing_fields


def test_displacement_reports_a_field_present_as_null_on_only_one_candidate() -> None:
    winner = app("shared", "rjny", Variant.SINGLE, raw={"nullable": None})
    loser = app("shared", "bboi", Variant.SINGLE)
    dual = replace(winner, variant=Variant.DUAL)

    report = compose([loser, winner, dual], [], {}, {}).report

    assert "nullable" in report.displacements[0].differing_fields


def test_unscoped_denial_removes_both_variants_and_reports_reasons() -> None:
    candidates = [
        app("gone", "rjny", Variant.SINGLE),
        app("gone", "rjny", Variant.DUAL),
    ]
    result = compose(candidates, [{"id": "gone", "reason": "broken"}], {}, {})
    assert result.apps == {Variant.SINGLE: [], Variant.DUAL: []}
    assert {(item.variant, item.reason) for item in result.report.removals} == {
        (Variant.SINGLE, "broken"),
        (Variant.DUAL, "broken"),
    }
    assert result.report.stale_exclusions == []


def test_variant_denial_removes_only_named_variant() -> None:
    candidates = [
        app("kept", "rjny", Variant.SINGLE),
        app("kept", "rjny", Variant.DUAL),
    ]
    result = compose(
        candidates,
        [{"id": "kept", "variant": "dual", "reason": "dual bug"}],
        {},
        {},
    )
    assert set(by_variant(result, Variant.SINGLE)) == {"kept"}
    assert result.apps[Variant.DUAL] == []


@pytest.mark.parametrize(
    ("candidates", "denial"),
    [
        ([], {"id": "missing", "reason": "obsolete"}),
        (
            [app("single-only", "rjny", Variant.SINGLE)],
            {"id": "single-only", "variant": "dual", "reason": "omit dual"},
        ),
    ],
)
def test_stale_denials_are_reported_against_their_applicable_variants(
    candidates: list[App], denial: dict[str, str]
) -> None:
    result = compose(candidates, [denial], {}, {})
    assert result.report.removals == []
    assert len(result.report.stale_exclusions) == 1
    assert result.report.stale_exclusions[0].package_id == denial["id"]


def test_unknown_denylist_variant_fails_with_entry_and_value() -> None:
    denial = {"id": "bad", "variant": "foldable", "reason": "no"}
    with pytest.raises(CompositionError, match=r"bad.*foldable|foldable.*bad"):
        compose([], [denial], {}, {})


def test_overlay_target_validation_happens_after_denial() -> None:
    candidate = app("removed", "rjny", Variant.DUAL)
    with pytest.raises(CompositionError, match="removed"):
        compose(
            [candidate],
            [{"id": "removed", "reason": "broken"}],
            {"removed": {"name": "patched"}},
            {},
        )


def test_common_overlay_requires_a_target_in_at_least_one_variant() -> None:
    with pytest.raises(CompositionError, match="missing"):
        compose([], [], {"missing": {"name": "patched"}}, {})


def test_dual_overlay_requires_a_dual_target() -> None:
    candidate = app("single", "rjny", Variant.SINGLE)
    with pytest.raises(CompositionError, match="single"):
        compose([candidate], [], {}, {"single": {"name": "patched"}})


def test_common_overlay_may_patch_an_id_present_in_one_variant() -> None:
    candidate = app("dual-only", "codm2000", Variant.DUAL)
    result = compose([candidate], [], {"dual-only": {"name": "patched"}}, {})
    assert by_variant(result, Variant.DUAL)["dual-only"].data["name"] == "patched"


def test_common_and_dual_overlays_layer_without_mutating_inputs_or_sibling() -> None:
    settings: dict[str, object] = {"nested": {"common": False, "dual": False}}
    single = app("both", "rjny", Variant.SINGLE, settings=settings)
    dual = replace(single, variant=Variant.DUAL)

    result = compose(
        [single, dual],
        [],
        {"both": {"additionalSettings": {"nested": {"common": True}}}},
        {"both": {"additionalSettings": {"nested": {"dual": True}}}},
    )

    single_result = by_variant(result, Variant.SINGLE)["both"]
    dual_result = by_variant(result, Variant.DUAL)["both"]
    assert single_result.data["additionalSettings"] == {
        "nested": {"common": True, "dual": False}
    }
    assert dual_result.data["additionalSettings"] == {
        "nested": {"common": True, "dual": True}
    }
    assert single.additional_settings == settings
    assert dual.additional_settings == settings
    assert (
        single_result.data["additionalSettings"]
        is not dual_result.data["additionalSettings"]
    )


def test_overlay_null_deletes_nested_and_raw_keys() -> None:
    candidate = app(
        "patched",
        "rjny",
        Variant.DUAL,
        settings={"keep": 1, "delete": 2},
        raw={"keepRaw": 1, "deleteRaw": 2},
    )
    result = compose(
        [candidate],
        [],
        {
            "patched": {
                "additionalSettings": {"delete": None},
                "deleteRaw": None,
            }
        },
        {},
    )
    patched = by_variant(result, Variant.DUAL)["patched"]
    assert patched.data["additionalSettings"] == {"keep": 1}
    assert patched.data["keepRaw"] == 1
    assert "deleteRaw" not in patched.data


def test_overlay_may_delete_a_required_candidate_field() -> None:
    candidate = app("patched", "rjny", Variant.DUAL)
    result = compose([candidate], [], {"patched": {"name": None}}, {})
    assert "name" not in by_variant(result, Variant.DUAL)["patched"].data


@pytest.mark.parametrize("field", ["id", "overrideSource"])
@pytest.mark.parametrize("value", ["replacement", None])
def test_overlay_rejects_identity_fields_even_when_null(
    field: str, value: object
) -> None:
    candidate = app("guarded", "rjny", Variant.DUAL)
    with pytest.raises(CompositionError, match="guarded"):
        compose([candidate], [], {"guarded": {field: value}}, {})


@pytest.mark.parametrize("overlay_scope", ["common", "dual"])
def test_overlay_cannot_move_a_surviving_app_to_a_denied_id(
    overlay_scope: str,
) -> None:
    candidates = [
        app(package_id, "rjny", variant)
        for package_id in ("survivor", "denied")
        for variant in Variant
    ]
    denylist = [{"id": "denied", "reason": "broken"}]
    overlay: dict[str, object] = {"survivor": {"id": "denied"}}

    with pytest.raises(
        CompositionError, match=r"overlay for 'survivor'.*protected field id"
    ):
        compose(
            candidates,
            denylist,
            overlay if overlay_scope == "common" else {},
            overlay if overlay_scope == "dual" else {},
        )

    assert [candidate.id for candidate in candidates] == [
        "survivor",
        "survivor",
        "denied",
        "denied",
    ]
    result = compose(candidates, denylist, {}, {})
    for variant in Variant:
        assert set(by_variant(result, variant)) == {"survivor"}


@pytest.mark.parametrize("patch", [None, "replacement", ["replacement"]])
def test_overlay_patch_must_be_an_object(patch: object) -> None:
    candidate = app("guarded", "rjny", Variant.DUAL)
    with pytest.raises(CompositionError, match="guarded"):
        compose([candidate], [], {"guarded": patch}, {})  # type: ignore[arg-type]


def test_missing_dual_coverage_fails() -> None:
    with pytest.raises(CompositionError, match="single-only"):
        compose([app("single-only", "rjny", Variant.SINGLE)], [], {}, {})
