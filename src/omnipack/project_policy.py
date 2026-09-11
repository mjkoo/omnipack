"""Validation and normalization for reviewed codm project treatment."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from omnipack.urls import normalize_project_url


class PolicyError(ValueError):
    """A reviewed project policy is malformed or internally inconsistent."""


_SETTING_TYPES: dict[str, type] = {
    "includePrereleases": bool,
    "filterReleaseTitlesByRegEx": str,
    "apkFilterRegEx": str,
    "versionExtractionRegEx": str,
    "matchGroupToUse": str,
    "fallbackToOlderReleases": bool,
}
_REGEX_SETTINGS = {
    "filterReleaseTitlesByRegEx",
    "apkFilterRegEx",
    "versionExtractionRegEx",
}
_UNSUPPORTED_REGEX_TOKENS = ("(?<=", "(?<!", "(?P<", "(?(", "(?>")


@dataclass(frozen=True, slots=True)
class ProjectRule:
    kind: str
    name: str | None
    additional_settings: dict[str, Any]
    tracker_id: str | None = None
    rationale: str | None = None
    installation: str | None = None

    @property
    def fingerprint(self) -> str:
        value = self.canonical()
        value["additionalSettings"] = {
            "includePrereleases": False,
            "filterReleaseTitlesByRegEx": "",
            "apkFilterRegEx": "",
            "versionExtractionRegEx": "",
            "matchGroupToUse": "",
            "fallbackToOlderReleases": True,
            **self.additional_settings,
        }
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def canonical(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "kind": self.kind,
            "name": self.name,
            "additionalSettings": self.additional_settings,
        }
        if self.kind == "track-only":
            result.update(
                trackerId=self.tracker_id,
                rationale=self.rationale,
                installation=self.installation,
            )
        return result


@dataclass(frozen=True, slots=True)
class ProjectPolicy:
    projects: dict[str, ProjectRule]


def default_apk_rule() -> ProjectRule:
    return ProjectRule("apk", None, {})


def parse_project_policy(data: bytes | object) -> ProjectPolicy:
    try:
        document = json.loads(data) if isinstance(data, bytes) else data
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PolicyError(f"project policy is not valid JSON: {error}") from error
    if not isinstance(document, dict) or set(document) != {"schemaVersion", "projects"}:
        raise PolicyError("project policy must contain schemaVersion and projects")
    if document["schemaVersion"] != 1 or isinstance(document["schemaVersion"], bool):
        raise PolicyError("project policy schemaVersion must be 1")
    raw_projects = document["projects"]
    if not isinstance(raw_projects, dict):
        raise PolicyError("project policy projects must be an object")
    projects: dict[str, ProjectRule] = {}
    for raw_url, value in raw_projects.items():
        if not isinstance(raw_url, str) or not isinstance(value, dict):
            raise PolicyError("project policy entries must map URL strings to objects")
        try:
            url = normalize_project_url(raw_url)
        except ValueError as error:
            raise PolicyError(f"invalid project policy URL {raw_url!r}") from error
        if not url.startswith("github.com/") or len(url.split("/")) != 3:
            raise PolicyError(f"unsupported project policy URL {raw_url!r}")
        if url in projects:
            raise PolicyError(f"duplicate normalized project policy URL {url!r}")
        projects[url] = _parse_rule(url, value)
    return ProjectPolicy(projects)


def _parse_rule(url: str, value: dict[str, Any]) -> ProjectRule:
    kind = value.get("kind")
    if kind not in {"apk", "track-only"}:
        raise PolicyError(f"{url}: kind must be 'apk' or 'track-only'")
    allowed = {"kind", "name", "additionalSettings"}
    if kind == "track-only":
        allowed |= {"trackerId", "rationale", "installation"}
    unknown = set(value) - allowed
    if unknown:
        raise PolicyError(f"{url}: unsupported field {min(unknown)!r}")
    name = value.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise PolicyError(f"{url}: name must be a nonempty string")
    settings = value.get("additionalSettings", {})
    if not isinstance(settings, dict):
        raise PolicyError(f"{url}: additionalSettings must be an object")
    for key, setting in settings.items():
        expected = _SETTING_TYPES.get(key)
        if expected is None:
            raise PolicyError(f"{url}: unsupported setting {key!r}")
        if not isinstance(setting, expected):
            raise PolicyError(f"{url}: setting {key!r} has invalid type")
        if key in _REGEX_SETTINGS and setting:
            if any(token in setting for token in _UNSUPPORTED_REGEX_TOKENS):
                raise PolicyError(
                    f"{url}: regex for {key} uses syntax unsupported by Obtainium"
                )
            try:
                re.compile(setting)
            except re.error as error:
                raise PolicyError(f"{url}: invalid regex for {key}: {error}") from error
    if settings.get("matchGroupToUse") and not settings.get("versionExtractionRegEx"):
        raise PolicyError(f"{url}: matchGroupToUse requires versionExtractionRegEx")
    if kind == "apk":
        return ProjectRule(kind, name, dict(settings))
    tracker_id = value.get("trackerId")
    rationale = value.get("rationale")
    installation = value.get("installation")
    if not isinstance(tracker_id, str) or not tracker_id.isdecimal():
        raise PolicyError(f"{url}: trackerId must be a numeric string")
    if not isinstance(rationale, str) or not rationale.strip():
        raise PolicyError(f"{url}: rationale must be a nonempty string")
    if not isinstance(installation, str) or not installation.strip():
        raise PolicyError(f"{url}: installation must be a nonempty string")
    forbidden = set(settings) & {
        "apkFilterRegEx",
        "versionExtractionRegEx",
        "matchGroupToUse",
    }
    if forbidden:
        raise PolicyError(
            f"{url}: track-only rule has APK-only setting {min(forbidden)!r}"
        )
    return ProjectRule(kind, name, dict(settings), tracker_id, rationale, installation)
