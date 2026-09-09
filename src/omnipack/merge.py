"""Compose source candidates into the single- and dual-screen packs."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from omnipack.model import App, Variant
from omnipack.overlay import ComposedApp, OverlayError, apply_overlay

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


@dataclass(frozen=True, slots=True)
class StaleExclusion:
    package_id: str
    variant: Variant | None
    reason: str


@dataclass(slots=True)
class CompositionReport:
    displacements: list[Displacement] = field(default_factory=list)
    removals: list[Removal] = field(default_factory=list)
    stale_exclusions: list[StaleExclusion] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CompositionResult:
    apps: dict[Variant, list[ComposedApp]]
    report: CompositionReport


def compose(
    candidates: list[App],
    denylist: list[dict[str, str]],
    common_overlay: dict[str, object],
    dual_overlay: dict[str, object],
    *,
    report: CompositionReport | None = None,
) -> CompositionResult:
    """Run all composition stages in their required order."""
    if report is None:
        report = CompositionReport()
    apps = _union(candidates, report)
    dual_exemptions = _apply_denylist(apps, denylist, report)
    _validate_targets(apps, common_overlay, dual_overlay)
    try:
        for variant in Variant:
            apps[variant] = apply_overlay(apps[variant], common_overlay)
        apps[Variant.DUAL] = apply_overlay(apps[Variant.DUAL], dual_overlay)
    except OverlayError as error:
        raise CompositionError(str(error)) from error
    missing = (
        {app.id for app in apps[Variant.SINGLE]}
        - {app.id for app in apps[Variant.DUAL]}
        - dual_exemptions
    )
    if missing:
        raise CompositionError(
            "dual-screen variant is missing package id(s): "
            + ", ".join(sorted(missing))
        )
    return CompositionResult(apps, report)


def _union(
    candidates: list[App], report: CompositionReport
) -> dict[Variant, list[ComposedApp]]:
    grouped: dict[tuple[Variant, str, str], list[App]] = {}
    for candidate in candidates:
        source = candidate.provenance.source
        if source not in _PRECEDENCE:
            raise CompositionError(f"unknown candidate source {source!r}")
        grouped.setdefault((candidate.variant, candidate.id, source), []).append(
            candidate
        )

    collapsed: dict[tuple[Variant, str], list[App]] = {}
    for (variant, package_id, source), duplicates in grouped.items():
        first = duplicates[0]
        if any(candidate != first for candidate in duplicates[1:]):
            raise CompositionError(
                f"source {source!r} contributed differing candidates for "
                f"variant {variant.value!r}, package id {package_id!r}"
            )
        collapsed.setdefault((variant, package_id), []).append(first)

    result = {variant: [] for variant in Variant}
    for (variant, package_id), choices in collapsed.items():
        winner = max(choices, key=lambda app: _PRECEDENCE[app.provenance.source])
        winner_data = _import_data(winner)
        for loser in choices:
            if loser is winner:
                continue
            report.displacements.append(
                Displacement(
                    package_id,
                    variant,
                    winner.provenance.source,
                    loser.provenance.source,
                    _differing_fields(winner_data, _import_data(loser)),
                )
            )
        result[variant].append(
            ComposedApp(variant, winner.provenance, deepcopy(winner_data))
        )
    for variant_apps in result.values():
        variant_apps.sort(key=lambda app: app.id)
    return result


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


def _apply_denylist(
    apps: dict[Variant, list[ComposedApp]],
    denylist: list[dict[str, str]],
    report: CompositionReport,
) -> set[str]:
    dual_exemptions: set[str] = set()
    for entry in denylist:
        package_id = entry.get("id", "")
        reason = entry.get("reason", "")
        variant_value = entry.get("variant")
        if variant_value is None:
            variants = tuple(Variant)
        else:
            try:
                variants = (Variant(variant_value),)
            except ValueError as error:
                raise CompositionError(
                    f"denylist entry {package_id!r} has unknown variant "
                    f"{variant_value!r}"
                ) from error
        if Variant.DUAL in variants:
            dual_exemptions.add(package_id)
        matched = False
        for variant in variants:
            kept: list[ComposedApp] = []
            for app in apps[variant]:
                if app.id == package_id:
                    matched = True
                    report.removals.append(Removal(package_id, variant, reason))
                else:
                    kept.append(app)
            apps[variant] = kept
        if not matched:
            report.stale_exclusions.append(
                StaleExclusion(
                    package_id,
                    None if variant_value is None else variants[0],
                    reason,
                )
            )
    return dual_exemptions


def _validate_targets(
    apps: dict[Variant, list[ComposedApp]],
    common_overlay: dict[str, object],
    dual_overlay: dict[str, object],
) -> None:
    all_ids = {app.id for variant_apps in apps.values() for app in variant_apps}
    dual_ids = {app.id for app in apps[Variant.DUAL]}
    missing_common = set(common_overlay) - all_ids
    if missing_common:
        raise CompositionError(
            "common overlay has no target for package id(s): "
            + ", ".join(sorted(missing_common))
        )
    missing_dual = set(dual_overlay) - dual_ids
    if missing_dual:
        raise CompositionError(
            "dual-screen overlay has no target for package id(s): "
            + ", ".join(sorted(missing_dual))
        )
