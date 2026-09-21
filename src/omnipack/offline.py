"""Pure validation of serialized Obtainium pack and configuration snapshots."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from omnipack.report_model import FindingRecord
from omnipack.settings_defaults import SETTINGS_DEFAULTS


@dataclass(frozen=True, slots=True)
class OfflineInputs:
    """Exact bytes examined by offline verification."""

    single: bytes | None
    dual: bytes | None
    deny: bytes | None
    overlay: bytes | None
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

    def to_record(self) -> FindingRecord:
        """Serialize a finding, omitting absent location fields."""
        record: FindingRecord = {
            "stage": self.stage,
            "code": self.code,
            "message": self.message,
        }
        if self.variant is not None:
            record["variant"] = self.variant
        if self.entry_id is not None:
            record["entry_id"] = self.entry_id
        if self.index is not None:
            record["index"] = self.index
        if self.field is not None:
            record["field"] = self.field
        return record


_HTML_STEP_TYPES: dict[str, type] = {
    "customLinkFilterRegex": str,
    "filterByLinkText": bool,
    "reverseSort": bool,
    "skipSort": bool,
    "sortByLastLinkSegment": bool,
}
_INVALID = object()


def validate_offline(inputs: OfflineInputs) -> tuple[Finding, ...]:
    """Validate a pair and its composition configuration without I/O.

    Rendering fills every default setting key and derives the category
    colours from the entries it renders, and ingestion enforces GitLab project
    URLs, so none of those is checked again here. Setting values are checked:
    upstream records and overlay patches supply them, and rendering copies them
    without checking their types.
    """
    findings: list[Finding] = []
    documents = {
        variant: _decode_snapshot(getattr(inputs, variant), variant, findings)
        for variant in ("single", "dual")
    }
    deny = _decode_snapshot(inputs.deny, "deny", findings)
    overlay = _decode_snapshot(inputs.overlay, "overlay", findings)
    composition = _decode_snapshot(inputs.composition, "composition", findings)
    for variant, document in documents.items():
        _validate_document(variant, document, findings)
    _validate_composition(deny, overlay, composition, documents, findings)
    return tuple(findings)


def missing_input(name: str) -> Finding:
    """Return the finding reported for an input whose snapshot is absent."""
    return Finding("input", "input_missing", f"{name} input is missing")


def _decode_snapshot(value: bytes | None, name: str, findings: list[Finding]) -> object:
    if value is None:
        findings.append(missing_input(name))
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


def _validate_document(variant: str, document: object, findings: list[Finding]) -> None:
    if document is _INVALID:
        return
    if not isinstance(document, dict):
        findings.append(
            Finding(
                "document", "invalid_root", "document root must be an object", variant
            )
        )
        return
    apps = document.get("apps")
    if not isinstance(apps, list):
        findings.append(
            Finding("document", "invalid_apps", "apps must be a list", variant)
        )
        apps = []
    if not isinstance(document.get("settings"), dict):
        findings.append(
            Finding(
                "document",
                "invalid_document_settings",
                "settings must be an object",
                variant,
            )
        )

    seen: set[str] = set()
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
        _validate_entry(variant, index, raw, findings)


def _validate_entry(
    variant: str, index: int, raw: object, findings: list[Finding]
) -> None:
    if not isinstance(raw, dict):
        _add(
            findings,
            "entry",
            "invalid_entry",
            "app must be an object",
            variant,
            index=index,
        )
        return
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
    for key, default in SETTINGS_DEFAULTS[source].items():
        if key in settings and type(settings[key]) is not type(default):
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


def _validate_composition(
    deny: object,
    overlay: object,
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
        patches = parse_overlay(overlay, "overlay")
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
    for patch in patches:
        if patch.key not in all_keys:
            findings.append(
                Finding(
                    "composition",
                    "stale_overlay",
                    f"overlay has no target for {patch.key!r}",
                    entry_id=patch.package_id,
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
