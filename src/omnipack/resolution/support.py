"""Classify Obtainium settings against the live verification boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SupportClass(str, Enum):
    """How live verification treats a configured setting."""

    IMPLEMENTED = "implemented"
    DEVICE_OR_HARMLESS = "device-specific or harmless"
    INACTIVE_UNSUPPORTED = "inactive unsupported"
    LIVE_ERROR = "live error"


@dataclass(frozen=True, slots=True)
class SettingSupport:
    """Classification and human-readable reason for one setting."""

    classification: SupportClass
    reason: str


_COMMON_IMPLEMENTED = {
    "trackOnly",
    "versionExtractionRegEx",
    "matchGroupToUse",
    "versionDetection",
    "releaseDateAsVersion",
    "apkFilterRegEx",
    "invertAPKFilter",
}
_COMMON_DEVICE_OR_HARMLESS = {
    "useVersionCodeAsOSVersion",
    "autoApkFilterByArch",
    "appName",
    "appAuthor",
    "shizukuPretendToBeGooglePlay",
    "exemptFromBackgroundUpdates",
    "skipUpdateNotifications",
    "about",
    "refreshBeforeDownload",
    "preferredApkIndex",
}
_COMMON_UNSUPPORTED = {
    "allowInsecure": False,
    "includeZips": False,
    "zippedApkFilterRegEx": "",
}
_SOURCE_IMPLEMENTED = {
    "GitHub": {
        "includeZips",
        "verifyLatestTag",
        "includePrereleases",
        "fallbackToOlderReleases",
        "filterReleaseTitlesByRegEx",
        "filterReleaseNotesByRegEx",
        "sortMethodChoice",
        "useLatestAssetDateAsReleaseDate",
        "releaseTitleAsVersion",
    },
    "HTML": {
        "intermediateLink",
        "customLinkFilterRegex",
        "filterByLinkText",
        "matchLinksOutsideATags",
        "skipSort",
        "reverseSort",
        "sortByLastLinkSegment",
        "versionExtractWholePage",
        "requestHeader",
    },
    "GitLab": {"fallbackToOlderReleases"},
}
_SOURCE_UNSUPPORTED = {
    "GitHub": {"github-creds": "", "GHReqPrefix": ""},
    "HTML": {},
    "GitLab": {},
}


def _unsupported(value: Any, inactive_value: Any, reason: str) -> SettingSupport:
    classification = (
        SupportClass.INACTIVE_UNSUPPORTED
        if value == inactive_value
        else SupportClass.LIVE_ERROR
    )
    return SettingSupport(classification, reason)


def classify_settings(
    source: str, settings: dict[str, Any]
) -> dict[str, SettingSupport]:
    """Classify all settings without treating unknown false values as safe."""
    implemented = _SOURCE_IMPLEMENTED.get(source)
    unsupported = _SOURCE_UNSUPPORTED.get(source)
    if implemented is None or unsupported is None:
        return {
            key: SettingSupport(SupportClass.LIVE_ERROR, f"unknown source {source!r}")
            for key in settings
        }

    result: dict[str, SettingSupport] = {}
    for key, value in settings.items():
        if source == "GitLab" and key in {
            "trackOnly",
            "versionDetection",
            "releaseDateAsVersion",
            "invertAPKFilter",
        }:
            inactive = {
                "trackOnly": False,
                "versionDetection": True,
                "releaseDateAsVersion": False,
                "invertAPKFilter": False,
            }[key]
            result[key] = _unsupported(
                value, inactive, "outside the supported GitLab release-tag boundary"
            )
        elif (
            key == "sortMethodChoice"
            and source == "GitHub"
            and value
            not in {
                "date",
                "none",
            }
        ):
            result[key] = SettingSupport(
                SupportClass.LIVE_ERROR, "only date and none sorting are supported"
            )
        elif (
            key == "requestHeader"
            and source == "HTML"
            and isinstance(value, list)
            and any(
                isinstance(item, dict)
                and str(item.get("requestHeader", "")).partition(":")[0].strip().lower()
                in {"authorization", "cookie"}
                for item in value
            )
        ):
            result[key] = SettingSupport(
                SupportClass.LIVE_ERROR,
                "pack-provided authorization and cookie headers are unsupported",
            )
        elif (
            key == "intermediateLink"
            and source == "HTML"
            and isinstance(value, list)
            and any(
                isinstance(item, dict)
                and bool(item.get("customLinkFilterRegex"))
                and item.get("autoLinkFilterByArch") is True
                for item in value
            )
        ):
            result[key] = SettingSupport(
                SupportClass.LIVE_ERROR,
                "device-dependent intermediate filtering is unsupported",
            )
        elif key == "releaseDateAsVersion" and source == "HTML":
            result[key] = _unsupported(
                value, False, "HTML source provides no usable release date"
            )
        elif source == "GitHub" and key == "zippedApkFilterRegEx":
            result[key] = SettingSupport(
                SupportClass.DEVICE_OR_HARMLESS,
                "ZIP member filtering and extraction occur on device; members are not inspected",
            )
        elif key in _COMMON_IMPLEMENTED or key in implemented:
            result[key] = SettingSupport(
                SupportClass.IMPLEMENTED, "interpreted by live verification"
            )
        elif key in _COMMON_DEVICE_OR_HARMLESS:
            result[key] = SettingSupport(
                SupportClass.DEVICE_OR_HARMLESS,
                "does not change device-independent source resolution",
            )
        elif key in _COMMON_UNSUPPORTED:
            result[key] = _unsupported(
                value, _COMMON_UNSUPPORTED[key], "unsupported when active"
            )
        elif key in unsupported:
            result[key] = _unsupported(
                value, unsupported[key], "unsupported when active"
            )
        elif key == "defaultPseudoVersioningMethod" and source == "HTML":
            result[key] = _unsupported(
                value if not settings.get("versionExtractionRegEx") else "",
                "",
                "unsupported when explicit version extraction is absent",
            )
        else:
            result[key] = SettingSupport(
                SupportClass.LIVE_ERROR, "unknown setting is not classified as harmless"
            )
    return result
