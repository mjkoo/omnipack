"""Compose source candidates into device-specific app-family selections."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from omnipack.composition_policy import (
    CandidateSelector,
    CompositionPolicy,
    CompositionPolicyError,
    Pin,
    PinKey,
    apply_composition_policy,
    rendered_key,
)
from omnipack.model import App, Variant
from omnipack.overlay import (
    ComposedApp,
    OverlayError,
    OverlayPatch,
    apply_overlay,
    parse_overlay,
)

_PRECEDENCE = {"codm2000": 0, "bboi": 1, "rjny": 2, "extras": 3}


class CompositionError(ValueError):
    """Candidate data or curation rules cannot produce a valid composition."""


@dataclass(frozen=True, slots=True)
class Removal:
    package_id: str
    variant: Variant
    reason: str
    family: str | None = None


@dataclass(frozen=True, slots=True)
class StaleExclusion:
    package_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class ConsideredCandidate:
    """A candidate that was available for a selection and did not win it."""

    source: str
    origin: str
    original_id: str
    url: str


@dataclass(frozen=True, slots=True)
class FamilySelection:
    """One family's winner for one variant, why it won and what it beat.

    `reason` is `pin`, `dual-preferred`, `ordinary-fallback` or `source`.
    `considered` holds the family's other candidates that were eligible for
    the variant and not denied; denied ones appear among the removals.
    """

    family: str
    variant: Variant
    original_id: str
    effective_id: str
    url: str
    source: str
    origin: str
    reason: str
    considered: tuple[ConsideredCandidate, ...]


@dataclass(slots=True)
class CompositionReport:
    removals: list[Removal] = field(default_factory=list)
    stale_exclusions: list[StaleExclusion] = field(default_factory=list)
    selections: list[FamilySelection] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CompositionResult:
    apps: dict[Variant, list[ComposedApp]]
    report: CompositionReport


@dataclass(frozen=True, slots=True)
class _Exclusion:
    package_id: str
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
        candidates = list(apply_composition_policy(policy, candidates).candidates)
    except CompositionPolicyError as error:
        raise CompositionError(str(error)) from error
    families = _families(candidates)
    denied = _exclude(candidates, exclusions, report)
    pinned = _resolve_pins(candidates, policy.pins, denied)
    selected = _select(families, denied, pinned, report)
    try:
        patches = parse_overlay(overlay, "overlay")
        _validate_overlay_targets(selected, patches)
        for variant in Variant:
            selected[variant] = apply_overlay(selected[variant], patches)
    except OverlayError as error:
        raise CompositionError(str(error)) from error
    _validate_unique_packages(selected)
    _validate_coverage(selected)
    return CompositionResult(selected, report)


def parse_exclusions(entries: list[Any]) -> tuple[_Exclusion, ...]:
    """Parse package denials, each of which applies to both variants."""
    result: list[_Exclusion] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise CompositionError(f"denylist[{index}] must be an object")
        unknown = set(entry) - {"id", "reason"}
        if unknown:
            raise CompositionError(
                f"denylist[{index}] has unknown field {min(unknown)!r}"
            )
        package_id, reason = entry.get("id"), entry.get("reason")
        if not isinstance(package_id, str) or not package_id.strip():
            raise CompositionError(f"denylist[{index}].id must be a nonempty string")
        if not isinstance(reason, str) or not reason.strip():
            raise CompositionError(
                f"denylist[{index}].reason must be a nonempty string"
            )
        result.append(_Exclusion(package_id, reason))
    return tuple(result)


def _families(candidates: list[App]) -> dict[str, list[App]]:
    families: dict[str, list[App]] = {}
    for candidate in candidates:
        source = candidate.provenance.source
        if source not in _PRECEDENCE:
            raise CompositionError(f"unknown candidate source {source!r}")
        if candidate.family is None:
            raise CompositionError(f"candidate {candidate.original_id!r} has no family")
        families.setdefault(candidate.family, []).append(candidate)
    return families


def _exclude(
    candidates: list[App],
    exclusions: tuple[_Exclusion, ...],
    report: CompositionReport,
) -> dict[tuple[int, Variant], str]:
    """Record each candidate a denial removes, keyed by candidate and variant."""
    denied: dict[tuple[int, Variant], str] = {}
    for rule in exclusions:
        matched = False
        for candidate in candidates:
            if candidate.id != rule.package_id:
                continue
            for variant in Variant:
                if variant in candidate.eligibility:
                    matched = True
                    denied[(id(candidate), variant)] = rule.reason
                    report.removals.append(
                        Removal(candidate.id, variant, rule.reason, candidate.family)
                    )
        if not matched:
            report.stale_exclusions.append(StaleExclusion(rule.package_id, rule.reason))
    return denied


def _resolve_pins(
    candidates: list[App],
    pins: tuple[Pin, ...],
    denied: dict[tuple[int, Variant], str],
) -> dict[PinKey, App]:
    """Validate every pin against the admitted candidates before any selection."""
    resolved: dict[PinKey, App] = {}
    # Sorted so the first failing pin reported does not depend on policy order.
    for pin in sorted(pins, key=lambda item: (item.family, item.variant.value)):
        label = f"pin for family {pin.family!r} target {pin.variant.value!r}"
        matches = [item for item in candidates if _matches_pin(item, pin.match)]
        if len(matches) != 1:
            raise CompositionError(f"{label} is missing or ambiguous")
        [winner] = matches
        if winner.family != pin.family:
            raise CompositionError(
                f"{label} names a candidate of family {winner.family!r}"
            )
        if pin.variant not in winner.eligibility:
            raise CompositionError(f"{label} is ineligible")
        denied_reason = denied.get((id(winner), pin.variant))
        if denied_reason is not None:
            raise CompositionError(f"{label} is denied: {denied_reason}")
        resolved[(pin.family, pin.variant)] = winner
    return resolved


def _select(
    families: dict[str, list[App]],
    denied: dict[tuple[int, Variant], str],
    pinned: dict[PinKey, App],
    report: CompositionReport,
) -> dict[Variant, list[ComposedApp]]:
    result = {variant: [] for variant in Variant}
    for family in sorted(families):
        family_candidates = families[family]
        for variant in Variant:
            available = [
                item
                for item in family_candidates
                if variant in item.eligibility and (id(item), variant) not in denied
            ]
            pinned_winner = pinned.get((family, variant))
            if pinned_winner is not None:
                winner, reason = pinned_winner, "pin"
            elif available:
                tier, reason = available, "source"
                if variant is Variant.DUAL and any(
                    item.dual_preferred for item in available
                ):
                    tier = [item for item in available if item.dual_preferred]
                    reason = "dual-preferred"
                elif variant is Variant.DUAL:
                    reason = "ordinary-fallback"
                rank = max(_PRECEDENCE[item.provenance.source] for item in tier)
                winners = [
                    item for item in tier if _PRECEDENCE[item.provenance.source] == rank
                ]
                if len({_identity(item) for item in winners}) != 1:
                    selectors = "; ".join(
                        f"source={source!r}, origin={origin!r}, original_id={original_id!r}, url={url!r}"
                        for source, origin, original_id, url in sorted(
                            {_identity(item) for item in winners}
                        )
                    )
                    raise CompositionError(
                        f"family {family!r} target {variant.value!r} has ambiguous winning candidates: {selectors}"
                    )
                winner = winners[0]
            else:
                continue
            report.selections.append(
                FamilySelection(
                    family,
                    variant,
                    winner.original_id or winner.id,
                    winner.id,
                    winner.url,
                    winner.provenance.source,
                    winner.origin or winner.provenance.source,
                    reason,
                    tuple(
                        ConsideredCandidate(
                            item.provenance.source,
                            item.origin or item.provenance.source,
                            item.original_id or item.id,
                            item.url,
                        )
                        for item in sorted(available, key=_identity)
                        if item is not winner
                    ),
                )
            )
            result[variant].append(ComposedApp(family, _import_data(winner)))
    for values in result.values():
        values.sort(key=lambda item: (item.family, item.id, item.url))
    return result


def _identity(app: App) -> tuple[str, str, str, str]:
    return (
        app.provenance.source,
        app.origin or app.provenance.source,
        app.original_id or app.id,
        rendered_key(app.id, app.url)[1],
    )


def _matches_pin(app: App, selector: CandidateSelector) -> bool:
    return (
        app.provenance.source == selector.source
        and (app.origin or app.provenance.source) == selector.origin
        and (app.original_id or app.id) == selector.id
        and rendered_key(app.id, app.url)[1] == selector.url
    )


def _validate_unique_packages(apps: dict[Variant, list[ComposedApp]]) -> None:
    for variant, values in apps.items():
        seen: dict[str, str] = {}
        for app in values:
            if app.id in seen and seen[app.id] != app.family:
                raise CompositionError(
                    f"target {variant.value!r} selects package id {app.id!r} for distinct families {seen[app.id]!r} and {app.family!r}"
                )
            seen[app.id] = app.family


def _validate_coverage(apps: dict[Variant, list[ComposedApp]]) -> None:
    dual_families = {app.family for app in apps[Variant.DUAL]}
    missing = [
        single.family
        for single in apps[Variant.SINGLE]
        if single.family not in dual_families
    ]
    if missing:
        raise CompositionError(
            "dual-screen variant is missing app family/families: "
            + ", ".join(sorted(missing))
        )


def _validate_overlay_targets(
    apps: dict[Variant, list[ComposedApp]], patches: tuple[OverlayPatch, ...]
) -> None:
    """Require each record to match a selected entry in at least one variant."""
    selected = {
        rendered_key(app.id, app.url) for values in apps.values() for app in values
    }
    missing = sorted(item.key for item in patches if item.key not in selected)
    if missing:
        raise OverlayError(f"overlay has no selected target for {missing!r}")


def _import_data(app: App) -> dict[str, Any]:
    data = deepcopy(app.raw)
    data.update(
        {
            "id": app.id,
            "url": app.url,
            "name": app.name,
            "overrideSource": app.source_type.value,
            "categories": list(app.categories),
            "additionalSettings": deepcopy(app.additional_settings),
        }
    )
    return data
