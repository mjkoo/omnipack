"""Compose source candidates into device-specific app-family selections."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from omnipack.composition_policy import (
    CandidateSelector,
    CompositionPolicy,
    CompositionPolicyError,
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
class Displacement:
    package_id: str
    variant: Variant
    winner_source: str
    loser_source: str
    differing_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Removal:
    package_id: str
    variant: Variant
    reason: str
    family: str | None = None


@dataclass(frozen=True, slots=True)
class StaleExclusion:
    package_id: str | None
    variant: Variant | None
    reason: str
    family: str | None = None


@dataclass(frozen=True, slots=True)
class SelectionAlternative:
    original_id: str
    effective_id: str
    url: str
    source: str
    origin: str
    eligibility: tuple[Variant, ...]
    dual_preferred: bool
    differing_fields: tuple[str, ...]
    loss_reason: str
    excluded_reason: str | None = None


@dataclass(frozen=True, slots=True)
class FamilySelection:
    family: str
    variant: Variant
    original_id: str
    effective_id: str
    url: str
    source: str
    origin: str
    eligibility: tuple[Variant, ...]
    dual_preferred: bool
    reason: str
    alternatives: tuple[SelectionAlternative, ...]


@dataclass(slots=True)
class CompositionReport:
    displacements: list[Displacement] = field(default_factory=list)
    removals: list[Removal] = field(default_factory=list)
    stale_exclusions: list[StaleExclusion] = field(default_factory=list)
    selections: list[FamilySelection] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CompositionResult:
    apps: dict[Variant, list[ComposedApp]]
    report: CompositionReport


@dataclass(frozen=True, slots=True)
class _Exclusion:
    package_id: str | None
    family: str | None
    variant: Variant | None
    reason: str

    def applies(self, candidate: App, variant: Variant) -> bool:
        return (self.variant is None or self.variant is variant) and (
            candidate.id == self.package_id or candidate.family == self.family
        )


def compose(
    candidates: list[App],
    denylist: list[dict[str, str]],
    common_overlay: object,
    dual_overlay: object,
    *,
    policy: CompositionPolicy,
    report: CompositionReport | None = None,
) -> CompositionResult:
    report = report or CompositionReport()
    exclusions = _parse_exclusions(denylist)
    try:
        candidates = list(
            apply_composition_policy(policy, candidates, validate_pins=False).candidates
        )
    except CompositionPolicyError as error:
        raise CompositionError(str(error)) from error
    pins = {(pin.family, pin.variant): pin.match for pin in policy.pins}
    selected = _select(candidates, exclusions, pins, report)
    try:
        common = parse_overlay(common_overlay, "common overlay")
        dual = parse_overlay(dual_overlay, "dual-screen overlay")
        _validate_overlay_targets(selected, common, dual)
        for variant in Variant:
            selected[variant] = apply_overlay(selected[variant], common)
        selected[Variant.DUAL] = apply_overlay(selected[Variant.DUAL], dual)
    except OverlayError as error:
        raise CompositionError(str(error)) from error
    _validate_unique_packages(selected)
    _validate_coverage(selected, exclusions)
    return CompositionResult(selected, report)


def _parse_exclusions(entries: list[dict[str, str]]) -> tuple[_Exclusion, ...]:
    result: list[_Exclusion] = []
    for index, entry in enumerate(entries):
        unknown = set(entry) - {"id", "family", "variant", "reason"}
        if unknown:
            raise CompositionError(
                f"denylist[{index}] has unknown field {min(unknown)!r}"
            )
        package_id, family = entry.get("id"), entry.get("family")
        if (("id" in entry) + ("family" in entry)) != 1:
            raise CompositionError(
                f"denylist[{index}] must contain exactly one of id or family"
            )
        selector, reason = (
            package_id if package_id is not None else family,
            entry.get("reason"),
        )
        if not isinstance(selector, str) or not selector.strip():
            raise CompositionError(
                f"denylist[{index}] selector must be a nonempty string"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise CompositionError(
                f"denylist[{index}].reason must be a nonempty string"
            )
        variant_value = entry.get("variant")
        try:
            variant = None if variant_value is None else Variant(variant_value)
        except ValueError as error:
            raise CompositionError(
                f"denylist entry {selector!r} has unknown variant {variant_value!r}"
            ) from error
        result.append(_Exclusion(package_id, family, variant, reason))
    return tuple(result)


def _select(
    candidates: list[App],
    exclusions: tuple[_Exclusion, ...],
    pins: dict[PinKey, CandidateSelector],
    report: CompositionReport,
) -> dict[Variant, list[ComposedApp]]:
    families: dict[str, list[App]] = {}
    for candidate in candidates:
        source = candidate.provenance.source
        if source not in _PRECEDENCE:
            raise CompositionError(f"unknown candidate source {source!r}")
        if candidate.family is None:
            raise CompositionError(f"candidate {candidate.original_id!r} has no family")
        families.setdefault(candidate.family, []).append(candidate)
    denied: dict[tuple[int, Variant], str] = {}
    for rule in exclusions:
        matched = False
        for candidate in candidates:
            for variant in Variant:
                if variant in candidate.eligibility and rule.applies(
                    candidate, variant
                ):
                    matched = True
                    denied[(id(candidate), variant)] = rule.reason
                    report.removals.append(
                        Removal(candidate.id, variant, rule.reason, candidate.family)
                    )
        if not matched:
            report.stale_exclusions.append(
                StaleExclusion(rule.package_id, rule.variant, rule.reason, rule.family)
            )
    result = {variant: [] for variant in Variant}
    processed_pins: set[PinKey] = set()
    for family in sorted(families):
        family_candidates = families[family]
        for variant in Variant:
            eligible = [
                item for item in family_candidates if variant in item.eligibility
            ]
            excluded: list[tuple[App, str]] = []
            available: list[App] = []
            for candidate in eligible:
                denied_reason = denied.get((id(candidate), variant))
                if denied_reason is not None:
                    excluded.append((candidate, denied_reason))
                else:
                    available.append(candidate)
            pin_key = (family, variant)
            pin = pins.get(pin_key)
            if pin is not None:
                processed_pins.add(pin_key)
                matches = [
                    item for item in family_candidates if _matches_pin(item, pin)
                ]
                if len(matches) != 1:
                    raise CompositionError(
                        f"pin for family {family!r} target {variant.value!r} is missing or ambiguous"
                    )
                winner = matches[0]
                if variant not in winner.eligibility:
                    raise CompositionError(
                        f"pin for family {family!r} target {variant.value!r} is ineligible"
                    )
                denied_reason = denied.get((id(winner), variant))
                if denied_reason is not None:
                    raise CompositionError(
                        f"pin for family {family!r} target {variant.value!r} is denied: {denied_reason}"
                    )
                reason = "pin"
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
                    raise CompositionError(
                        f"family {family!r} target {variant.value!r} has ambiguous winning candidates"
                    )
                winner = winners[0]
            else:
                continue
            winner_data = _import_data(winner)
            loser_pairs = [
                (item, None)
                for item in family_candidates
                if item is not winner and all(item is not x for x, _ in excluded)
            ] + excluded
            alternatives = tuple(
                _alternative(item, winner, winner_data, denied, variant, reason)
                for item, denied in sorted(
                    loser_pairs, key=lambda pair: _identity(pair[0])
                )
            )
            for alternative in alternatives:
                if alternative.excluded_reason is None:
                    report.displacements.append(
                        Displacement(
                            winner.id,
                            variant,
                            winner.provenance.source,
                            alternative.source,
                            alternative.differing_fields,
                        )
                    )
            report.selections.append(
                FamilySelection(
                    family,
                    variant,
                    winner.original_id or winner.id,
                    winner.id,
                    winner.url,
                    winner.provenance.source,
                    winner.origin or winner.provenance.source,
                    tuple(sorted(winner.eligibility, key=lambda item: item.value)),
                    winner.dual_preferred,
                    reason,
                    alternatives,
                )
            )
            result[variant].append(
                ComposedApp(
                    variant,
                    winner.provenance,
                    deepcopy(winner_data),
                    family,
                    winner.original_id,
                    winner.origin,
                )
            )
    missing_pins = set(pins) - processed_pins
    if missing_pins:
        family, variant = min(missing_pins, key=lambda item: (item[0], item[1].value))
        raise CompositionError(
            f"pin for family {family!r} target {variant.value!r} is missing or ambiguous"
        )
    for values in result.values():
        values.sort(key=lambda item: (item.family or "", item.id, item.url))
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


def _alternative(
    app: App,
    winner: App,
    winner_data: dict[str, Any],
    denied: str | None,
    variant: Variant,
    selection_reason: str,
) -> SelectionAlternative:
    if variant not in app.eligibility:
        loss_reason = "ineligible"
    elif denied is not None:
        loss_reason = "excluded"
    elif selection_reason == "pin":
        loss_reason = "not-pinned"
    elif selection_reason == "dual-preferred" and not app.dual_preferred:
        loss_reason = "outside-preferred-tier"
    elif _PRECEDENCE[app.provenance.source] < _PRECEDENCE[winner.provenance.source]:
        loss_reason = "lower-source-precedence"
    else:
        loss_reason = "duplicate-winning-identity"
    return SelectionAlternative(
        app.original_id or app.id,
        app.id,
        app.url,
        app.provenance.source,
        app.origin or app.provenance.source,
        tuple(sorted(app.eligibility, key=lambda item: item.value)),
        app.dual_preferred,
        _differing_fields(winner_data, _import_data(app)),
        loss_reason,
        denied,
    )


def _validate_unique_packages(apps: dict[Variant, list[ComposedApp]]) -> None:
    for variant, values in apps.items():
        seen: dict[str, str | None] = {}
        for app in values:
            if app.id in seen and seen[app.id] != app.family:
                raise CompositionError(
                    f"target {variant.value!r} selects package id {app.id!r} for distinct families {seen[app.id]!r} and {app.family!r}"
                )
            seen[app.id] = app.family


def _validate_coverage(
    apps: dict[Variant, list[ComposedApp]], exclusions: tuple[_Exclusion, ...]
) -> None:
    dual_families = {app.family for app in apps[Variant.DUAL]}
    missing = []
    for single in apps[Variant.SINGLE]:
        if single.family in dual_families:
            continue
        if any(
            rule.variant in (None, Variant.DUAL)
            and (rule.family == single.family or rule.package_id == single.id)
            for rule in exclusions
        ):
            continue
        missing.append(single.family or single.id)
    if missing:
        raise CompositionError(
            "dual-screen variant is missing app family/families: "
            + ", ".join(sorted(missing))
        )


def _validate_overlay_targets(
    apps: dict[Variant, list[ComposedApp]],
    common: tuple[OverlayPatch, ...],
    dual: tuple[OverlayPatch, ...],
) -> None:
    all_keys = {
        rendered_key(app.id, app.url) for values in apps.values() for app in values
    }
    dual_keys = {rendered_key(app.id, app.url) for app in apps[Variant.DUAL]}
    missing_common = sorted(item.key for item in common if item.key not in all_keys)
    missing_dual = sorted(item.key for item in dual if item.key not in dual_keys)
    if missing_common:
        raise OverlayError(
            f"common overlay has no selected target for {missing_common!r}"
        )
    if missing_dual:
        raise OverlayError(
            f"dual-screen overlay has no selected target for {missing_dual!r}"
        )


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


def _differing_fields(left: dict[str, Any], right: dict[str, Any]) -> tuple[str, ...]:
    keys = left.keys() | right.keys()
    return tuple(
        sorted(
            key
            for key in keys
            if key not in left or key not in right or left[key] != right[key]
        )
    )
