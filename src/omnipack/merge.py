"""Compose source candidates into device-specific app-family selections."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
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
from omnipack.model import ASSIGNABLE_CATEGORIES, App, Category, Source, Variant
from omnipack.overlay import (
    ComposedApp,
    OverlayError,
    OverlayPatch,
    apply_overlay,
    parse_overlay,
    patch_object,
)
from omnipack.render import RenderError, canonical_serialization, published_form
from omnipack.report_model import SelectionReason
from omnipack.source_registry import PRECEDENCE
from omnipack.urls import normalize_project_url, parse_project_url

_PRECEDENCE = {source: rank for rank, source in enumerate(PRECEDENCE)}


class CompositionError(ValueError):
    """Candidate data or curation rules cannot produce a valid composition."""


@dataclass(frozen=True, slots=True)
class Removal:
    """A denial that removed candidates from `variants`, with the families
    they belonged to.
    """

    url: str
    reason: str
    variants: tuple[Variant, ...]
    families: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StaleExclusion:
    url: str
    reason: str


@dataclass(frozen=True, slots=True)
class ConsideredCandidate:
    """A candidate that was available for a selection and did not win it."""

    source: Source
    origin: str
    id: str
    url: str


@dataclass(frozen=True, slots=True)
class FamilySelection:
    """One family's winner for one variant, why it won and what it beat.

    `considered` holds the family's other candidates not denied in the
    variant; denied ones appear among the removals.
    """

    family: str
    variant: Variant
    id: str
    url: str
    source: Source
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


@dataclass(frozen=True, slots=True)
class RedundantOverlayKeys:
    """An overlay record's patch keys that change no published entry.

    Each key is the dotted path to a leaf of the patch, the keys along it
    joined with `.`.
    """

    url: str
    keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ListingSource:
    """A source listing an extra's project, with the fields whose published
    values differ between the extra and that source's candidates there.

    A settings field is named `additionalSettings.<key>`; `variants` names a
    difference in build kind, which decides the pack each is preferred in, and
    `unpublishable` a candidate that rendering rejects.
    """

    source: Source
    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ListedExtra:
    """A selected extra that another source also lists at its project URL,
    identified by its normalized URL and published package id.
    """

    url: str
    id: str
    sources: tuple[ListingSource, ...]


@dataclass(slots=True)
class CompositionReport:
    removals: list[Removal] = field(default_factory=list)
    stale_exclusions: list[StaleExclusion] = field(default_factory=list)
    selections: list[FamilySelection] = field(default_factory=list)
    same_rank_ties: list[SameRankTie] = field(default_factory=list)
    uncategorized_families: list[UncategorizedFamily] = field(default_factory=list)
    # Category map keys that set no selected entry's category.
    stale_category_assignments: list[str] = field(default_factory=list)
    repeated_ids: list[RepeatedId] = field(default_factory=list)
    # Overlay records with patch keys that change no published entry.
    redundant_overlay_keys: list[RedundantOverlayKeys] = field(default_factory=list)
    extras_listed_by_catalog: list[ListedExtra] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CompositionResult:
    apps: dict[Variant, list[ComposedApp]]
    report: CompositionReport


@dataclass(frozen=True, slots=True)
class Exclusion:
    """A project denial: every candidate at `url`, a normalized URL, is
    removed from each of `variants`.
    """

    url: str
    reason: str
    variants: frozenset[Variant]


def compose(
    candidates: list[App],
    denylist: list[dict[str, Any]],
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
    denied = _exclude(candidates, exclusions, report)
    formed = tuple(
        item for item in candidates if len(denied.get(id(item), {})) < len(Variant)
    )
    pinned = _resolve_pins(candidates, formed, policy.pins, denied)
    selected = _select(_families(formed), pinned, denied, report)
    try:
        patches = parse_overlay(overlay, "overlay")
        check_overlay_id_patches(policy, patches)
        _validate_overlay_targets(selected, patches)
        report.redundant_overlay_keys.extend(
            _redundant_overlay_keys(
                (app for values in selected.values() for app in values), patches
            )
        )
        for variant in Variant:
            selected[variant] = apply_overlay(selected[variant], patches)
    except (OverlayError, CompositionPolicyError) as error:
        raise CompositionError(str(error)) from error
    report.extras_listed_by_catalog.extend(
        _listed_extras(report.selections, selected, formed, patches)
    )
    applied = _assign_categories(selected, policy)
    report.uncategorized_families.extend(_uncategorized_families(selected))
    report.stale_category_assignments.extend(sorted(set(policy.categories) - applied))
    report.repeated_ids.extend(_repeated_ids(selected))
    return CompositionResult(selected, report)


def parse_exclusions(entries: list[Any]) -> tuple[Exclusion, ...]:
    """Parse project denials; one without `packs` applies to both variants."""
    result: list[Exclusion] = []
    for index, entry in enumerate(entries):
        label = f"denylist[{index}]"
        if not isinstance(entry, dict):
            raise CompositionError(f"{label} must be an object")
        unknown = set(entry) - {"url", "reason", "packs"}
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
        result.append(Exclusion(normalized, reason, _denied_packs(entry, label)))
    return tuple(result)


def _denied_packs(entry: dict[str, Any], label: str) -> frozenset[Variant]:
    if "packs" not in entry:
        return frozenset(Variant)
    packs = entry["packs"]
    names = {variant.value for variant in Variant}
    if (
        not isinstance(packs, list)
        or not packs
        or not all(isinstance(item, str) and item in names for item in packs)
        or len(set(packs)) != len(packs)
    ):
        raise CompositionError(
            f"{label}.packs must be a nonempty list of distinct pack names "
            f"from {sorted(names)!r}"
        )
    return frozenset(Variant(item) for item in packs)


def _families(candidates: tuple[App, ...]) -> dict[str, list[App]]:
    families: dict[str, list[App]] = {}
    for candidate in candidates:
        families.setdefault(assigned_family(candidate), []).append(candidate)
    return families


def _exclude(
    candidates: list[App],
    exclusions: tuple[Exclusion, ...],
    report: CompositionReport,
) -> dict[int, dict[Variant, str]]:
    """Record, per candidate, each variant a denial removes it from and why.

    A denial is reported once, under its URL, with its variants and every
    family whose candidates it removed. It is stale only when no candidate is
    at its URL.
    """
    denied: dict[int, dict[Variant, str]] = {}
    by_url: dict[str, list[App]] = {}
    for candidate in candidates:
        by_url.setdefault(normalize_project_url(candidate.url), []).append(candidate)
    for rule in exclusions:
        matched = by_url.get(rule.url, [])
        if not matched:
            report.stale_exclusions.append(StaleExclusion(rule.url, rule.reason))
            continue
        for candidate in matched:
            for variant in rule.variants:
                denied.setdefault(id(candidate), {})[variant] = rule.reason
        report.removals.append(
            Removal(
                rule.url,
                rule.reason,
                tuple(variant for variant in Variant if variant in rule.variants),
                tuple(sorted({assigned_family(candidate) for candidate in matched})),
            )
        )
    return denied


def _resolve_pins(
    candidates: list[App],
    formed: tuple[App, ...],
    pins: tuple[Pin, ...],
    denied: dict[int, dict[Variant, str]],
) -> dict[PinKey, App]:
    """Validate every pin against the admitted candidates before any selection.

    A pin fails when a denial removes its candidate from the pin's variant.
    A candidate denied in every variant forms no family, so its pin fails on
    that denial before the family comparison.
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
        denied_reason = denied.get(id(candidate), {}).get(pin.variant)
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
        resolved[(pin.family, pin.variant)] = winner
    return resolved


def _select(
    families: dict[str, list[App]],
    pinned: dict[PinKey, App],
    denied: dict[int, dict[Variant, str]],
    report: CompositionReport,
) -> dict[Variant, list[ComposedApp]]:
    """Select each family's winner per variant.

    Each variant prefers its own build kind, dual-screen builds in dual and
    baseline builds in single, and falls back to the other kind when the
    family has none of its own left after denials.
    """
    result = {variant: [] for variant in Variant}
    for family in sorted(families):
        family_candidates = families[family]
        for variant in Variant:
            available = [
                item
                for item in family_candidates
                if variant not in denied.get(id(item), {})
            ]
            pinned_winner = pinned.get((family, variant))
            if pinned_winner is not None:
                winner, reason = pinned_winner, SelectionReason.PIN
            elif available:
                dual = variant is Variant.DUAL
                preferred = [item for item in available if item.dual_screen == dual]
                tier = preferred or available
                if not dual:
                    reason = SelectionReason.SOURCE
                elif preferred:
                    reason = SelectionReason.DUAL_PREFERRED
                else:
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


def _listed_extras(
    selections: list[FamilySelection],
    apps: dict[Variant, list[ComposedApp]],
    formed: tuple[App, ...],
    patches: tuple[OverlayPatch, ...],
) -> list[ListedExtra]:
    """Selected extras that another source lists at the same project URL.

    Only the candidates the extra's own family selection considered count, so
    a candidate that a split family rule puts in another family never lists
    it, and neither does a denied one. Each record is merged across variants:
    its sources are unioned, and so are each source's differing fields, so
    two candidates of one source at the URL both keep their differences.
    """
    by_selector = {candidate_selector(item).key: item for item in formed}
    overlay = {item.url: item.patch for item in patches}
    found: dict[tuple[str, str], dict[Source, set[str]]] = {}
    for selection in selections:
        if selection.source is not Source.EXTRAS:
            continue
        url = normalize_project_url(selection.url)
        listings = [
            item
            for item in selection.considered
            if item.source is not Source.EXTRAS
            and normalize_project_url(item.url) == url
        ]
        if not listings:
            continue
        extra = next(
            app for app in apps[selection.variant] if app.family == selection.family
        )
        winner = by_selector[
            CandidateSelector(selection.source, selection.origin, selection.id, url).key
        ]
        sources = found.setdefault((url, extra.id), {})
        for listing in listings:
            candidate = by_selector[
                CandidateSelector(listing.source, listing.origin, listing.id, url).key
            ]
            fields = sources.setdefault(listing.source, set())
            fields.update(_differing_fields(extra, candidate, overlay.get(url)))
            if candidate.dual_screen != winner.dual_screen:
                fields.add("variants")
    return [
        ListedExtra(
            url,
            package_id,
            tuple(
                ListingSource(source, tuple(sorted(fields)))
                for source, fields in sorted(sources.items())
            ),
        )
        for (url, package_id), sources in sorted(found.items())
    ]


def _redundant_overlay_keys(
    apps: Iterable[ComposedApp], overlay: tuple[OverlayPatch, ...]
) -> list[RedundantOverlayKeys]:
    """Each record's keys that leave every targeted entry's published form as is.

    `apps` are the selected entries of every variant before overlays apply.
    Each leaf of a record's patch (any value that is not an object; an array
    counts whole) is merged alone into each entry the record targets, and it
    changes nothing when the published forms with and without it are equal
    for every target. A null is judged the same way, so deleting an absent key
    or a defaulted setting changes nothing. A leaf whose patched entry cannot
    be published counts as changing it, so this never raises; the build's own
    rendering reports that error.
    """
    targets: dict[str, list[ComposedApp]] = {}
    for app in apps:
        targets.setdefault(normalize_project_url(app.url), []).append(app)
    result: list[RedundantOverlayKeys] = []
    for record in overlay:
        entries = targets.get(record.url)
        if not entries:
            continue
        try:
            baselines = [published_form(app) for app in entries]
        except RenderError:
            continue
        keys = tuple(
            sorted(
                ".".join(path)
                for path, value in _leaves(record.patch)
                if all(
                    _unchanged(app, baseline, _leaf_patch(path, value))
                    for app, baseline in zip(entries, baselines, strict=True)
                )
            )
        )
        if keys:
            result.append(RedundantOverlayKeys(record.url, keys))
    result.sort(key=lambda item: item.url)
    return result


def _leaves(
    patch: dict[str, Any], path: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], Any]]:
    for key, value in patch.items():
        if isinstance(value, dict):
            yield from _leaves(value, (*path, key))
        else:
            yield (*path, key), value


def _leaf_patch(path: tuple[str, ...], value: Any) -> dict[str, Any]:
    """A patch holding `value` alone at `path`."""
    patch: Any = value
    for key in reversed(path):
        patch = {key: patch}
    return patch


def _unchanged(app: ComposedApp, baseline: object, patch: dict[str, Any]) -> bool:
    patched = patch_object(app.data, patch)
    try:
        return published_form(ComposedApp(app.family, patched)) == baseline
    except RenderError:
        return False


_ABSENT = object()


def _differing_fields(
    extra: ComposedApp, candidate: App, patch: dict[str, Any] | None
) -> set[str]:
    """Fields whose published values differ between the selected extra and the
    candidate's import data with the same overlay record applied.

    Top-level keys and settings keys are compared; categories are the category
    map's and the project URL matches by construction. A candidate whose data
    cannot be published differs as `unpublishable`, since retiring the extra
    would make the build render it. An extra that cannot be published is
    compared on nothing; the build's own rendering reports it.
    """
    data = _import_data(candidate)
    if patch is not None:
        data = patch_object(data, patch)
    try:
        ours = published_form(extra)
    except RenderError:
        return set()
    try:
        theirs = published_form(ComposedApp(extra.family, data))
    except RenderError:
        return {"unpublishable"}
    fields = {
        key
        for key in (ours.keys() | theirs.keys()) - {"url", "additionalSettings"}
        if ours.get(key, _ABSENT) != theirs.get(key, _ABSENT)
    }
    our_settings, their_settings = (
        ours["additionalSettings"],
        theirs["additionalSettings"],
    )
    fields.update(
        f"additionalSettings.{key}"
        for key in our_settings.keys() | their_settings.keys()
        if our_settings.get(key, _ABSENT) != their_settings.get(key, _ABSENT)
    )
    return fields


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
