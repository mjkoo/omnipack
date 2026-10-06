"""Compose source candidates into device-specific app-family selections."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import astuple, dataclass, field
from typing import Any

from omnipack.composition_policy import (
    CandidateSelector,
    CompositionPolicy,
    CompositionPolicyError,
    Pin,
    PinKey,
    apply_composition_policy,
    assigned_family,
    candidate_selector,
    check_overlay_id_patches,
    rendered_key,
    repeated_ids,
)
from omnipack.model import ASSIGNABLE_CATEGORIES, App, Category, Variant
from omnipack.overlay import (
    ComposedApp,
    OverlayError,
    OverlayPatch,
    apply_overlay,
    parse_overlay,
)
from omnipack.render import canonical_serialization
from omnipack.report_model import SelectionReason
from omnipack.urls import normalize_project_url, parse_project_url

_PRECEDENCE = {"codm2000": 0, "bboi": 1, "quiver": 2, "rjny": 3, "extras": 4}


class CompositionError(ValueError):
    """Candidate data or curation rules cannot produce a valid composition."""


@dataclass(frozen=True, slots=True)
class Removal:
    """A denial that removed candidates, with the families they belonged to."""

    url: str
    reason: str
    families: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StaleExclusion:
    url: str
    reason: str


@dataclass(frozen=True, slots=True)
class ConsideredCandidate:
    """A candidate that was available for a selection and did not win it."""

    source: str
    origin: str
    id: str
    url: str


@dataclass(frozen=True, slots=True)
class FamilySelection:
    """One family's winner for one variant, why it won and what it beat.

    `considered` holds the family's other candidates that were eligible for
    the variant and not denied; denied ones appear among the removals.
    """

    family: str
    variant: Variant
    id: str
    url: str
    source: str
    origin: str
    reason: SelectionReason
    considered: tuple[ConsideredCandidate, ...]


@dataclass(frozen=True, slots=True)
class SameRankTie:
    """A family and variant whose winner was chosen among tied candidates.

    The winner is the tied candidate whose canonical serialized form sorts
    first, so the choice never depends on input order.
    """

    family: str
    variant: Variant
    tied: tuple[CandidateSelector, ...]
    winner: CandidateSelector


@dataclass(frozen=True, slots=True)
class SingleOnlyFamily:
    """A family published in single with no selected build in dual, with its
    single entry's package id and normalized project URL.
    """

    family: str
    id: str
    url: str


@dataclass(frozen=True, slots=True)
class RepeatedEntry:
    """One entry carrying a repeated package id: its family and normalized URL."""

    family: str
    url: str


@dataclass(frozen=True, slots=True)
class RepeatedId:
    """A package id more than one selected entry of a variant carries.

    Obtainium stores imported apps by id, so it keeps only one of them.
    """

    variant: Variant
    id: str
    entries: tuple[RepeatedEntry, ...]


@dataclass(frozen=True, slots=True)
class UncategorizedFamily:
    """A family whose selected entry ended without a category in `variants`."""

    family: str
    variants: tuple[Variant, ...]


@dataclass(slots=True)
class CompositionReport:
    removals: list[Removal] = field(default_factory=list)
    stale_exclusions: list[StaleExclusion] = field(default_factory=list)
    selections: list[FamilySelection] = field(default_factory=list)
    same_rank_ties: list[SameRankTie] = field(default_factory=list)
    uncategorized_families: list[UncategorizedFamily] = field(default_factory=list)
    # Category map keys that set no selected entry's category.
    stale_category_assignments: list[str] = field(default_factory=list)
    single_only_families: list[SingleOnlyFamily] = field(default_factory=list)
    repeated_ids: list[RepeatedId] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CompositionResult:
    apps: dict[Variant, list[ComposedApp]]
    report: CompositionReport


@dataclass(frozen=True, slots=True)
class Exclusion:
    """A project denial: every candidate at `url`, a normalized URL, is removed."""

    url: str
    reason: str


def compose(
    candidates: list[App],
    denylist: list[dict[str, str]],
    overlay: object,
    *,
    policy: CompositionPolicy,
    report: CompositionReport | None = None,
) -> CompositionResult:
    report = report or CompositionReport()
    exclusions = parse_exclusions(denylist)
    try:
        candidates = list(apply_composition_policy(policy, candidates))
    except CompositionPolicyError as error:
        raise CompositionError(str(error)) from error
    _check_sources(candidates)
    denied = _exclude(candidates, exclusions, report)
    formed = tuple(
        item for item in candidates if item.eligibility and id(item) not in denied
    )
    pinned = _resolve_pins(candidates, formed, policy.pins, denied)
    selected = _select(_families(formed), pinned, report)
    try:
        patches = parse_overlay(overlay, "overlay")
        check_overlay_id_patches(policy, patches)
        _validate_overlay_targets(selected, patches)
        for variant in Variant:
            selected[variant] = apply_overlay(selected[variant], patches)
    except (OverlayError, CompositionPolicyError) as error:
        raise CompositionError(str(error)) from error
    applied = _assign_categories(selected, policy)
    report.uncategorized_families.extend(_uncategorized_families(selected))
    report.stale_category_assignments.extend(sorted(set(policy.categories) - applied))
    report.single_only_families.extend(_single_only_families(selected))
    report.repeated_ids.extend(_repeated_ids(selected))
    return CompositionResult(selected, report)


def parse_exclusions(entries: list[Any]) -> tuple[Exclusion, ...]:
    """Parse project denials, each of which applies to both variants."""
    result: list[Exclusion] = []
    for index, entry in enumerate(entries):
        label = f"denylist[{index}]"
        if not isinstance(entry, dict):
            raise CompositionError(f"{label} must be an object")
        unknown = set(entry) - {"url", "reason"}
        if unknown:
            raise CompositionError(f"{label} has unknown field {min(unknown)!r}")
        url, reason = entry.get("url"), entry.get("reason")
        if not isinstance(url, str) or not url.strip():
            raise CompositionError(f"{label}.url must be a nonempty string")
        if not isinstance(reason, str) or not reason.strip():
            raise CompositionError(f"{label}.reason must be a nonempty string")
        try:
            normalized = parse_project_url(url)
        except ValueError as error:
            raise CompositionError(
                f"{label}.url is not a project URL: {url!r}"
            ) from error
        result.append(Exclusion(normalized, reason))
    return tuple(result)


def _check_sources(candidates: list[App]) -> None:
    for candidate in candidates:
        source = candidate.provenance.source
        if source not in _PRECEDENCE:
            raise CompositionError(f"unknown candidate source {source!r}")


def _families(candidates: tuple[App, ...]) -> dict[str, list[App]]:
    families: dict[str, list[App]] = {}
    for candidate in candidates:
        families.setdefault(assigned_family(candidate), []).append(candidate)
    return families


def _exclude(
    candidates: list[App],
    exclusions: tuple[Exclusion, ...],
    report: CompositionReport,
) -> dict[int, str]:
    """Record each candidate a denial removes, keyed by candidate.

    A denial is reported once, under its URL, with every family whose
    candidates it removed. It is stale only when no candidate is at its URL;
    one whose candidates are eligible for neither pack removes nothing but
    still applies.
    """
    denied: dict[int, str] = {}
    by_url: dict[str, list[App]] = {}
    for candidate in candidates:
        by_url.setdefault(normalize_project_url(candidate.url), []).append(candidate)
    for rule in exclusions:
        matched = by_url.get(rule.url, [])
        if not matched:
            report.stale_exclusions.append(StaleExclusion(rule.url, rule.reason))
            continue
        for candidate in matched:
            denied[id(candidate)] = rule.reason
        families = sorted(
            {
                assigned_family(candidate)
                for candidate in matched
                if candidate.eligibility
            }
        )
        if families:
            report.removals.append(Removal(rule.url, rule.reason, tuple(families)))
    return denied


def _resolve_pins(
    candidates: list[App],
    formed: tuple[App, ...],
    pins: tuple[Pin, ...],
    denied: dict[int, str],
) -> dict[PinKey, App]:
    """Validate every pin against the admitted candidates before any selection.

    A candidate eligible for no variant, or a denied one, forms no family, so
    its pin fails on that exclusion before the family comparison. Ineligibility
    is checked first, since a denial of such a candidate removes nothing.
    """
    by_selector = {candidate_selector(item).key: item for item in formed}
    resolved: dict[PinKey, App] = {}
    # Sorted so the first failing pin reported does not depend on policy order.
    for pin in sorted(pins, key=lambda item: (item.family, item.variant.value)):
        label = f"pin for family {pin.family!r} target {pin.variant.value!r}"
        # Policy application has already collapsed identical candidates and
        # failed on different records sharing one selector, so at most one
        # candidate matches.
        candidate = next(
            (item for item in candidates if candidate_selector(item) == pin.match),
            None,
        )
        if candidate is None:
            raise CompositionError(f"{label} is missing")
        if not candidate.eligibility:
            raise CompositionError(f"{label} is ineligible for every variant")
        denied_reason = denied.get(id(candidate))
        if denied_reason is not None:
            denied_url = normalize_project_url(candidate.url)
            raise CompositionError(
                f"{label} is denied at {denied_url!r}: {denied_reason}"
            )
        winner = by_selector[pin.match.key]
        if winner.family != pin.family:
            raise CompositionError(
                f"{label} names a candidate of family {winner.family!r}"
            )
        if pin.variant not in winner.eligibility:
            raise CompositionError(f"{label} is ineligible")
        resolved[(pin.family, pin.variant)] = winner
    return resolved


def _select(
    families: dict[str, list[App]],
    pinned: dict[PinKey, App],
    report: CompositionReport,
) -> dict[Variant, list[ComposedApp]]:
    result = {variant: [] for variant in Variant}
    for family in sorted(families):
        family_candidates = families[family]
        for variant in Variant:
            available = [
                item for item in family_candidates if variant in item.eligibility
            ]
            pinned_winner = pinned.get((family, variant))
            if pinned_winner is not None:
                winner, reason = pinned_winner, SelectionReason.PIN
            elif available:
                tier, reason = available, SelectionReason.SOURCE
                if variant is Variant.DUAL and any(
                    item.dual_preferred for item in available
                ):
                    tier = [item for item in available if item.dual_preferred]
                    reason = SelectionReason.DUAL_PREFERRED
                elif variant is Variant.DUAL:
                    reason = SelectionReason.ORDINARY_FALLBACK
                rank = max(_PRECEDENCE[item.provenance.source] for item in tier)
                winners = sorted(
                    (
                        item
                        for item in tier
                        if _PRECEDENCE[item.provenance.source] == rank
                    ),
                    key=_tie_order,
                )
                winner = winners[0]
                if len(winners) > 1:
                    report.same_rank_ties.append(
                        SameRankTie(
                            family,
                            variant,
                            tuple(
                                sorted(
                                    (candidate_selector(item) for item in winners),
                                    key=lambda selector: selector.key,
                                )
                            ),
                            candidate_selector(winner),
                        )
                    )
            else:
                continue
            report.selections.append(
                FamilySelection(
                    family,
                    variant,
                    winner.id,
                    winner.url,
                    winner.provenance.source,
                    winner.origin,
                    reason,
                    tuple(
                        ConsideredCandidate(
                            item.provenance.source,
                            item.origin,
                            item.id,
                            item.url,
                        )
                        for item in sorted(
                            available, key=lambda item: candidate_selector(item).key
                        )
                        if item is not winner
                    ),
                )
            )
            result[variant].append(ComposedApp(family, _import_data(winner)))
    for values in result.values():
        values.sort(key=lambda item: (item.family, item.id, item.url))
    return result


def _assign_categories(
    apps: dict[Variant, list[ComposedApp]], policy: CompositionPolicy
) -> set[str]:
    """Give each selected entry its final categories, returning the map keys used.

    A track-only entry carries exactly Track Only, a mapped family its mapped
    category, and any other entry the source categories in the closed set
    other than Track Only, in source order. Overlays cannot patch categories,
    so nothing after this changes them.
    """
    applied = {
        app.family
        for values in apps.values()
        for app in values
        if app.family in policy.categories and not _track_only(app.data)
    }
    for variant in Variant:
        apps[variant] = [_categorized(app, policy) for app in apps[variant]]
    return applied


def _categorized(app: ComposedApp, policy: CompositionPolicy) -> ComposedApp:
    mapped = policy.categories.get(app.family)
    if _track_only(app.data):
        categories = [Category.TRACK_ONLY.value]
    elif mapped is not None:
        categories = [mapped.value]
    else:
        categories = [
            item for item in app.data["categories"] if item in ASSIGNABLE_CATEGORIES
        ]
    return ComposedApp(app.family, {**app.data, "categories": categories})


def _track_only(data: dict[str, Any]) -> bool:
    """Whether an entry's final settings mark it track-only."""
    settings = data.get("additionalSettings")
    return isinstance(settings, dict) and settings.get("trackOnly") is True


def _uncategorized_families(
    apps: dict[Variant, list[ComposedApp]],
) -> list[UncategorizedFamily]:
    variants: dict[str, list[Variant]] = {}
    for variant in Variant:
        for app in apps[variant]:
            if not app.data["categories"]:
                variants.setdefault(app.family, []).append(variant)
    return [
        UncategorizedFamily(family, tuple(found))
        for family, found in sorted(variants.items())
    ]


def _single_only_families(
    apps: dict[Variant, list[ComposedApp]],
) -> list[SingleOnlyFamily]:
    """Families selected in single that dual does not select at all.

    Such a family still ships in single; nothing ineligible is copied into dual.
    """
    dual_families = {app.family for app in apps[Variant.DUAL]}
    return [
        SingleOnlyFamily(app.family, app.id, normalize_project_url(app.url))
        for app in apps[Variant.SINGLE]
        if app.family not in dual_families
    ]


def _repeated_ids(apps: dict[Variant, list[ComposedApp]]) -> list[RepeatedId]:
    """Package ids, after overlays, that several entries of one variant carry."""
    result: list[RepeatedId] = []
    for variant in Variant:
        families = {rendered_key(app.id, app.url): app.family for app in apps[variant]}
        result.extend(
            RepeatedId(
                variant,
                package_id,
                tuple(
                    sorted(
                        (RepeatedEntry(families[key], key[1]) for key in members),
                        key=astuple,
                    )
                ),
            )
            for package_id, members in repeated_ids(
                [rendered_key(app.id, app.url) for app in apps[variant]]
            ).items()
        )
    return result


def _validate_overlay_targets(
    apps: dict[Variant, list[ComposedApp]], patches: tuple[OverlayPatch, ...]
) -> None:
    """Require each record to match a selected entry in at least one variant."""
    selected = {
        normalize_project_url(app.url) for values in apps.values() for app in values
    }
    missing = sorted(item.url for item in patches if item.url not in selected)
    if missing:
        raise OverlayError(f"overlay has no selected target for {missing!r}")


def _tie_order(app: App) -> tuple[str, tuple[str, str, str, str]]:
    """Order tied candidates by their import record as ingested, serialized
    canonically, so input order never picks the winner.

    Records that serialize identically publish identical entries, and their
    selectors order them so the recorded winner is stable too.
    """
    return canonical_serialization(_import_data(app)), candidate_selector(app).key


def _import_data(app: App) -> dict[str, Any]:
    data = deepcopy(app.raw)
    data.update(
        {
            "id": app.id,
            "url": app.url,
            "name": app.name,
            "categories": list(app.categories),
            "additionalSettings": deepcopy(app.additional_settings),
        }
    )
    if app.source_type is not None:
        data["overrideSource"] = app.source_type
    return data
