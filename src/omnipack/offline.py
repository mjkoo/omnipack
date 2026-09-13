"""Pure validation of serialized Obtainium pack and configuration snapshots."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from omnipack.settings_defaults import SETTINGS_DEFAULTS
from omnipack.urls import gitlab_project_path


@dataclass(frozen=True, slots=True)
class OfflineInputs:
    """Exact bytes examined by offline verification."""

    single: bytes | None
    dual: bytes | None
    deny: bytes | None
    common_overlay: bytes | None
    dual_overlay: bytes | None
    settings: bytes | None
    composition: bytes | None


@dataclass(frozen=True, slots=True)
class Finding:
    """One validation problem at a stable location."""

    stage: str
    code: str
    message: str
    variant: str | None = None
    entry_id: str | None = None
    index: int | None = None
    field: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatedEntry:
    """An unchanged serialized entry with its checked settings decoded."""

    variant: str
    index: int
    entry_id: str
    source: str
    raw: dict[str, Any]
    settings: dict[str, Any]


@dataclass(frozen=True, slots=True)
class OfflineResult:
    """Collected findings and entries usable by later verification stages."""

    inputs: OfflineInputs
    findings: tuple[Finding, ...]
    entries: dict[str, tuple[ValidatedEntry, ...]]

    @property
    def ok(self) -> bool:
        return not self.findings


_HTML_STEP_TYPES: dict[str, type] = {
    "customLinkFilterRegex": str,
    "filterByLinkText": bool,
    "reverseSort": bool,
    "skipSort": bool,
    "sortByLastLinkSegment": bool,
}
_INVALID = object()


def validate_offline(inputs: OfflineInputs) -> OfflineResult:
    """Validate a pair and its composition configuration without I/O."""
    findings: list[Finding] = []
    documents = {
        variant: _decode_snapshot(getattr(inputs, variant), variant, findings)
        for variant in ("single", "dual")
    }
    deny = _decode_snapshot(inputs.deny, "deny", findings)
    common = _decode_snapshot(inputs.common_overlay, "common_overlay", findings)
    dual_overlay = _decode_snapshot(inputs.dual_overlay, "dual_overlay", findings)
    configured = _decode_snapshot(inputs.settings, "settings", findings)
    composition = _decode_snapshot(inputs.composition, "composition", findings)

    entries: dict[str, tuple[ValidatedEntry, ...]] = {}
    id_sets: dict[str, set[str]] = {}
    for variant, document in documents.items():
        validated, ids = _validate_document(variant, document, configured, findings)
        entries[variant] = tuple(validated)
        id_sets[variant] = ids

    _validate_composition(deny, common, dual_overlay, composition, documents, findings)
    return OfflineResult(inputs, tuple(findings), entries)


def _decode_snapshot(value: bytes | None, name: str, findings: list[Finding]) -> object:
    if value is None:
        findings.append(Finding("input", "input_missing", f"{name} input is missing"))
        return _INVALID
    if not isinstance(value, bytes):
        findings.append(
            Finding("input", "input_unreadable", f"{name} input is not bytes")
        )
        return _INVALID
    try:
        decoded = json.loads(
            value,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite number {token}")
            ),
        )
        if not _all_finite(decoded):
            findings.append(
                Finding("decode", "non_finite_number", f"{name}: non-finite number")
            )
            return _INVALID
        return decoded
    except UnicodeDecodeError as error:
        findings.append(Finding("decode", "input_unreadable", f"{name}: {error}"))
    except ValueError as error:
        code = "non_finite_number" if "non-finite" in str(error) else "invalid_json"
        findings.append(Finding("decode", code, f"{name}: {error}"))
    return _INVALID


def _all_finite(value: object) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_all_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(_all_finite(item) for item in value)
    return True


def _validate_document(
    variant: str,
    document: object,
    configured: object,
    findings: list[Finding],
) -> tuple[list[ValidatedEntry], set[str]]:
    if document is _INVALID:
        return [], set()
    if not isinstance(document, dict):
        findings.append(
            Finding(
                "document", "invalid_root", "document root must be an object", variant
            )
        )
        return [], set()
    apps = document.get("apps")
    rendered_settings = document.get("settings")
    if not isinstance(apps, list):
        findings.append(
            Finding("document", "invalid_apps", "apps must be a list", variant)
        )
        apps = []
    if not isinstance(rendered_settings, dict):
        findings.append(
            Finding(
                "document",
                "invalid_document_settings",
                "settings must be an object",
                variant,
            )
        )
        rendered_settings = None

    result: list[ValidatedEntry] = []
    seen: set[str] = set()
    categories: set[str] = set()
    for index, raw in enumerate(apps):
        if isinstance(raw, dict):
            entry_id = raw.get("id")
            if isinstance(entry_id, str) and entry_id:
                if entry_id in seen:
                    _add(
                        findings,
                        "entry",
                        "duplicate_id",
                        "duplicate id",
                        variant,
                        entry_id,
                        index,
                        "id",
                    )
                seen.add(entry_id)
            raw_categories = raw.get("categories")
            if isinstance(raw_categories, list):
                categories.update(
                    item for item in raw_categories if isinstance(item, str)
                )
        entry = _validate_entry(variant, index, raw, findings)
        if entry is not None:
            result.append(entry)
    if rendered_settings is not None:
        _validate_pack_settings(
            variant, rendered_settings, configured, categories, findings
        )
    return result, seen


def _validate_entry(
    variant: str, index: int, raw: object, findings: list[Finding]
) -> ValidatedEntry | None:
    if not isinstance(raw, dict):
        _add(
            findings,
            "entry",
            "invalid_entry",
            "app must be an object",
            variant,
            index=index,
        )
        return None
    entry_id = raw.get("id") if isinstance(raw.get("id"), str) else None
    for field in ("id", "name", "url", "author"):
        if field not in raw:
            _add(
                findings,
                "entry",
                "missing_field",
                f"missing {field}",
                variant,
                entry_id,
                index,
                field,
            )
        elif not isinstance(raw[field], str) or (
            field in {"id", "name", "url"} and not raw[field]
        ):
            _add(
                findings,
                "entry",
                "invalid_field",
                f"{field} must be a valid string",
                variant,
                entry_id,
                index,
                field,
            )
    url = raw.get("url")
    if isinstance(url, str):
        try:
            parsed = urlsplit(url)
            valid_url = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
        except ValueError:
            valid_url = False
        if not valid_url:
            _add(
                findings,
                "entry",
                "invalid_url",
                "url must be absolute HTTP(S)",
                variant,
                entry_id,
                index,
                "url",
            )
    categories = raw.get("categories")
    if not isinstance(categories, list) or not all(
        isinstance(value, str) for value in categories
    ):
        _add(
            findings,
            "entry",
            "invalid_categories",
            "categories must be a string list",
            variant,
            entry_id,
            index,
            "categories",
        )
    source = raw.get("overrideSource")
    if not isinstance(source, str) or source not in SETTINGS_DEFAULTS:
        _add(
            findings,
            "entry",
            "unsupported_source",
            f"unsupported source {source!r}",
            variant,
            entry_id,
            index,
            "overrideSource",
        )
        source = None
    if source == "GitLab" and isinstance(url, str) and not _valid_gitlab_url(url):
        _add(
            findings,
            "entry",
            "invalid_gitlab_url",
            "GitLab URL must identify a public HTTPS gitlab.com project",
            variant,
            entry_id,
            index,
            "url",
        )
    preferred = raw.get("preferredApkIndex")
    if "preferredApkIndex" in raw and (
        not isinstance(preferred, int) or isinstance(preferred, bool)
    ):
        _add(
            findings,
            "entry",
            "invalid_preferred_apk_index",
            "preferredApkIndex must be an integer",
            variant,
            entry_id,
            index,
            "preferredApkIndex",
        )
    settings = _decode_additional(
        raw.get("additionalSettings"), variant, entry_id, index, findings
    )
    if settings is not None and source is not None:
        _validate_additional(source, settings, variant, entry_id, index, findings)
    if entry_id is None or source is None or settings is None:
        return None
    return ValidatedEntry(variant, index, entry_id, source, raw, settings)


def _valid_gitlab_url(url: str) -> bool:
    try:
        gitlab_project_path(url)
    except ValueError:
        return False
    return True


def _decode_additional(
    value: object,
    variant: str,
    entry_id: str | None,
    index: int,
    findings: list[Finding],
) -> dict[str, Any] | None:
    if not isinstance(value, str):
        _add(
            findings,
            "entry",
            "invalid_additional_settings",
            "additionalSettings must be an encoded object",
            variant,
            entry_id,
            index,
            "additionalSettings",
        )
        return None
    try:
        decoded = json.loads(
            value, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token))
        )
    except ValueError as error:
        _add(
            findings,
            "entry",
            "invalid_additional_settings",
            f"additionalSettings is invalid JSON: {error}",
            variant,
            entry_id,
            index,
            "additionalSettings",
        )
        return None
    if not isinstance(decoded, dict):
        _add(
            findings,
            "entry",
            "invalid_additional_settings",
            "additionalSettings must decode to an object",
            variant,
            entry_id,
            index,
            "additionalSettings",
        )
        return None
    if not _all_finite(decoded):
        _add(
            findings,
            "entry",
            "non_finite_number",
            "additionalSettings contains a non-finite number",
            variant,
            entry_id,
            index,
            "additionalSettings",
        )
        return None
    return decoded


def _validate_additional(
    source: str,
    settings: dict[str, Any],
    variant: str,
    entry_id: str | None,
    index: int,
    findings: list[Finding],
) -> None:
    defaults = SETTINGS_DEFAULTS[source]
    for key, default in defaults.items():
        if key not in settings:
            _add(
                findings,
                "settings",
                "missing_setting_default",
                f"missing setting {key}",
                variant,
                entry_id,
                index,
                key,
            )
        elif type(settings[key]) is not type(default):
            _add(
                findings,
                "settings",
                "wrong_setting_type",
                f"setting {key} has wrong type",
                variant,
                entry_id,
                index,
                key,
            )
    if source != "HTML":
        return
    steps = settings.get("intermediateLink")
    if isinstance(steps, list):
        for step_index, step in enumerate(steps):
            if not isinstance(step, dict):
                _add(
                    findings,
                    "settings",
                    "invalid_html_step",
                    f"HTML step {step_index} must be an object",
                    variant,
                    entry_id,
                    index,
                    "intermediateLink",
                )
                continue
            for key, expected in _HTML_STEP_TYPES.items():
                if key not in step or type(step[key]) is not expected:
                    _add(
                        findings,
                        "settings",
                        "invalid_html_step",
                        f"HTML step {step_index} has invalid {key}",
                        variant,
                        entry_id,
                        index,
                        "intermediateLink",
                    )
    headers = settings.get("requestHeader")
    if isinstance(headers, list):
        for header_index, header in enumerate(headers):
            if not isinstance(header, dict) or not isinstance(
                header.get("requestHeader"), str
            ):
                _add(
                    findings,
                    "settings",
                    "invalid_request_header",
                    f"request header {header_index} is invalid",
                    variant,
                    entry_id,
                    index,
                    "requestHeader",
                )


def _validate_pack_settings(
    variant: str,
    rendered: dict[str, Any],
    configured: object,
    observed: set[str],
    findings: list[Finding],
) -> None:
    if not isinstance(configured, dict):
        if configured is not _INVALID:
            findings.append(
                Finding(
                    "config",
                    "invalid_settings_config",
                    "settings config must be an object",
                )
            )
        return
    raw_categories = rendered.get("categories")
    if not isinstance(raw_categories, str):
        findings.append(
            Finding(
                "document",
                "invalid_category_mapping",
                "settings.categories must be an encoded object",
                variant,
            )
        )
        actual: object = None
    else:
        try:
            actual = json.loads(
                raw_categories,
                parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
            )
        except ValueError:
            actual = None
    if not isinstance(actual, dict):
        findings.append(
            Finding(
                "document",
                "invalid_category_mapping",
                "settings.categories must decode to an object",
                variant,
            )
        )
    else:
        if set(actual) != observed:
            findings.append(
                Finding(
                    "document",
                    "category_mapping_mismatch",
                    "category mapping must exactly match observed categories",
                    variant,
                )
            )
        for name, color in actual.items():
            if (
                not isinstance(name, str)
                or not isinstance(color, int)
                or isinstance(color, bool)
                or not 0 <= color <= 0xFFFFFFFF
            ):
                findings.append(
                    Finding(
                        "document",
                        "invalid_category_color",
                        f"category {name!r} has invalid ARGB color",
                        variant,
                        field="settings.categories",
                    )
                )
        configured_categories = configured.get("categories", {})
        if isinstance(configured_categories, str):
            try:
                configured_categories = json.loads(configured_categories)
            except ValueError:
                configured_categories = None
        if not isinstance(configured_categories, dict):
            findings.append(
                Finding(
                    "config",
                    "invalid_settings_config",
                    "configured categories must be an object",
                )
            )
        else:
            for name, color in configured_categories.items():
                if (
                    not isinstance(name, str)
                    or not isinstance(color, int)
                    or isinstance(color, bool)
                    or not 0 <= color <= 0xFFFFFFFF
                ):
                    findings.append(
                        Finding(
                            "config",
                            "invalid_category_color",
                            f"configured category {name!r} has invalid ARGB color",
                            field="categories",
                        )
                    )
            for name in observed:
                expected = configured_categories.get(name)
                if expected is None:
                    expected = int.from_bytes(
                        b"\xff" + hashlib.sha256(name.encode()).digest()[:3]
                    )
                if actual.get(name) != expected:
                    findings.append(
                        Finding(
                            "document",
                            "configured_category_mismatch",
                            f"category {name!r} color disagrees with configuration",
                            variant,
                        )
                    )
    for key in sorted((configured.keys() | rendered.keys()) - {"categories"}):
        if (
            key not in configured
            or key not in rendered
            or rendered[key] != configured[key]
        ):
            findings.append(
                Finding(
                    "document",
                    "configured_setting_mismatch",
                    f"setting {key!r} disagrees with configuration",
                    variant,
                    field=key,
                )
            )


def _validate_composition(
    deny: object,
    common: object,
    dual_overlay: object,
    composition: object,
    documents: dict[str, object],
    findings: list[Finding],
) -> None:
    if composition is _INVALID:
        return
    from omnipack.composition_policy import (
        CompositionPolicyError,
        parse_composition_policy,
    )
    from omnipack.merge import CompositionError, parse_exclusions
    from omnipack.model import Variant
    from omnipack.overlay import OverlayError, parse_overlay
    from omnipack.urls import normalize_project_url

    try:
        policy = parse_composition_policy(composition)
        if not isinstance(deny, list):
            raise CompositionError("denylist must be a list")
        exclusions = parse_exclusions(deny)
        common_patches = parse_overlay(common, "common overlay")
        dual_patches = parse_overlay(dual_overlay, "dual-screen overlay")
    except (CompositionPolicyError, CompositionError, OverlayError, TypeError) as error:
        findings.append(Finding("config", "invalid_composition_config", str(error)))
        return

    families: dict[str, set[str]] = {"single": set(), "dual": set()}
    keys: dict[str, set[tuple[str, str]]] = {"single": set(), "dual": set()}
    family_ids: dict[str, dict[str, str]] = {"single": {}, "dual": {}}
    for variant, document in documents.items():
        raw_apps = document.get("apps", []) if isinstance(document, dict) else []
        for raw in raw_apps if isinstance(raw_apps, list) else []:
            if not isinstance(raw, dict):
                continue
            package_id, url = raw.get("id"), raw.get("url")
            if (
                not isinstance(package_id, str)
                or not package_id
                or not isinstance(url, str)
            ):
                continue
            try:
                key = (package_id, normalize_project_url(url))
            except ValueError:
                continue
            family = policy.rendered_family(*key)
            if family in families[variant]:
                findings.append(
                    Finding(
                        "composition",
                        "duplicate_family",
                        f"family {family!r} is selected more than once",
                        variant,
                        package_id,
                    )
                )
            families[variant].add(family)
            keys[variant].add(key)
            family_ids[variant][family] = package_id
    for (family, target), pinned in policy.projected_pins.items():
        if pinned not in keys[target.value]:
            findings.append(
                Finding(
                    "composition",
                    "pin_mismatch",
                    f"family {family!r} requires pinned output {pinned!r} in {target.value}",
                    target.value,
                    pinned[0],
                )
            )

    for exclusion in exclusions:
        for target in Variant:
            for family, package_id in family_ids[target.value].items():
                if package_id == exclusion.package_id:
                    findings.append(
                        Finding(
                            "composition",
                            "denied_output_present",
                            f"denied selection {package_id!r} in family {family!r} remains present",
                            target.value,
                            package_id,
                        )
                    )

    all_keys = keys["single"] | keys["dual"]
    for patch in common_patches:
        if patch.key not in all_keys:
            findings.append(
                Finding(
                    "composition",
                    "stale_common_overlay",
                    f"common overlay has no target for {patch.key!r}",
                    entry_id=patch.package_id,
                )
            )
    for patch in dual_patches:
        if patch.key not in keys["dual"]:
            findings.append(
                Finding(
                    "composition",
                    "stale_dual_overlay",
                    f"dual overlay has no target for {patch.key!r}",
                    "dual",
                    patch.package_id,
                )
            )

    for family in families["single"] - families["dual"]:
        findings.append(
            Finding(
                "composition",
                "dual_coverage_gap",
                f"dual variant is missing family {family!r}",
                "dual",
                family_ids["single"][family],
            )
        )


def _add(
    findings: list[Finding],
    stage: str,
    code: str,
    message: str,
    variant: str | None = None,
    entry_id: str | None = None,
    index: int | None = None,
    field: str | None = None,
) -> None:
    findings.append(Finding(stage, code, message, variant, entry_id, index, field))
