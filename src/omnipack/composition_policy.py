"""Strict, pure interpretation of device-aware composition policy."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from omnipack.model import App, Variant
from omnipack.urls import normalize_project_url

RenderedKey = tuple[str, str]
PinKey = tuple[str, Variant]

SOURCES = frozenset({"rjny", "bboi", "extras", "codm2000"})
ORIGINS = frozenset(
    {
        "rjny-catalog",
        "bboi-standard-asset",
        "bboi-dual-asset",
        "extras",
        "codm-generated",
    }
)
_SOURCE_ORIGINS = {
    "rjny": frozenset({"rjny-catalog"}),
    "bboi": frozenset({"bboi-standard-asset", "bboi-dual-asset"}),
    "extras": frozenset({"extras"}),
    "codm2000": frozenset({"codm-generated"}),
}


class CompositionPolicyError(ValueError):
    """The composition policy is malformed or inconsistent with candidates."""


@dataclass(frozen=True, slots=True)
class CandidateSelector:
    source: str
    origin: str
    id: str
    url: str

    @property
    def key(self) -> tuple[str, str, str, str]:
        return self.source, self.origin, self.id, self.url


@dataclass(frozen=True, slots=True)
class CandidateRule:
    match: CandidateSelector
    rationale: str
    family: str | None = None
    package_id: str | None = None


@dataclass(frozen=True, slots=True)
class Pin:
    family: str
    variant: Variant
    match: CandidateSelector
    rationale: str


@dataclass(frozen=True, slots=True)
class CompositionPolicy:
    candidate_rules: tuple[CandidateRule, ...]
    pins: tuple[Pin, ...]
    # The explicit family each `family` rule assigns, by the rendered key its
    # builds end up with. Identity-only rules project nothing.
    projections: dict[RenderedKey, str]
    projected_pins: dict[PinKey, RenderedKey]

    def rendered_family(self, package_id: str, url: str) -> str:
        """Interpret a current rendered entry without build-report state."""
        return self.projections.get(
            rendered_key(package_id, url), f"package:{package_id}"
        )


def rendered_key(package_id: str, url: str) -> RenderedKey:
    return package_id, normalize_project_url(url)


@dataclass(frozen=True, slots=True)
class Pairing:
    """A single-screen and a dual-screen entry that pair, or one left unpaired.

    The label is the explicit family either entry projects, otherwise
    `package:<id>` after the entry's package id.
    """

    label: str
    single: RenderedKey | None
    dual: RenderedKey | None


@dataclass(frozen=True, slots=True)
class Pairings:
    """Rendered entries paired without provenance.

    Package ids and explicit families repeated within a variant are listed
    here, and every entry carrying one, in either variant, is left out of
    `pairs`, so no pairing depends on entry order.
    """

    pairs: tuple[Pairing, ...]
    repeated_ids: tuple[str, ...]
    repeated_families: tuple[str, ...]


def pair_entries(
    policy: CompositionPolicy,
    single: Sequence[RenderedKey],
    dual: Sequence[RenderedKey],
) -> Pairings:
    """Pair entries by package id, then by explicit family among the rest.

    Entries whose projections name different explicit families never pair.
    """
    family = policy.projections.get
    repeated_ids = _repeated([key[0] for key in single], [key[0] for key in dual])
    repeated_families = _repeated(
        [name for key in single if (name := family(key)) is not None],
        [name for key in dual if (name := family(key)) is not None],
    )

    def pairable(key: RenderedKey) -> bool:
        return key[0] not in repeated_ids and family(key) not in repeated_families

    singles = [key for key in single if pairable(key)]
    duals = [key for key in dual if pairable(key)]
    matched: dict[RenderedKey, RenderedKey] = {}
    dual_by_id = {key[0]: key for key in duals}
    for key in singles:
        other = dual_by_id.get(key[0])
        if other is not None and _compatible(family(key), family(other)):
            matched[key] = other
    paired_duals = set(matched.values())
    dual_by_family = {
        name: key
        for key in duals
        if key not in paired_duals and (name := family(key)) is not None
    }
    for key in singles:
        name = family(key)
        if key not in matched and name is not None and name in dual_by_family:
            matched[key] = dual_by_family[name]
    paired_duals = set(matched.values())

    def label(*keys: RenderedKey) -> str:
        names = [name for key in keys if (name := family(key)) is not None]
        return names[0] if names else f"package:{keys[0][0]}"

    pairs = [
        Pairing(label(key, matched[key]), key, matched[key])
        if key in matched
        else Pairing(label(key), key, None)
        for key in singles
    ]
    pairs.extend(
        Pairing(label(key), None, key) for key in duals if key not in paired_duals
    )
    return Pairings(
        tuple(pairs), tuple(sorted(repeated_ids)), tuple(sorted(repeated_families))
    )


def _compatible(first: str | None, second: str | None) -> bool:
    """Whether two projections leave room for one family."""
    return first is None or second is None or first == second


def _repeated(*variants: list[str]) -> set[str]:
    """Values occurring more than once within any one variant."""
    repeated: set[str] = set()
    for values in variants:
        seen: set[str] = set()
        for value in values:
            if value in seen:
                repeated.add(value)
            seen.add(value)
    return repeated


def parse_composition_policy(document: object) -> CompositionPolicy:
    root = _object(document, "composition policy")
    _fields(root, {"schemaVersion", "candidates", "pins"}, "policy")
    if type(root.get("schemaVersion")) is not int or root["schemaVersion"] != 1:
        raise CompositionPolicyError("schemaVersion must be integer 1")
    candidates_raw = _array(root.get("candidates"), "candidates")
    pins_raw = _array(root.get("pins"), "pins")

    rules = tuple(
        _parse_rule(value, index) for index, value in enumerate(candidates_raw)
    )
    selectors: set[tuple[str, str, str, str]] = set()
    projections: dict[RenderedKey, str] = {}
    for rule in rules:
        if rule.match.key in selectors:
            raise CompositionPolicyError(
                f"duplicate candidate selector {_show(rule.match)}"
            )
        selectors.add(rule.match.key)
        if rule.family is None:
            continue
        key = rendered_key(rule.package_id or rule.match.id, rule.match.url)
        if projections.setdefault(key, rule.family) != rule.family:
            raise CompositionPolicyError(
                f"rendered key {key!r} has conflicting projections"
            )

    pins = tuple(_parse_pin(value, index) for index, value in enumerate(pins_raw))
    pin_keys: set[PinKey] = set()
    projected_pins: dict[PinKey, RenderedKey] = {}
    for pin in pins:
        key = (pin.family, pin.variant)
        if key in pin_keys:
            raise CompositionPolicyError(
                f"multiple pins for family {pin.family!r} target {pin.variant.value!r}"
            )
        pin_keys.add(key)
        rule = next((item for item in rules if item.match == pin.match), None)
        effective_id = rule.package_id if rule and rule.package_id else pin.match.id
        pinned = rendered_key(effective_id, pin.match.url)
        # Only an explicit projection is known here. Any other pin names the
        # family its candidate forms, which composition checks once it forms.
        projected = projections.get(pinned)
        if projected is not None and pin.family != projected:
            raise CompositionPolicyError(
                f"pin family {pin.family!r} target {pin.variant.value!r} conflicts "
                f"with projected family {projected!r}"
            )
        projected_pins[key] = pinned
    return CompositionPolicy(rules, pins, projections, projected_pins)


def load_composition_policy(data: str | bytes | bytearray) -> CompositionPolicy:
    """Decode policy JSON and apply the same strict shared interpretation."""
    try:
        document = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise CompositionPolicyError(
            f"composition policy is invalid JSON: {error}"
        ) from error
    return parse_composition_policy(document)


def apply_composition_policy(
    policy: CompositionPolicy, candidates: list[App] | tuple[App, ...]
) -> tuple[App, ...]:
    """Apply identity corrections once, requiring every rule selector.

    Each candidate's `family` becomes its own assignment: the explicit family
    projected at its effective id and URL, or `package:<effective id>`.
    `form_families` later joins the candidates that survive exclusions. Pins
    are left to composition, which validates them after processing exclusions
    so that a failed pin still leaves the exclusion diagnostics.
    """
    collapsed = _collapse(candidates)
    by_selector = {candidate_selector(app).key: app for app in collapsed}
    rules = {rule.match.key: rule for rule in policy.candidate_rules}
    for selector in rules:
        if selector not in by_selector:
            shown = CandidateSelector(*selector)
            raise CompositionPolicyError(
                f"selector {_show(shown)} matched no candidate"
            )

    _reject_track_only_conflicts(collapsed, rules)

    result: list[App] = []
    for app in collapsed:
        effective_id = _effective_id(app, rules.get(candidate_selector(app).key))
        family = policy.projections.get(
            rendered_key(effective_id, app.url), f"package:{effective_id}"
        )
        result.append(replace(app, id=effective_id, family=family))
    return tuple(result)


def form_families(candidates: Sequence[App]) -> tuple[App, ...]:
    """Join candidates transitively by shared effective id or explicit family.

    The caller passes only the candidates that survive exclusions and are
    eligible for some variant, each carrying its own assignment from
    `apply_composition_policy`. A family holding an explicit assignment takes
    that `app:` name; any other holds one effective id and keeps its
    `package:<id>` name. Two explicit families joined through a shared id fail.
    """
    parent = list(range(len(candidates)))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    # A default `package:<id>` assignment is the id itself, so joining on the
    # assignment and on the id together covers both kinds of shared identity.
    first: dict[str, int] = {}
    for index, app in enumerate(candidates):
        for key in (f"id:{app.id}", f"family:{app.family}"):
            parent[root(index)] = root(first.setdefault(key, index))

    groups: dict[int, list[int]] = {}
    for index in range(len(candidates)):
        groups.setdefault(root(index), []).append(index)
    names: dict[int, str] = {}
    for group, members in groups.items():
        apps = [candidates[index] for index in members]
        explicit = sorted(
            {family for app in apps if (family := _explicit_family(app)) is not None}
        )
        if len(explicit) > 1:
            raise CompositionPolicyError(_joined_families_message(explicit, apps))
        names[group] = explicit[0] if explicit else f"package:{apps[0].id}"
    return tuple(
        replace(app, family=names[root(index)]) for index, app in enumerate(candidates)
    )


def _explicit_family(app: App) -> str | None:
    """The candidate's own `app:` assignment, if it has one."""
    if app.family is not None and app.family.startswith("app:"):
        return app.family
    return None


def _joined_families_message(explicit: list[str], apps: list[App]) -> str:
    """Name the families and the candidates whose shared id joins them.

    A rule-less candidate carries a single id, so families can only meet at an
    id whose carriers hold two different explicit assignments.
    """
    carriers: dict[str, list[App]] = {}
    for app in apps:
        carriers.setdefault(app.id, []).append(app)
    joining = sorted(
        candidate_selector(app).key
        for members in carriers.values()
        if len({_explicit_family(app) for app in members} - {None}) > 1
        for app in members
    )
    return (
        f"explicit families {', '.join(map(repr, explicit))} join through a shared "
        f"package id: {'; '.join(map(repr, joining))}"
    )


def _reject_track_only_conflicts(
    collapsed: tuple[App, ...],
    rules: dict[tuple[str, str, str, str], CandidateRule],
) -> None:
    """Keep track-only identities out of reach of every rule and other candidate.

    This runs over all candidates before any rule is applied or any exclusion
    removes one, so a denial cannot hide the offending selector.
    """
    reserved = {app.id for app in collapsed if _is_track_only(app)}
    for app in collapsed:
        selector = candidate_selector(app)
        rule = rules.get(selector.key)
        if _is_track_only(app):
            if rule is not None and (
                rule.family is not None or rule.package_id is not None
            ):
                raise CompositionPolicyError(
                    f"track-only candidate {_show(selector)} cannot assign "
                    "family or packageId"
                )
        elif (effective_id := _effective_id(app, rule)) in reserved:
            raise CompositionPolicyError(
                f"reserved track-only id {effective_id!r} used by candidate "
                f"{_show(selector)}"
            )


def _is_track_only(app: App) -> bool:
    return app.additional_settings.get("trackOnly") is True


def _effective_id(app: App, rule: CandidateRule | None) -> str:
    return (rule.package_id if rule else None) or app.id


def _collapse(candidates: list[App] | tuple[App, ...]) -> tuple[App, ...]:
    unique: dict[tuple[str, str, str, str], App] = {}
    for app in candidates:
        selector = candidate_selector(app)
        previous = unique.get(selector.key)
        if previous is not None and previous != app:
            raise CompositionPolicyError(
                f"ambiguous original candidate identity {_show(selector)}"
            )
        unique[selector.key] = app
    return tuple(unique.values())


def candidate_selector(app: App) -> CandidateSelector:
    """The original identity a rule or pin names this candidate by."""
    return CandidateSelector(
        app.provenance.source,
        app.origin,
        app.original_id,
        normalize_project_url(app.url),
    )


def _parse_rule(value: object, index: int) -> CandidateRule:
    record = _object(value, f"candidates[{index}]")
    _fields(
        record, {"match", "family", "packageId", "rationale"}, f"candidates[{index}]"
    )
    selector = _selector(record.get("match"), f"candidates[{index}].match")
    rationale = _text(record.get("rationale"), f"candidates[{index}].rationale")
    family = (
        _family(record["family"], explicit_only=True) if "family" in record else None
    )
    package_id = (
        _text(record["packageId"], f"candidates[{index}].packageId")
        if "packageId" in record
        else None
    )
    return CandidateRule(selector, rationale, family, package_id)


def _parse_pin(value: object, index: int) -> Pin:
    record = _object(value, f"pins[{index}]")
    _fields(record, {"family", "variant", "match", "rationale"}, f"pins[{index}]")
    family = _family(record.get("family"), explicit_only=False)
    try:
        variant = Variant(record.get("variant"))
    except (TypeError, ValueError) as error:
        raise CompositionPolicyError(
            f"pins[{index}].variant has unknown target {record.get('variant')!r}"
        ) from error
    return Pin(
        family,
        variant,
        _selector(record.get("match"), f"pins[{index}].match"),
        _text(record.get("rationale"), f"pins[{index}].rationale"),
    )


def _selector(value: object, label: str) -> CandidateSelector:
    record = _object(value, label)
    _fields(record, {"source", "origin", "id", "url"}, label)
    source = _text(record.get("source"), f"{label}.source")
    origin = _text(record.get("origin"), f"{label}.origin")
    if source not in SOURCES:
        raise CompositionPolicyError(f"{label}.source has unknown source {source!r}")
    if origin not in ORIGINS or origin not in _SOURCE_ORIGINS[source]:
        raise CompositionPolicyError(
            f"{label}.origin {origin!r} is invalid for source {source!r}"
        )
    return CandidateSelector(
        source,
        origin,
        _text(record.get("id"), f"{label}.id"),
        _url(record.get("url"), f"{label}.url"),
    )


def _family(value: object, *, explicit_only: bool) -> str:
    family = _text(value, "family")
    prefixes = ("app:",) if explicit_only else ("app:", "package:")
    if (
        not family.startswith(prefixes)
        or re.fullmatch(r"(?:app|package):[A-Za-z0-9][A-Za-z0-9._-]*", family) is None
    ):
        expected = "app:" if explicit_only else "app: or package:"
        raise CompositionPolicyError(f"family must use a nonempty {expected} namespace")
    return family


def _url(value: object, label: str) -> str:
    url = _text(value, label)
    if any(character.isspace() for character in url):
        raise CompositionPolicyError(f"{label} is not a project URL: {url!r}")
    try:
        return normalize_project_url(url)
    except ValueError as error:
        raise CompositionPolicyError(
            f"{label} is not a project URL: {url!r}"
        ) from error


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompositionPolicyError(f"{label} must be a nonempty string")
    return value


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise CompositionPolicyError(f"{label} must be an object")
    return value


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise CompositionPolicyError(f"{label} must be an array")
    return value


def _fields(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise CompositionPolicyError(f"{label} has unknown field {min(unknown)!r}")


def _show(selector: CandidateSelector) -> str:
    return repr(selector.key)
