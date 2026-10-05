"""Strict, pure interpretation of device-aware composition policy."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from omnipack.model import ASSIGNABLE_CATEGORIES, App, Category, Variant
from omnipack.overlay import OverlayPatch
from omnipack.strict_json import DuplicateKeyError, reject_duplicate_keys
from omnipack.urls import normalize_project_url, parse_project_url

RenderedKey = tuple[str, str]
PinKey = tuple[str, Variant]

SOURCES = frozenset({"rjny", "bboi", "extras", "codm2000", "quiver"})
ORIGINS = frozenset(
    {
        "rjny-catalog",
        "bboi-standard-asset",
        "bboi-dual-asset",
        "extras",
        "codm-generated",
        "quiver-generated",
    }
)
_SOURCE_ORIGINS = {
    "rjny": frozenset({"rjny-catalog"}),
    "bboi": frozenset({"bboi-standard-asset", "bboi-dual-asset"}),
    "extras": frozenset({"extras"}),
    "codm2000": frozenset({"codm-generated"}),
    "quiver": frozenset({"quiver-generated"}),
}


_EXPLICIT_FAMILY = re.compile(r"app:[A-Za-z0-9][A-Za-z0-9._-]*")


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
    # The family every candidate at a URL belongs to, where each family rule
    # at that URL names the same family.
    url_families: dict[str, str]
    # Where family rules at one URL name different families, the family each
    # rule projects onto its selector's package id there.
    split_families: dict[str, dict[str, str]]
    # Each pin's selected package id and normalized URL.
    projected_pins: dict[PinKey, RenderedKey]
    # The one category each named family carries unless its entry is track-only.
    categories: dict[str, Category]

    def explicit_family(self, package_id: str, url: str) -> str | None:
        """The explicit family the rules project onto `package_id` at `url`, if any."""
        normalized = normalize_project_url(url)
        whole = self.url_families.get(normalized)
        if whole is not None:
            return whole
        return self.split_families.get(normalized, {}).get(package_id)

    def family(self, package_id: str, url: str) -> str:
        """The family of an entry carrying `package_id` at project `url`.

        It is the explicit family the rules project there, otherwise the
        entry's default family, named by its normalized project URL.
        """
        explicit = self.explicit_family(package_id, url)
        return explicit if explicit is not None else normalize_project_url(url)

    def url_rule_families(self, url: str) -> tuple[str, ...]:
        """The distinct families the rules at `url` name, sorted."""
        normalized = normalize_project_url(url)
        if normalized in self.url_families:
            return (self.url_families[normalized],)
        return tuple(sorted(set(self.split_families.get(normalized, {}).values())))


def rendered_key(package_id: str, url: str) -> RenderedKey:
    return package_id, normalize_project_url(url)


def assigned_family(app: App) -> str:
    """The family `apply_composition_policy` assigned to a candidate."""
    if app.family is None:
        raise CompositionPolicyError(
            f"candidate {_show(candidate_selector(app))} has no family assignment"
        )
    return app.family


@dataclass(frozen=True, slots=True)
class Pairing:
    """A single-screen and a dual-screen entry carrying one family label, or one
    entry no entry of the other variant shares a label with.
    """

    label: str
    single: RenderedKey | None
    dual: RenderedKey | None


def repeated_labels(
    policy: CompositionPolicy, keys: Sequence[RenderedKey]
) -> dict[str, tuple[RenderedKey, ...]]:
    """The family labels more than one entry of one variant carries, sorted."""
    by_label: dict[str, list[RenderedKey]] = {}
    for key in keys:
        by_label.setdefault(policy.family(*key), []).append(key)
    return {
        label: tuple(sorted(members))
        for label, members in sorted(by_label.items())
        if len(members) > 1
    }


def repeated_ids(keys: Sequence[RenderedKey]) -> dict[str, tuple[RenderedKey, ...]]:
    """The package ids more than one entry of one variant carries, sorted."""
    by_id: dict[str, list[RenderedKey]] = {}
    for key in keys:
        by_id.setdefault(key[0], []).append(key)
    return {
        package_id: tuple(sorted(members))
        for package_id, members in sorted(by_id.items())
        if len(members) > 1
    }


def pair_entries(
    policy: CompositionPolicy,
    single: Sequence[RenderedKey],
    dual: Sequence[RenderedKey],
) -> tuple[Pairing, ...]:
    """Pair rendered entries carrying one family label, sorted by label.

    Every entry carrying a label repeated within either variant is left out,
    so no pairing depends on entry order.
    """
    repeated = {*repeated_labels(policy, single), *repeated_labels(policy, dual)}
    singles = {policy.family(*key): key for key in single}
    duals = {policy.family(*key): key for key in dual}
    return tuple(
        Pairing(label, singles.get(label), duals.get(label))
        for label in sorted((singles.keys() | duals.keys()) - repeated)
    )


def build_policy(
    rules: Sequence[CandidateRule],
    pins: Sequence[Pin] = (),
    categories: dict[str, Category] | None = None,
) -> CompositionPolicy:
    """Check rules and pins against each other and derive their projections."""
    selectors: set[tuple[str, str, str, str]] = set()
    by_url: dict[str, list[tuple[CandidateRule, str]]] = {}
    for rule in rules:
        if rule.match.key in selectors:
            raise CompositionPolicyError(
                f"duplicate candidate selector {_show(rule.match)}"
            )
        selectors.add(rule.match.key)
        if rule.family is not None:
            by_url.setdefault(rule.match.url, []).append((rule, rule.family))

    url_families: dict[str, str] = {}
    split_families: dict[str, dict[str, str]] = {}
    for url, members in by_url.items():
        if len({family for _, family in members}) == 1:
            url_families[url] = members[0][1]
            continue
        by_id: dict[str, tuple[CandidateRule, str]] = {}
        for rule, family in members:
            first, first_family = by_id.setdefault(rule.match.id, (rule, family))
            if first_family != family:
                raise CompositionPolicyError(
                    f"rules {_show(first.match)} and {_show(rule.match)} project "
                    f"conflicting families {first_family!r} and {family!r} "
                    f"onto {rendered_key(rule.match.id, url)!r}"
                )
        split_families[url] = {
            package_id: family for package_id, (_, family) in by_id.items()
        }

    policy = CompositionPolicy(
        tuple(rules), tuple(pins), url_families, split_families, {}, categories or {}
    )
    projected_pins: dict[PinKey, RenderedKey] = {}
    for pin in pins:
        key = (pin.family, pin.variant)
        if key in projected_pins:
            raise CompositionPolicyError(
                f"multiple pins for family {pin.family!r} target {pin.variant.value!r}"
            )
        pinned = rendered_key(pin.match.id, pin.match.url)
        # Only an explicit projection is known here. Any other pin names the
        # family its candidate forms, which composition checks once it forms.
        projected = policy.explicit_family(*pinned)
        if projected is not None and pin.family != projected:
            raise CompositionPolicyError(
                f"pin family {pin.family!r} target {pin.variant.value!r} conflicts "
                f"with projected family {projected!r}"
            )
        projected_pins[key] = pinned
    return replace(policy, projected_pins=projected_pins)


def check_overlay_id_patches(
    policy: CompositionPolicy, patches: Sequence[OverlayPatch]
) -> None:
    """Refuse an `id` patch at a URL whose family rules name different families.

    Such a patch would give every family there one id, so the rendered entries
    could no longer be told apart by family. `patches` keep the overlay's
    record order, so each error names its record by index.
    """
    for index, patch in enumerate(patches):
        families = policy.url_rule_families(patch.url)
        if "id" in patch.patch and len(families) > 1:
            raise CompositionPolicyError(
                f"overlay[{index}] for {patch.url!r} patches id at a URL whose "
                f"rules name families {', '.join(map(repr, families))}"
            )


def parse_composition_policy(document: object) -> CompositionPolicy:
    root = _object(document, "composition policy")
    _fields(root, {"schemaVersion", "candidates", "pins", "categories"}, "policy")
    if type(root.get("schemaVersion")) is not int or root["schemaVersion"] != 1:
        raise CompositionPolicyError("schemaVersion must be integer 1")
    candidates_raw = _array(root.get("candidates"), "candidates")
    pins_raw = _array(root.get("pins"), "pins")
    rules = [_parse_rule(value, index) for index, value in enumerate(candidates_raw)]
    pins = [_parse_pin(value, index) for index, value in enumerate(pins_raw)]
    categories = _parse_categories(root.get("categories", {}))
    return build_policy(rules, pins, categories)


def load_composition_policy(data: str | bytes | bytearray) -> CompositionPolicy:
    """Decode policy JSON and apply the same strict shared interpretation.

    This is the one decoder of the policy file, so every command that loads it
    rejects a repeated object key rather than letting one occurrence win.
    """
    try:
        document = json.loads(data, object_pairs_hook=reject_duplicate_keys)
    except DuplicateKeyError as error:
        raise CompositionPolicyError(str(error)) from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise CompositionPolicyError(f"invalid JSON: {error}") from error
    return parse_composition_policy(document)


def apply_composition_policy(
    policy: CompositionPolicy, candidates: list[App] | tuple[App, ...]
) -> tuple[App, ...]:
    """Collapse identical candidates and give each its family, requiring every
    rule selector to match.

    A candidate's family depends only on its package id, its URL and the
    rules, so it is the same whether or not the candidate a rule matches
    survives exclusions. Pins are left to composition, which validates them
    after processing exclusions so that a failed pin still leaves the
    exclusion diagnostics.
    """
    collapsed = _collapse(candidates)
    by_selector = {candidate_selector(app).key for app in collapsed}
    for rule in policy.candidate_rules:
        if rule.match.key not in by_selector:
            raise CompositionPolicyError(
                f"selector {_show(rule.match)} matched no candidate"
            )
    return tuple(
        replace(app, family=policy.family(app.id, app.url)) for app in collapsed
    )


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
        app.id,
        normalize_project_url(app.url),
    )


def _parse_rule(value: object, index: int) -> CandidateRule:
    label = f"candidates[{index}]"
    record = _object(value, label)
    _fields(record, {"match", "family", "rationale"}, label)
    selector = _selector(record.get("match"), f"{label}.match")
    rationale = _text(record.get("rationale"), f"{label}.rationale")
    family = (
        _explicit_family(record["family"], f"{label}.family")
        if "family" in record
        else None
    )
    return CandidateRule(selector, rationale, family)


def _parse_categories(value: object) -> dict[str, Category]:
    record = _object(value, "categories")
    result: dict[str, Category] = {}
    for key, category in record.items():
        _family_name(key, f"categories key {key!r}")
        if category not in ASSIGNABLE_CATEGORIES:
            raise CompositionPolicyError(
                f"categories[{key!r}] must be one of "
                f"{[str(item) for item in ASSIGNABLE_CATEGORIES]}, not {category!r}"
            )
        result[key] = Category(category)
    return result


def _parse_pin(value: object, index: int) -> Pin:
    record = _object(value, f"pins[{index}]")
    _fields(record, {"family", "variant", "match", "rationale"}, f"pins[{index}]")
    family = _family_name(record.get("family"), f"pins[{index}].family")
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


def _explicit_family(value: object, label: str) -> str:
    family = _text(value, label)
    if _EXPLICIT_FAMILY.fullmatch(family) is None:
        raise CompositionPolicyError(
            f"{label} must use a nonempty app: namespace, not {family!r}"
        )
    return family


def _family_name(value: object, label: str) -> str:
    """An `app:` family, or a default family's normalized project URL.

    A URL must already be in normalized form and carry a host and a path, so a
    full `https://` URL or an `app:` name typed without its prefix fails
    instead of naming nothing.
    """
    family = _text(value, label)
    if family.startswith("app:"):
        return _explicit_family(family, label)
    try:
        normalized = normalize_project_url(family)
    except ValueError:
        normalized = None
    if normalized != family or "/" not in family.strip("/"):
        raise CompositionPolicyError(
            f"{label} must be an app: family or a normalized project URL "
            f"with a host and a path, not {family!r}"
        )
    return family


def _url(value: object, label: str) -> str:
    url = _text(value, label)
    try:
        return parse_project_url(url)
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
