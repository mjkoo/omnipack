"""Strict, pure interpretation of device-aware composition policy."""

from __future__ import annotations

import json
import re
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
    eligibility: frozenset[Variant] | None = None
    dual_preferred: bool | None = None


@dataclass(frozen=True, slots=True)
class Pin:
    family: str
    variant: Variant
    match: CandidateSelector
    rationale: str


@dataclass(frozen=True, slots=True)
class Projection:
    family: str
    eligibility: frozenset[Variant] | None


@dataclass(frozen=True, slots=True)
class CompositionPolicy:
    candidate_rules: tuple[CandidateRule, ...]
    pins: tuple[Pin, ...]
    history: dict[RenderedKey, str]
    projections: dict[RenderedKey, Projection]
    projected_pins: dict[PinKey, RenderedKey]

    def rendered_family(self, package_id: str, url: str) -> str:
        """Interpret a current rendered entry without build-report state."""
        key = rendered_key(package_id, url)
        projection = self.projections.get(key)
        return projection.family if projection else f"package:{package_id}"

    def historical_family(self, package_id: str, url: str) -> str | None:
        """Classify a previous output only from explicit retained history."""
        return self.history.get(rendered_key(package_id, url))


@dataclass(frozen=True, slots=True)
class AppliedPolicy:
    candidates: tuple[App, ...]
    projected_pins: dict[PinKey, RenderedKey]


def rendered_key(package_id: str, url: str) -> RenderedKey:
    return package_id, normalize_project_url(url)


def parse_composition_policy(document: object) -> CompositionPolicy:
    root = _object(document, "composition policy")
    _fields(root, {"schemaVersion", "candidates", "pins", "history"}, "policy")
    if type(root.get("schemaVersion")) is not int or root["schemaVersion"] != 1:
        raise CompositionPolicyError("schemaVersion must be integer 1")
    candidates_raw = _array(root.get("candidates"), "candidates")
    pins_raw = _array(root.get("pins"), "pins")
    history_raw = _array(root.get("history", []), "history")

    rules = tuple(
        _parse_rule(value, index) for index, value in enumerate(candidates_raw)
    )
    selectors: set[tuple[str, str, str, str]] = set()
    projections: dict[RenderedKey, Projection] = {}
    for rule in rules:
        if rule.match.key in selectors:
            raise CompositionPolicyError(
                f"duplicate candidate selector {_show(rule.match)}"
            )
        selectors.add(rule.match.key)
        effective_id = rule.package_id or rule.match.id
        family = rule.family or f"package:{effective_id}"
        key = rendered_key(effective_id, rule.match.url)
        projected = Projection(family, rule.eligibility)
        previous = projections.get(key)
        if previous is not None:
            if previous.family != projected.family or (
                previous.eligibility is not None
                and projected.eligibility is not None
                and previous.eligibility != projected.eligibility
            ):
                raise CompositionPolicyError(
                    f"rendered key {key!r} has conflicting projections"
                )
            projected = Projection(
                projected.family, previous.eligibility or projected.eligibility
            )
        projections[key] = projected

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
        projection = projections.get(rendered_key(effective_id, pin.match.url))
        effective_family = (
            projection.family if projection is not None else f"package:{effective_id}"
        )
        if pin.family != effective_family:
            raise CompositionPolicyError(
                f"pin family {pin.family!r} conflicts with projected family "
                f"{effective_family!r}"
            )
        projected_pins[key] = rendered_key(effective_id, pin.match.url)

    history: dict[RenderedKey, str] = {}
    for index, value in enumerate(history_raw):
        record = _object(value, f"history[{index}]")
        _fields(record, {"id", "url", "family", "rationale"}, f"history[{index}]")
        package_id = _text(record.get("id"), f"history[{index}].id")
        url = _url(record.get("url"), f"history[{index}].url")
        family = _family(record.get("family"), explicit_only=False)
        _text(record.get("rationale"), f"history[{index}].rationale")
        key = rendered_key(package_id, url)
        if key in history:
            raise CompositionPolicyError(f"duplicate history key {key!r}")
        projection = projections.get(key)
        if projection is not None and projection.family != family:
            raise CompositionPolicyError(
                f"history key {key!r} conflicts with active projection"
            )
        history[key] = family
    return CompositionPolicy(rules, pins, history, projections, projected_pins)


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
    policy: CompositionPolicy,
    candidates: list[App] | tuple[App, ...],
    *,
    require_all: bool = True,
    validate_pins: bool = True,
) -> AppliedPolicy:
    """Apply rules; composition defers pin validation until after exclusions.

    Deferring pins preserves candidate-rule presence and identity checks.
    Ingestion retains full pin validation, including required selectors.
    """
    collapsed = _collapse(candidates)
    by_selector = {_candidate_selector(app).key: app for app in collapsed}
    rules = {rule.match.key: rule for rule in policy.candidate_rules}
    pin_selectors = tuple(pin.match.key for pin in policy.pins) if validate_pins else ()
    for selector in (*rules, *pin_selectors):
        if require_all and selector not in by_selector:
            shown = CandidateSelector(*selector)
            raise CompositionPolicyError(
                f"selector {_show(shown)} matched no candidate"
            )

    result: list[App] = []
    applied_by_selector: dict[tuple[str, str, str, str], App] = {}
    for app in collapsed:
        selector = _candidate_selector(app)
        rule = rules.get(selector.key)
        if rule is None:
            updated = replace(app, family=f"package:{app.id}")
        else:
            effective_id = rule.package_id or app.id
            updated = replace(
                app,
                id=effective_id,
                family=rule.family or f"package:{effective_id}",
                eligibility=rule.eligibility or app.eligibility,
                dual_preferred=(
                    rule.dual_preferred
                    if rule.dual_preferred is not None
                    else app.dual_preferred
                ),
            )
            if updated.dual_preferred and Variant.DUAL not in updated.eligibility:
                raise CompositionPolicyError(
                    f"candidate {_show(selector)} is dualPreferred without dual eligibility"
                )
        projection = policy.projections.get(rendered_key(updated.id, updated.url))
        if projection is not None and (
            updated.family != projection.family
            or (
                projection.eligibility is not None
                and updated.eligibility != projection.eligibility
            )
        ):
            kind = "unruled candidate" if rule is None else "candidate"
            raise CompositionPolicyError(
                f"{kind} {_show(selector)} conflicts with rendered projection"
            )
        result.append(updated)
        applied_by_selector[selector.key] = updated

    if validate_pins:
        for pin in policy.pins:
            candidate = applied_by_selector.get(pin.match.key)
            if candidate is None:
                continue
            if (
                candidate.family != pin.family
                or pin.variant not in candidate.eligibility
            ):
                raise CompositionPolicyError(
                    f"pin for family {pin.family!r} target {pin.variant.value!r} "
                    "conflicts with candidate family or eligibility"
                )

    return AppliedPolicy(tuple(result), dict(policy.projected_pins))


def _collapse(candidates: list[App] | tuple[App, ...]) -> tuple[App, ...]:
    unique: dict[tuple[str, str, str, str], App] = {}
    for app in candidates:
        selector = _candidate_selector(app)
        previous = unique.get(selector.key)
        if previous is not None and previous != app:
            raise CompositionPolicyError(
                f"ambiguous original candidate identity {_show(selector)}"
            )
        unique[selector.key] = app
    return tuple(unique.values())


def _candidate_selector(app: App) -> CandidateSelector:
    return CandidateSelector(
        app.provenance.source,
        app.origin or app.provenance.source,
        app.original_id or app.id,
        normalize_project_url(app.url),
    )


def _parse_rule(value: object, index: int) -> CandidateRule:
    record = _object(value, f"candidates[{index}]")
    _fields(
        record,
        {"match", "family", "packageId", "eligible", "dualPreferred", "rationale"},
        f"candidates[{index}]",
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
    eligibility = (
        _eligibility(record["eligible"], f"candidates[{index}].eligible")
        if "eligible" in record
        else None
    )
    preferred = record.get("dualPreferred")
    if "dualPreferred" in record and type(preferred) is not bool:
        raise CompositionPolicyError(
            f"candidates[{index}].dualPreferred must be boolean"
        )
    if preferred is True and (
        eligibility is not None and Variant.DUAL not in eligibility
    ):
        raise CompositionPolicyError("dualPreferred requires dual eligibility")
    return CandidateRule(
        selector,
        rationale,
        family,
        package_id,
        eligibility,
        preferred if isinstance(preferred, bool) else None,
    )


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


def _eligibility(value: object, label: str) -> frozenset[Variant]:
    values = _array(value, label)
    if not values:
        raise CompositionPolicyError(f"{label} must not be empty")
    try:
        variants = frozenset(Variant(item) for item in values)
    except (TypeError, ValueError) as error:
        raise CompositionPolicyError(f"{label} contains an unknown target") from error
    if len(variants) != len(values):
        raise CompositionPolicyError(f"{label} contains duplicate targets")
    return variants


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
